#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "dio_system_sources.json"
TEXT_SUFFIXES = {".py", ".md", ".json", ".yaml", ".yml", ".txt", ".toml", ".ini"}
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "dist", "build"}


def timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(str(part or "") for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16].upper()}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except (OSError, PermissionError):
        return None


def run_git(repo: Path, *args: str, check: bool = True, strip: bool = True) -> str:
    process = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
        check=False,
    )
    if check and process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or f"git {' '.join(args)} failed")
    return process.stdout.strip() if strip else process.stdout


def git_root_or_none(repo: Path) -> tuple[Path | None, str | None]:
    """Resolve a valid Git root without treating absent/broken metadata as a capture failure."""
    try:
        process = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if process.returncode != 0 or not process.stdout.strip():
        return None, process.stderr.strip() or "Git metadata unavailable."
    try:
        return Path(process.stdout.strip()).resolve(), None
    except OSError as exc:
        return None, f"{type(exc).__name__}: {exc}"


def parse_overrides(values: list[str]) -> dict[str, Path]:
    overrides: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Invalid --source override: {value!r}; expected SOURCE_ID=/path")
        source_id, raw_path = value.split("=", 1)
        source_id = source_id.strip()
        if not source_id:
            raise ValueError("Source override requires a source ID.")
        overrides[source_id] = Path(raw_path).expanduser().resolve()
    return overrides


