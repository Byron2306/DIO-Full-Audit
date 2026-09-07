import json
import subprocess
import sys
from pathlib import Path

from experiments.metamorphic_adaptation.human_gated_product_capability_dry_run_marketing_proof_pack import (
    READY_TOKEN,
    build_human_gated_product_capability_dry_run_marketing_proof_pack,
)


def _write_dry_run_receipt(path: Path) -> Path:
    receipt = {
        "status": "DIO_METAMORPHIC_ADAPTATION_HUMAN_GATED_PRODUCT_CAPABILITY_DRY_RUN_READY",
        "gauntlet_version": "DIO_METAMORPHIC_ADAPTATION_HUMAN_GATED_PRODUCT_CAPABILITY_DRY_RUN_V1",
        "allowed_claim_tier": "T18_CANDIDATE_HUMAN_GATED_PRODUCT_CAPABILITY_DRY_RUN_EVIDENCE",
        "selected_product": "DIO_TRUST_DOSSIER_STUDIO",
        "synthetic_inputs_processed": 3,
        "draft_dossiers_written": 3,
        "dry_run_receipts_written": 3,
        "boundary_checks_passed": 3,
        "human_gate_checks_written": 3,
        "controlled_dry_run_mean_score": 0.98,
        "static_dry_run_baseline_mean_score": 0.25,
        "controlled_dry_run_minus_static_effect": 0.73,
        "synthetic_dry_run_evidence": True,
        "product_capability_dry_run_claim_authorized": True,
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


def test_build_pack_authorizes_only_safe_dry_run_language(tmp_path):
    dry_run = _write_dry_run_receipt(tmp_path / "human_gated_product_capability_dry_run_receipt.json")
    receipt = build_human_gated_product_capability_dry_run_marketing_proof_pack(dry_run, tmp_path / "out")

    assert receipt.status == READY_TOKEN
    assert receipt.marketing_claim_tier == "T18_MARKETING_SAFE_HUMAN_GATED_PRODUCT_CAPABILITY_DRY_RUN"
    assert receipt.selected_product == "DIO_TRUST_DOSSIER_STUDIO"
    assert receipt.product_capability_dry_run_marketing_language_authorized is True
    assert receipt.product_capability_dry_run_claim_authorized is True
    assert receipt.synthetic_dry_run_evidence is True
    assert receipt.actual_product_execution_authorized is False
    assert receipt.external_use_authorized is False
    assert receipt.product_capability_execution_authorized is False
    assert receipt.product_market_fit_claim_authorized is False
    assert receipt.commercial_validation_claim_authorized is False
    assert receipt.allowed_public_claims_count == 7
    assert receipt.forbidden_public_claims_count == 12
    assert Path(receipt.dry_run_marketing_claims_path).exists()
    assert Path(receipt.dry_run_marketing_copy_path).exists()

    copy = Path(receipt.dry_run_marketing_copy_path).read_text(encoding="utf-8")
    assert "human-gated product capability dry run" in copy
    assert "synthetic internal inputs" in copy
    assert "No actual product execution" in copy
    assert "No external use" in copy
    assert "DIO_TRUST_DOSSIER_STUDIO" in copy


def test_pack_refuses_wrong_dry_run_status(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"status": "NOPE"}) + "\n", encoding="utf-8")

    try:
        build_human_gated_product_capability_dry_run_marketing_proof_pack(bad, tmp_path / "out")
    except ValueError as exc:
        assert "expected human gated product capability dry run" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_cli_runner_writes_receipt(tmp_path):
    dry_run = _write_dry_run_receipt(tmp_path / "human_gated_product_capability_dry_run_receipt.json")
    output = tmp_path / "pack"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_human_gated_product_capability_dry_run_marketing_proof_pack.py",
            "--human-gated-product-capability-dry-run",
            str(dry_run),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert READY_TOKEN in result.stdout
    written = output / "human_gated_product_capability_dry_run_marketing_proof_pack_receipt.json"
    assert written.exists()
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["status"] == READY_TOKEN
    assert payload["actual_product_execution_authorized"] is False
    assert payload["external_use_authorized"] is False
