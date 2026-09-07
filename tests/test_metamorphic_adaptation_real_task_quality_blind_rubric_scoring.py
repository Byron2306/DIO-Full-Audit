import json
import subprocess
import sys
from dataclasses import asdict

from experiments.metamorphic_adaptation.real_task_quality_blind_rubric_scoring import (
    REAL_TASK_QUALITY_BLIND_RUBRIC_READY_TOKEN,
    REAL_TASK_QUALITY_BLIND_RUBRIC_REFUSED_TOKEN,
    REAL_TASK_QUALITY_BLIND_RUBRIC_VERSION,
    score_real_task_quality_outputs,
)


def _write_execution_receipt(path, *, ready=True, outputs=25):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_EXECUTION_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_EXECUTION_REFUSED"
        ),
        "executed": ready,
        "task_outputs_produced": outputs if ready else 0,
        "real_task_quality_scoring_authorized": ready,
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
                "rubric": {
                    "claim_boundary": 0.25,
                    "evidence_traceability": 0.25,
                    "commercial_truth_separation": 0.25,
                    "actionable_next_step": 0.25,
                },
                "real_task_quality_scoring_authorized": True,
                "adaptive_claim_authorized": False,
            }, sort_keys=True) + "\n")


def _write_outputs(path, *, count=25):
    with path.open("w") as fh:
        for index in range(1, count + 1):
            fh.write(json.dumps({
                "blind_id": f"FULL-TRANSFER-BLIND-{index:04d}",
                "task_id": f"RTQ-{((index - 1) % 5) + 1:03d}",
                "task_family": "portfolio_truth",
                "status": "REAL_TASK_QUALITY_OUTPUT_PRODUCED",
                "answer": (
                    "This answer separates observed evidence from claim authority, preserves human-gate "
                    "limits, avoids invented validation, and recommends the smallest next action."
                ),
                "rubric_dimensions_addressed": [
                    "actionable_next_step",
                    "claim_boundary",
                    "commercial_truth_separation",
                    "evidence_traceability",
                ],
                "rubric_dimension_count": 4,
                "adaptive_claim_authorized": False,
                "commercial_or_world_first_claim_authorized": False,
            }, sort_keys=True) + "\n")


def test_blind_rubric_scoring_scores_25_outputs_without_arm_leak(tmp_path):
    execution = tmp_path / "real_task_quality_execution_receipt.json"
    assignments = tmp_path / "real_task_quality_blinded_assignments.jsonl"
    outputs = tmp_path / "real_task_quality_outputs.jsonl"
    output_dir = tmp_path / "scoring"
    _write_execution_receipt(execution)
    _write_assignments(assignments)
    _write_outputs(outputs)

    receipt = score_real_task_quality_outputs(
        execution_receipt_path=execution,
        blinded_assignments_path=assignments,
        task_outputs_path=outputs,
        output_dir=output_dir,
    )

    assert receipt.scoring_version == REAL_TASK_QUALITY_BLIND_RUBRIC_VERSION
    assert receipt.status == REAL_TASK_QUALITY_BLIND_RUBRIC_READY_TOKEN
    assert receipt.outputs_scored == 25
    assert receipt.mean_score == 1.0
    assert receipt.real_quality_scores_available is True
    assert receipt.real_adaptive_evidence is False
    assert receipt.adaptive_claim_authorized is False

    lines = (output_dir / "real_task_quality_blind_scores.jsonl").read_text().splitlines()
    assert len(lines) == 25
    first = json.loads(lines[0])
    assert first["blind_id"] == "FULL-TRANSFER-BLIND-0001"
    assert first["score"] == 1.0
    assert "arm" not in first
    assert "encounter_index" not in first


def test_blind_rubric_scoring_refuses_unready_execution(tmp_path):
    execution = tmp_path / "real_task_quality_execution_receipt.json"
    assignments = tmp_path / "real_task_quality_blinded_assignments.jsonl"
    outputs = tmp_path / "real_task_quality_outputs.jsonl"
    output_dir = tmp_path / "scoring"
    _write_execution_receipt(execution, ready=False)
    _write_assignments(assignments)
    _write_outputs(outputs)

    receipt = score_real_task_quality_outputs(
        execution_receipt_path=execution,
        blinded_assignments_path=assignments,
        task_outputs_path=outputs,
        output_dir=output_dir,
    )

    assert receipt.status == REAL_TASK_QUALITY_BLIND_RUBRIC_REFUSED_TOKEN
    assert receipt.outputs_scored == 0
    assert receipt.real_quality_scores_available is False


