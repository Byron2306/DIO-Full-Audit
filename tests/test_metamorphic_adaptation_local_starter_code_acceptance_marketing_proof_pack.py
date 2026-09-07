import json
import subprocess
import sys
from pathlib import Path

from experiments.metamorphic_adaptation.local_starter_code_acceptance_marketing_proof_pack import (
    READY_TOKEN,
    build_local_starter_code_acceptance_marketing_proof_pack,
)


def _write_acceptance_receipt(path: Path) -> Path:
    receipt = {
        "status": "DIO_METAMORPHIC_ADAPTATION_LOCAL_STARTER_CODE_ACCEPTANCE_VERIFICATION_READY",
        "gauntlet_version": "DIO_METAMORPHIC_ADAPTATION_LOCAL_STARTER_CODE_ACCEPTANCE_VERIFICATION_V1",
        "allowed_claim_tier": "T17_CANDIDATE_LOCAL_STARTER_CODE_ACCEPTANCE_VERIFICATION_EVIDENCE",
        "selected_product": "DIO_TRUST_DOSSIER_STUDIO",
        "files_inspected": 9,
        "source_files_verified": 6,
        "test_files_verified": 1,
        "receipt_schema_files_verified": 1,
        "readmes_verified": 1,
        "acceptance_tests_discovered": 2,
        "acceptance_tests_passed": True,
        "pytest_exit_code": 0,
        "starter_code_acceptance_verified": True,
        "starter_code_claim_authorized": True,
        "starter_code_acceptance_verification_claim_authorized": True,
        "local_acceptance_verification_evidence": True,
        "static_acceptance_baseline_mean_score": 0.24,
        "local_acceptance_verification_mean_score": 0.97,
        "local_acceptance_minus_static_effect": 0.73,
        "actual_product_execution_authorized": False,
        "product_capability_execution_authorized": False,
        "external_use_authorized": False,
        "autonomous_development_authorized": False,
        "commercial_validation_claim_authorized": False,
        "product_market_fit_claim_authorized": False,
        "agi_claim_authorized": False,
        "world_first_claim_authorized": False,
        "authority_expansion_authorized": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "fulfilment_authorized": False,
    }
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_build_pack_authorizes_only_safe_acceptance_language(tmp_path):
    acceptance = _write_acceptance_receipt(tmp_path / "local_starter_code_acceptance_verification_receipt.json")
    receipt = build_local_starter_code_acceptance_marketing_proof_pack(acceptance, tmp_path / "out")

    assert receipt.status == READY_TOKEN
    assert receipt.marketing_claim_tier == "T17_MARKETING_SAFE_LOCAL_STARTER_CODE_ACCEPTANCE_VERIFICATION"
    assert receipt.selected_product == "DIO_TRUST_DOSSIER_STUDIO"
    assert receipt.starter_code_acceptance_marketing_language_authorized is True
    assert receipt.starter_code_acceptance_verified is True
    assert receipt.acceptance_tests_passed is True
    assert receipt.pytest_exit_code == 0
    assert receipt.actual_product_execution_authorized is False
    assert receipt.product_capability_execution_authorized is False
    assert receipt.external_use_authorized is False
    assert receipt.autonomous_development_authorized is False
    assert receipt.product_market_fit_claim_authorized is False
    assert receipt.commercial_validation_claim_authorized is False
    assert receipt.allowed_public_claims_count == 7
    assert receipt.forbidden_public_claims_count == 12
    assert Path(receipt.acceptance_marketing_copy_path).exists()
    assert Path(receipt.acceptance_marketing_claims_path).exists()

    copy = Path(receipt.acceptance_marketing_copy_path).read_text(encoding="utf-8")
    assert "local starter-code acceptance verification" in copy
    assert "pytest exit code 0" in copy
    assert "No actual product execution" in copy
    assert "No external use" in copy
    assert "DIO_TRUST_DOSSIER_STUDIO" in copy


def test_pack_refuses_wrong_acceptance_status(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"status": "NOPE"}) + "\n", encoding="utf-8")

    try:
        build_local_starter_code_acceptance_marketing_proof_pack(bad, tmp_path / "out")
    except ValueError as exc:
        assert "expected local starter code acceptance verification" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_cli_runner_writes_receipt(tmp_path):
    acceptance = _write_acceptance_receipt(tmp_path / "local_starter_code_acceptance_verification_receipt.json")
    output = tmp_path / "pack"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_local_starter_code_acceptance_marketing_proof_pack.py",
            "--local-starter-code-acceptance-verification",
            str(acceptance),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert READY_TOKEN in result.stdout
    written = output / "local_starter_code_acceptance_marketing_proof_pack_receipt.json"
    assert written.exists()
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["status"] == READY_TOKEN
    assert payload["external_use_authorized"] is False
