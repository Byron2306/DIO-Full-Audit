import json
import subprocess
import sys
from pathlib import Path

from experiments.metamorphic_adaptation.human_gated_product_capability_dry_run_gauntlet import (
    READY_TOKEN,
    build_human_gated_product_capability_dry_run_gauntlet,
)


def _write_acceptance_marketing_receipt(path: Path) -> Path:
    receipt = {
        "status": "DIO_METAMORPHIC_ADAPTATION_LOCAL_STARTER_CODE_ACCEPTANCE_MARKETING_PROOF_PACK_READY",
        "pack_version": "DIO_METAMORPHIC_ADAPTATION_LOCAL_STARTER_CODE_ACCEPTANCE_MARKETING_PROOF_PACK_V1",
        "marketing_claim_tier": "T17_MARKETING_SAFE_LOCAL_STARTER_CODE_ACCEPTANCE_VERIFICATION",
        "selected_product": "DIO_TRUST_DOSSIER_STUDIO",
        "starter_code_root_path": str(path.parent / "controlled_starter_code" / "dio_trust_dossier_studio"),
        "starter_code_acceptance_verified": True,
        "acceptance_tests_passed": True,
        "pytest_exit_code": 0,
        "files_inspected": 9,
        "source_files_verified": 6,
        "test_files_verified": 1,
        "receipt_schema_files_verified": 1,
        "readmes_verified": 1,
        "starter_code_claim_authorized": True,
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


def test_build_gauntlet_runs_synthetic_dry_run_with_human_gate(tmp_path):
    acceptance = _write_acceptance_marketing_receipt(tmp_path / "local_starter_code_acceptance_marketing_proof_pack_receipt.json")
    receipt = build_human_gated_product_capability_dry_run_gauntlet(acceptance, tmp_path / "out", execute=True)

    assert receipt.status == READY_TOKEN
    assert receipt.allowed_claim_tier == "T18_CANDIDATE_HUMAN_GATED_PRODUCT_CAPABILITY_DRY_RUN_EVIDENCE"
    assert receipt.selected_product == "DIO_TRUST_DOSSIER_STUDIO"
    assert receipt.synthetic_inputs_processed == 3
    assert receipt.draft_dossiers_written == 3
    assert receipt.dry_run_receipts_written == 3
    assert receipt.boundary_checks_passed == 3
    assert receipt.human_gate_checks_written == 3
    assert receipt.product_capability_dry_run_claim_authorized is True
    assert receipt.synthetic_dry_run_evidence is True
    assert receipt.actual_product_execution_authorized is False
    assert receipt.external_use_authorized is False
    assert receipt.publication_authorized is False
    assert receipt.product_market_fit_claim_authorized is False
    assert receipt.commercial_validation_claim_authorized is False

    summary = Path(receipt.dry_run_summary_path)
    assert summary.exists()
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert payload["synthetic_inputs_processed"] == 3
    assert payload["external_use_authorized"] is False

    manifest = Path(receipt.dry_run_manifest_path)
    assert manifest.exists()
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(manifest_payload["artifacts"]) == 9
    assert all(item["synthetic_only"] is True for item in manifest_payload["artifacts"])


def test_build_gauntlet_plan_only_keeps_dry_run_unexecuted(tmp_path):
    acceptance = _write_acceptance_marketing_receipt(tmp_path / "local_starter_code_acceptance_marketing_proof_pack_receipt.json")
    receipt = build_human_gated_product_capability_dry_run_gauntlet(acceptance, tmp_path / "out", execute=False)

    assert receipt.status == READY_TOKEN
    assert receipt.execute_requested is False
    assert receipt.executed is False
    assert receipt.synthetic_dry_run_evidence is False
    assert receipt.product_capability_dry_run_claim_authorized is False
    assert receipt.synthetic_inputs_processed == 0
    assert receipt.actual_product_execution_authorized is False


def test_build_gauntlet_refuses_wrong_acceptance_status(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"status": "NOPE"}) + "\n", encoding="utf-8")

    try:
        build_human_gated_product_capability_dry_run_gauntlet(bad, tmp_path / "out", execute=True)
    except ValueError as exc:
        assert "expected local starter code acceptance marketing proof pack" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_cli_runner_writes_receipt(tmp_path):
    acceptance = _write_acceptance_marketing_receipt(tmp_path / "local_starter_code_acceptance_marketing_proof_pack_receipt.json")
    output = tmp_path / "gauntlet"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_human_gated_product_capability_dry_run_gauntlet.py",
            "--local-starter-code-acceptance-marketing-pack",
            str(acceptance),
            "--output",
            str(output),
            "--execute",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert READY_TOKEN in result.stdout
    written = output / "human_gated_product_capability_dry_run_receipt.json"
    assert written.exists()
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["status"] == READY_TOKEN
    assert payload["synthetic_dry_run_evidence"] is True
    assert payload["actual_product_execution_authorized"] is False
