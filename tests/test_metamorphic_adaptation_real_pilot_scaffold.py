import json
import subprocess
import sys

from experiments.metamorphic_adaptation.real_pilot_scaffold import (
    REAL_PILOT_SCAFFOLD_READY_TOKEN,
    REAL_PILOT_SCAFFOLD_REFUSED_TOKEN,
    REAL_PILOT_SCAFFOLD_VERSION,
    stage_real_pilot_encounters,
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
            "DIO_METAMORPHIC_ADAPTATION_REAL_CONTROLLED_TRANSFER_PILOT_PLAN_READY"
            if authorized
            else "DIO_METAMORPHIC_ADAPTATION_REAL_CONTROLLED_TRANSFER_PILOT_PLAN_REFUSED"
        ),
        "real_pilot_authorized": authorized,
        "execute_by_default": execute_by_default,
        "pilot_encounters": 5 if authorized else 0,
        "full_run_encounters_locked": 25,
        "arms": ARMS,
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
    }, indent=2, sort_keys=True))


def test_real_pilot_scaffold_stages_one_encounter_per_arm(tmp_path):
    plan = tmp_path / "real_controlled_transfer_plan.json"
    output = tmp_path / "real_pilot"
    _write_plan(plan)

    receipt = stage_real_pilot_encounters(
        real_plan_path=plan,
        output_dir=output,
    )

    assert receipt.scaffold_version == REAL_PILOT_SCAFFOLD_VERSION
    assert receipt.status == REAL_PILOT_SCAFFOLD_READY_TOKEN
    assert receipt.real_pilot_authorized is True
    assert receipt.execute_by_default is False
    assert receipt.pilot_encounters_staged == 5
    assert receipt.arms_staged == 5
    assert receipt.adaptive_claim_authorized is False
    assert receipt.commercial_or_world_first_claim_authorized is False

    lines = (output / "real_pilot_encounter_receipts.jsonl").read_text().splitlines()
    assert len(lines) == 5

    encounters = [json.loads(line) for line in lines]
    assert [item["arm"] for item in encounters] == ARMS
    assert all(item["status"] == "REAL_PILOT_STAGED_NOT_EXECUTED" for item in encounters)
    assert all(item["executed"] is False for item in encounters)


def test_real_pilot_scaffold_writes_blind_labels(tmp_path):
    plan = tmp_path / "real_controlled_transfer_plan.json"
    output = tmp_path / "real_pilot"
    _write_plan(plan)

    stage_real_pilot_encounters(real_plan_path=plan, output_dir=output)

    labels = json.loads((output / "real_pilot_blind_labels.json").read_text())

    assert len(labels) == 5
    assert labels["REAL-PILOT-BLIND-0001"]["arm"] == "A_STATELESS_RESET"
    assert labels["REAL-PILOT-BLIND-0005"]["arm"] == "E_FULL_SEMANTIC_MARKET_BEAST"


def test_real_pilot_scaffold_refuses_when_plan_not_authorized(tmp_path):
    plan = tmp_path / "real_controlled_transfer_plan.json"
    output = tmp_path / "real_pilot"
    _write_plan(plan, authorized=False)

    receipt = stage_real_pilot_encounters(real_plan_path=plan, output_dir=output)

    assert receipt.status == REAL_PILOT_SCAFFOLD_REFUSED_TOKEN
    assert receipt.real_pilot_authorized is False
    assert receipt.pilot_encounters_staged == 0
    assert receipt.adaptive_claim_authorized is False


def test_real_pilot_scaffold_refuses_execute_by_default(tmp_path):
    plan = tmp_path / "real_controlled_transfer_plan.json"
    output = tmp_path / "real_pilot"
    _write_plan(plan, execute_by_default=True)

    receipt = stage_real_pilot_encounters(real_plan_path=plan, output_dir=output)

    assert receipt.status == REAL_PILOT_SCAFFOLD_REFUSED_TOKEN
    assert receipt.real_pilot_authorized is False
    assert receipt.execute_by_default is True


def test_real_pilot_scaffold_writes_receipt_and_hashes_plan(tmp_path):
    plan = tmp_path / "real_controlled_transfer_plan.json"
    output = tmp_path / "real_pilot"
    _write_plan(plan)

    receipt = stage_real_pilot_encounters(real_plan_path=plan, output_dir=output)

    data = json.loads((output / "real_pilot_scaffold_receipt.json").read_text())

    assert data["status"] == receipt.status
    assert data["pilot_encounters_staged"] == 5
    assert len(data["plan_sha256"]) == 64


def test_real_pilot_scaffold_boundary_blocks_overclaiming(tmp_path):
    plan = tmp_path / "real_controlled_transfer_plan.json"
    output = tmp_path / "real_pilot"
    _write_plan(plan)

    receipt = stage_real_pilot_encounters(real_plan_path=plan, output_dir=output)

    boundary = receipt.boundary.lower()

    assert "one limited real native pilot encounter per arm" in boundary
    assert "does not execute native commands by default" in boundary
    assert "does not authorize the full 25-encounter run" in boundary
    assert "world-first" in boundary
    assert "authority-expansion" in boundary


def test_real_pilot_scaffold_cli_runner(tmp_path):
    plan = tmp_path / "real_controlled_transfer_plan.json"
    output = tmp_path / "real_pilot"
    _write_plan(plan)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_real_pilot_scaffold.py",
            "--real-plan",
            str(plan),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert REAL_PILOT_SCAFFOLD_READY_TOKEN in completed.stdout
    assert (output / "real_pilot_scaffold_receipt.json").exists()
    assert (output / "real_pilot_encounter_receipts.jsonl").exists()
    assert (output / "real_pilot_blind_labels.json").exists()
