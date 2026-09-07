from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.metamorphic_adaptation import ARMS
from experiments.metamorphic_adaptation.contracts import ContractError, load_experiment_config


def _write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _base_config() -> dict:
    return {
        "schema": "dio.metamorphic_adaptation.experiment.v1",
        "confirmatory": False,
        "state_classes": {
            "S": {"include": ["state/semantic/**"]},
            "M": {"include": ["state/market/**"]},
            "B": {"include": ["state/beast/**"]},
        },
        "authority_paths": ["state/authority.json"],
        "adaptation_episodes": [
            {"id": "media", "command": {"argv": ["python", "scripts/media.py"]}},
            {"id": "marketfront", "command": {"argv": ["python", "scripts/site.py"]}},
            {"id": "marketing", "command": {"argv": ["python", "scripts/marketing.py"]}},
        ],
        "held_out_task_count": 3,
        "replicates_per_arm": 5,
    }


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for rel in (
        "state/semantic/value.json",
        "state/market/value.json",
        "state/beast/value.json",
        "state/authority.json",
        "scripts/media.py",
        "scripts/site.py",
        "scripts/marketing.py",
    ):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}" if path.suffix == ".json" else "print('ok')\n", encoding="utf-8")
    return root


def test_factorial_arms_are_complete_and_exact() -> None:
    assert ARMS == {
        "000": frozenset(),
        "100": frozenset({"S"}),
        "010": frozenset({"M"}),
        "001": frozenset({"B"}),
        "110": frozenset({"S", "M"}),
        "101": frozenset({"S", "B"}),
        "011": frozenset({"M", "B"}),
        "111": frozenset({"S", "M", "B"}),
    }


def test_valid_manifest_expands_disjoint_state_paths(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    config_path = _write(root / "experiment.json", _base_config())
    config = load_experiment_config(config_path, root)
    assert set(config["expanded_state_paths"]) == {"S", "M", "B"}
    assert config["expanded_state_paths"]["S"] == ["state/semantic/value.json"]


def test_state_path_may_not_escape_repository(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    config = _base_config()
    config["state_classes"]["S"]["include"] = ["../outside/**"]
    config_path = _write(root / "experiment.json", config)
    with pytest.raises(ContractError, match="escape"):
        load_experiment_config(config_path, root)


def test_state_classes_must_be_disjoint_after_expansion(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    config = _base_config()
    config["state_classes"]["B"]["include"] = ["state/semantic/**"]
    config_path = _write(root / "experiment.json", config)
    with pytest.raises(ContractError, match="overlap"):
        load_experiment_config(config_path, root)


def test_adaptation_episode_ids_must_be_unique(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    config = _base_config()
    config["adaptation_episodes"][1]["id"] = "media"
    config_path = _write(root / "experiment.json", config)
    with pytest.raises(ContractError, match="unique"):
        load_experiment_config(config_path, root)


def test_commands_must_be_argv_arrays_not_shell_strings(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    config = _base_config()
    config["adaptation_episodes"][0]["command"] = {"argv": "python scripts/media.py"}
    config_path = _write(root / "experiment.json", config)
    with pytest.raises(ContractError, match="argv"):
        load_experiment_config(config_path, root)


def test_confirmatory_manifest_requires_three_tasks_and_five_replicates(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    config = _base_config()
    config["confirmatory"] = True
    config["held_out_task_count"] = 2
    config_path = _write(root / "experiment.json", config)
    with pytest.raises(ContractError, match="three held-out tasks"):
        load_experiment_config(config_path, root)

    config["held_out_task_count"] = 3
    config["replicates_per_arm"] = 4
    config_path = _write(root / "experiment.json", config)
    with pytest.raises(ContractError, match="five replicates"):
        load_experiment_config(config_path, root)


def test_authority_snapshot_paths_are_mandatory(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    config = _base_config()
    config["authority_paths"] = []
    config_path = _write(root / "experiment.json", config)
    with pytest.raises(ContractError, match="authority"):
        load_experiment_config(config_path, root)
