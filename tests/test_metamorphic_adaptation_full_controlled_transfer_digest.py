import json
import subprocess
import sys
from dataclasses import asdict

from experiments.metamorphic_adaptation.full_controlled_transfer_digest import (
    FULL_TRANSFER_DIGEST_READY_TOKEN,
    FULL_TRANSFER_DIGEST_REFUSED_TOKEN,
    FULL_TRANSFER_DIGEST_VERSION,
    build_full_controlled_transfer_digest,
    write_full_controlled_transfer_digest,
)


def _write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def _chain(tmp_path, *, passed=25, failed=0, timed_out=0, claim_ready=True):
    plan = tmp_path / "full_controlled_transfer_plan.json"
    scaffold = tmp_path / "full_controlled_transfer_scaffold_receipt.json"
    execution = tmp_path / "full_controlled_transfer_execution_receipt.json"
    compatibility = tmp_path / "full_controlled_transfer_compatibility_verdict.json"
    blind = tmp_path / "full_controlled_transfer_blind_evaluation_receipt.json"
    factorial = tmp_path / "full_controlled_transfer_factorial_analysis_receipt.json"
    claim_gate = tmp_path / "full_controlled_transfer_claim_gate.json"

    _write(plan, {
        "status": "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_PLAN_READY",
        "adaptive_claim_authorized": False,
    })
    _write(scaffold, {
        "status": "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_SCAFFOLD_READY",
        "adaptive_claim_authorized": False,
    })
    _write(execution, {
        "status": "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_EXECUTION_READY",
        "executed": True,
        "real_native_mode": True,
        "full_run_encounters_passed": passed,
        "full_run_encounters_failed": failed,
        "full_run_encounters_timed_out": timed_out,
        "adaptive_claim_authorized": False,
    })
    _write(compatibility, {
        "status": "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_COMPATIBILITY_VERDICT_READY",
        "full_run_native_compatibility_proven": passed == 25 and failed == 0 and timed_out == 0,
        "adaptive_claim_authorized": False,
    })
    _write(blind, {
        "status": "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_BLIND_EVALUATION_READY",
        "evaluated_blind_outputs": 25,
        "adaptive_claim_authorized": False,
    })
    _write(factorial, {
        "status": "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_FACTORIAL_ANALYSIS_READY",
        "arms_analyzed": 5,
        "full_minus_baseline_effect": 0.0,
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
    })
    _write(claim_gate, {
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_CLAIM_GATE_VERDICT_READY"
            if claim_ready
            else "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_CLAIM_GATE_REFUSED"
        ),
        "mechanics_proven": claim_ready,
        "allowed_claim_tier": (
            "T3_FULL_NATIVE_COMPATIBILITY_BLIND_FACTORIAL_PIPELINE_ONLY"
            if claim_ready
            else "T0_NO_CLAIM"
        ),
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
    })

    return plan, scaffold, execution, compatibility, blind, factorial, claim_gate


def test_full_controlled_transfer_digest_seals_clean_pipeline(tmp_path):
    chain = _chain(tmp_path)

    digest = build_full_controlled_transfer_digest(
        plan_path=chain[0],
        scaffold_receipt_path=chain[1],
        execution_receipt_path=chain[2],
        compatibility_verdict_path=chain[3],
        blind_evaluation_receipt_path=chain[4],
        factorial_analysis_receipt_path=chain[5],
        claim_gate_path=chain[6],
    )

    assert digest.digest_version == FULL_TRANSFER_DIGEST_VERSION
    assert digest.status == FULL_TRANSFER_DIGEST_READY_TOKEN
    assert digest.full_transfer_end_to_end_proven is True
    assert digest.full_native_run_passed is True
    assert digest.full_run_encounters_passed == 25
    assert digest.evaluated_blind_outputs == 25
    assert digest.arms_analyzed == 5
    assert digest.allowed_claim_tier == "T3_FULL_NATIVE_COMPATIBILITY_BLIND_FACTORIAL_PIPELINE_ONLY"
    assert digest.real_adaptive_evidence is False
    assert digest.adaptive_claim_authorized is False
    assert digest.commercial_or_world_first_claim_authorized is False


