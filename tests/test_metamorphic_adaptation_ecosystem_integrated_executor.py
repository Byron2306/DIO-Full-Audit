import json
import subprocess
import sys

from experiments.metamorphic_adaptation.ecosystem_integrated_executor import (
    ECOSYSTEM_INTEGRATED_EXECUTOR_READY_TOKEN,
    ECOSYSTEM_INTEGRATED_EXECUTOR_REFUSED_TOKEN,
    ECOSYSTEM_INTEGRATED_EXECUTOR_VERSION,
    execute_ecosystem_integrated_adaptation_plan,
)


ARMS = [
    ("A_DIO_CORE_ONLY", ["DIO_CORE"]),
    ("B_DIO_CORE_LINGUA", ["DIO_CORE", "LINGUA"]),
    ("C_DIO_BEAST_CONTEXT", ["DIO_CORE", "LINGUA", "BEAST"]),
    ("D_DIO_DOMAIN_ORGANS", ["DIO_CORE", "SOPHIA", "EVIDEX", "HIVENANCE", "MARKET_SENSORIUM", "LEGALIS"]),
    (
        "E_FULL_ECOSYSTEM_ORCHESTRATION",
        [
            "DIO_CORE",
            "LINGUA",
            "BEAST",
            "SOPHIA",
            "EVIDEX",
            "HIVENANCE",
            "MARKET_SENSORIUM",
            "LEGALIS",
            "DOCUMENT_STUDIO",
            "NICHEFOUNDRY",
            "HOMS",
        ],
    ),
]

TASKS = [
    ("ECO-001", "repo_failure_governance", ["BEAST", "LINGUA", "DIO_CORE"]),
    ("ECO-002", "evidence_lineage_repair", ["EVIDEX", "SOPHIA", "DIO_CORE"]),
    ("ECO-003", "market_signal_translation", ["MARKET_SENSORIUM", "HIVENANCE", "LEGALIS", "DIO_CORE"]),
    ("ECO-004", "authority_gate_decision", ["LEGALIS", "SOPHIA", "EVIDEX", "DIO_CORE"]),
    ("ECO-005", "governed_deliverable_incarnation", ["DOCUMENT_STUDIO", "NICHEFOUNDRY", "HOMS", "LINGUA", "DIO_CORE"]),
]


def _write_plan_receipt(path, *, ready=True):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_REFUSED"
        ),
        "tests_true_adaptive_surface": ready,
        "planned_encounters": 25 if ready else 0,
        "execute_by_default": False,
        "adaptive_claim_authorized": False,
    }, indent=2, sort_keys=True))


def _write_assignments(path, *, count=25):
    ordinal = 1
    with path.open("w") as fh:
        for _arm_id, enabled_organs in ARMS:
            for task_id, family, required_organs in TASKS:
                if ordinal > count:
                    return
                fh.write(json.dumps({
                    "blind_id": f"ECO-BLIND-{ordinal:04d}",
                    "task_id": task_id,
                    "task_family": family,
                    "title": f"{family} task",
                    "required_organs": required_organs,
                    "enabled_organs": enabled_organs,
                    "success_criteria": ["criterion one", "criterion two", "criterion three"],
                    "status": "ECOSYSTEM_INTEGRATED_ASSIGNMENT_STAGED_NOT_EXECUTED",
                    "execute_by_default": False,
                    "adaptive_claim_authorized": False,
                    "commercial_or_world_first_claim_authorized": False,
                }, sort_keys=True) + "\n")
                ordinal += 1


def test_ecosystem_integrated_executor_produces_25_outputs(tmp_path):
    plan = tmp_path / "ecosystem_integrated_adaptation_plan_receipt.json"
    assignments = tmp_path / "ecosystem_integrated_blinded_assignments.jsonl"
    output = tmp_path / "execution"

    _write_plan_receipt(plan)
    _write_assignments(assignments)

    receipt = execute_ecosystem_integrated_adaptation_plan(
        plan_receipt_path=plan,
        blinded_assignments_path=assignments,
        output_dir=output,
        execute=True,
    )

    assert receipt.executor_version == ECOSYSTEM_INTEGRATED_EXECUTOR_VERSION
    assert receipt.status == ECOSYSTEM_INTEGRATED_EXECUTOR_READY_TOKEN
    assert receipt.executed is True
    assert receipt.assignments_loaded == 25
    assert receipt.ecosystem_outputs_produced == 25
    assert receipt.organ_gap_outputs > 0
    assert receipt.full_coverage_outputs > 0
    assert 0 < receipt.mean_organ_coverage_score <= 1
    assert receipt.ecosystem_quality_scoring_authorized is True
    assert receipt.adaptive_claim_authorized is False

    lines = (output / "ecosystem_integrated_outputs.jsonl").read_text().splitlines()
    assert len(lines) == 25
    first = json.loads(lines[0])
    assert first["blind_id"] == "ECO-BLIND-0001"
    assert first["status"] == "ECOSYSTEM_INTEGRATED_OUTPUT_PRODUCED"
    assert "arm_id" not in first
    assert first["organ_gap_count"] > 0


