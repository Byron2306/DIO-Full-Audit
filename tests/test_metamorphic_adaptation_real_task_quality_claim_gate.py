import json
import subprocess
import sys
from dataclasses import asdict

from experiments.metamorphic_adaptation.real_task_quality_claim_gate import (
    REAL_TASK_QUALITY_CLAIM_GATE_READY_TOKEN,
    REAL_TASK_QUALITY_CLAIM_GATE_REFUSED_TOKEN,
    REAL_TASK_QUALITY_CLAIM_GATE_VERSION,
    evaluate_real_task_quality_claim_gate,
    write_real_task_quality_claim_gate,
)


def _write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def _bundle(tmp_path, *, bundle_ready=True, execution_ready=True, rubric_ready=True, analysis_ready=True, scores=25, arms=5, tasks=5):
    bundle = tmp_path / "real_task_quality_bundle_receipt.json"
    execution = tmp_path / "real_task_quality_execution_receipt.json"
    rubric = tmp_path / "real_task_quality_rubric_evaluation_receipt.json"
    analysis = tmp_path / "real_task_quality_arm_analysis_receipt.json"

    _write(bundle, {
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_BUNDLE_READY"
            if bundle_ready
            else "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_BUNDLE_REFUSED"
        ),
        "task_assignments_staged": 25 if bundle_ready else 0,
        "real_task_quality_scoring_authorized": bundle_ready,
        "execute_by_default": False,
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
    })

    _write(execution, {
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_EXECUTION_READY"
            if execution_ready
            else "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_EXECUTION_REFUSED"
        ),
        "executed": execution_ready,
        "assignments_loaded": 25 if execution_ready else 0,
        "task_outputs_produced": 25 if execution_ready else 0,
        "real_task_quality_scoring_authorized": execution_ready,
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
    })

    _write(rubric, {
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_RUBRIC_EVALUATION_READY"
            if rubric_ready
            else "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_RUBRIC_EVALUATION_REFUSED"
        ),
        "outputs_loaded": scores if rubric_ready else 0,
        "rubric_scores_written": scores if rubric_ready else 0,
        "mean_quality_score": 0.0,
        "real_task_quality_evaluation_authorized": rubric_ready,
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
    })

    _write(analysis, {
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_ARM_ANALYSIS_READY"
            if analysis_ready
            else "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_ARM_ANALYSIS_REFUSED"
        ),
        "scores_loaded": scores if analysis_ready else 0,
        "labels_loaded": scores if analysis_ready else 0,
        "arms_analyzed": arms if analysis_ready else 0,
        "tasks_analyzed": tasks if analysis_ready else 0,
        "baseline_arm": "A_STATELESS_RESET",
        "baseline_arm_mean": 0.0,
        "full_arm": "E_FULL_SEMANTIC_MARKET_BEAST",
        "full_arm_mean": 0.0,
        "full_minus_baseline_effect": 0.0,
        "real_task_quality_analysis_authorized": analysis_ready,
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
    })

    return bundle, execution, rubric, analysis


def test_real_task_quality_claim_gate_allows_only_quality_pipeline_claim(tmp_path):
    bundle, execution, rubric, analysis = _bundle(tmp_path)

    receipt = evaluate_real_task_quality_claim_gate(
        bundle_receipt_path=bundle,
        execution_receipt_path=execution,
        rubric_evaluation_receipt_path=rubric,
        arm_analysis_receipt_path=analysis,
    )

    assert receipt.gate_version == REAL_TASK_QUALITY_CLAIM_GATE_VERSION
    assert receipt.status == REAL_TASK_QUALITY_CLAIM_GATE_READY_TOKEN
    assert receipt.quality_pipeline_exercised is True
    assert receipt.mechanics_proven is True
    assert receipt.assignments_staged == 25
    assert receipt.task_outputs_produced == 25
    assert receipt.rubric_scores_written == 25
    assert receipt.scores_loaded == 25
    assert receipt.arms_analyzed == 5
    assert receipt.tasks_analyzed == 5
    assert receipt.allowed_claim_tier == "T4_REAL_TASK_QUALITY_PIPELINE_EXERCISED_NO_ADAPTIVE_CLAIM"
    assert receipt.real_adaptive_evidence is False
    assert receipt.adaptive_claim_authorized is False
    assert receipt.commercial_or_world_first_claim_authorized is False