def workspace_overrides(workspace: Path | None) -> tuple[dict[str, Path], str | None]:
    if workspace is None:
        return {}, None
    root = workspace.expanduser().resolve()
    manifest_path = root / "WORKSPACE.json"
    if not manifest_path.is_file():
        raise ValueError(f"Unified DIO workspace manifest not found: {manifest_path}. Run scripts/build_unified_dio_workspace.py first.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "dio.unified_workspace_receipt.v1":
        raise ValueError("Unsupported unified DIO workspace manifest schema.")
    overrides: dict[str, Path] = {}
    for mount in manifest.get("mounts") or []:
        if mount.get("state") != "mounted":
            continue
        source_id = str(mount.get("source_id") or "")
        workspace_path = mount.get("workspace_path")
        if source_id and workspace_path:
            path = Path(str(workspace_path)).expanduser()
            if path.exists():
                overrides[source_id] = path.resolve()
    return overrides, str(manifest_path)


def resolve_local_path(source: dict[str, Any], overrides: dict[str, Path]) -> Path | None:
    source_id = str(source["source_id"])
    if source_id in overrides:
        return overrides[source_id]
    for hint in source.get("local_path_hints") or []:
        path = Path(str(hint)).expanduser()
        if path.exists():
            return path.resolve()
    return None


def dirty_entries(repo: Path) -> tuple[bool, list[dict[str, Any]], str | None]:
    # Porcelain v1 uses a significant leading space in statuses such as " M".
    # Never strip this output, or " M README.md" becomes "M README.md" and the
    # first character of the path is silently lost during parsing.
    raw = run_git(repo, "status", "--porcelain=v1", "-z", strip=False)
    if not raw:
        return False, [], None
    chunks = [chunk for chunk in raw.split("\x00") if chunk]
    rows: list[dict[str, Any]] = []
    digest_material: list[str] = []
    index = 0
    while index < len(chunks):
        entry = chunks[index]
        status = entry[:2]
        path_text = entry[3:] if len(entry) >= 4 else ""
        if status.startswith("R") or status.startswith("C"):
            index += 1
            if index < len(chunks):
                path_text = chunks[index]
        path = repo / path_text
        file_hash = sha256_file(path) if path.is_file() else None
        rows.append({"path": path_text, "status": status, "sha256": file_hash})
        digest_material.append(f"{status}\t{path_text}\t{file_hash or 'missing'}")
        index += 1
    fingerprint = sha256_bytes("\n".join(sorted(digest_material)).encode("utf-8"))
    return True, rows, fingerprint


def filesystem_tree_fingerprint(root: Path, max_files: int = 50000) -> tuple[str, int, int]:
    """Hash a current filesystem tree without implying any Git ancestry.

    The fingerprint includes relative paths, file sizes and content hashes, plus
    symlink targets. Known generated/cache directories are excluded consistently.
    Capture refuses rather than silently truncating if the safety file limit is hit.
    """
    digest = hashlib.sha256()
    file_count = 0
    total_bytes = 0
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        dirs[:] = sorted(
            name
            for name in dirs
            if name not in SKIP_DIRS and not (current_path / name).is_symlink()
        )
        for filename in sorted(files):
            path = current_path / filename
            try:
                relative = path.relative_to(root).as_posix()
            except ValueError:
                continue
            if path.is_symlink():
                try:
                    target = os.readlink(path)
                except OSError as exc:
                    raise RuntimeError(f"Could not read symlink {relative}: {exc}") from exc
                material = f"symlink\t{relative}\t{target}"
            elif path.is_file():
                file_count += 1
                if file_count > max_files:
                    raise RuntimeError(
                        f"Filesystem capture exceeded safety limit of {max_files} files; refusing partial provenance receipt."
                    )
                try:
                    size = path.stat().st_size
                except OSError as exc:
                    raise RuntimeError(f"Could not stat {relative}: {exc}") from exc
                file_hash = sha256_file(path)
                if file_hash is None:
                    raise RuntimeError(f"Could not hash {relative}; refusing partial provenance receipt.")
                total_bytes += size
                material = f"file\t{relative}\t{size}\t{file_hash}"
            else:
                continue
            digest.update(material.encode("utf-8", errors="surrogateescape"))
            digest.update(b"\n")
    return digest.hexdigest(), file_count, total_bytes


def filesystem_marker(repo: Path, marker: str, max_files: int = 8000) -> str | None:
    folded = marker.casefold()
    visited = 0
    for current, dirs, files in os.walk(repo):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        current_path = Path(current)
        try:
            depth = len(current_path.relative_to(repo).parts)
        except ValueError:
            continue
        if depth > 7:
            dirs[:] = []
            continue
        for filename in files:
            path = current_path / filename
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            visited += 1
            if visited > max_files:
                return None
            try:
                if path.stat().st_size > 1_000_000:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore").casefold()
            except OSError:
                continue
            if folded in text:
                return str(path.relative_to(repo))
    return None


def marker_presence(repo: Path, markers: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for marker in markers:
        sample: str | None = None
        try:
            process = subprocess.run(
                ["git", "-C", str(repo), "grep", "-I", "-n", "-F", "--", marker],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=False,
            )
            lines = [line for line in process.stdout.splitlines() if line.strip()]
            sample = lines[0][:500] if lines else None
        except (OSError, subprocess.SubprocessError):
            sample = None
        if sample is None:
            untracked_hit = filesystem_marker(repo, marker)
            if untracked_hit:
                sample = f"worktree:{untracked_hit}"
        results.append({"marker": marker, "found": sample is not None, "sample": sample})
    return results


def capture_source(source: dict[str, Any], overrides: dict[str, Path]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source_id": source["source_id"],
        "role": source["role"],
        "capture_state": "source_unresolved",
        "claim_authority": "none",
        "github_repo": source.get("github_repo"),
        "published_ref": source.get("published_ref"),
        "published_sha": source.get("published_sha"),
        "local_path": None,
        "local_head_sha": None,
        "local_branch": None,
        "local_origin": None,
        "dirty": None,
        "dirty_tree_sha256": None,
        "dirty_files": [],
        "published_sha_matches_local_head": None,
        "provenance_mode": None,
        "git_metadata_state": None,
        "git_metadata_detail": None,
        "filesystem_tree_sha256": None,
        "filesystem_file_count": None,
        "filesystem_total_bytes": None,
        "provenance_note": None,
        "marker_presence": [],
        "notes": source.get("notes"),
        "error": None,
    }
    local_path = resolve_local_path(source, overrides)
    policy = str(source.get("capture_policy") or "")
    if local_path is None:
        if policy in {"published_reference_only", "published_plus_local_if_newer", "self_dynamic"} and source.get("published_sha"):
            result["capture_state"] = "published_only"
            result["claim_authority"] = "published"
            result["provenance_mode"] = "published_reference"
        elif source.get("published_sha"):
            result["capture_state"] = "local_path_missing"
            result["claim_authority"] = "limited"
        return result

    result["local_path"] = str(local_path)
    if not local_path.is_dir():
        result["capture_state"] = "local_path_missing"
        result["claim_authority"] = "limited" if source.get("published_sha") else "none"
        result["error"] = "Resolved path is not a directory."
        return result

    root, git_detail = git_root_or_none(local_path)
    if root is None:
        try:
            tree_sha, file_count, total_bytes = filesystem_tree_fingerprint(local_path)
            result["capture_state"] = "local_filesystem_captured"
            result["claim_authority"] = "local_captured"
            result["provenance_mode"] = "filesystem_snapshot"
            result["git_metadata_state"] = "missing_or_invalid"
            result["git_metadata_detail"] = git_detail
            result["filesystem_tree_sha256"] = tree_sha
            result["filesystem_file_count"] = file_count
            result["filesystem_total_bytes"] = total_bytes
            result["provenance_note"] = (
                "Current filesystem bytes were captured deterministically. Git ancestry is unavailable and was not inferred; "
                "any published SHA is a baseline reference only."
            )
            result["marker_presence"] = marker_presence(
                local_path,
                [str(item) for item in source.get("expected_local_markers") or []],
            )
        except Exception as exc:
            result["capture_state"] = "capture_error"
            result["claim_authority"] = "limited" if source.get("published_sha") else "none"
            result["provenance_mode"] = "filesystem_snapshot"
            result["git_metadata_state"] = "missing_or_invalid"
            result["git_metadata_detail"] = git_detail
            result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    try:
        result["local_path"] = str(root)
        result["provenance_mode"] = "git_worktree"
        result["git_metadata_state"] = "valid"
        result["local_head_sha"] = run_git(root, "rev-parse", "HEAD")
        result["local_branch"] = run_git(root, "branch", "--show-current", check=False) or None
        result["local_origin"] = run_git(root, "remote", "get-url", "origin", check=False) or None
        dirty, files, dirty_fingerprint = dirty_entries(root)
        result["dirty"] = dirty
        result["dirty_files"] = files
        result["dirty_tree_sha256"] = dirty_fingerprint
        published_sha = source.get("published_sha")
        result["published_sha_matches_local_head"] = bool(published_sha and published_sha == result["local_head_sha"]) if published_sha else None
        result["marker_presence"] = marker_presence(root, [str(item) for item in source.get("expected_local_markers") or []])
        if dirty:
            result["capture_state"] = "local_dirty_captured"
        elif result["published_sha_matches_local_head"]:
            result["capture_state"] = "local_clean_matches_published"
        else:
            result["capture_state"] = "local_clean_newer_or_different"
        result["claim_authority"] = "local_captured"
    except Exception as exc:
        result["capture_state"] = "capture_error"
        result["claim_authority"] = "limited" if source.get("published_sha") else "none"
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def blocker_for(source_cfg: dict[str, Any], captured: dict[str, Any]) -> dict[str, str] | None:
    policy = str(source_cfg.get("capture_policy") or "")
    state = str(captured["capture_state"])
    source_id = str(source_cfg["source_id"])
    if state == "capture_error":
        return {"source_id": source_id, "code": "CAPTURE_ERROR", "message": captured.get("error") or "Source capture failed."}
    if policy == "source_path_required" and state in {"source_unresolved", "local_path_missing"}:
        return {"source_id": source_id, "code": "SOURCE_PATH_REQUIRED", "message": "A local source path must be resolved and captured before implementation claims are promoted."}
    if policy == "local_required_when_newer" and state in {"source_unresolved", "local_path_missing", "published_only"}:
        return {"source_id": source_id, "code": "LOCAL_CAPTURE_REQUIRED", "message": "Known newer local work requires a local source-tree capture receipt."}
    expected = [str(item) for item in source_cfg.get("expected_local_markers") or []]
    if expected and captured.get("claim_authority") == "local_captured":
        missing = [str(item.get("marker")) for item in captured.get("marker_presence") or [] if not item.get("found")]
        if missing:
            return {
                "source_id": source_id,
                "code": "EXPECTED_EVIDENCE_MARKER_MISSING",
                "message": "Captured source tree does not contain every expected evidence marker: " + ", ".join(missing),
            }
    return None


def build_snapshot(registry_path: Path, overrides: dict[str, Path], workspace_manifest_path: str | None = None) -> dict[str, Any]:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    created_at = timestamp()
    sources: list[dict[str, Any]] = []
    blockers: list[dict[str, str]] = []
    for source_cfg in registry["sources"]:
        captured = capture_source(source_cfg, overrides)
        sources.append(captured)
        blocker = blocker_for(source_cfg, captured)
        if blocker:
            blockers.append(blocker)

    unresolved = any(item["capture_state"] in {"source_unresolved", "local_path_missing", "capture_error"} for item in sources)
    if blockers:
        overall = "BLOCKED"
    elif unresolved:
        overall = "NEEDS_LOCAL_CAPTURE"
    else:
        overall = "READY"
    snapshot: dict[str, Any] = {
        "schema": "dio.system_snapshot.v1",
        "snapshot_id": stable_id(
            "SNAP",
            created_at,
            *(
                f"{row['source_id']}:{row.get('local_head_sha') or row.get('filesystem_tree_sha256') or row.get('published_sha') or 'none'}:"
                f"{row.get('dirty_tree_sha256') or row.get('filesystem_tree_sha256') or 'clean'}"
                for row in sources
            ),
        ),
        "created_at": created_at,
        "overall_state": overall,
        "source_registry_path": str(registry_path.resolve()),
        "workspace_manifest_path": workspace_manifest_path,
        "sources": sources,
        "blockers": blockers,
        "snapshot_sha256": "",
    }
    canonical = json.dumps({**snapshot, "snapshot_sha256": ""}, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    snapshot["snapshot_sha256"] = sha256_bytes(canonical)
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture a read-only DIO cross-system truth snapshot from published pins and local source trees.")
    parser.add_argument("--registry", default=str(REGISTRY_PATH))
    parser.add_argument("--workspace", help="Canonical unified DIO workspace root. Mounted sources override legacy path hints.")
    parser.add_argument("--out", default=str(ROOT / "state" / "system_snapshots" / "latest.json"))
    parser.add_argument("--source", action="append", default=[], metavar="SOURCE_ID=/path", help="Override or supply a local source path. Repeatable; explicit overrides win over workspace mounts.")
    parser.add_argument("--require-ready", action="store_true", help="Exit non-zero unless the resulting snapshot is READY.")
    args = parser.parse_args()

    registry_path = Path(args.registry).expanduser().resolve()
    mounted, workspace_manifest_path = workspace_overrides(Path(args.workspace) if args.workspace else None)
    explicit = parse_overrides(args.source)
    overrides = {**mounted, **explicit}
    snapshot = build_snapshot(registry_path, overrides, workspace_manifest_path)
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.with_suffix(out.suffix + ".tmp")
    temp.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(out)
    try:
        out.chmod(0o600)
    except OSError:
        pass
    print(json.dumps({"snapshot_id": snapshot["snapshot_id"], "overall_state": snapshot["overall_state"], "blockers": snapshot["blockers"], "path": str(out)}, indent=2))
    if args.require_ready and snapshot["overall_state"] != "READY":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())