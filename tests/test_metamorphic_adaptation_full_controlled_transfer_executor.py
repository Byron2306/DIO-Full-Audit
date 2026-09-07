import json
import subprocess
import sys

from experiments.metamorphic_adaptation.full_controlled_transfer_executor import (
    FULL_TRANSFER_EXECUTOR_READY_TOKEN,
    FULL_TRANSFER_EXECUTOR_REFUSED_TOKEN,
    FULL_TRANSFER_EXECUTOR_VERSION,
    execute_full_controlled_transfer,
)


ARMS = [
    "A_STATELESS_RESET",
    "B_COMPOSITION_ONLY_NO_RETAINED_LEARNING",
    "C_SEMANTIC_RETAINED",
    "D_MARKET_RETAINED",
    "E_FULL_SEMANTIC_MARKET_BEAST",
]


def _write_scaffold(path, *, ready=True, execute_by_default=False):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_SCAFFOLD_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_SCAFFOLD_REFUSED"
        ),
        "full_run_planning_authorized": ready,
        "execute_by_default": execute_by_default,
        "full_run_encounters_staged": 25 if ready else 0,
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
    }, indent=2, sort_keys=True))


def _write_encounters(path, *, count=25):
    with path.open("w") as fh:
        ordinal = 1
        for arm in ARMS:
            for encounter_index in range(1, 6):
                if ordinal > count:
                    return
                fh.write(json.dumps({
                    "blind_id": f"FULL-TRANSFER-BLIND-{ordinal:04d}",
                    "arm": arm,
                    "encounter_index": encounter_index,
                    "status": "FULL_CONTROLLED_TRANSFER_STAGED_NOT_EXECUTED",
                    "execute_by_default": False,
                    "executed": False,
                    "native_execution_allowed_only_with_explicit_flag": True,
                    "adaptive_claim_authorized": False,
                    "commercial_or_world_first_claim_authorized": False,
                }, sort_keys=True) + "\n")
                ordinal += 1


def test_full_controlled_transfer_executor_refuses_without_execute_flag(tmp_path):
    scaffold = tmp_path / "full_controlled_transfer_scaffold_receipt.json"
    encounters = tmp_path / "full_controlled_transfer_encounter_receipts.jsonl"
    output = tmp_path / "execution"

    _write_scaffold(scaffold)
    _write_encounters(encounters)

    receipt = execute_full_controlled_transfer(
        scaffold_receipt_path=scaffold,
        scaffold_encounters_path=encounters,
        output_dir=output,
        execute=False,
    )

    assert receipt.executor_version == FULL_TRANSFER_EXECUTOR_VERSION
    assert receipt.status == FULL_TRANSFER_EXECUTOR_REFUSED_TOKEN
    assert receipt.execute_requested is False
    assert receipt.executed is False
    assert receipt.full_run_encounters_loaded == 25
    assert receipt.full_run_encounters_executed == 0
    assert receipt.adaptive_claim_authorized is False


def test_full_controlled_transfer_executor_refuses_unready_scaffold(tmp_path):
    scaffold = tmp_path / "full_controlled_transfer_scaffold_receipt.json"
    encounters = tmp_path / "full_controlled_transfer_encounter_receipts.jsonl"
    output = tmp_path / "execution"

    _write_scaffold(scaffold, ready=False)
    _write_encounters(encounters)

    receipt = execute_full_controlled_transfer(
        scaffold_receipt_path=scaffold,
        scaffold_encounters_path=encounters,
        output_dir=output,
        execute=True,
    )

    assert receipt.status == FULL_TRANSFER_EXECUTOR_REFUSED_TOKEN
    assert receipt.executed is False
    assert receipt.full_run_encounters_executed == 0


def test_full_controlled_transfer_executor_refuses_wrong_encounter_count(tmp_path):
    scaffold = tmp_path / "full_controlled_transfer_scaffold_receipt.json"
    encounters = tmp_path / "full_controlled_transfer_encounter_receipts.jsonl"
    output = tmp_path / "execution"

    _write_scaffold(scaffold)
    _write_encounters(encounters, count=24)

    receipt = execute_full_controlled_transfer(
        scaffold_receipt_path=scaffold,
        scaffold_encounters_path=encounters,
        output_dir=output,
        execute=True,
    )

    assert receipt.status == FULL_TRANSFER_EXECUTOR_REFUSED_TOKEN
    assert receipt.full_run_encounters_loaded == 24


