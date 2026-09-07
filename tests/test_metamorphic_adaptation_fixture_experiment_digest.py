import json
import subprocess
import sys
from dataclasses import asdict

from experiments.metamorphic_adaptation.fixture_experiment_digest import (
    FIXTURE_DIGEST_READY_TOKEN,
    FIXTURE_DIGEST_REFUSED_TOKEN,
    FIXTURE_DIGEST_VERSION,
    build_fixture_experiment_digest,
    write_fixture_experiment_digest,
)


def _write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def _fixture_chain(tmp_path, *, claim_gate_ready=True):
    manifest = tmp_path / "controlled_transfer_manifest.json"
    run = tmp_path / "controlled_transfer_run_receipt.json"
    execution = tmp_path / "controlled_transfer_execution_receipt.json"
    blind = tmp_path / "blind_evaluation_receipt.json"
    factorial = tmp_path / "factorial_analysis_receipt.json"
    claim_gate = tmp_path / "transfer_claim_gate.json"

    _write(manifest, {
        "status": "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_TRANSFER_MANIFEST_READY",
        "transfer_run_authorized": True,
        "adaptive_claim_authorized": False,
    })
    _write(run, {
        "status": "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_TRANSFER_RUN_SCAFFOLD_READY",
        "adaptive_claim_authorized": False,
    })
    _write(execution, {
        "status": "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_TRANSFER_EXECUTION_FIXTURE_READY",
        "adaptive_claim_authorized": False,
    })
    _write(blind, {
        "status": "DIO_METAMORPHIC_ADAPTATION_BLIND_EVALUATION_FIXTURE_READY",
        "adaptive_claim_authorized": False,
    })
    _write(factorial, {
        "status": "DIO_METAMORPHIC_ADAPTATION_FACTORIAL_ANALYSIS_FIXTURE_READY",
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
    })
    _write(claim_gate, {
        "status": (
            "DIO_METAMORPHIC_ADAPTATION_TRANSFER_CLAIM_GATE_FIXTURE_VERDICT_READY"
            if claim_gate_ready
            else "DIO_METAMORPHIC_ADAPTATION_TRANSFER_CLAIM_GATE_REFUSED"
        ),
        "mechanics_proven": claim_gate_ready,
        "allowed_claim_tier": (
            "T1_FIXTURE_MECHANICS_PROVEN_NO_ADAPTIVE_CLAIM"
            if claim_gate_ready
            else "T0_NO_CLAIM"
        ),
        "adaptive_claim_authorized": False,
    })

    return manifest, run, execution, blind, factorial, claim_gate


def test_fixture_experiment_digest_marks_end_to_end_mechanics_ready(tmp_path):
    manifest, run, execution, blind, factorial, claim_gate = _fixture_chain(tmp_path)

    digest = build_fixture_experiment_digest(
        controlled_transfer_manifest_path=manifest,
        controlled_transfer_run_receipt_path=run,
        controlled_transfer_execution_receipt_path=execution,
        blind_evaluation_receipt_path=blind,
        factorial_analysis_receipt_path=factorial,
        transfer_claim_gate_path=claim_gate,
    )

    assert digest.digest_version == FIXTURE_DIGEST_VERSION
    assert digest.status == FIXTURE_DIGEST_READY_TOKEN
    assert digest.end_to_end_fixture_mechanics_proven is True
    assert digest.ready_for_real_controlled_transfer_execution is True
    assert digest.allowed_claim_tier == "T1_FIXTURE_MECHANICS_PROVEN_NO_ADAPTIVE_CLAIM"
    assert digest.adaptive_claim_authorized is False
    assert digest.commercial_or_world_first_claim_authorized is False
    assert digest.professional_approval_claim_authorized is False


def test_fixture_experiment_digest_refuses_when_claim_gate_not_ready(tmp_path):
    manifest, run, execution, blind, factorial, claim_gate = _fixture_chain(
        tmp_path,
        claim_gate_ready=False,
    )

    digest = build_fixture_experiment_digest(
        controlled_transfer_manifest_path=manifest,
        controlled_transfer_run_receipt_path=run,
        controlled_transfer_execution_receipt_path=execution,
        blind_evaluation_receipt_path=blind,
        factorial_analysis_receipt_path=factorial,
        transfer_claim_gate_path=claim_gate,
    )

    assert digest.status == FIXTURE_DIGEST_REFUSED_TOKEN
    assert digest.end_to_end_fixture_mechanics_proven is False
    assert digest.ready_for_real_controlled_transfer_execution is False
    assert digest.allowed_claim_tier == "T0_NO_CLAIM"
    assert digest.adaptive_claim_authorized is False


def test_fixture_experiment_digest_writes_json_and_hashes_sources(tmp_path):
    manifest, run, execution, blind, factorial, claim_gate = _fixture_chain(tmp_path)
    output = tmp_path / "fixture_experiment_digest.json"

    digest = write_fixture_experiment_digest(
        controlled_transfer_manifest_path=manifest,
        controlled_transfer_run_receipt_path=run,
        controlled_transfer_execution_receipt_path=execution,
        blind_evaluation_receipt_path=blind,
        factorial_analysis_receipt_path=factorial,
        transfer_claim_gate_path=claim_gate,
        output_path=output,
    )

    data = json.loads(output.read_text())

    assert data == json.loads(json.dumps(asdict(digest)))
    assert len(data["controlled_transfer_manifest_sha256"]) == 64
    assert len(data["controlled_transfer_run_receipt_sha256"]) == 64
    assert len(data["controlled_transfer_execution_receipt_sha256"]) == 64
    assert len(data["blind_evaluation_receipt_sha256"]) == 64
    assert len(data["factorial_analysis_receipt_sha256"]) == 64
    assert len(data["transfer_claim_gate_sha256"]) == 64


def test_fixture_experiment_digest_boundary_blocks_overclaiming(tmp_path):
    manifest, run, execution, blind, factorial, claim_gate = _fixture_chain(tmp_path)

    digest = build_fixture_experiment_digest(
        controlled_transfer_manifest_path=manifest,
        controlled_transfer_run_receipt_path=run,
        controlled_transfer_execution_receipt_path=execution,
        blind_evaluation_receipt_path=blind,
        factorial_analysis_receipt_path=factorial,
        transfer_claim_gate_path=claim_gate,
    )

    boundary = digest.boundary.lower()

    assert "fixture-mode end-to-end" in boundary
    assert "preparation for real controlled transfer execution" in boundary
    assert "does not authorize" in boundary
    assert "adaptive-composition claim" in boundary
    assert "world-first claim" in boundary
    assert "authority expansion" in boundary


def test_fixture_experiment_digest_cli_runner(tmp_path):
    manifest, run, execution, blind, factorial, claim_gate = _fixture_chain(tmp_path)
    output = tmp_path / "fixture_experiment_digest.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_fixture_experiment_digest.py",
            "--manifest",
            str(manifest),
            "--run-receipt",
            str(run),
            "--execution-receipt",
            str(execution),
            "--blind-evaluation-receipt",
            str(blind),
            "--factorial-analysis-receipt",
            str(factorial),
            "--transfer-claim-gate",
            str(claim_gate),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert FIXTURE_DIGEST_READY_TOKEN in completed.stdout
    assert output.exists()
