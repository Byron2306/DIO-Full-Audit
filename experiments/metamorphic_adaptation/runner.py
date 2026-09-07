from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from .contracts import canonical_json
from .state import StateController


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_tree(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": "sha256:" + _sha256_file(path),
                "size": path.stat().st_size,
            }
        )
    return rows


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def snapshot_authority(repo_root: Path, paths: list[str]) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in paths:
        target = (repo_root / raw).resolve()
        try:
            target.relative_to(repo_root)
        except ValueError as exc:
            raise ValueError(f"authority path escapes repository: {raw}") from exc
        if not target.exists():
            raise FileNotFoundError(f"authority path missing: {raw}")
        candidates = [target] if target.is_file() else sorted(path for path in target.rglob("*") if path.is_file())
        for candidate in candidates:
            rel = candidate.relative_to(repo_root).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            rows.append({"path": rel, "sha256": "sha256:" + _sha256_file(candidate), "size": candidate.stat().st_size})
    rows.sort(key=lambda row: row["path"])
    hash_value = "sha256:" + hashlib.sha256(canonical_json(rows).encode("utf-8")).hexdigest()
    return {"schema": "dio.metamorphic_adaptation.authority_snapshot.v1", "files": rows, "snapshot_hash": hash_value}


def run_command(
    argv: list[str],
    cwd: Path,
    env: dict[str, str],
    timeout_s: int,
) -> dict[str, Any]:
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
        raise ValueError("argv must be a non-empty list of strings")
    if timeout_s <= 0:
        raise ValueError("timeout_s must be positive")

    merged_env = os.environ.copy()
    merged_env.update({str(key): str(value) for key, value in env.items()})
    started = time.monotonic()
    timed_out = False
    exit_code: int | None
    stdout = ""
    stderr = ""
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            env=merged_env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            shell=False,
            check=False,
        )
        exit_code = completed.returncode
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = None
        stdout_value = exc.stdout or ""
        stderr_value = exc.stderr or ""
        stdout = stdout_value.decode("utf-8", errors="replace") if isinstance(stdout_value, bytes) else str(stdout_value)
        stderr = stderr_value.decode("utf-8", errors="replace") if isinstance(stderr_value, bytes) else str(stderr_value)
    duration = time.monotonic() - started

    output_text = merged_env.get("DIO_EXPERIMENT_OUTPUT_DIR")
    artifacts = _hash_tree(Path(output_text)) if output_text else []
    return {
        "schema": "dio.metamorphic_adaptation.command_run.v1",
        "argv": list(argv),
        "status": "PASS" if not timed_out and exit_code == 0 else "FAILED",
        "exit_code": exit_code,
        "timed_out": timed_out,
        "duration_seconds": duration,
        "stdout": stdout,
        "stderr": stderr,
        "artifacts": artifacts,
    }


def run_encounter(
    *,
    experiment_id: str,
    arm_id: str,
    encounter_id: str,
    replicate: int,
    argv: list[str],
    repo_root: Path,
    experiment_root: Path,
    state_controller: StateController,
    authority_paths: list[str],
    timeout_s: int,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    experiment_root = experiment_root.resolve()
    arm_root = experiment_root / "arms" / arm_id
    state_controller.prepare_arm(arm_id, arm_root)
    state_before = state_controller.current_state_hashes()
    authority_before = snapshot_authority(repo_root, authority_paths)

    output_dir = experiment_root / "runs" / encounter_id / arm_id / f"replicate_{replicate:02d}"
    output_dir.mkdir(parents=True, exist_ok=True)
    lineage_path = experiment_root / "lineage_event.jsonl"
    command_env = {
        "DIO_EXPERIMENT_ID": experiment_id,
        "DIO_EXPERIMENT_ARM": arm_id,
        "DIO_EXPERIMENT_ENCOUNTER": encounter_id,
        "DIO_EXPERIMENT_REPLICATE": str(replicate),
        "DIO_EXPERIMENT_OUTPUT_DIR": str(output_dir),
        "DIO_EXPERIMENT_LINEAGE_PATH": str(lineage_path),
    }
    command = run_command(argv, cwd=repo_root, env=command_env, timeout_s=timeout_s)
    authority_after = snapshot_authority(repo_root, authority_paths)
    state_after = state_controller.current_state_hashes()
    transient_disabled_mutations = state_controller.verify_no_leakage(arm_id, state_before, state_after)

    invalidation_reasons: list[str] = []
    if authority_before["snapshot_hash"] != authority_after["snapshot_hash"]:
        invalidation_reasons.append("AUTHORITY_CHANGED")
    if command["status"] != "PASS":
        invalidation_reasons.append("COMMAND_FAILED")

    seal = state_controller.seal_arm_state(arm_id, arm_root, encounter_id)
    receipt = {
        "schema": "dio.metamorphic_adaptation.encounter_receipt.v1",
        "experiment_id": experiment_id,
        "arm_id": arm_id,
        "encounter_id": encounter_id,
        "replicate": replicate,
        "valid": not invalidation_reasons,
        "invalidation_reasons": invalidation_reasons,
        "authority_before": authority_before,
        "authority_after": authority_after,
        "state_before": state_before,
        "state_after": state_after,
        "transient_disabled_state_mutations": transient_disabled_mutations,
        "command": command,
        "seal": seal,
        "output_dir": str(output_dir),
        "lineage_path": str(lineage_path),
    }
    _write_json(output_dir / "encounter_receipt.json", receipt)
    return receipt


def run_factorial_adaptation(
    *,
    experiment_id: str,
    episodes: list[dict[str, Any]],
    repo_root: Path,
    experiment_root: Path,
    state_controller: StateController,
    authority_paths: list[str],
    timeout_s: int,
) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for episode in episodes:
        episode_id = str(episode["id"])
        argv = list((episode["command"] or {})["argv"])
        for arm_id in ("000", "100", "010", "001", "110", "101", "011", "111"):
            receipts.append(
                run_encounter(
                    experiment_id=experiment_id,
                    arm_id=arm_id,
                    encounter_id=episode_id,
                    replicate=1,
                    argv=argv,
                    repo_root=repo_root,
                    experiment_root=experiment_root,
                    state_controller=state_controller,
                    authority_paths=authority_paths,
                    timeout_s=timeout_s,
                )
            )
    return receipts


def run_transfer_replicates(
    *,
    experiment_id: str,
    tasks: list[dict[str, Any]],
    replicates_per_arm: int,
    repo_root: Path,
    experiment_root: Path,
    state_controller: StateController,
    authority_paths: list[str],
    timeout_s: int,
) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for task in tasks:
        task_id = str(task["id"])
        argv = list((task["command"] or {})["argv"])
        for arm_id in ("000", "100", "010", "001", "110", "101", "011", "111"):
            for replicate in range(1, replicates_per_arm + 1):
                receipts.append(
                    run_encounter(
                        experiment_id=experiment_id,
                        arm_id=arm_id,
                        encounter_id=f"transfer-{task_id}",
                        replicate=replicate,
                        argv=argv,
                        repo_root=repo_root,
                        experiment_root=experiment_root,
                        state_controller=state_controller,
                        authority_paths=authority_paths,
                        timeout_s=timeout_s,
                    )
                )
    return receipts