def test_full_controlled_transfer_executor_executes_mocked_25_encounters(tmp_path, monkeypatch):
    scaffold = tmp_path / "full_controlled_transfer_scaffold_receipt.json"
    encounters = tmp_path / "full_controlled_transfer_encounter_receipts.jsonl"
    output = tmp_path / "execution"

    _write_scaffold(scaffold)
    _write_encounters(encounters)

    class Completed:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Completed())

    receipt = execute_full_controlled_transfer(
        scaffold_receipt_path=scaffold,
        scaffold_encounters_path=encounters,
        output_dir=output,
        execute=True,
        timeout_seconds=1,
    )

    assert receipt.status == FULL_TRANSFER_EXECUTOR_READY_TOKEN
    assert receipt.executed is True
    assert receipt.real_native_mode is True
    assert receipt.full_run_encounters_loaded == 25
    assert receipt.full_run_encounters_executed == 25
    assert receipt.full_run_encounters_passed == 25
    assert receipt.full_run_encounters_failed == 0
    assert receipt.full_run_encounters_timed_out == 0
    assert receipt.adaptive_claim_authorized is False

    lines = (output / "full_controlled_transfer_execution_receipts.jsonl").read_text().splitlines()
    assert len(lines) == 25
    assert all(json.loads(line)["status"] == "FULL_CONTROLLED_TRANSFER_NATIVE_PASSED" for line in lines)


def test_full_controlled_transfer_executor_records_timeouts_without_claim(tmp_path, monkeypatch):
    scaffold = tmp_path / "full_controlled_transfer_scaffold_receipt.json"
    encounters = tmp_path / "full_controlled_transfer_encounter_receipts.jsonl"
    output = tmp_path / "execution"

    _write_scaffold(scaffold)
    _write_encounters(encounters)

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["x"], timeout=1, output="partial", stderr="slow")

    monkeypatch.setattr(subprocess, "run", fake_run)

    receipt = execute_full_controlled_transfer(
        scaffold_receipt_path=scaffold,
        scaffold_encounters_path=encounters,
        output_dir=output,
        execute=True,
        timeout_seconds=1,
    )

    assert receipt.status == FULL_TRANSFER_EXECUTOR_READY_TOKEN
    assert receipt.full_run_encounters_timed_out == 25
    assert receipt.full_run_encounters_failed == 0
    assert receipt.adaptive_claim_authorized is False


def test_full_controlled_transfer_executor_writes_receipt_and_log_hashes(tmp_path, monkeypatch):
    scaffold = tmp_path / "full_controlled_transfer_scaffold_receipt.json"
    encounters = tmp_path / "full_controlled_transfer_encounter_receipts.jsonl"
    output = tmp_path / "execution"

    _write_scaffold(scaffold)
    _write_encounters(encounters)

    class Completed:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Completed())

    receipt = execute_full_controlled_transfer(
        scaffold_receipt_path=scaffold,
        scaffold_encounters_path=encounters,
        output_dir=output,
        execute=True,
    )

    data = json.loads((output / "full_controlled_transfer_execution_receipt.json").read_text())
    first = json.loads((output / "full_controlled_transfer_execution_receipts.jsonl").read_text().splitlines()[0])

    assert data["status"] == receipt.status
    assert len(data["scaffold_receipt_sha256"]) == 64
    assert len(data["scaffold_encounters_sha256"]) == 64
    assert len(first["stdout_sha256"]) == 64
    assert len(first["stderr_sha256"]) == 64


def test_full_controlled_transfer_executor_boundary_blocks_overclaiming(tmp_path):
    scaffold = tmp_path / "full_controlled_transfer_scaffold_receipt.json"
    encounters = tmp_path / "full_controlled_transfer_encounter_receipts.jsonl"
    output = tmp_path / "execution"

    _write_scaffold(scaffold)
    _write_encounters(encounters)

    receipt = execute_full_controlled_transfer(
        scaffold_receipt_path=scaffold,
        scaffold_encounters_path=encounters,
        output_dir=output,
        execute=False,
    )

    boundary = receipt.boundary.lower()

    assert "explicit execution" in boundary
    assert "no adaptive" in boundary
    assert "world-first" in boundary
    assert "authority-expansion" in boundary


def test_full_controlled_transfer_executor_cli_refuses_without_execute(tmp_path):
    scaffold = tmp_path / "full_controlled_transfer_scaffold_receipt.json"
    encounters = tmp_path / "full_controlled_transfer_encounter_receipts.jsonl"
    output = tmp_path / "execution"

    _write_scaffold(scaffold)
    _write_encounters(encounters)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_full_controlled_transfer_executor.py",
            "--scaffold-receipt",
            str(scaffold),
            "--scaffold-encounters",
            str(encounters),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert FULL_TRANSFER_EXECUTOR_REFUSED_TOKEN in completed.stdout
    assert (output / "full_controlled_transfer_execution_receipt.json").exists()
