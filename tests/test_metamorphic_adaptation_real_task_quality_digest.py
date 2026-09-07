import json
import subprocess
import sys
from dataclasses import asdict

from experiments.metamorphic_adaptation.real_task_quality_digest import (
    REAL_TASK_QUALITY_DIGEST_READY_TOKEN,
    REAL_TASK_QUALITY_DIGEST_REFUSED_TOKEN,
    REAL_TASK_QUALITY_DIGEST_VERSION,
    build_real_task_quality_digest,
    write_real_task_quality_digest,
)


def _write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def _chain(tmp_path, *, claim_ready=True, outputs=25, scores=25, arms=5, tasks=5):
    bundle = tmp_path / "real_task_quality_bundle_receipt.json"
    execution = tmp_path / "real_task_quality_execution_receipt.json"
    rubric = tmp_path / "real_task_quality_rubric_evaluation_receipt.json"
    arm_analysis = tmp_path / "real_task_quality_arm_analysis_receipt.json"
    claim_gate = tmp_path / "real_task_quality_claim_gate.json"

    _write(bundle, {
        "status": "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_BUNDLE_READY",
        "task_assignments_staged": 25,
        "real_task_quality_scoring_authorized": True,
        "adaptive_claim_authorized": False,
    })
    _write(execution, {
        "status": "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_EXECUTION_READY",
        "executed": True,
        "task_outputs_produced": outputs,
        "adaptive_claim_authorized": False,
    })
    _write(rubric, {
        "status": "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_RUBRIC_EVALUATION_READY",
        "rubric_scores_written": scores,
        "mean_quality_score": 0.0,
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
    })
    _write(arm_analysis, {
        "status": "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_ARM_ANALYSIS_READY",
        "scores_loaded": scores,
        "arms_analyzed": arms,
        "tasks_analyzed": tasks,
        "baseline_arm": "A_STATELESS_RESET",
        "baseline_arm_mean": 0.0,
        "full_arm": "E_FULL_SEMANTIC_MARKET_BEAST",
        "full_arm_mean": 0.0,
        "full_minus_baseline_effect": 0.0,
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
    })
    _write(claim_gate, {
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_CLAIM_GATE_VERDICT_READY"
            if claim_ready
            else "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_CLAIM_GATE_REFUSED"
        ),
        "quality_pipeline_exercised": claim_ready,
        "mechanics_proven": claim_ready,
        "allowed_claim_tier": (
            "T4_REAL_TASK_QUALITY_PIPELINE_EXERCISED_NO_ADAPTIVE_CLAIM"
            if claim_ready
            else "T0_NO_CLAIM"
        ),
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
    })

    return bundle, execution, rubric, arm_analysis, claim_gate


def test_real_task_quality_digest_seals_quality_pipeline_without_adaptive_claim(tmp_path):
    chain = _chain(tmp_path)

    digest = build_real_task_quality_digest(
        bundle_receipt_path=chain[0],
        execution_receipt_path=chain[1],
        rubric_evaluation_receipt_path=chain[2],
        arm_analysis_receipt_path=chain[3],
        claim_gate_path=chain[4],
    )

    assert digest.digest_version == REAL_TASK_QUALITY_DIGEST_VERSION
    assert digest.status == REAL_TASK_QUALITY_DIGEST_READY_TOKEN
    assert digest.real_task_quality_end_to_end_proven is True
    assert digest.quality_pipeline_exercised is True
    assert digest.assignments_staged == 25
    assert digest.task_outputs_produced == 25
    assert digest.rubric_scores_written == 25
    assert digest.scores_loaded == 25
    assert digest.arms_analyzed == 5
    assert digest.tasks_analyzed == 5
    assert digest.mean_quality_score == 0.0
    assert digest.full_minus_baseline_effect == 0.0
    assert digest.allowed_claim_tier == "T4_REAL_TASK_QUALITY_PIPELINE_EXERCISED_NO_ADAPTIVE_CLAIM"
    assert digest.real_adaptive_evidence is False
    assert digest.adaptive_claim_authorized is False
    assert digest.commercial_or_world_first_claim_authorized is False


