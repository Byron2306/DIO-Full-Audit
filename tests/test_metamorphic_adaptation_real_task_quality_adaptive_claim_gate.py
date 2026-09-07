import json
import subprocess
import sys
from dataclasses import asdict

from experiments.metamorphic_adaptation.real_task_quality_adaptive_claim_gate import (
    REAL_TASK_QUALITY_ADAPTIVE_CLAIM_GATE_READY_TOKEN,
    REAL_TASK_QUALITY_ADAPTIVE_CLAIM_GATE_REFUSED_TOKEN,
    REAL_TASK_QUALITY_ADAPTIVE_CLAIM_GATE_VERSION,
    evaluate_real_task_quality_adaptive_claim_gate,
    write_real_task_quality_adaptive_claim_gate,
)


def _write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def _analysis(path, *, ready=True, effect=0.0, positive=False, adaptive_evidence=False):
    _write(path, {
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_FACTORIAL_ANALYSIS_READY"
            if ready
            else "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_FACTORIAL_ANALYSIS_REFUSED"
        ),
        "real_quality_scores_analyzed": ready,
        "scores_loaded": 25 if ready else 0,
        "labels_loaded": 25 if ready else 0,
        "arms_analyzed": 5 if ready else 0,
        "baseline_arm": "A_STATELESS_RESET",
        "baseline_mean_score": 1.0 - effect if positive else 1.0,
        "full_arm": "E_FULL_SEMANTIC_MARKET_BEAST",
        "full_mean_score": 1.0,
        "full_minus_baseline_effect": effect,
        "positive_full_stack_quality_effect_observed": positive,
        "real_adaptive_evidence": adaptive_evidence,
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
    })


def test_real_task_quality_adaptive_claim_gate_refuses_tied_quality_scores(tmp_path):
    analysis = tmp_path / "real_task_quality_factorial_analysis_receipt.json"
    _analysis(analysis, effect=0.0, positive=False, adaptive_evidence=False)

    receipt = evaluate_real_task_quality_adaptive_claim_gate(factorial_analysis_receipt_path=analysis)

    assert receipt.gate_version == REAL_TASK_QUALITY_ADAPTIVE_CLAIM_GATE_VERSION
    assert receipt.status == REAL_TASK_QUALITY_ADAPTIVE_CLAIM_GATE_READY_TOKEN
    assert receipt.real_quality_scores_analyzed is True
    assert receipt.positive_full_stack_quality_effect_observed is False
    assert receipt.full_minus_baseline_effect == 0.0
    assert receipt.allowed_claim_tier == "T4_REAL_TASK_QUALITY_ANALYZED_NO_ADAPTIVE_CLAIM"
    assert receipt.real_adaptive_evidence is False
    assert receipt.adaptive_claim_authorized is False
    assert receipt.commercial_or_world_first_claim_authorized is False


def test_real_task_quality_adaptive_claim_gate_still_requires_separate_authority_for_positive_effect(tmp_path):
    analysis = tmp_path / "real_task_quality_factorial_analysis_receipt.json"
    _analysis(analysis, effect=0.25, positive=True, adaptive_evidence=True)

    receipt = evaluate_real_task_quality_adaptive_claim_gate(factorial_analysis_receipt_path=analysis)

    assert receipt.status == REAL_TASK_QUALITY_ADAPTIVE_CLAIM_GATE_READY_TOKEN
    assert receipt.positive_full_stack_quality_effect_observed is True
    assert receipt.full_minus_baseline_effect == 0.25
    assert receipt.real_adaptive_evidence is True
    assert receipt.allowed_claim_tier == "T5_REAL_TASK_QUALITY_DIFFERENTIAL_OBSERVED_REQUIRES_EXTERNAL_REPLICATION"
    assert receipt.adaptive_claim_authorized is False
    assert receipt.commercial_or_world_first_claim_authorized is False
    assert receipt.publication_authorized is False


def test_real_task_quality_adaptive_claim_gate_refuses_unready_factorial_analysis(tmp_path):
    analysis = tmp_path / "real_task_quality_factorial_analysis_receipt.json"
    _analysis(analysis, ready=False)

    receipt = evaluate_real_task_quality_adaptive_claim_gate(factorial_analysis_receipt_path=analysis)

    assert receipt.status == REAL_TASK_QUALITY_ADAPTIVE_CLAIM_GATE_REFUSED_TOKEN
    assert receipt.real_quality_scores_analyzed is False
    assert receipt.allowed_claim_tier == "T0_NO_CLAIM"
    assert receipt.adaptive_claim_authorized is False


def test_real_task_quality_adaptive_claim_gate_writes_receipt_and_hashes_source(tmp_path):
    analysis = tmp_path / "real_task_quality_factorial_analysis_receipt.json"
    output = tmp_path / "real_task_quality_adaptive_claim_gate.json"
    _analysis(analysis)

    receipt = write_real_task_quality_adaptive_claim_gate(
        factorial_analysis_receipt_path=analysis,
        output_path=output,
    )
    data = json.loads(output.read_text())

    assert data == json.loads(json.dumps(asdict(receipt)))
    assert len(data["factorial_analysis_sha256"]) == 64


def test_real_task_quality_adaptive_claim_gate_boundary_blocks_overclaiming(tmp_path):
    analysis = tmp_path / "real_task_quality_factorial_analysis_receipt.json"
    _analysis(analysis, effect=0.25, positive=True, adaptive_evidence=True)

    receipt = evaluate_real_task_quality_adaptive_claim_gate(factorial_analysis_receipt_path=analysis)
    boundary = receipt.boundary.lower()

    assert "real task-quality factorial" in boundary
    assert "does not authorize" in boundary
    assert "external replication" in boundary
    assert "commercial validation" in boundary
    assert "world-first" in boundary
    assert "authority expansion" in boundary


def test_real_task_quality_adaptive_claim_gate_cli_runner(tmp_path):
    analysis = tmp_path / "real_task_quality_factorial_analysis_receipt.json"
    output = tmp_path / "real_task_quality_adaptive_claim_gate.json"
    _analysis(analysis)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_real_task_quality_adaptive_claim_gate.py",
            "--factorial-analysis-receipt",
            str(analysis),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert REAL_TASK_QUALITY_ADAPTIVE_CLAIM_GATE_READY_TOKEN in completed.stdout
    assert output.exists()
