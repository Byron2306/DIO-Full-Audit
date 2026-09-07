import json
import subprocess
import sys
from dataclasses import asdict

from experiments.metamorphic_adaptation.transfer_claim_gate import (
    TRANSFER_CLAIM_GATE_READY_TOKEN,
    TRANSFER_CLAIM_GATE_REFUSED_TOKEN,
    TRANSFER_CLAIM_GATE_VERSION,
    evaluate_transfer_claim_gate,
    write_transfer_claim_gate,
)


def _write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def _fixture_receipts(tmp_path, *, executed=25, blind=25, factorial=25, real_adaptive=False):
    execution = tmp_path / "controlled_transfer_execution_receipt.json"
    blind_eval = tmp_path / "blind_evaluation_receipt.json"
    factorial_analysis = tmp_path / "factorial_analysis_receipt.json"

    _write(execution, {
        "status": "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_TRANSFER_EXECUTION_FIXTURE_READY",
        "fixture_mode": True,
        "encounters_executed": executed,
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
    })

    _write(blind_eval, {
        "status": "DIO_METAMORPHIC_ADAPTATION_BLIND_EVALUATION_FIXTURE_READY",
        "fixture_mode": True,
        "evaluated_blind_outputs": blind,
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
    })

    _write(factorial_analysis, {
        "status": "DIO_METAMORPHIC_ADAPTATION_FACTORIAL_ANALYSIS_FIXTURE_READY",
        "fixture_mode": True,
        "blind_scores_loaded": factorial,
        "real_adaptive_evidence": real_adaptive,
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
    })

    return execution, blind_eval, factorial_analysis


def test_transfer_claim_gate_allows_only_fixture_mechanics_claim(tmp_path):
    execution, blind_eval, factorial_analysis = _fixture_receipts(tmp_path)

    receipt = evaluate_transfer_claim_gate(
        execution_receipt_path=execution,
        blind_evaluation_receipt_path=blind_eval,
        factorial_analysis_receipt_path=factorial_analysis,
    )

    assert receipt.gate_version == TRANSFER_CLAIM_GATE_VERSION
    assert receipt.status == TRANSFER_CLAIM_GATE_READY_TOKEN
    assert receipt.fixture_mode is True
    assert receipt.mechanics_proven is True
    assert receipt.real_adaptive_evidence is False
    assert receipt.allowed_claim_tier == "T1_FIXTURE_MECHANICS_PROVEN_NO_ADAPTIVE_CLAIM"
    assert receipt.adaptive_claim_authorized is False
    assert receipt.commercial_or_world_first_claim_authorized is False
    assert receipt.professional_approval_claim_authorized is False
    assert receipt.publication_authorized is False
    assert receipt.spend_authorized is False
    assert receipt.fulfilment_authorized is False
    assert receipt.authority_expansion_authorized is False


def test_transfer_claim_gate_refuses_when_counts_do_not_match(tmp_path):
    execution, blind_eval, factorial_analysis = _fixture_receipts(
        tmp_path,
        executed=25,
        blind=24,
        factorial=24,
    )

    receipt = evaluate_transfer_claim_gate(
        execution_receipt_path=execution,
        blind_evaluation_receipt_path=blind_eval,
        factorial_analysis_receipt_path=factorial_analysis,
    )

    assert receipt.status == TRANSFER_CLAIM_GATE_REFUSED_TOKEN
    assert receipt.mechanics_proven is False
    assert receipt.allowed_claim_tier == "T0_NO_CLAIM"
    assert receipt.adaptive_claim_authorized is False


def test_transfer_claim_gate_refuses_if_real_adaptive_evidence_is_marked_in_fixture(tmp_path):
    execution, blind_eval, factorial_analysis = _fixture_receipts(
        tmp_path,
        real_adaptive=True,
    )

    receipt = evaluate_transfer_claim_gate(
        execution_receipt_path=execution,
        blind_evaluation_receipt_path=blind_eval,
        factorial_analysis_receipt_path=factorial_analysis,
    )

    assert receipt.status == TRANSFER_CLAIM_GATE_REFUSED_TOKEN
    assert receipt.mechanics_proven is False
    assert receipt.real_adaptive_evidence is False
    assert receipt.adaptive_claim_authorized is False


def test_transfer_claim_gate_writes_receipt_and_hashes_sources(tmp_path):
    execution, blind_eval, factorial_analysis = _fixture_receipts(tmp_path)
    output = tmp_path / "transfer_claim_gate.json"

    receipt = write_transfer_claim_gate(
        execution_receipt_path=execution,
        blind_evaluation_receipt_path=blind_eval,
        factorial_analysis_receipt_path=factorial_analysis,
        output_path=output,
    )

    data = json.loads(output.read_text())

    assert data == json.loads(json.dumps(asdict(receipt)))
    assert len(data["execution_receipt_sha256"]) == 64
    assert len(data["blind_evaluation_sha256"]) == 64
    assert len(data["factorial_analysis_sha256"]) == 64


def test_transfer_claim_gate_boundary_blocks_overclaiming(tmp_path):
    execution, blind_eval, factorial_analysis = _fixture_receipts(tmp_path)

    receipt = evaluate_transfer_claim_gate(
        execution_receipt_path=execution,
        blind_evaluation_receipt_path=blind_eval,
        factorial_analysis_receipt_path=factorial_analysis,
    )

    boundary = receipt.boundary.lower()

    assert "fixture-mode controlled-transfer mechanics" in boundary
    assert "does not authorize" in boundary
    assert "adaptive-composition claim" in boundary
    assert "commercial validation claim" in boundary
    assert "world-first claim" in boundary
    assert "authority expansion" in boundary


def test_transfer_claim_gate_cli_runner(tmp_path):
    execution, blind_eval, factorial_analysis = _fixture_receipts(tmp_path)
    output = tmp_path / "transfer_claim_gate.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_transfer_claim_gate.py",
            "--execution-receipt",
            str(execution),
            "--blind-evaluation-receipt",
            str(blind_eval),
            "--factorial-analysis-receipt",
            str(factorial_analysis),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert TRANSFER_CLAIM_GATE_READY_TOKEN in completed.stdout
    assert output.exists()
