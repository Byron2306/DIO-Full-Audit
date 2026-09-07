import json
import subprocess
import sys

import pytest

from experiments.metamorphic_adaptation.real_pilot_executor import (
    REAL_PILOT_EXECUTOR_READY_TOKEN,
    REAL_PILOT_EXECUTOR_REFUSED_TOKEN,
    REAL_PILOT_EXECUTOR_VERSION,
    execute_real_pilot,
)


ARMS = [
    "A_STATELESS_RESET",
    "B_COMPOSITION_ONLY_NO_RETAINED_LEARNING",
    "C_SEMANTIC_RETAINED",
    "D_MARKET_RETAINED",
    "E_FULL_SEMANTIC_MARKET_BEAST",
]


def _write_scaffold(path, *, ready=True):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_SCAFFOLD_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_SCAFFOLD_REFUSED"
        ),
        "real_pilot_authorized": ready,
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
    }, indent=2, sort_keys=True))


def _write_encounters(path):
    with path.open("w") as fh:
        for index, arm in enumerate(ARMS, start=1):
            fh.write(json.dumps({
                "blind_id": f"REAL-PILOT-BLIND-{index:04d}",
                "arm": arm,
                "encounter_index": 1,
                "status": "REAL_PILOT_STAGED_NOT_EXECUTED",
                "executed": False,
                "adaptive_claim_authorized": False,
                "commercial_or_world_first_claim_authorized": False,
            }, sort_keys=True) + "\n")


def test_real_pilot_executor_refuses_without_execute_flag(tmp_path):
    scaffold = tmp_path / "real_pilot_scaffold_receipt.json"
    encounters = tmp_path / "real_pilot_encounter_receipts.jsonl"
    output = tmp_path / "pilot_execution"

    _write_scaffold(scaffold)
    _write_encounters(encounters)

    receipt = execute_real_pilot(
        scaffold_receipt_path=scaffold,
        pilot_encounters_path=encounters,
        output_dir=output,
        execute=False,
    )

    assert receipt.executor_version == REAL_PILOT_EXECUTOR_VERSION
    assert receipt.status == REAL_PILOT_EXECUTOR_REFUSED_TOKEN
    assert receipt.execute_requested is False
    assert receipt.executed is False
    assert receipt.pilot_encounters_loaded == 5
    assert receipt.pilot_encounters_executed == 0
    assert receipt.adaptive_claim_authorized is False


def test_real_pilot_executor_refuses_when_scaffold_not_ready(tmp_path):
    scaffold = tmp_path / "real_pilot_scaffold_receipt.json"
    encounters = tmp_path / "real_pilot_encounter_receipts.jsonl"
    output = tmp_path / "pilot_execution"

    _write_scaffold(scaffold, ready=False)
    _write_encounters(encounters)

    receipt = execute_real_pilot(
        scaffold_receipt_path=scaffold,
        pilot_encounters_path=encounters,
        output_dir=output,
        execute=True,
    )

    assert receipt.status == REAL_PILOT_EXECUTOR_REFUSED_TOKEN
    assert receipt.executed is False
    assert receipt.pilot_encounters_executed == 0


def test_real_pilot_executor_executes_mocked_native_commands(tmp_path, monkeypatch):
    scaffold = tmp_path / "real_pilot_scaffold_receipt.json"
    encounters = tmp_path / "real_pilot_encounter_receipts.jsonl"
    output = tmp_path / "pilot_execution"

    _write_scaffold(scaffold)
    _write_encounters(encounters)

    class Completed:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(*args, **kwargs):
        return Completed()

    monkeypatch.setattr(subprocess, "run", fake_run)

    receipt = execute_real_pilot(
        scaffold_receipt_path=scaffold,
        pilot_encounters_path=encounters,
        output_dir=output,
        execute=True,
        timeout_seconds=1,
    )

    assert receipt.status == REAL_PILOT_EXECUTOR_READY_TOKEN
    assert receipt.executed is True
    assert receipt.real_native_mode is True
    assert receipt.pilot_encounters_loaded == 5
    assert receipt.pilot_encounters_executed == 5
    assert receipt.pilot_encounters_passed == 5
    assert receipt.pilot_encounters_failed == 0
    assert receipt.pilot_encounters_timed_out == 0
    assert receipt.adaptive_claim_authorized is False

    lines = (output / "real_pilot_execution_receipts.jsonl").read_text().splitlines()
    assert len(lines) == 5
    assert all(json.loads(line)["status"] == "REAL_PILOT_NATIVE_PASSED" for line in lines)


