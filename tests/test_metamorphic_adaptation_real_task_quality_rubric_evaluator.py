import json
import subprocess
import sys

from experiments.metamorphic_adaptation.real_task_quality_rubric_evaluator import (
    REAL_TASK_QUALITY_RUBRIC_EVALUATOR_READY_TOKEN,
    REAL_TASK_QUALITY_RUBRIC_EVALUATOR_REFUSED_TOKEN,
    REAL_TASK_QUALITY_RUBRIC_EVALUATOR_VERSION,
    evaluate_real_task_quality_rubrics,
)


def _write_execution_receipt(path, *, ready=True, produced=25):
    path.write_text(json.dumps({
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_EXECUTION_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_EXECUTION_REFUSED"
        ),
        "executed": ready,
        "task_outputs_produced": produced,
        "real_task_quality_scoring_authorized": ready,
        "adaptive_claim_authorized": False,
    }, indent=2, sort_keys=True))


def _write_task_outputs(path, *, count=25, use_answer_field=False):
    with path.open("w") as fh:
        for index in range(1, count + 1):
            rubric = {
                "claim_boundary": 0.25,
                "evidence_traceability": 0.25,
                "commercial_truth_separation": 0.25,
                "actionable_next_step": 0.25,
            }
            payload = {
                "blind_id": f"FULL-TRANSFER-BLIND-{index:04d}",
                "task_id": "RTQ-001",
                "task_family": "portfolio_truth",
                "status": "REAL_TASK_QUALITY_OUTPUT_RECORDED",
                "rubric": rubric,
                "adaptive_claim_authorized": False,
                "commercial_or_world_first_claim_authorized": False,
            }
            text = (
                "Claim boundary: separate execution evidence from product proof and commercial validation. "
                "Evidence traceability requires receipts. Authority boundary says refuse external claims. "
                "Next step: collect task-quality scoring evidence before any adaptive claim."
            )
            if use_answer_field:
                payload["answer"] = text
                payload["answer_sha256"] = "b" * 64
            else:
                payload["output_text"] = text
                payload["output_sha256"] = "a" * 64
            fh.write(json.dumps(payload, sort_keys=True) + "\n")


def test_rubric_evaluator_scores_25_blinded_outputs(tmp_path):
    execution = tmp_path / "real_task_quality_execution_receipt.json"
    outputs = tmp_path / "real_task_quality_outputs.jsonl"
    output_dir = tmp_path / "rubric"

    _write_execution_receipt(execution)
    _write_task_outputs(outputs)

    receipt = evaluate_real_task_quality_rubrics(
        execution_receipt_path=execution,
        task_outputs_path=outputs,
        output_dir=output_dir,
    )

    assert receipt.evaluator_version == REAL_TASK_QUALITY_RUBRIC_EVALUATOR_VERSION
    assert receipt.status == REAL_TASK_QUALITY_RUBRIC_EVALUATOR_READY_TOKEN
    assert receipt.outputs_loaded == 25
    assert receipt.rubric_scores_written == 25
    assert receipt.mean_quality_score > 0
    assert receipt.real_task_quality_evaluation_authorized is True
    assert receipt.real_adaptive_evidence is False
    assert receipt.adaptive_claim_authorized is False

    lines = (output_dir / "real_task_quality_rubric_scores.jsonl").read_text().splitlines()
    assert len(lines) == 25
    first = json.loads(lines[0])
    assert first["blind_id"] == "FULL-TRANSFER-BLIND-0001"
    assert "arm" not in first
    assert first["quality_score"] > 0


def test_rubric_evaluator_scores_executor_answer_field(tmp_path):
    execution = tmp_path / "real_task_quality_execution_receipt.json"
    outputs = tmp_path / "real_task_quality_outputs.jsonl"
    output_dir = tmp_path / "rubric"

    _write_execution_receipt(execution)
    _write_task_outputs(outputs, use_answer_field=True)

    receipt = evaluate_real_task_quality_rubrics(
        execution_receipt_path=execution,
        task_outputs_path=outputs,
        output_dir=output_dir,
    )

    first_score = json.loads(
        (output_dir / "real_task_quality_rubric_scores.jsonl").read_text().splitlines()[0]
    )

    assert receipt.status == REAL_TASK_QUALITY_RUBRIC_EVALUATOR_READY_TOKEN
    assert receipt.mean_quality_score > 0
    assert first_score["quality_score"] > 0
    assert first_score["output_sha256"] == "b" * 64
    assert "arm" not in first_score


