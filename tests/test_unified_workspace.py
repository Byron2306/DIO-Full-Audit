from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.build_unified_dio_workspace import build_workspace
from scripts.capture_system_snapshot import workspace_overrides


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def init_repo(path: Path, text: str = "DIO organ\n") -> Path:
    if not shutil.which("git"):
        pytest.skip("git is required")
    path.mkdir(parents=True)
    subprocess.run(["git", "init", str(path)], capture_output=True, text=True, check=True)
    git(path, "config", "user.email", "dio-test@example.invalid")
    git(path, "config", "user.name", "DIO Test")
    (path / "README.md").write_text(text, encoding="utf-8")
    git(path, "add", "README.md")
    git(path, "commit", "-m", "initial")
    return path


def write_config(path: Path, workspace: Path, organ: Path | None) -> Path:
    mounts = [
        {
            "alias": "core",
            "source_id": "dio_full_audit",
            "kind": "core",
            "required_for_phase0": True,
            "candidate_paths": [],
        },
        {
            "alias": "legalis",
            "source_id": "dio_legalis",
            "kind": "organ",
            "required_for_phase0": True,
            "candidate_paths": [str(organ)] if organ else [],
            "marker_terms": ["requirement registry", "NEEDS_YOU"],
        },
    ]
    payload = {
        "schema": "dio.unified_workspace.v1",
        "workspace_root": str(workspace),
        "policy": {},
        "layout": {
            "core": "core",
            "organs": "organs",
            "surfaces": "surfaces",
            "state": "state",
            "receipts": "receipts",
            "launcher": "dio",
            "manifest": "WORKSPACE.json",
        },
        "mounts": mounts,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_workspace_builds_one_entrypoint_and_mount_manifest(tmp_path: Path) -> None:
    organ = init_repo(tmp_path / "legalis-source", "requirement registry\nALLOW REFUSE NEEDS_YOU\n")
    workspace = tmp_path / "DIO"
    config = write_config(tmp_path / "workspace.json", workspace, organ)

    manifest, manifest_path = build_workspace(config, None, repair=False)

    assert manifest["state"] == "READY_FOR_PHASE0"
    assert manifest["required_missing"] == []
    assert (workspace / "core").is_symlink()
    assert (workspace / "organs" / "legalis").is_symlink()
    assert (workspace / "dio").is_file()
    assert (workspace / "README.md").is_file()
    assert manifest_path == workspace / "WORKSPACE.json"

    overrides, used_manifest = workspace_overrides(workspace)
    assert used_manifest == str(manifest_path)
    assert overrides["dio_legalis"] == organ.resolve()
    assert overrides["dio_full_audit"] == (workspace / "core").resolve()


def test_workspace_refuses_ready_state_when_required_organ_missing(tmp_path: Path) -> None:
    workspace = tmp_path / "DIO"
    config = write_config(tmp_path / "workspace.json", workspace, None)

    manifest, _ = build_workspace(config, None, repair=False)

    assert manifest["state"] == "NEEDS_SOURCE_RESOLUTION"
    assert manifest["required_missing"] == ["dio_legalis"]
    assert not (workspace / "organs" / "legalis").exists()


def test_marker_terms_can_resolve_untracked_local_organ_work(tmp_path: Path) -> None:
    organ = init_repo(tmp_path / "legalis-source", "base\n")
    (organ / "wave1.md").write_text("DIO Legalis requirement registry\nstatus NEEDS_YOU\n", encoding="utf-8")
    workspace = tmp_path / "DIO"
    config = write_config(tmp_path / "workspace.json", workspace, organ)

    manifest, _ = build_workspace(config, None, repair=False)
    legalis = next(item for item in manifest["mounts"] if item["source_id"] == "dio_legalis")

    assert manifest["state"] == "READY_FOR_PHASE0"
    assert legalis["state"] == "mounted"
    assert legalis["dirty"] is True
    assert "requirement registry" in legalis["marker_hits"]
    assert "NEEDS_YOU" in legalis["marker_hits"]