def test_real_pilot_executor_records_timeout_without_claim(tmp_path, monkeypatch):
    scaffold = tmp_path / "real_pilot_scaffold_receipt.json"
    encounters = tmp_path / "real_pilot_encounter_receipts.jsonl"
    output = tmp_path / "pilot_execution"

    _write_scaffold(scaffold)
    _write_encounters(encounters)

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["x"], timeout=1, output="partial", stderr="slow")

    monkeypatch.setattr(subprocess, "run", fake_run)

    receipt = execute_real_pilot(
        scaffold_receipt_path=scaffold,
        pilot_encounters_path=encounters,
        output_dir=output,
        execute=True,
        timeout_seconds=1,
    )

    assert receipt.status == REAL_PILOT_EXECUTOR_READY_TOKEN
    assert receipt.pilot_encounters_timed_out == 5
    assert receipt.pilot_encounters_failed == 0
    assert receipt.adaptive_claim_authorized is False

    lines = (output / "real_pilot_execution_receipts.jsonl").read_text().splitlines()
    assert all(json.loads(line)["exit_code"] == 124 for line in lines)


def test_real_pilot_executor_writes_receipt_and_hashes_logs(tmp_path, monkeypatch):
    scaffold = tmp_path / "real_pilot_scaffold_receipt.json"
    encounters = tmp_path / "real_pilot_encounter_receipts.jsonl"
    output = tmp_path / "pilot_execution"

    _write_scaffold(scaffold)
    _write_encounters(encounters)

    class Completed:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Completed())

    receipt = execute_real_pilot(
        scaffold_receipt_path=scaffold,
        pilot_encounters_path=encounters,
        output_dir=output,
        execute=True,
    )

    data = json.loads((output / "real_pilot_execution_receipt.json").read_text())
    first = json.loads((output / "real_pilot_execution_receipts.jsonl").read_text().splitlines()[0])

    assert data["status"] == receipt.status
    assert len(first["stdout_sha256"]) == 64
    assert len(first["stderr_sha256"]) == 64


def test_real_pilot_executor_boundary_blocks_overclaiming(tmp_path):
    scaffold = tmp_path / "real_pilot_scaffold_receipt.json"
    encounters = tmp_path / "real_pilot_encounter_receipts.jsonl"
    output = tmp_path / "pilot_execution"

    _write_scaffold(scaffold)
    _write_encounters(encounters)

    receipt = execute_real_pilot(
        scaffold_receipt_path=scaffold,
        pilot_encounters_path=encounters,
        output_dir=output,
        execute=False,
    )

    boundary = receipt.boundary.lower()

    assert "explicit execution" in boundary
    assert "no adaptive" in boundary
    assert "world-first" in boundary
    assert "authority-expansion" in boundary


def test_real_pilot_executor_cli_refuses_without_execute(tmp_path):
    scaffold = tmp_path / "real_pilot_scaffold_receipt.json"
    encounters = tmp_path / "real_pilot_encounter_receipts.jsonl"
    output = tmp_path / "pilot_execution"

    _write_scaffold(scaffold)
    _write_encounters(encounters)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_real_pilot_executor.py",
            "--scaffold-receipt",
            str(scaffold),
            "--pilot-encounters",
            str(encounters),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert REAL_PILOT_EXECUTOR_REFUSED_TOKEN in completed.stdout
    assert (output / "real_pilot_execution_receipt.json").exists()
