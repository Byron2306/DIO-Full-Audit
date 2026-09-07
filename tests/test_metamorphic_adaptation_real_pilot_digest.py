import json
import subprocess
import sys
from dataclasses import asdict

from experiments.metamorphic_adaptation.real_pilot_digest import (
    REAL_PILOT_DIGEST_READY_TOKEN,
    REAL_PILOT_DIGEST_REFUSED_TOKEN,
    REAL_PILOT_DIGEST_VERSION,
    build_real_pilot_digest,
    write_real_pilot_digest,
)


def _write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def _pilot_chain(tmp_path, *, passed=5, failed=0, timed_out=0, claim_ready=True):
    plan = tmp_path / "real_controlled_transfer_plan.json"
    scaffold = tmp_path / "real_pilot_scaffold_receipt.json"
    execution = tmp_path / "real_pilot_execution_receipt.json"
    compatibility = tmp_path / "real_pilot_compatibility_verdict.json"
    blind = tmp_path / "real_pilot_blind_evaluation_receipt.json"
    claim_gate = tmp_path / "real_pilot_claim_gate.json"

    _write(plan, {
        "status": "DIO_METAMORPHIC_ADAPTATION_REAL_CONTROLLED_TRANSFER_PILOT_PLAN_READY",
        "adaptive_claim_authorized": False,
    })
    _write(scaffold, {
        "status": "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_SCAFFOLD_READY",
        "adaptive_claim_authorized": False,
    })
    _write(execution, {
        "status": "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_EXECUTION_READY",
        "executed": True,
        "real_native_mode": True,
        "pilot_encounters_passed": passed,
        "pilot_encounters_failed": failed,
        "pilot_encounters_timed_out": timed_out,
        "adaptive_claim_authorized": False,
    })
    _write(compatibility, {
        "status": "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_COMPATIBILITY_VERDICT_READY",
        "real_pilot_native_compatibility_proven": passed == 5 and failed == 0 and timed_out == 0,
        "adaptive_claim_authorized": False,
    })
    _write(blind, {
        "status": "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_BLIND_EVALUATION_READY",
        "evaluated_blind_outputs": 5,
        "adaptive_claim_authorized": False,
    })
    _write(claim_gate, {
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_CLAIM_GATE_VERDICT_READY"
            if claim_ready
            else "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_CLAIM_GATE_REFUSED"
        ),
        "mechanics_proven": claim_ready,
        "allowed_claim_tier": (
            "T2_REAL_PILOT_COMPATIBILITY_AND_BLIND_PIPELINE_ONLY"
            if claim_ready
            else "T0_NO_CLAIM"
        ),
        "adaptive_claim_authorized": False,
    })

    return plan, scaffold, execution, compatibility, blind, claim_gate


def test_real_pilot_digest_seals_clean_real_pilot_pipeline(tmp_path):
    plan, scaffold, execution, compatibility, blind, claim_gate = _pilot_chain(tmp_path)

    digest = build_real_pilot_digest(
        real_plan_path=plan,
        scaffold_receipt_path=scaffold,
        execution_receipt_path=execution,
        compatibility_verdict_path=compatibility,
        blind_evaluation_receipt_path=blind,
        claim_gate_path=claim_gate,
    )

    assert digest.digest_version == REAL_PILOT_DIGEST_VERSION
    assert digest.status == REAL_PILOT_DIGEST_READY_TOKEN
    assert digest.real_pilot_end_to_end_proven is True
    assert digest.real_native_pilot_passed is True
    assert digest.ready_to_plan_full_controlled_transfer_run is True
    assert digest.allowed_claim_tier == "T2_REAL_PILOT_COMPATIBILITY_AND_BLIND_PIPELINE_ONLY"
    assert digest.adaptive_claim_authorized is False
    assert digest.commercial_or_world_first_claim_authorized is False