def test_ecosystem_integrated_executor_refuses_without_execute_flag(tmp_path):
    plan = tmp_path / "ecosystem_integrated_adaptation_plan_receipt.json"
    assignments = tmp_path / "ecosystem_integrated_blinded_assignments.jsonl"
    output = tmp_path / "execution"

    _write_plan_receipt(plan)
    _write_assignments(assignments)

    receipt = execute_ecosystem_integrated_adaptation_plan(
        plan_receipt_path=plan,
        blinded_assignments_path=assignments,
        output_dir=output,
        execute=False,
    )

    assert receipt.status == ECOSYSTEM_INTEGRATED_EXECUTOR_REFUSED_TOKEN
    assert receipt.executed is False
    assert receipt.ecosystem_outputs_produced == 0
    assert receipt.ecosystem_quality_scoring_authorized is False


def test_ecosystem_integrated_executor_refuses_unready_plan(tmp_path):
    plan = tmp_path / "ecosystem_integrated_adaptation_plan_receipt.json"
    assignments = tmp_path / "ecosystem_integrated_blinded_assignments.jsonl"
    output = tmp_path / "execution"

    _write_plan_receipt(plan, ready=False)
    _write_assignments(assignments)

    receipt = execute_ecosystem_integrated_adaptation_plan(
        plan_receipt_path=plan,
        blinded_assignments_path=assignments,
        output_dir=output,
        execute=True,
    )

    assert receipt.status == ECOSYSTEM_INTEGRATED_EXECUTOR_REFUSED_TOKEN
    assert receipt.executed is False
    assert receipt.adaptive_claim_authorized is False


def test_ecosystem_integrated_executor_refuses_wrong_assignment_count(tmp_path):
    plan = tmp_path / "ecosystem_integrated_adaptation_plan_receipt.json"
    assignments = tmp_path / "ecosystem_integrated_blinded_assignments.jsonl"
    output = tmp_path / "execution"

    _write_plan_receipt(plan)
    _write_assignments(assignments, count=24)

    receipt = execute_ecosystem_integrated_adaptation_plan(
        plan_receipt_path=plan,
        blinded_assignments_path=assignments,
        output_dir=output,
        execute=True,
    )

    assert receipt.status == ECOSYSTEM_INTEGRATED_EXECUTOR_REFUSED_TOKEN
    assert receipt.assignments_loaded == 24
    assert receipt.ecosystem_outputs_produced == 0


def test_ecosystem_integrated_executor_full_arm_has_full_coverage(tmp_path):
    plan = tmp_path / "ecosystem_integrated_adaptation_plan_receipt.json"
    assignments = tmp_path / "ecosystem_integrated_blinded_assignments.jsonl"
    output = tmp_path / "execution"

    _write_plan_receipt(plan)
    _write_assignments(assignments)

    receipt = execute_ecosystem_integrated_adaptation_plan(
        plan_receipt_path=plan,
        blinded_assignments_path=assignments,
        output_dir=output,
        execute=True,
    )

    outputs = [
        json.loads(line)
        for line in (output / "ecosystem_integrated_outputs.jsonl").read_text().splitlines()
    ]
    full_coverage = [item for item in outputs if item["organ_coverage_score"] == 1.0]

    assert receipt.full_coverage_outputs >= 5
    assert len(full_coverage) >= 5
    assert all("arm_id" not in item for item in outputs)


def test_ecosystem_integrated_executor_boundary_blocks_overclaiming(tmp_path):
    plan = tmp_path / "ecosystem_integrated_adaptation_plan_receipt.json"
    assignments = tmp_path / "ecosystem_integrated_blinded_assignments.jsonl"
    output = tmp_path / "execution"

    _write_plan_receipt(plan)
    _write_assignments(assignments)

    receipt = execute_ecosystem_integrated_adaptation_plan(
        plan_receipt_path=plan,
        blinded_assignments_path=assignments,
        output_dir=output,
        execute=True,
    )

    boundary = receipt.boundary.lower()
    assert "25 blinded ecosystem integrated outputs" in boundary
    assert "never expose arm labels" in boundary
    assert "does not compare arms" in boundary
    assert "does not constitute adaptive" in boundary
    assert "world-first" in boundary
    assert "authority expansion" in boundary


def test_ecosystem_integrated_executor_cli_runner(tmp_path):
    plan = tmp_path / "ecosystem_integrated_adaptation_plan_receipt.json"
    assignments = tmp_path / "ecosystem_integrated_blinded_assignments.jsonl"
    output = tmp_path / "execution"

    _write_plan_receipt(plan)
    _write_assignments(assignments)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_ecosystem_integrated_executor.py",
            "--plan-receipt",
            str(plan),
            "--blinded-assignments",
            str(assignments),
            "--output",
            str(output),
            "--execute",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert ECOSYSTEM_INTEGRATED_EXECUTOR_READY_TOKEN in completed.stdout
    assert (output / "ecosystem_integrated_execution_receipt.json").exists()
    assert (output / "ecosystem_integrated_outputs.jsonl").exists()
