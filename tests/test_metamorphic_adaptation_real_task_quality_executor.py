import json
import subprocess
import sys

from experiments.metamorphic_adaptation.real_task_quality_executor import (
    REAL_TASK_QUALITY_EXECUTOR_READY_TOKEN,
    REAL_TASK_QUALITY_EXECUTOR_REFUSED_TOKEN,
    REAL_TASK_QUALITY_EXECUTOR_VERSION,
    execute_real_task_quality_bundle,
)


def _write_bundle(path, *, ready=True):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_BUNDLE_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_BUNDLE_REFUSED"
        ),
        "real_task_quality_scoring_authorized": ready,
        "execute_by_default": False,
        "task_assignments_staged": 25 if ready else 0,
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
    }, indent=2, sort_keys=True))


def _write_assignments(path, *, count=25):
    with path.open("w") as fh:
        for index in range(1, count + 1):
            fh.write(json.dumps({
                "blind_id": f"FULL-TRANSFER-BLIND-{index:04d}",
                "task_id": f"RTQ-{((index - 1) % 5) + 1:03d}",
                "task_family": "portfolio_truth",
                "title": "Bounded task",
                "prompt": "Produce a governed bounded answer.",
                "rubric": {
                    "claim_boundary": 0.25,
                    "evidence_traceability": 0.25,
                    "commercial_truth_separation": 0.25,
                    "actionable_next_step": 0.25,
                },
                "status": "REAL_TASK_QUALITY_ASSIGNMENT_STAGED_NOT_EXECUTED",
                "execute_by_default": False,
                "real_task_quality_scoring_authorized": True,
                "adaptive_claim_authorized": False,
                "commercial_or_world_first_claim_authorized": False,
            }, sort_keys=True) + "\n")


def test_real_task_quality_executor_refuses_without_execute_flag(tmp_path):
    bundle = tmp_path / "real_task_quality_bundle_receipt.json"
    assignments = tmp_path / "real_task_quality_blinded_assignments.jsonl"
    output = tmp_path / "execution"
    _write_bundle(bundle)
    _write_assignments(assignments)

    receipt = execute_real_task_quality_bundle(
        bundle_receipt_path=bundle,
        blinded_assignments_path=assignments,
        output_dir=output,
        execute=False,
    )

    assert receipt.executor_version == REAL_TASK_QUALITY_EXECUTOR_VERSION
    assert receipt.status == REAL_TASK_QUALITY_EXECUTOR_REFUSED_TOKEN
    assert receipt.execute_requested is False
    assert receipt.executed is False
    assert receipt.assignments_loaded == 25
    assert receipt.task_outputs_produced == 0
    assert receipt.adaptive_claim_authorized is False


def test_real_task_quality_executor_refuses_unready_bundle(tmp_path):
    bundle = tmp_path / "real_task_quality_bundle_receipt.json"
    assignments = tmp_path / "real_task_quality_blinded_assignments.jsonl"
    output = tmp_path / "execution"
    _write_bundle(bundle, ready=False)
    _write_assignments(assignments)

    receipt = execute_real_task_quality_bundle(
        bundle_receipt_path=bundle,
        blinded_assignments_path=assignments,
        output_dir=output,
        execute=True,
    )

    assert receipt.status == REAL_TASK_QUALITY_EXECUTOR_REFUSED_TOKEN
    assert receipt.executed is False
    assert receipt.task_outputs_produced == 0


def test_real_task_quality_executor_refuses_incomplete_assignments(tmp_path):
    bundle = tmp_path / "real_task_quality_bundle_receipt.json"
    assignments = tmp_path / "real_task_quality_blinded_assignments.jsonl"
    output = tmp_path / "execution"
    _write_bundle(bundle)
    _write_assignments(assignments, count=24)

    receipt = execute_real_task_quality_bundle(
        bundle_receipt_path=bundle,
        blinded_assignments_path=assignments,
        output_dir=output,
        execute=True,
    )

    assert receipt.status == REAL_TASK_QUALITY_EXECUTOR_REFUSED_TOKEN
    assert receipt.assignments_loaded == 24
    assert receipt.task_outputs_produced == 0


def test_real_task_quality_executor_produces_25_blinded_outputs(tmp_path):
    bundle = tmp_path / "real_task_quality_bundle_receipt.json"
    assignments = tmp_path / "real_task_quality_blinded_assignments.jsonl"
    output = tmp_path / "execution"
    _write_bundle(bundle)
    _write_assignments(assignments)

    receipt = execute_real_task_quality_bundle(
        bundle_receipt_path=bundle,
        blinded_assignments_path=assignments,
        output_dir=output,
        execute=True,
    )

    assert receipt.status == REAL_TASK_QUALITY_EXECUTOR_READY_TOKEN
    assert receipt.execute_requested is True
    assert receipt.executed is True
    assert receipt.assignments_loaded == 25
    assert receipt.task_outputs_produced == 25
    assert receipt.real_task_quality_scoring_authorized is True
    assert receipt.adaptive_claim_authorized is False

    lines = (output / "real_task_quality_outputs.jsonl").read_text().splitlines()
    assert len(lines) == 25
    first = json.loads(lines[0])
    assert first["blind_id"] == "FULL-TRANSFER-BLIND-0001"
    assert first["status"] == "REAL_TASK_QUALITY_OUTPUT_PRODUCED"
    assert "arm" not in first
    assert len(first["answer_sha256"]) == 64


def test_real_task_quality_executor_writes_receipt_and_hashes_sources(tmp_path):
    bundle = tmp_path / "real_task_quality_bundle_receipt.json"
    assignments = tmp_path / "real_task_quality_blinded_assignments.jsonl"
    output = tmp_path / "execution"
    _write_bundle(bundle)
    _write_assignments(assignments)

    receipt = execute_real_task_quality_bundle(
        bundle_receipt_path=bundle,
        blinded_assignments_path=assignments,
        output_dir=output,
        execute=True,
    )

    data = json.loads((output / "real_task_quality_execution_receipt.json").read_text())
    assert data["status"] == receipt.status
    assert len(data["bundle_receipt_sha256"]) == 64
    assert len(data["assignments_sha256"]) == 64


def test_real_task_quality_executor_boundary_blocks_overclaiming(tmp_path):
    bundle = tmp_path / "real_task_quality_bundle_receipt.json"
    assignments = tmp_path / "real_task_quality_blinded_assignments.jsonl"
    output = tmp_path / "execution"
    _write_bundle(bundle)
    _write_assignments(assignments)

    receipt = execute_real_task_quality_bundle(
        bundle_receipt_path=bundle,
        blinded_assignments_path=assignments,
        output_dir=output,
        execute=True,
    )

    boundary = receipt.boundary.lower()
    assert "25 blinded governed task-quality outputs" in boundary
    assert "does not score quality" in boundary
    assert "does not constitute adaptive" in boundary
    assert "world-first" in boundary
    assert "authority expansion" in boundary


def test_real_task_quality_executor_cli_refuses_without_execute(tmp_path):
    bundle = tmp_path / "real_task_quality_bundle_receipt.json"
    assignments = tmp_path / "real_task_quality_blinded_assignments.jsonl"
    output = tmp_path / "execution"
    _write_bundle(bundle)
    _write_assignments(assignments)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_real_task_quality_executor.py",
            "--bundle-receipt",
            str(bundle),
            "--blinded-assignments",
            str(assignments),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert REAL_TASK_QUALITY_EXECUTOR_REFUSED_TOKEN in completed.stdout
    assert (output / "real_task_quality_execution_receipt.json").exists()
