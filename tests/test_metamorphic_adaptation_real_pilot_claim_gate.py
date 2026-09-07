import json
import subprocess
import sys
from dataclasses import asdict

from experiments.metamorphic_adaptation.real_pilot_claim_gate import (
    REAL_PILOT_CLAIM_GATE_READY_TOKEN,
    REAL_PILOT_CLAIM_GATE_REFUSED_TOKEN,
    REAL_PILOT_CLAIM_GATE_VERSION,
    evaluate_real_pilot_claim_gate,
    write_real_pilot_claim_gate,
)


def _write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def _receipt_bundle(tmp_path, *, compatibility_ready=True, blind_ready=True, outputs=5):
    compatibility = tmp_path / "real_pilot_compatibility_verdict.json"
    blind = tmp_path / "real_pilot_blind_evaluation_receipt.json"

    _write(compatibility, {
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_COMPATIBILITY_VERDICT_READY"
            if compatibility_ready
            else "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_COMPATIBILITY_VERDICT_REFUSED"
        ),
        "real_pilot_native_compatibility_proven": compatibility_ready,
        "ready_for_real_blind_evaluation": compatibility_ready,
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
    })

    _write(blind, {
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_BLIND_EVALUATION_READY"
            if blind_ready
            else "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_BLIND_EVALUATION_REFUSED"
        ),
        "real_pilot_native_compatibility_proven": blind_ready,
        "evaluated_blind_outputs": outputs,
        "real_native_mode": True,
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
        "commercial_or_world_first_claim_authorized": False,
    })

    return compatibility, blind


def test_real_pilot_claim_gate_allows_only_pipeline_mechanics_claim(tmp_path):
    compatibility, blind = _receipt_bundle(tmp_path)

    receipt = evaluate_real_pilot_claim_gate(
        compatibility_verdict_path=compatibility,
        blind_evaluation_receipt_path=blind,
    )

    assert receipt.gate_version == REAL_PILOT_CLAIM_GATE_VERSION
    assert receipt.status == REAL_PILOT_CLAIM_GATE_READY_TOKEN
    assert receipt.real_pilot_native_compatibility_proven is True
    assert receipt.real_blind_evaluation_exercised is True
    assert receipt.evaluated_blind_outputs == 5
    assert receipt.mechanics_proven is True
    assert receipt.real_adaptive_evidence is False
    assert receipt.allowed_claim_tier == "T2_REAL_PILOT_COMPATIBILITY_AND_BLIND_PIPELINE_ONLY"
    assert receipt.adaptive_claim_authorized is False
    assert receipt.commercial_or_world_first_claim_authorized is False
    assert receipt.professional_approval_claim_authorized is False
    assert receipt.publication_authorized is False
    assert receipt.spend_authorized is False
    assert receipt.fulfilment_authorized is False
    assert receipt.authority_expansion_authorized is False


def test_real_pilot_claim_gate_refuses_without_compatibility(tmp_path):
    compatibility, blind = _receipt_bundle(tmp_path, compatibility_ready=False)

    receipt = evaluate_real_pilot_claim_gate(
        compatibility_verdict_path=compatibility,
        blind_evaluation_receipt_path=blind,
    )

    assert receipt.status == REAL_PILOT_CLAIM_GATE_REFUSED_TOKEN
    assert receipt.mechanics_proven is False
    assert receipt.allowed_claim_tier == "T0_NO_CLAIM"
    assert receipt.adaptive_claim_authorized is False


def test_real_pilot_claim_gate_refuses_without_blind_evaluation(tmp_path):
    compatibility, blind = _receipt_bundle(tmp_path, blind_ready=False)

    receipt = evaluate_real_pilot_claim_gate(
        compatibility_verdict_path=compatibility,
        blind_evaluation_receipt_path=blind,
    )

    assert receipt.status == REAL_PILOT_CLAIM_GATE_REFUSED_TOKEN
    assert receipt.real_blind_evaluation_exercised is False
    assert receipt.mechanics_proven is False


def test_real_pilot_claim_gate_refuses_wrong_output_count(tmp_path):
    compatibility, blind = _receipt_bundle(tmp_path, outputs=4)

    receipt = evaluate_real_pilot_claim_gate(
        compatibility_verdict_path=compatibility,
        blind_evaluation_receipt_path=blind,
    )

    assert receipt.status == REAL_PILOT_CLAIM_GATE_REFUSED_TOKEN
    assert receipt.mechanics_proven is False


def test_real_pilot_claim_gate_writes_json_and_hashes_sources(tmp_path):
    compatibility, blind = _receipt_bundle(tmp_path)
    output = tmp_path / "real_pilot_claim_gate.json"

    receipt = write_real_pilot_claim_gate(
        compatibility_verdict_path=compatibility,
        blind_evaluation_receipt_path=blind,
        output_path=output,
    )

    data = json.loads(output.read_text())

    assert data == json.loads(json.dumps(asdict(receipt)))
    assert len(data["compatibility_verdict_sha256"]) == 64
    assert len(data["blind_evaluation_sha256"]) == 64


def test_real_pilot_claim_gate_boundary_blocks_overclaiming(tmp_path):
    compatibility, blind = _receipt_bundle(tmp_path)

    receipt = evaluate_real_pilot_claim_gate(
        compatibility_verdict_path=compatibility,
        blind_evaluation_receipt_path=blind,
    )

    boundary = receipt.boundary.lower()

    assert "limited real native pilot compatibility run" in boundary
    assert "blind evaluation pipeline" in boundary
    assert "does not authorize" in boundary
    assert "adaptive-composition claim" in boundary
    assert "world-first claim" in boundary
    assert "authority expansion" in boundary


def test_real_pilot_claim_gate_cli_runner(tmp_path):
    compatibility, blind = _receipt_bundle(tmp_path)
    output = tmp_path / "real_pilot_claim_gate.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_real_pilot_claim_gate.py",
            "--compatibility-verdict",
            str(compatibility),
            "--blind-evaluation-receipt",
            str(blind),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert REAL_PILOT_CLAIM_GATE_READY_TOKEN in completed.stdout
    assert output.exists()
