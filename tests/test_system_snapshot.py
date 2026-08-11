from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.capture_system_snapshot import build_snapshot


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def init_repo(tmp_path: Path) -> tuple[Path, str]:
    if not shutil.which("git"):
        pytest.skip("git is required for snapshot capture tests")
    repo = tmp_path / "source"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], capture_output=True, text=True, check=True)
    git(repo, "config", "user.email", "dio-test@example.invalid")
    git(repo, "config", "user.name", "DIO Test")
    (repo / "README.md").write_text("Sophia stable DIO lineage identity\nUNVERIFIED -> SUPPORTED\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "initial")
    return repo, git(repo, "rev-parse", "HEAD")


def write_registry(path: Path, source: dict) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema": "dio.system_source_registry.v1",
                "captured_at": "2026-08-11T13:00:00Z",
                "purpose": "test",
                "truth_policy": {},
                "sources": [source],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def test_unresolved_required_source_blocks_snapshot(tmp_path: Path) -> None:
    registry = write_registry(
        tmp_path / "registry.json",
        {
            "source_id": "dio_legalis",
            "role": "requirements",
            "github_repo": None,
            "published_ref": None,
            "published_sha": None,
            "local_path_hints": [],
            "capture_policy": "source_path_required",
            "expected_local_markers": [],
            "notes": "test",
        },
    )
    snapshot = build_snapshot(registry, {})
    assert snapshot["overall_state"] == "BLOCKED"
    assert snapshot["sources"][0]["capture_state"] == "source_unresolved"
    assert snapshot["blockers"][0]["code"] == "SOURCE_PATH_REQUIRED"
    assert len(snapshot["snapshot_sha256"]) == 64


def test_clean_local_repo_matching_published_is_captured(tmp_path: Path) -> None:
    repo, head = init_repo(tmp_path)
    registry = write_registry(
        tmp_path / "registry.json",
        {
            "source_id": "sophia",
            "role": "epistemic lineage",
            "github_repo": "example/sophia",
            "published_ref": "main",
            "published_sha": head,
            "local_path_hints": [str(repo)],
            "capture_policy": "local_required_when_newer",
            "expected_local_markers": ["stable DIO lineage identity", "UNVERIFIED"],
            "notes": "test",
        },
    )
    snapshot = build_snapshot(registry, {})
    source = snapshot["sources"][0]
    assert snapshot["overall_state"] == "READY"
    assert source["capture_state"] == "local_clean_matches_published"
    assert source["claim_authority"] == "local_captured"
    assert source["dirty"] is False
    assert all(item["found"] for item in source["marker_presence"])


def test_dirty_local_repo_gets_content_fingerprint_instead_of_being_rejected(tmp_path: Path) -> None:
    repo, head = init_repo(tmp_path)
    (repo / "README.md").write_text("Sophia stable DIO lineage identity\nhuman final decision\n", encoding="utf-8")
    (repo / "NEW.json").write_text('{"state":"SUPPORTED"}\n', encoding="utf-8")
    registry = write_registry(
        tmp_path / "registry.json",
        {
            "source_id": "sophia",
            "role": "epistemic lineage",
            "github_repo": "example/sophia",
            "published_ref": "main",
            "published_sha": head,
            "local_path_hints": [str(repo)],
            "capture_policy": "local_required_when_newer",
            "expected_local_markers": ["human final decision"],
            "notes": "test",
        },
    )
    snapshot = build_snapshot(registry, {})
    source = snapshot["sources"][0]
    assert snapshot["overall_state"] == "READY"
    assert source["capture_state"] == "local_dirty_captured"
    assert source["dirty"] is True
    assert source["dirty_tree_sha256"] and len(source["dirty_tree_sha256"]) == 64
    assert {item["path"] for item in source["dirty_files"]} == {"README.md", "NEW.json"}


def test_explicit_override_resolves_source_without_guessing_path(tmp_path: Path) -> None:
    repo, head = init_repo(tmp_path)
    registry = write_registry(
        tmp_path / "registry.json",
        {
            "source_id": "dio_legalis",
            "role": "requirements",
            "github_repo": None,
            "published_ref": None,
            "published_sha": None,
            "local_path_hints": [],
            "capture_policy": "source_path_required",
            "expected_local_markers": ["UNVERIFIED"],
            "notes": "test",
        },
    )
    snapshot = build_snapshot(registry, {"dio_legalis": repo})
    assert snapshot["overall_state"] == "READY"
    assert snapshot["sources"][0]["claim_authority"] == "local_captured"
    assert snapshot["sources"][0]["local_head_sha"] == head


def test_resolved_source_with_missing_expected_marker_is_still_blocked(tmp_path: Path) -> None:
    repo, _ = init_repo(tmp_path)
    registry = write_registry(
        tmp_path / "registry.json",
        {
            "source_id": "dio_legalis",
            "role": "requirements",
            "github_repo": None,
            "published_ref": None,
            "published_sha": None,
            "local_path_hints": [str(repo)],
            "capture_policy": "source_path_required",
            "expected_local_markers": ["requirement registry", "evidence receipts", "NEEDS_YOU"],
            "notes": "test",
        },
    )
    snapshot = build_snapshot(registry, {})
    assert snapshot["overall_state"] == "BLOCKED"
    assert snapshot["sources"][0]["claim_authority"] == "local_captured"
    assert snapshot["blockers"][0]["code"] == "EXPECTED_EVIDENCE_MARKER_MISSING"