def test_real_pilot_digest_refuses_when_native_pilot_has_failure(tmp_path):
    plan, scaffold, execution, compatibility, blind, claim_gate = _pilot_chain(
        tmp_path,
        passed=4,
        failed=1,
    )

    digest = build_real_pilot_digest(
        real_plan_path=plan,
        scaffold_receipt_path=scaffold,
        execution_receipt_path=execution,
        compatibility_verdict_path=compatibility,
        blind_evaluation_receipt_path=blind,
        claim_gate_path=claim_gate,
    )

    assert digest.status == REAL_PILOT_DIGEST_REFUSED_TOKEN
    assert digest.real_pilot_end_to_end_proven is False
    assert digest.ready_to_plan_full_controlled_transfer_run is False
    assert digest.allowed_claim_tier == "T0_NO_CLAIM"


def test_real_pilot_digest_refuses_when_claim_gate_not_ready(tmp_path):
    plan, scaffold, execution, compatibility, blind, claim_gate = _pilot_chain(
        tmp_path,
        claim_ready=False,
    )

    digest = build_real_pilot_digest(
        real_plan_path=plan,
        scaffold_receipt_path=scaffold,
        execution_receipt_path=execution,
        compatibility_verdict_path=compatibility,
        blind_evaluation_receipt_path=blind,
        claim_gate_path=claim_gate,
    )

    assert digest.status == REAL_PILOT_DIGEST_REFUSED_TOKEN
    assert digest.ready_to_plan_full_controlled_transfer_run is False
    assert digest.adaptive_claim_authorized is False


def test_real_pilot_digest_writes_json_and_hashes_sources(tmp_path):
    plan, scaffold, execution, compatibility, blind, claim_gate = _pilot_chain(tmp_path)
    output = tmp_path / "real_pilot_digest.json"

    digest = write_real_pilot_digest(
        real_plan_path=plan,
        scaffold_receipt_path=scaffold,
        execution_receipt_path=execution,
        compatibility_verdict_path=compatibility,
        blind_evaluation_receipt_path=blind,
        claim_gate_path=claim_gate,
        output_path=output,
    )

    data = json.loads(output.read_text())

    assert data == json.loads(json.dumps(asdict(digest)))
    assert len(data["real_plan_sha256"]) == 64
    assert len(data["scaffold_receipt_sha256"]) == 64
    assert len(data["execution_receipt_sha256"]) == 64
    assert len(data["compatibility_verdict_sha256"]) == 64
    assert len(data["blind_evaluation_sha256"]) == 64
    assert len(data["claim_gate_sha256"]) == 64


def test_real_pilot_digest_boundary_blocks_overclaiming(tmp_path):
    plan, scaffold, execution, compatibility, blind, claim_gate = _pilot_chain(tmp_path)

    digest = build_real_pilot_digest(
        real_plan_path=plan,
        scaffold_receipt_path=scaffold,
        execution_receipt_path=execution,
        compatibility_verdict_path=compatibility,
        blind_evaluation_receipt_path=blind,
        claim_gate_path=claim_gate,
    )

    boundary = digest.boundary.lower()

    assert "limited real native pilot" in boundary
    assert "permits planning a full" in boundary
    assert "does not authorize" in boundary
    assert "adaptive-composition claim" in boundary
    assert "world-first claim" in boundary
    assert "authority expansion" in boundary


def test_real_pilot_digest_cli_runner(tmp_path):
    plan, scaffold, execution, compatibility, blind, claim_gate = _pilot_chain(tmp_path)
    output = tmp_path / "real_pilot_digest.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_real_pilot_digest.py",
            "--real-plan",
            str(plan),
            "--scaffold-receipt",
            str(scaffold),
            "--execution-receipt",
            str(execution),
            "--compatibility-verdict",
            str(compatibility),
            "--blind-evaluation-receipt",
            str(blind),
            "--claim-gate",
            str(claim_gate),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert REAL_PILOT_DIGEST_READY_TOKEN in completed.stdout
    assert output.exists()