def test_real_task_quality_claim_gate_refuses_without_bundle(tmp_path):
    bundle, execution, rubric, analysis = _bundle(tmp_path, bundle_ready=False)

    receipt = evaluate_real_task_quality_claim_gate(
        bundle_receipt_path=bundle,
        execution_receipt_path=execution,
        rubric_evaluation_receipt_path=rubric,
        arm_analysis_receipt_path=analysis,
    )

    assert receipt.status == REAL_TASK_QUALITY_CLAIM_GATE_REFUSED_TOKEN
    assert receipt.quality_pipeline_exercised is False
    assert receipt.allowed_claim_tier == "T0_NO_CLAIM"


def test_real_task_quality_claim_gate_refuses_without_execution(tmp_path):
    bundle, execution, rubric, analysis = _bundle(tmp_path, execution_ready=False)

    receipt = evaluate_real_task_quality_claim_gate(
        bundle_receipt_path=bundle,
        execution_receipt_path=execution,
        rubric_evaluation_receipt_path=rubric,
        arm_analysis_receipt_path=analysis,
    )

    assert receipt.status == REAL_TASK_QUALITY_CLAIM_GATE_REFUSED_TOKEN
    assert receipt.task_outputs_produced == 0
    assert receipt.mechanics_proven is False


def test_real_task_quality_claim_gate_refuses_wrong_score_count(tmp_path):
    bundle, execution, rubric, analysis = _bundle(tmp_path, scores=24)

    receipt = evaluate_real_task_quality_claim_gate(
        bundle_receipt_path=bundle,
        execution_receipt_path=execution,
        rubric_evaluation_receipt_path=rubric,
        arm_analysis_receipt_path=analysis,
    )

    assert receipt.status == REAL_TASK_QUALITY_CLAIM_GATE_REFUSED_TOKEN
    assert receipt.scores_loaded == 24
    assert receipt.adaptive_claim_authorized is False


def test_real_task_quality_claim_gate_refuses_wrong_arm_count(tmp_path):
    bundle, execution, rubric, analysis = _bundle(tmp_path, arms=4)

    receipt = evaluate_real_task_quality_claim_gate(
        bundle_receipt_path=bundle,
        execution_receipt_path=execution,
        rubric_evaluation_receipt_path=rubric,
        arm_analysis_receipt_path=analysis,
    )

    assert receipt.status == REAL_TASK_QUALITY_CLAIM_GATE_REFUSED_TOKEN
    assert receipt.arms_analyzed == 4
    assert receipt.mechanics_proven is False


def test_real_task_quality_claim_gate_writes_json_and_hashes_sources(tmp_path):
    bundle, execution, rubric, analysis = _bundle(tmp_path)
    output = tmp_path / "real_task_quality_claim_gate.json"

    receipt = write_real_task_quality_claim_gate(
        bundle_receipt_path=bundle,
        execution_receipt_path=execution,
        rubric_evaluation_receipt_path=rubric,
        arm_analysis_receipt_path=analysis,
        output_path=output,
    )

    data = json.loads(output.read_text())

    assert data == json.loads(json.dumps(asdict(receipt)))
    assert len(data["bundle_receipt_sha256"]) == 64
    assert len(data["execution_receipt_sha256"]) == 64
    assert len(data["rubric_evaluation_sha256"]) == 64
    assert len(data["arm_analysis_sha256"]) == 64


def test_real_task_quality_claim_gate_boundary_blocks_overclaiming(tmp_path):
    bundle, execution, rubric, analysis = _bundle(tmp_path)

    receipt = evaluate_real_task_quality_claim_gate(
        bundle_receipt_path=bundle,
        execution_receipt_path=execution,
        rubric_evaluation_receipt_path=rubric,
        arm_analysis_receipt_path=analysis,
    )

    boundary = receipt.boundary.lower()

    assert "frozen task-quality bundle" in boundary
    assert "rubric scoring" in boundary
    assert "post-score arm analysis" in boundary
    assert "does not authorize" in boundary
    assert "world-first claim" in boundary
    assert "authority expansion" in boundary


def test_real_task_quality_claim_gate_cli_runner(tmp_path):
    bundle, execution, rubric, analysis = _bundle(tmp_path)
    output = tmp_path / "real_task_quality_claim_gate.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_real_task_quality_claim_gate.py",
            "--bundle-receipt",
            str(bundle),
            "--execution-receipt",
            str(execution),
            "--rubric-evaluation-receipt",
            str(rubric),
            "--arm-analysis-receipt",
            str(analysis),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert REAL_TASK_QUALITY_CLAIM_GATE_READY_TOKEN in completed.stdout
    assert output.exists()
