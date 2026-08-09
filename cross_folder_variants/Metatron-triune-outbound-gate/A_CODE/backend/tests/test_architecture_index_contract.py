import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = ROOT / "docs" / "architecture_index.json"


def test_architecture_index_points_to_existing_paths():
    payload = json.loads(INDEX_PATH.read_text())

    for section in payload["canonical_runtime_paths"].values():
        for rel_path in section["owners"].values():
            assert (ROOT / rel_path).exists(), f"Missing canonical path: {rel_path}"

    adapter = payload["non_canonical_paths"]["windows_platform_manifold_adapter"]["path"]
    assert (ROOT / adapter).exists(), f"Missing adapter path: {adapter}"

    for item in payload["non_canonical_paths"]["legacy_and_compatibility_surfaces"]:
        assert (ROOT / item["path"]).exists(), f"Missing non-canonical path: {item['path']}"


def test_architecture_index_keeps_world_manifold_authority_unambiguous():
    payload = json.loads(INDEX_PATH.read_text())

    canonical_world_manifold = payload["canonical_runtime_paths"]["world_state_and_governance"]["owners"]["world_manifold"]
    adapter_world_manifold = payload["non_canonical_paths"]["windows_platform_manifold_adapter"]["path"]

    assert canonical_world_manifold == "backend/services/world_manifold.py"
    assert adapter_world_manifold == "backend/arda_windows/world_manifold.py"
    assert canonical_world_manifold != adapter_world_manifold


def test_architecture_index_no_longer_lists_removed_server_old_surface():
    payload = json.loads(INDEX_PATH.read_text())

    paths = [item["path"] for item in payload["non_canonical_paths"]["legacy_and_compatibility_surfaces"]]
    assert "backend/server_old.py" not in paths