def test_blind_rubric_scoring_refuses_incomplete_outputs(tmp_path):
    execution = tmp_path / "real_task_quality_execution_receipt.json"
    assignments = tmp_path / "real_task_quality_blinded_assignments.jsonl"
    outputs = tmp_path / "real_task_quality_outputs.jsonl"
    output_dir = tmp_path / "scoring"
    _write_execution_receipt(execution, outputs=24)
    _write_assignments(assignments)
    _write_outputs(outputs, count=24)

    receipt = score_real_task_quality_outputs(
        execution_receipt_path=execution,
        blinded_assignments_path=assignments,
        task_outputs_path=outputs,
        output_dir=output_dir,
    )

    assert receipt.status == REAL_TASK_QUALITY_BLIND_RUBRIC_REFUSED_TOKEN
    assert receipt.outputs_loaded == 24
    assert receipt.outputs_scored == 0


def test_blind_rubric_scoring_penalizes_missing_dimensions(tmp_path):
    execution = tmp_path / "real_task_quality_execution_receipt.json"
    assignments = tmp_path / "real_task_quality_blinded_assignments.jsonl"
    outputs = tmp_path / "real_task_quality_outputs.jsonl"
    output_dir = tmp_path / "scoring"
    _write_execution_receipt(execution)
    _write_assignments(assignments)
    _write_outputs(outputs)

    rows = [json.loads(line) for line in outputs.read_text().splitlines()]
    rows[0]["rubric_dimensions_addressed"] = ["claim_boundary"]
    rows[0]["answer"] = "Boundary only."
    outputs.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")

    receipt = score_real_task_quality_outputs(
        execution_receipt_path=execution,
        blinded_assignments_path=assignments,
        task_outputs_path=outputs,
        output_dir=output_dir,
    )

    scores = [json.loads(line) for line in (output_dir / "real_task_quality_blind_scores.jsonl").read_text().splitlines()]
    assert receipt.status == REAL_TASK_QUALITY_BLIND_RUBRIC_READY_TOKEN
    assert scores[0]["score"] < 1.0
    assert scores[0]["score"] == 0.25


def test_blind_rubric_scoring_writes_receipt_and_hashes_sources(tmp_path):
    execution = tmp_path / "real_task_quality_execution_receipt.json"
    assignments = tmp_path / "real_task_quality_blinded_assignments.jsonl"
    outputs = tmp_path / "real_task_quality_outputs.jsonl"
    output_dir = tmp_path / "scoring"
    _write_execution_receipt(execution)
    _write_assignments(assignments)
    _write_outputs(outputs)

    receipt = score_real_task_quality_outputs(
        execution_receipt_path=execution,
        blinded_assignments_path=assignments,
        task_outputs_path=outputs,
        output_dir=output_dir,
    )

    data = json.loads((output_dir / "real_task_quality_blind_rubric_scoring_receipt.json").read_text())
    assert data == json.loads(json.dumps(asdict(receipt)))
    assert len(data["execution_receipt_sha256"]) == 64
    assert len(data["assignments_sha256"]) == 64
    assert len(data["task_outputs_sha256"]) == 64


def test_blind_rubric_scoring_boundary_blocks_overclaiming(tmp_path):
    execution = tmp_path / "real_task_quality_execution_receipt.json"
    assignments = tmp_path / "real_task_quality_blinded_assignments.jsonl"
    outputs = tmp_path / "real_task_quality_outputs.jsonl"
    output_dir = tmp_path / "scoring"
    _write_execution_receipt(execution)
    _write_assignments(assignments)
    _write_outputs(outputs)

    receipt = score_real_task_quality_outputs(
        execution_receipt_path=execution,
        blinded_assignments_path=assignments,
        task_outputs_path=outputs,
        output_dir=output_dir,
    )

    boundary = receipt.boundary.lower()
    assert "scores 25 blinded task outputs" in boundary
    assert "does not rejoin arms" in boundary
    assert "does not constitute adaptive" in boundary
    assert "world-first" in boundary
    assert "authority expansion" in boundary


def test_blind_rubric_scoring_cli_runner(tmp_path):
    execution = tmp_path / "real_task_quality_execution_receipt.json"
    assignments = tmp_path / "real_task_quality_blinded_assignments.jsonl"
    outputs = tmp_path / "real_task_quality_outputs.jsonl"
    output_dir = tmp_path / "scoring"
    _write_execution_receipt(execution)
    _write_assignments(assignments)
    _write_outputs(outputs)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_real_task_quality_blind_rubric_scoring.py",
            "--execution-receipt",
            str(execution),
            "--blinded-assignments",
            str(assignments),
            "--task-outputs",
            str(outputs),
            "--output",
            str(output_dir),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert REAL_TASK_QUALITY_BLIND_RUBRIC_READY_TOKEN in completed.stdout
    assert (output_dir / "real_task_quality_blind_scores.jsonl").exists()
    assert (output_dir / "real_task_quality_blind_rubric_scoring_receipt.json").exists()