def test_full_controlled_transfer_digest_refuses_native_failure(tmp_path):
    chain = _chain(tmp_path, passed=24, failed=1)

    digest = build_full_controlled_transfer_digest(
        plan_path=chain[0],
        scaffold_receipt_path=chain[1],
        execution_receipt_path=chain[2],
        compatibility_verdict_path=chain[3],
        blind_evaluation_receipt_path=chain[4],
        factorial_analysis_receipt_path=chain[5],
        claim_gate_path=chain[6],
    )

    assert digest.status == FULL_TRANSFER_DIGEST_REFUSED_TOKEN
    assert digest.full_transfer_end_to_end_proven is False
    assert digest.allowed_claim_tier == "T0_NO_CLAIM"


def test_full_controlled_transfer_digest_refuses_bad_claim_gate(tmp_path):
    chain = _chain(tmp_path, claim_ready=False)

    digest = build_full_controlled_transfer_digest(
        plan_path=chain[0],
        scaffold_receipt_path=chain[1],
        execution_receipt_path=chain[2],
        compatibility_verdict_path=chain[3],
        blind_evaluation_receipt_path=chain[4],
        factorial_analysis_receipt_path=chain[5],
        claim_gate_path=chain[6],
    )

    assert digest.status == FULL_TRANSFER_DIGEST_REFUSED_TOKEN
    assert digest.full_transfer_end_to_end_proven is False
    assert digest.adaptive_claim_authorized is False


def test_full_controlled_transfer_digest_writes_json_and_hashes_sources(tmp_path):
    chain = _chain(tmp_path)
    output = tmp_path / "full_controlled_transfer_digest.json"

    digest = write_full_controlled_transfer_digest(
        plan_path=chain[0],
        scaffold_receipt_path=chain[1],
        execution_receipt_path=chain[2],
        compatibility_verdict_path=chain[3],
        blind_evaluation_receipt_path=chain[4],
        factorial_analysis_receipt_path=chain[5],
        claim_gate_path=chain[6],
        output_path=output,
    )

    data = json.loads(output.read_text())

    assert data == json.loads(json.dumps(asdict(digest)))
    assert len(data["plan_sha256"]) == 64
    assert len(data["scaffold_sha256"]) == 64
    assert len(data["execution_sha256"]) == 64
    assert len(data["compatibility_sha256"]) == 64
    assert len(data["blind_evaluation_sha256"]) == 64
    assert len(data["factorial_analysis_sha256"]) == 64
    assert len(data["claim_gate_sha256"]) == 64


def test_full_controlled_transfer_digest_boundary_blocks_overclaiming(tmp_path):
    chain = _chain(tmp_path)

    digest = build_full_controlled_transfer_digest(
        plan_path=chain[0],
        scaffold_receipt_path=chain[1],
        execution_receipt_path=chain[2],
        compatibility_verdict_path=chain[3],
        blind_evaluation_receipt_path=chain[4],
        factorial_analysis_receipt_path=chain[5],
        claim_gate_path=chain[6],
    )

    boundary = digest.boundary.lower()

    assert "full 25-encounter real native" in boundary
    assert "blind evaluation" in boundary
    assert "factorial analysis" in boundary
    assert "does not authorize" in boundary
    assert "world-first claim" in boundary
    assert "authority expansion" in boundary


def test_full_controlled_transfer_digest_cli_runner(tmp_path):
    chain = _chain(tmp_path)
    output = tmp_path / "full_controlled_transfer_digest.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_full_controlled_transfer_digest.py",
            "--plan",
            str(chain[0]),
            "--scaffold-receipt",
            str(chain[1]),
            "--execution-receipt",
            str(chain[2]),
            "--compatibility-verdict",
            str(chain[3]),
            "--blind-evaluation-receipt",
            str(chain[4]),
            "--factorial-analysis-receipt",
            str(chain[5]),
            "--claim-gate",
            str(chain[6]),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert FULL_TRANSFER_DIGEST_READY_TOKEN in completed.stdout
    assert output.exists()
