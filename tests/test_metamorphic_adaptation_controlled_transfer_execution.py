import json
import subprocess
import sys

from experiments.metamorphic_adaptation.controlled_transfer_execution import (
    CONTROLLED_TRANSFER_EXECUTION_READY_TOKEN,
    CONTROLLED_TRANSFER_EXECUTION_REFUSED_TOKEN,
    CONTROLLED_TRANSFER_EXECUTION_VERSION,
    execute_controlled_transfer_fixture,
)


ARMS = [
    "A_STATELESS_RESET",
    "B_COMPOSITION_ONLY_NO_RETAINED_LEARNING",
    "C_SEMANTIC_RETAINED",
    "D_MARKET_RETAINED",
    "E_FULL_SEMANTIC_MARKET_BEAST",
]


def _write_run_receipt(path, *, ready=True):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_TRANSFER_RUN_SCAFFOLD_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_TRANSFER_RUN_REFUSED"
        ),
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
    }, indent=2, sort_keys=True))


def _write_encounters(path, *, encounter_count=5):
    with path.open("w") as fh:
        for arm in ARMS:
            for encounter_index in range(1, encounter_count + 1):
                fh.write(json.dumps({
                    "arm": arm,
                    "encounter_index": encounter_index,
                    "status": "STAGED_NOT_EXECUTED",
                    "executed": False,
                    "adaptive_claim_authorized": False,
                    "commercial_or_world_first_claim_authorized": False,
                }, sort_keys=True) + "\n")


def test_controlled_transfer_execution_executes_fixture_encounters(tmp_path):
    run_receipt = tmp_path / "controlled_transfer_run_receipt.json"
    encounters = tmp_path / "encounter_receipts.jsonl"
    output = tmp_path / "execution"

    _write_run_receipt(run_receipt)
    _write_encounters(encounters, encounter_count=5)

    receipt = execute_controlled_transfer_fixture(
        run_receipt_path=run_receipt,
        encounter_receipts_path=encounters,
        output_dir=output,
        execute=True,
    )

    assert receipt.execution_version == CONTROLLED_TRANSFER_EXECUTION_VERSION
    assert receipt.status == CONTROLLED_TRANSFER_EXECUTION_READY_TOKEN
    assert receipt.execute_requested is True
    assert receipt.fixture_mode is True
    assert receipt.encounters_loaded == 25
    assert receipt.encounters_executed == 25
    assert receipt.adaptive_claim_authorized is False
    assert receipt.commercial_or_world_first_claim_authorized is False

    executed = (output / "executed_encounter_receipts.jsonl").read_text().splitlines()
    assert len(executed) == 25
    assert all(json.loads(line)["status"] == "EXECUTED_FIXTURE" for line in executed)
    assert all(json.loads(line)["executed"] is True for line in executed)


def test_controlled_transfer_execution_refuses_when_scaffold_not_ready(tmp_path):
    run_receipt = tmp_path / "controlled_transfer_run_receipt.json"
    encounters = tmp_path / "encounter_receipts.jsonl"
    output = tmp_path / "execution"

    _write_run_receipt(run_receipt, ready=False)
    _write_encounters(encounters)

    receipt = execute_controlled_transfer_fixture(
        run_receipt_path=run_receipt,
        encounter_receipts_path=encounters,
        output_dir=output,
        execute=True,
    )

    assert receipt.status == CONTROLLED_TRANSFER_EXECUTION_REFUSED_TOKEN
    assert receipt.encounters_loaded == 25
    assert receipt.encounters_executed == 0
    assert receipt.adaptive_claim_authorized is False


def test_controlled_transfer_execution_writes_hashes_and_blind_labels(tmp_path):
    run_receipt = tmp_path / "controlled_transfer_run_receipt.json"
    encounters = tmp_path / "encounter_receipts.jsonl"
    output = tmp_path / "execution"

    _write_run_receipt(run_receipt)
    _write_encounters(encounters, encounter_count=1)

    execute_controlled_transfer_fixture(
        run_receipt_path=run_receipt,
        encounter_receipts_path=encounters,
        output_dir=output,
        execute=True,
    )

    lines = (output / "executed_encounter_receipts.jsonl").read_text().splitlines()
    labels = json.loads((output / "blind_labels.json").read_text())

    assert len(lines) == 5
    assert len(labels) == 5

    first = json.loads(lines[0])
    assert first["blind_id"] == "BLIND-0001"
    assert len(first["input_sha256"]) == 64
    assert len(first["output_sha256"]) == 64
    assert isinstance(first["score_proxy"], float)
    assert labels["BLIND-0001"]["arm"] == "A_STATELESS_RESET"


def test_controlled_transfer_execution_writes_top_level_receipt(tmp_path):
    run_receipt = tmp_path / "controlled_transfer_run_receipt.json"
    encounters = tmp_path / "encounter_receipts.jsonl"
    output = tmp_path / "execution"

    _write_run_receipt(run_receipt)
    _write_encounters(encounters, encounter_count=2)

    receipt = execute_controlled_transfer_fixture(
        run_receipt_path=run_receipt,
        encounter_receipts_path=encounters,
        output_dir=output,
        execute=True,
    )

    data = json.loads((output / "controlled_transfer_execution_receipt.json").read_text())

    assert data["status"] == receipt.status
    assert data["encounters_loaded"] == 10
    assert data["encounters_executed"] == 10
    assert data["adaptive_claim_authorized"] is False


def test_controlled_transfer_execution_boundary_blocks_overclaiming(tmp_path):
    run_receipt = tmp_path / "controlled_transfer_run_receipt.json"
    encounters = tmp_path / "encounter_receipts.jsonl"
    output = tmp_path / "execution"

    _write_run_receipt(run_receipt)
    _write_encounters(encounters, encounter_count=1)

    receipt = execute_controlled_transfer_fixture(
        run_receipt_path=run_receipt,
        encounter_receipts_path=encounters,
        output_dir=output,
        execute=True,
    )

    boundary = receipt.boundary.lower()

    assert "fixture execution" in boundary
    assert "does not constitute real adaptive performance evidence" in boundary
    assert "does not claim improvement" in boundary
    assert "world-first" in boundary
    assert "authority-expansion" in boundary


def test_controlled_transfer_execution_cli_runner(tmp_path):
    run_receipt = tmp_path / "controlled_transfer_run_receipt.json"
    encounters = tmp_path / "encounter_receipts.jsonl"
    output = tmp_path / "execution"

    _write_run_receipt(run_receipt)
    _write_encounters(encounters, encounter_count=2)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_controlled_transfer_execution.py",
            "--run-receipt",
            str(run_receipt),
            "--encounters",
            str(encounters),
            "--output",
            str(output),
            "--execute",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert CONTROLLED_TRANSFER_EXECUTION_READY_TOKEN in completed.stdout
    assert (output / "controlled_transfer_execution_receipt.json").exists()
    assert (output / "executed_encounter_receipts.jsonl").exists()

    lines = (output / "executed_encounter_receipts.jsonl").read_text().splitlines()
    assert len(lines) == 10
