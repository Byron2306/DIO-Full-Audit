from __future__ import annotations

import json
from pathlib import Path

from experiments.metamorphic_adaptation.freeze import build_freeze_manifest, verify_freeze
from experiments.metamorphic_adaptation.state import StateController


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _repo(tmp_path: Path) -> tuple[Path, dict]:
    root = tmp_path / "repo"
    _write(root / "src/core.py", "VALUE = 'frozen'\n")
    _write(root / "prompts/system.txt", "frozen prompt\n")
    _write(root / "state/authority.json", '{"send":"REFUSE"}\n')
    _write(root / "state/semantic/value.json", '{"value":"S0"}\n')
    _write(root / "state/market/value.json", '{"value":"M0"}\n')
    _write(root / "state/beast/value.json", '{"value":"B0"}\n')
    config = {
        "freeze_paths": ["src/**", "prompts/**", "state/authority.json"],
        "state_classes": {
            "S": {"include": ["state/semantic/**"]},
            "M": {"include": ["state/market/**"]},
            "B": {"include": ["state/beast/**"]},
        },
        "expanded_state_paths": {
            "S": ["state/semantic/value.json"],
            "M": ["state/market/value.json"],
            "B": ["state/beast/value.json"],
        },
    }
    return root, config


def _read(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def test_freeze_detects_changed_frozen_file_but_ignores_experiment_output(tmp_path: Path) -> None:
    root, config = _repo(tmp_path)
    manifest = build_freeze_manifest(root, config)

    _write(root / "state/metamorphic_adaptation/run.json", '{"status":"working"}\n')
    assert verify_freeze(root, manifest) == []

    _write(root / "src/core.py", "VALUE = 'changed'\n")
    mismatches = verify_freeze(root, manifest)
    assert any(row["path"] == "src/core.py" and row["state"] == "CHANGED" for row in mismatches)


def test_freeze_detects_added_and_missing_files_inside_frozen_patterns(tmp_path: Path) -> None:
    root, config = _repo(tmp_path)
    manifest = build_freeze_manifest(root, config)

    _write(root / "prompts/new.txt", "late prompt\n")
    (root / "prompts/system.txt").unlink()
    mismatches = verify_freeze(root, manifest)

    assert any(row["path"] == "prompts/new.txt" and row["state"] == "ADDED" for row in mismatches)
    assert any(row["path"] == "prompts/system.txt" and row["state"] == "MISSING" for row in mismatches)


def test_baseline_snapshot_is_hash_bound(tmp_path: Path) -> None:
    root, config = _repo(tmp_path)
    controller = StateController(root, tmp_path / "experiment", config)
    receipt = controller.snapshot_baseline()

    assert receipt["schema"] == "dio.metamorphic_adaptation.state_snapshot.v1"
    assert set(receipt["classes"]) == {"S", "M", "B"}
    assert receipt["snapshot_hash"].startswith("sha256:")

    baseline_manifest = tmp_path / "experiment/state_snapshots/baseline/manifest.json"
    stored = json.loads(baseline_manifest.read_text(encoding="utf-8"))
    assert stored["snapshot_hash"] == receipt["snapshot_hash"]


def test_arm_100_persists_semantic_state_and_resets_market_and_beast(tmp_path: Path) -> None:
    root, config = _repo(tmp_path)
    controller = StateController(root, tmp_path / "experiment", config)
    controller.snapshot_baseline()
    arm_root = tmp_path / "experiment/arms/100"

    controller.prepare_arm("100", arm_root)
    _write(root / "state/semantic/value.json", '{"value":"S1"}\n')
    _write(root / "state/market/value.json", '{"value":"M1"}\n')
    _write(root / "state/beast/value.json", '{"value":"B1"}\n')
    controller.seal_arm_state("100", arm_root, "episode-a")

    controller.prepare_arm("100", arm_root)
    assert '"S1"' in _read(root, "state/semantic/value.json")
    assert '"M0"' in _read(root, "state/market/value.json")
    assert '"B0"' in _read(root, "state/beast/value.json")


def test_arm_111_persists_all_three_state_classes(tmp_path: Path) -> None:
    root, config = _repo(tmp_path)
    controller = StateController(root, tmp_path / "experiment", config)
    controller.snapshot_baseline()
    arm_root = tmp_path / "experiment/arms/111"

    controller.prepare_arm("111", arm_root)
    for state_class, rel in {
        "S": "state/semantic/value.json",
        "M": "state/market/value.json",
        "B": "state/beast/value.json",
    }.items():
        _write(root / rel, json.dumps({"value": f"{state_class}1"}) + "\n")
    controller.seal_arm_state("111", arm_root, "episode-a")

    controller.prepare_arm("111", arm_root)
    assert '"S1"' in _read(root, "state/semantic/value.json")
    assert '"M1"' in _read(root, "state/market/value.json")
    assert '"B1"' in _read(root, "state/beast/value.json")


def test_disabled_factor_creation_is_removed_on_next_prepare(tmp_path: Path) -> None:
    root, config = _repo(tmp_path)
    controller = StateController(root, tmp_path / "experiment", config)
    controller.snapshot_baseline()
    arm_root = tmp_path / "experiment/arms/100"

    controller.prepare_arm("100", arm_root)
    _write(root / "state/beast/late_crystal.json", '{"value":"forbidden persistence"}\n')
    controller.seal_arm_state("100", arm_root, "episode-a")
    controller.prepare_arm("100", arm_root)

    assert not (root / "state/beast/late_crystal.json").exists()


def test_verify_no_leakage_flags_mutation_of_disabled_factor(tmp_path: Path) -> None:
    root, config = _repo(tmp_path)
    controller = StateController(root, tmp_path / "experiment", config)
    controller.snapshot_baseline()
    before = controller.current_state_hashes()

    _write(root / "state/semantic/value.json", '{"value":"allowed"}\n')
    _write(root / "state/beast/value.json", '{"value":"leaked"}\n')
    after = controller.current_state_hashes()

    leaks = controller.verify_no_leakage("100", before, after)
    assert not any(row["state_class"] == "S" for row in leaks)
    assert any(row["state_class"] == "B" for row in leaks)
