from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .contracts import ContractError, canonical_json


FREEZE_SCHEMA = "dio.metamorphic_adaptation.freeze.v1"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(root: Path, path: Path) -> Path:
    resolved_root = root.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ContractError(f"freeze path escapes repository: {path}") from exc
    return resolved


def _expand(root: Path, patterns: list[str]) -> set[str]:
    files: set[str] = set()
    for pattern in patterns:
        candidate_pattern = Path(pattern)
        if candidate_pattern.is_absolute() or ".." in candidate_pattern.parts:
            raise ContractError(f"freeze path escapes repository: {pattern}")
        matched = False
        for candidate in root.glob(pattern):
            _inside(root, candidate)
            matched = True
            if candidate.is_file():
                files.add(candidate.relative_to(root).as_posix())
            elif candidate.is_dir():
                for child in candidate.rglob("*"):
                    if child.is_file():
                        _inside(root, child)
                        files.add(child.relative_to(root).as_posix())
        if not matched:
            raise ContractError(f"freeze path pattern matched nothing: {pattern}")
    return files


def build_freeze_manifest(repo_root: Path, config: dict[str, Any]) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    patterns = config.get("freeze_paths")
    if not isinstance(patterns, list) or not patterns or not all(isinstance(item, str) and item for item in patterns):
        raise ContractError("freeze_paths must be a non-empty array of repository-relative patterns")

    rows = []
    for rel in sorted(_expand(repo_root, patterns)):
        path = repo_root / rel
        rows.append({"path": rel, "size": path.stat().st_size, "sha256": _sha256_file(path)})
    body = {"schema": FREEZE_SCHEMA, "patterns": list(patterns), "files": rows}
    body["manifest_hash"] = "sha256:" + hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
    return body


def verify_freeze(repo_root: Path, freeze_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    repo_root = repo_root.resolve()
    expected_rows = freeze_manifest.get("files") or []
    expected = {str(row["path"]): row for row in expected_rows}
    patterns = freeze_manifest.get("patterns") or []
    current_paths = _expand(repo_root, list(patterns))
    mismatches: list[dict[str, Any]] = []

    for rel in sorted(set(expected).difference(current_paths)):
        mismatches.append({"path": rel, "state": "MISSING", "expected_sha256": expected[rel]["sha256"], "actual_sha256": None})
    for rel in sorted(current_paths.difference(expected)):
        path = repo_root / rel
        mismatches.append({"path": rel, "state": "ADDED", "expected_sha256": None, "actual_sha256": _sha256_file(path)})
    for rel in sorted(set(expected).intersection(current_paths)):
        path = repo_root / rel
        actual_hash = _sha256_file(path)
        actual_size = path.stat().st_size
        row = expected[rel]
        if actual_hash != row.get("sha256") or actual_size != row.get("size"):
            mismatches.append({
                "path": rel,
                "state": "CHANGED",
                "expected_sha256": row.get("sha256"),
                "actual_sha256": actual_hash,
                "expected_size": row.get("size"),
                "actual_size": actual_size,
            })
    return mismatches