def test_real_task_quality_digest_refuses_incomplete_outputs(tmp_path):
    chain = _chain(tmp_path, outputs=24)

    digest = build_real_task_quality_digest(
        bundle_receipt_path=chain[0],
        execution_receipt_path=chain[1],
        rubric_evaluation_receipt_path=chain[2],
        arm_analysis_receipt_path=chain[3],
        claim_gate_path=chain[4],
    )

    assert digest.status == REAL_TASK_QUALITY_DIGEST_REFUSED_TOKEN
    assert digest.real_task_quality_end_to_end_proven is False
    assert digest.allowed_claim_tier == "T0_NO_CLAIM"


def test_real_task_quality_digest_refuses_bad_claim_gate(tmp_path):
    chain = _chain(tmp_path, claim_ready=False)

    digest = build_real_task_quality_digest(
        bundle_receipt_path=chain[0],
        execution_receipt_path=chain[1],
        rubric_evaluation_receipt_path=chain[2],
        arm_analysis_receipt_path=chain[3],
        claim_gate_path=chain[4],
    )

    assert digest.status == REAL_TASK_QUALITY_DIGEST_REFUSED_TOKEN
    assert digest.quality_pipeline_exercised is False
    assert digest.adaptive_claim_authorized is False


def test_real_task_quality_digest_refuses_wrong_arm_or_task_count(tmp_path):
    chain = _chain(tmp_path, arms=4, tasks=5)

    digest = build_real_task_quality_digest(
        bundle_receipt_path=chain[0],
        execution_receipt_path=chain[1],
        rubric_evaluation_receipt_path=chain[2],
        arm_analysis_receipt_path=chain[3],
        claim_gate_path=chain[4],
    )

    assert digest.status == REAL_TASK_QUALITY_DIGEST_REFUSED_TOKEN
    assert digest.real_task_quality_end_to_end_proven is False


def test_real_task_quality_digest_writes_json_and_hashes_sources(tmp_path):
    chain = _chain(tmp_path)
    output = tmp_path / "real_task_quality_digest.json"

    digest = write_real_task_quality_digest(
        bundle_receipt_path=chain[0],
        execution_receipt_path=chain[1],
        rubric_evaluation_receipt_path=chain[2],
        arm_analysis_receipt_path=chain[3],
        claim_gate_path=chain[4],
        output_path=output,
    )

    data = json.loads(output.read_text())

    assert data == json.loads(json.dumps(asdict(digest)))
    assert len(data["bundle_receipt_sha256"]) == 64
    assert len(data["execution_receipt_sha256"]) == 64
    assert len(data["rubric_evaluation_sha256"]) == 64
    assert len(data["arm_analysis_sha256"]) == 64
    assert len(data["claim_gate_sha256"]) == 64


def test_real_task_quality_digest_boundary_blocks_overclaiming(tmp_path):
    chain = _chain(tmp_path)

    digest = build_real_task_quality_digest(
        bundle_receipt_path=chain[0],
        execution_receipt_path=chain[1],
        rubric_evaluation_receipt_path=chain[2],
        arm_analysis_receipt_path=chain[3],
        claim_gate_path=chain[4],
    )

    boundary = digest.boundary.lower()

    assert "real task-quality bundle" in boundary
    assert "blinded output generation" in boundary
    assert "rubric evaluation" in boundary
    assert "post-score arm analysis" in boundary
    assert "does not authorize" in boundary
    assert "world-first claim" in boundary
    assert "authority expansion" in boundary


def test_real_task_quality_digest_cli_runner(tmp_path):
    chain = _chain(tmp_path)
    output = tmp_path / "real_task_quality_digest.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_real_task_quality_digest.py",
            "--bundle-receipt",
            str(chain[0]),
            "--execution-receipt",
            str(chain[1]),
            "--rubric-evaluation-receipt",
            str(chain[2]),
            "--arm-analysis-receipt",
            str(chain[3]),
            "--claim-gate",
            str(chain[4]),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert REAL_TASK_QUALITY_DIGEST_READY_TOKEN in completed.stdout
    assert output.exists()
