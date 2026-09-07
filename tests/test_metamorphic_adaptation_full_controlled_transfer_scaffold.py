import json
import subprocess
import sys

from experiments.metamorphic_adaptation.full_controlled_transfer_scaffold import (
    FULL_TRANSFER_SCAFFOLD_READY_TOKEN,
    FULL_TRANSFER_SCAFFOLD_REFUSED_TOKEN,
    FULL_TRANSFER_SCAFFOLD_VERSION,
    stage_full_controlled_transfer_run,
)


ARMS = [
    "A_STATELESS_RESET",
    "B_COMPOSITION_ONLY_NO_RETAINED_LEARNING",
    "C_SEMANTIC_RETAINED",
    "D_MARKET_RETAINED",
    "E_FULL_SEMANTIC_MARKET_BEAST",
]


def _write_plan(path, *, authorized=True, execute_by_default=False):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_PLAN_READY"
            if authorized
            else "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_PLAN_REFUSED"
        ),
        "full_run_planning_authorized": authorized,
        "execute_by_default": execute_by_default,
        "requires_explicit_execute_flag": True,
        "arms": ARMS,
        "encounters_per_arm": 5 if authorized else 0,
        "full_run_encounters": 25 if authorized else 0,
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
    }, indent=2, sort_keys=True))


def test_full_controlled_transfer_scaffold_stages_25_encounters(tmp_path):
    plan = tmp_path / "full_controlled_transfer_plan.json"
    output = tmp_path / "full_scaffold"
    _write_plan(plan)

    receipt = stage_full_controlled_transfer_run(
        full_plan_path=plan,
        output_dir=output,
    )

    assert receipt.scaffold_version == FULL_TRANSFER_SCAFFOLD_VERSION
    assert receipt.status == FULL_TRANSFER_SCAFFOLD_READY_TOKEN
    assert receipt.full_run_planning_authorized is True
    assert receipt.execute_by_default is False
    assert receipt.arms_staged == 5
    assert receipt.encounters_per_arm == 5
    assert receipt.full_run_encounters_staged == 25
    assert receipt.adaptive_claim_authorized is False

    lines = (output / "full_controlled_transfer_encounter_receipts.jsonl").read_text().splitlines()
    assert len(lines) == 25

    encounters = [json.loads(line) for line in lines]
    assert encounters[0]["blind_id"] == "FULL-TRANSFER-BLIND-0001"
    assert encounters[-1]["blind_id"] == "FULL-TRANSFER-BLIND-0025"
    assert all(item["status"] == "FULL_CONTROLLED_TRANSFER_STAGED_NOT_EXECUTED" for item in encounters)
    assert all(item["executed"] is False for item in encounters)


def test_full_controlled_transfer_scaffold_writes_blind_labels(tmp_path):
    plan = tmp_path / "full_controlled_transfer_plan.json"
    output = tmp_path / "full_scaffold"
    _write_plan(plan)

    stage_full_controlled_transfer_run(full_plan_path=plan, output_dir=output)

    labels = json.loads((output / "full_controlled_transfer_blind_labels.json").read_text())

    assert len(labels) == 25
    assert labels["FULL-TRANSFER-BLIND-0001"]["arm"] == "A_STATELESS_RESET"
    assert labels["FULL-TRANSFER-BLIND-0005"]["encounter_index"] == 5
    assert labels["FULL-TRANSFER-BLIND-0025"]["arm"] == "E_FULL_SEMANTIC_MARKET_BEAST"


def test_full_controlled_transfer_scaffold_refuses_unready_plan(tmp_path):
    plan = tmp_path / "full_controlled_transfer_plan.json"
    output = tmp_path / "full_scaffold"
    _write_plan(plan, authorized=False)

    receipt = stage_full_controlled_transfer_run(full_plan_path=plan, output_dir=output)

    assert receipt.status == FULL_TRANSFER_SCAFFOLD_REFUSED_TOKEN
    assert receipt.full_run_planning_authorized is False
    assert receipt.full_run_encounters_staged == 0


def test_full_controlled_transfer_scaffold_refuses_execute_by_default(tmp_path):
    plan = tmp_path / "full_controlled_transfer_plan.json"
    output = tmp_path / "full_scaffold"
    _write_plan(plan, execute_by_default=True)

    receipt = stage_full_controlled_transfer_run(full_plan_path=plan, output_dir=output)

    assert receipt.status == FULL_TRANSFER_SCAFFOLD_REFUSED_TOKEN
    assert receipt.execute_by_default is True
    assert receipt.full_run_encounters_staged == 0


def test_full_controlled_transfer_scaffold_writes_receipt_and_hashes_plan(tmp_path):
    plan = tmp_path / "full_controlled_transfer_plan.json"
    output = tmp_path / "full_scaffold"
    _write_plan(plan)

    receipt = stage_full_controlled_transfer_run(full_plan_path=plan, output_dir=output)

    data = json.loads((output / "full_controlled_transfer_scaffold_receipt.json").read_text())

    assert data["status"] == receipt.status
    assert data["full_run_encounters_staged"] == 25
    assert len(data["plan_sha256"]) == 64


def test_full_controlled_transfer_scaffold_boundary_blocks_overclaiming(tmp_path):
    plan = tmp_path / "full_controlled_transfer_plan.json"
    output = tmp_path / "full_scaffold"
    _write_plan(plan)

    receipt = stage_full_controlled_transfer_run(full_plan_path=plan, output_dir=output)

    boundary = receipt.boundary.lower()

    assert "full 25-encounter real controlled transfer run only" in boundary
    assert "does not execute native commands by default" in boundary
    assert "adaptive-composition" in boundary
    assert "world-first" in boundary
    assert "authority-expansion" in boundary


def test_full_controlled_transfer_scaffold_cli_runner(tmp_path):
    plan = tmp_path / "full_controlled_transfer_plan.json"
    output = tmp_path / "full_scaffold"
    _write_plan(plan)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_full_controlled_transfer_scaffold.py",
            "--full-plan",
            str(plan),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert FULL_TRANSFER_SCAFFOLD_READY_TOKEN in completed.stdout
    assert (output / "full_controlled_transfer_scaffold_receipt.json").exists()
    assert (output / "full_controlled_transfer_encounter_receipts.jsonl").exists()
    assert (output / "full_controlled_transfer_blind_labels.json").exists()
