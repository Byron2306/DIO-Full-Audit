from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_SCHEMA = "dio.metamorphic_adaptation.experiment.v1"
STATE_CLASSES = ("S", "M", "B")


class ContractError(RuntimeError):
    """Raised when an experiment contract would make the test ambiguous or unsafe."""


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _safe_relative_pattern(pattern: str) -> None:
    _require(bool(pattern), "state path pattern must not be empty")
    path = Path(pattern)
    _require(not path.is_absolute(), f"state path may not be absolute or escape repository: {pattern}")
    _require(".." not in path.parts, f"state path may not escape repository: {pattern}")


def _resolved_inside(repo_root: Path, path: Path, *, label: str) -> Path:
    resolved_root = repo_root.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ContractError(f"{label} may not escape repository: {path}") from exc
    return resolved


def _expand_pattern(repo_root: Path, pattern: str) -> list[str]:
    _safe_relative_pattern(pattern)
    matches: set[str] = set()
    for candidate in repo_root.glob(pattern):
        _resolved_inside(repo_root, candidate, label="state path")
        if candidate.is_file():
            matches.add(candidate.relative_to(repo_root).as_posix())
        elif candidate.is_dir():
            for child in candidate.rglob("*"):
                if not child.is_file():
                    continue
                _resolved_inside(repo_root, child, label="state path")
                matches.add(child.relative_to(repo_root).as_posix())
    _require(bool(matches), f"state path pattern matched no files: {pattern}")
    return sorted(matches)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"experiment config not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid experiment JSON: {exc}") from exc
    _require(isinstance(value, dict), "experiment config must be a JSON object")
    return value


def _validate_command(command: object, episode_id: str) -> None:
    _require(isinstance(command, dict), f"adaptation episode {episode_id} command must be an object")
    argv = command.get("argv") if isinstance(command, dict) else None
    _require(isinstance(argv, list) and bool(argv), f"adaptation episode {episode_id} command argv must be a non-empty array")
    _require(all(isinstance(item, str) and item for item in argv), f"adaptation episode {episode_id} command argv must contain non-empty strings")


def _validate_authority_paths(repo_root: Path, paths: object) -> list[str]:
    _require(isinstance(paths, list) and bool(paths), "authority snapshot paths are mandatory")
    normalised: list[str] = []
    for raw in paths:
        _require(isinstance(raw, str) and bool(raw), "authority path must be a non-empty string")
        _safe_relative_pattern(raw)
        target = repo_root / raw
        _resolved_inside(repo_root, target, label="authority path")
        _require(target.exists(), f"authority path does not exist: {raw}")
        normalised.append(Path(raw).as_posix())
    return normalised


def load_experiment_config(path: Path, repo_root: Path) -> dict[str, Any]:
    """Load and fail-closed validate the experiment contract.

    This function establishes only experiment custody. It does not execute or
    import DIO organs and therefore cannot create new system capability.
    """

    repo_root = repo_root.resolve()
    config = _load_json(path)
    _require(config.get("schema") == EXPECTED_SCHEMA, f"unexpected experiment schema: {config.get('schema')}")

    state_classes = config.get("state_classes")
    _require(isinstance(state_classes, dict), "state_classes must be an object")
    _require(set(state_classes) == set(STATE_CLASSES), "state_classes must contain exactly S, M and B")

    expanded: dict[str, list[str]] = {}
    owners: dict[str, str] = {}
    for state_class in STATE_CLASSES:
        row = state_classes[state_class]
        _require(isinstance(row, dict), f"state class {state_class} must be an object")
        patterns = row.get("include")
        _require(isinstance(patterns, list) and bool(patterns), f"state class {state_class} include must be non-empty")
        files: set[str] = set()
        for pattern in patterns:
            _require(isinstance(pattern, str), f"state class {state_class} include entries must be strings")
            files.update(_expand_pattern(repo_root, pattern))
        expanded[state_class] = sorted(files)
        for rel in sorted(files):
            previous = owners.get(rel)
            if previous is not None and previous != state_class:
                raise ContractError(f"state class overlap: {rel} belongs to both {previous} and {state_class}")
            owners[rel] = state_class

    authority_paths = _validate_authority_paths(repo_root, config.get("authority_paths"))

    episodes = config.get("adaptation_episodes")
    _require(isinstance(episodes, list) and bool(episodes), "adaptation_episodes must be a non-empty array")
    ids: list[str] = []
    for row in episodes:
        _require(isinstance(row, dict), "adaptation episode must be an object")
        episode_id = row.get("id")
        _require(isinstance(episode_id, str) and bool(episode_id), "adaptation episode id must be a non-empty string")
        ids.append(episode_id)
        _validate_command(row.get("command"), episode_id)
    _require(len(ids) == len(set(ids)), "adaptation episode ids must be unique")

    confirmatory = bool(config.get("confirmatory"))
    held_out_task_count = config.get("held_out_task_count")
    replicates_per_arm = config.get("replicates_per_arm")
    _require(isinstance(held_out_task_count, int) and held_out_task_count > 0, "held_out_task_count must be a positive integer")
    _require(isinstance(replicates_per_arm, int) and replicates_per_arm > 0, "replicates_per_arm must be a positive integer")
    if confirmatory:
        _require(held_out_task_count == 3, "confirmatory experiment requires exactly three held-out tasks")
        _require(replicates_per_arm == 5, "confirmatory experiment requires exactly five replicates per arm")

    validated = json.loads(json.dumps(config))
    validated["expanded_state_paths"] = expanded
    validated["authority_paths"] = authority_paths
    return validated
