import json
import subprocess
import sys
from dataclasses import asdict

from experiments.metamorphic_adaptation.full_controlled_transfer_claim_gate import (
    FULL_TRANSFER_CLAIM_GATE_READY_TOKEN,
    FULL_TRANSFER_CLAIM_GATE_REFUSED_TOKEN,
    FULL_TRANSFER_CLAIM_GATE_VERSION,
    evaluate_full_transfer_claim_gate,
    write_full_transfer_claim_gate,
)


def _write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def _bundle(tmp_path, *, compatibility_ready=True, blind_ready=True, factorial_ready=True, outputs=25, arms=5):
    compatibility = tmp_path / "full_controlled_transfer_compatibility_verdict.json"
    blind = tmp_path / "full_controlled_transfer_blind_evaluation_receipt.json"
    factorial = tmp_path / "full_controlled_transfer_factorial_analysis_receipt.json"

    _write(compatibility, {
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_COMPATIBILITY_VERDICT_READY"
            if compatibility_ready
            else "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_COMPATIBILITY_VERDICT_REFUSED"
        ),
        "full_run_native_compatibility_proven": compatibility_ready,
        "ready_for_full_blind_evaluation": compatibility_ready,
        "full_run_encounters_passed": 25 if compatibility_ready else 0,
        "adaptive_claim_authorized": False,
    })

    _write(blind, {
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_BLIND_EVALUATION_READY"
            if blind_ready
            else "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_BLIND_EVALUATION_REFUSED"
        ),
        "evaluated_blind_outputs": outputs if blind_ready else 0,
        "full_run_native_compatibility_proven": blind_ready,
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
    })

    _write(factorial, {
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_FACTORIAL_ANALYSIS_READY"
            if factorial_ready
            else "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_FACTORIAL_ANALYSIS_REFUSED"
        ),
        "scores_loaded": outputs if factorial_ready else 0,
        "labels_loaded": outputs if factorial_ready else 0,
        "arms_analyzed": arms if factorial_ready else 0,
        "full_minus_baseline_effect": 0.0,
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
    })

    return compatibility, blind, factorial


def test_full_transfer_claim_gate_allows_only_full_pipeline_mechanics_claim(tmp_path):
    compatibility, blind, factorial = _bundle(tmp_path)

    receipt = evaluate_full_transfer_claim_gate(
        compatibility_verdict_path=compatibility,
        blind_evaluation_receipt_path=blind,
        factorial_analysis_receipt_path=factorial,
    )

    assert receipt.gate_version == FULL_TRANSFER_CLAIM_GATE_VERSION
    assert receipt.status == FULL_TRANSFER_CLAIM_GATE_READY_TOKEN
    assert receipt.full_run_native_compatibility_proven is True
    assert receipt.full_blind_evaluation_exercised is True
    assert receipt.full_factorial_analysis_exercised is True
    assert receipt.full_run_encounters_passed == 25
    assert receipt.evaluated_blind_outputs == 25
    assert receipt.arms_analyzed == 5
    assert receipt.mechanics_proven is True
    assert receipt.real_adaptive_evidence is False
    assert receipt.allowed_claim_tier == "T3_FULL_NATIVE_COMPATIBILITY_BLIND_FACTORIAL_PIPELINE_ONLY"
    assert receipt.adaptive_claim_authorized is False
    assert receipt.commercial_or_world_first_claim_authorized is False


def test_full_transfer_claim_gate_refuses_without_compatibility(tmp_path):
    compatibility, blind, factorial = _bundle(tmp_path, compatibility_ready=False)

    receipt = evaluate_full_transfer_claim_gate(
        compatibility_verdict_path=compatibility,
        blind_evaluation_receipt_path=blind,
        factorial_analysis_receipt_path=factorial,
    )

    assert receipt.status == FULL_TRANSFER_CLAIM_GATE_REFUSED_TOKEN
    assert receipt.mechanics_proven is False
    assert receipt.allowed_claim_tier == "T0_NO_CLAIM"


def test_full_transfer_claim_gate_refuses_without_blind_evaluation(tmp_path):
    compatibility, blind, factorial = _bundle(tmp_path, blind_ready=False)

    receipt = evaluate_full_transfer_claim_gate(
        compatibility_verdict_path=compatibility,
        blind_evaluation_receipt_path=blind,
        factorial_analysis_receipt_path=factorial,
    )

    assert receipt.status == FULL_TRANSFER_CLAIM_GATE_REFUSED_TOKEN
    assert receipt.full_blind_evaluation_exercised is False
    assert receipt.mechanics_proven is False


def test_full_transfer_claim_gate_refuses_without_factorial_analysis(tmp_path):
    compatibility, blind, factorial = _bundle(tmp_path, factorial_ready=False)

    receipt = evaluate_full_transfer_claim_gate(
        compatibility_verdict_path=compatibility,
        blind_evaluation_receipt_path=blind,
        factorial_analysis_receipt_path=factorial,
    )

    assert receipt.status == FULL_TRANSFER_CLAIM_GATE_REFUSED_TOKEN
    assert receipt.full_factorial_analysis_exercised is False
    assert receipt.mechanics_proven is False


def test_full_transfer_claim_gate_refuses_wrong_arm_count(tmp_path):
    compatibility, blind, factorial = _bundle(tmp_path, arms=4)

    receipt = evaluate_full_transfer_claim_gate(
        compatibility_verdict_path=compatibility,
        blind_evaluation_receipt_path=blind,
        factorial_analysis_receipt_path=factorial,
    )

    assert receipt.status == FULL_TRANSFER_CLAIM_GATE_REFUSED_TOKEN
    assert receipt.mechanics_proven is False


def test_full_transfer_claim_gate_writes_json_and_hashes_sources(tmp_path):
    compatibility, blind, factorial = _bundle(tmp_path)
    output = tmp_path / "full_controlled_transfer_claim_gate.json"

    receipt = write_full_transfer_claim_gate(
        compatibility_verdict_path=compatibility,
        blind_evaluation_receipt_path=blind,
        factorial_analysis_receipt_path=factorial,
        output_path=output,
    )

    data = json.loads(output.read_text())

    assert data == json.loads(json.dumps(asdict(receipt)))
    assert len(data["compatibility_verdict_sha256"]) == 64
    assert len(data["blind_evaluation_sha256"]) == 64
    assert len(data["factorial_analysis_sha256"]) == 64


def test_full_transfer_claim_gate_boundary_blocks_overclaiming(tmp_path):
    compatibility, blind, factorial = _bundle(tmp_path)

    receipt = evaluate_full_transfer_claim_gate(
        compatibility_verdict_path=compatibility,
        blind_evaluation_receipt_path=blind,
        factorial_analysis_receipt_path=factorial,
    )

    boundary = receipt.boundary.lower()

    assert "full 25-encounter native compatibility" in boundary
    assert "blind evaluation" in boundary
    assert "factorial analysis" in boundary
    assert "does not authorize" in boundary
    assert "world-first claim" in boundary
    assert "authority expansion" in boundary


def test_full_transfer_claim_gate_cli_runner(tmp_path):
    compatibility, blind, factorial = _bundle(tmp_path)
    output = tmp_path / "full_controlled_transfer_claim_gate.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_full_controlled_transfer_claim_gate.py",
            "--compatibility-verdict",
            str(compatibility),
            "--blind-evaluation-receipt",
            str(blind),
            "--factorial-analysis-receipt",
            str(factorial),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert FULL_TRANSFER_CLAIM_GATE_READY_TOKEN in completed.stdout
    assert output.exists()