def test_rubric_evaluator_refuses_unready_execution(tmp_path):
    execution = tmp_path / "real_task_quality_execution_receipt.json"
    outputs = tmp_path / "real_task_quality_outputs.jsonl"
    output_dir = tmp_path / "rubric"

    _write_execution_receipt(execution, ready=False, produced=0)
    _write_task_outputs(outputs)

    receipt = evaluate_real_task_quality_rubrics(
        execution_receipt_path=execution,
        task_outputs_path=outputs,
        output_dir=output_dir,
    )

    assert receipt.status == REAL_TASK_QUALITY_RUBRIC_EVALUATOR_REFUSED_TOKEN
    assert receipt.rubric_scores_written == 0
    assert receipt.real_task_quality_evaluation_authorized is False
    assert receipt.adaptive_claim_authorized is False


def test_rubric_evaluator_refuses_wrong_output_count(tmp_path):
    execution = tmp_path / "real_task_quality_execution_receipt.json"
    outputs = tmp_path / "real_task_quality_outputs.jsonl"
    output_dir = tmp_path / "rubric"

    _write_execution_receipt(execution, produced=24)
    _write_task_outputs(outputs, count=24)

    receipt = evaluate_real_task_quality_rubrics(
        execution_receipt_path=execution,
        task_outputs_path=outputs,
        output_dir=output_dir,
    )

    assert receipt.status == REAL_TASK_QUALITY_RUBRIC_EVALUATOR_REFUSED_TOKEN
    assert receipt.outputs_loaded == 24
    assert receipt.real_adaptive_evidence is False


def test_rubric_evaluator_writes_summary_and_hashes_sources(tmp_path):
    execution = tmp_path / "real_task_quality_execution_receipt.json"
    outputs = tmp_path / "real_task_quality_outputs.jsonl"
    output_dir = tmp_path / "rubric"

    _write_execution_receipt(execution)
    _write_task_outputs(outputs)

    receipt = evaluate_real_task_quality_rubrics(
        execution_receipt_path=execution,
        task_outputs_path=outputs,
        output_dir=output_dir,
    )

    saved = json.loads((output_dir / "real_task_quality_rubric_evaluation_receipt.json").read_text())
    summary = json.loads((output_dir / "real_task_quality_score_summary.json").read_text())

    assert saved["status"] == receipt.status
    assert summary["outputs_scored"] == 25
    assert summary["real_adaptive_evidence"] is False
    assert len(saved["execution_receipt_sha256"]) == 64
    assert len(saved["task_outputs_sha256"]) == 64


def test_rubric_evaluator_boundary_blocks_overclaiming(tmp_path):
    execution = tmp_path / "real_task_quality_execution_receipt.json"
    outputs = tmp_path / "real_task_quality_outputs.jsonl"
    output_dir = tmp_path / "rubric"

    _write_execution_receipt(execution)
    _write_task_outputs(outputs)

    receipt = evaluate_real_task_quality_rubrics(
        execution_receipt_path=execution,
        task_outputs_path=outputs,
        output_dir=output_dir,
    )

    boundary = receipt.boundary.lower()

    assert "scores 25 blinded real task-quality outputs" in boundary
    assert "does not rejoin" in boundary
    assert "does not compare arms" in boundary
    assert "does not constitute adaptive" in boundary
    assert "world-first" in boundary
    assert "authority expansion" in boundary


def test_rubric_evaluator_cli_runner(tmp_path):
    execution = tmp_path / "real_task_quality_execution_receipt.json"
    outputs = tmp_path / "real_task_quality_outputs.jsonl"
    output_dir = tmp_path / "rubric"

    _write_execution_receipt(execution)
    _write_task_outputs(outputs)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_real_task_quality_rubric_evaluator.py",
            "--execution-receipt",
            str(execution),
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
    assert REAL_TASK_QUALITY_RUBRIC_EVALUATOR_READY_TOKEN in completed.stdout
    assert (output_dir / "real_task_quality_rubric_evaluation_receipt.json").exists()
    assert (output_dir / "real_task_quality_rubric_scores.jsonl").exists()
    assert (output_dir / "real_task_quality_score_summary.json").exists()
