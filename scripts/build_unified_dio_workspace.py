#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "dio_workspace.json"
TEXT_SUFFIXES = {".py", ".md", ".json", ".yaml", ".yml", ".txt", ".toml", ".ini"}
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "dist", "build"}


def timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_git(repo: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def git_root(path: Path) -> Path | None:
    value = run_git(path, "rev-parse", "--show-toplevel")
    return Path(value).resolve() if value else None


def marker_hits(root: Path, terms: list[str], *, max_files: int = 6000) -> dict[str, list[str]]:
    """Find marker terms in bounded text files, including untracked files.

    This exists primarily so a newer local-only organ such as Legalis can be
    resolved without requiring it to have already been committed.
    """
    if not terms:
        return {}
    wanted = {term: term.casefold() for term in terms}
    hits: dict[str, list[str]] = {term: [] for term in terms}
    visited = 0
    for current, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        current_path = Path(current)
        try:
            relative_depth = len(current_path.relative_to(root).parts)
        except ValueError:
            continue
        if relative_depth > 6:
            dirs[:] = []
            continue
        for filename in files:
            path = current_path / filename
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            visited += 1
            if visited > max_files:
                return {key: value for key, value in hits.items() if value}
            try:
                if path.stat().st_size > 1_000_000:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore").casefold()
            except OSError:
                continue
            for term, folded in wanted.items():
                if folded in text and len(hits[term]) < 3:
                    hits[term].append(str(path.relative_to(root)))
        if all(hits[term] for term in terms):
            break
    return {key: value for key, value in hits.items() if value}


def candidate_valid(path: Path, marker_terms: list[str]) -> tuple[bool, dict[str, list[str]]]:
    if not path.is_dir():
        return False, {}
    if not marker_terms:
        return True, {}
    hits = marker_hits(path, marker_terms)
    return all(term in hits for term in marker_terms), hits


def select_target(mount: dict[str, Any], core_root: Path) -> tuple[Path | None, dict[str, list[str]]]:
    if mount["kind"] == "core":
        return core_root, {}
    terms = [str(value) for value in mount.get("marker_terms") or []]
    for raw in mount.get("candidate_paths") or []:
        path = Path(str(raw)).expanduser()
        valid, hits = candidate_valid(path, terms)
        if valid:
            return path.resolve(), hits
    return None, {}


def ensure_link(link: Path, target: Path, repair: bool) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink():
        existing = link.resolve(strict=False)
        if existing == target:
            return
        if not repair:
            raise RuntimeError(f"Workspace link already points elsewhere: {link} -> {existing}")
        link.unlink()
    elif link.exists():
        raise RuntimeError(f"Refusing to replace non-symlink workspace path: {link}")
    link.symlink_to(target, target_is_directory=True)


def write_launcher(workspace: Path) -> None:
    launcher = workspace / "dio"
    content = """#!/usr/bin/env bash
set -euo pipefail
DIO_WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$DIO_WORKSPACE_ROOT/core/scripts/dio_workspace.py" --workspace-root "$DIO_WORKSPACE_ROOT" "$@"
"""
    launcher.write_text(content, encoding="utf-8")
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def mount_path(workspace: Path, layout: dict[str, str], mount: dict[str, Any]) -> Path:
    kind = mount["kind"]
    alias = str(mount["alias"])
    if kind == "core":
        return workspace / layout["core"]
    if kind == "surface":
        return workspace / layout["surfaces"] / alias
    return workspace / layout["organs"] / alias


def canonical_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_workspace(config_path: Path, workspace_override: Path | None, *, repair: bool) -> tuple[dict[str, Any], Path]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    workspace = (workspace_override or Path(config["workspace_root"])).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    layout = config["layout"]
    for key in ("organs", "surfaces", "state", "receipts"):
        (workspace / layout[key]).mkdir(parents=True, exist_ok=True)

    mounts: list[dict[str, Any]] = []
    required_missing: list[str] = []
    for spec in config["mounts"]:
        target, hits = select_target(spec, ROOT)
        link = mount_path(workspace, layout, spec)
        row: dict[str, Any] = {
            "alias": spec["alias"],
            "source_id": spec["source_id"],
            "kind": spec["kind"],
            "required_for_phase0": bool(spec.get("required_for_phase0")),
            "workspace_path": str(link),
            "state": "unresolved",
            "target": None,
            "git_root": None,
            "git_head": None,
            "git_branch": None,
            "dirty": None,
            "marker_hits": hits,
        }
        if target is not None:
            ensure_link(link, target, repair)
            repo = git_root(target)
            row.update(
                {
                    "state": "mounted",
                    "target": str(target),
                    "git_root": str(repo) if repo else None,
                    "git_head": run_git(repo, "rev-parse", "HEAD") if repo else None,
                    "git_branch": run_git(repo, "branch", "--show-current") if repo else None,
                    "dirty": bool(run_git(repo, "status", "--porcelain=v1")) if repo else None,
                }
            )
        elif row["required_for_phase0"]:
            required_missing.append(str(spec["source_id"]))
        mounts.append(row)

    manifest: dict[str, Any] = {
        "schema": "dio.unified_workspace_receipt.v1",
        "created_at": timestamp(),
        "workspace_root": str(workspace),
        "core_root": str(ROOT),
        "state": "READY_FOR_PHASE0" if not required_missing else "NEEDS_SOURCE_RESOLUTION",
        "required_missing": required_missing,
        "mounts": mounts,
        "manifest_sha256": "",
    }
    manifest["manifest_sha256"] = canonical_hash({**manifest, "manifest_sha256": ""})
    manifest_path = workspace / layout["manifest"]
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_launcher(workspace)
    readme = workspace / "README.md"
    readme.write_text(
        "# DIO Unified Workspace\n\n"
        "This is the canonical local entry point for the full DIO organism. Existing organ repositories are mounted without moving or rewriting them.\n\n"
        "Use `./dio status`, `./dio phase0`, `./dio phase1`, or `./dio phase01`.\n",
        encoding="utf-8",
    )
    return manifest, manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create one canonical local folder for the full DIO organism without moving existing repositories.")
    parser.add_argument("--config", default=str(CONFIG))
    parser.add_argument("--root", help="Override workspace root; default comes from config/dio_workspace.json")
    parser.add_argument("--repair", action="store_true", help="Repair workspace symlinks that currently point at a different target.")
    args = parser.parse_args()
    manifest, path = build_workspace(
        Path(args.config).expanduser().resolve(),
        Path(args.root).expanduser().resolve() if args.root else None,
        repair=args.repair,
    )
    print(json.dumps({
        "workspace": manifest["workspace_root"],
        "state": manifest["state"],
        "required_missing": manifest["required_missing"],
        "manifest": str(path),
    }, indent=2))
    return 0 if manifest["state"] == "READY_FOR_PHASE0" else 2


if __name__ == "__main__":
    raise SystemExit(main())
