import json
import subprocess
import sys
from pathlib import Path

from experiments.metamorphic_adaptation.controlled_starter_code_generation_gauntlet import (
    READY_TOKEN,
    build_controlled_starter_code_generation_gauntlet,
)


def _write_readiness_marketing_receipt(path: Path) -> Path:
    receipt = {
        "status": "DIO_METAMORPHIC_ADAPTATION_CAPABILITY_EXECUTION_READINESS_MARKETING_PROOF_PACK_READY",
        "pack_version": "DIO_METAMORPHIC_ADAPTATION_CAPABILITY_EXECUTION_READINESS_MARKETING_PROOF_PACK_V1",
        "marketing_claim_tier": "T15_MARKETING_SAFE_CAPABILITY_EXECUTION_READINESS_MAP",
        "selected_product": "DIO_TRUST_DOSSIER_STUDIO",
        "capabilities_mapped": 12,
        "can_execute_now_count": 4,
        "could_execute_with_local_dependency_count": 3,
        "could_execute_with_config_count": 2,
        "human_gate_required_count": 2,
        "authority_refused_count": 1,
        "could_execute_total_count": 11,
        "could_execute_claim_authorized": True,
        "actual_execution_authorized": False,
        "starter_code_claim_authorized": False,
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


def test_build_gauntlet_writes_local_starter_code_with_locks(tmp_path):
    readiness = _write_readiness_marketing_receipt(tmp_path / "capability_execution_readiness_marketing_proof_pack_receipt.json")
    receipt = build_controlled_starter_code_generation_gauntlet(readiness, tmp_path / "out", execute=True)

    assert receipt.status == READY_TOKEN
    assert receipt.allowed_claim_tier == "T16_CANDIDATE_CONTROLLED_LOCAL_STARTER_CODE_GENERATION_EVIDENCE"
    assert receipt.selected_product == "DIO_TRUST_DOSSIER_STUDIO"
    assert receipt.local_starter_code_generation_claim_authorized is True
    assert receipt.starter_code_claim_authorized is True
    assert receipt.starter_code_written is True
    assert receipt.product_capability_execution_authorized is False
    assert receipt.autonomous_development_authorized is False
    assert receipt.publication_authorized is False
    assert receipt.product_market_fit_claim_authorized is False
    assert receipt.source_files_written == 6
    assert receipt.test_files_written == 1
    assert receipt.receipt_schema_files_written == 1
    assert receipt.starter_code_file_manifest_written is True
    assert receipt.controlled_starter_code_quality_threshold_met is True
    assert receipt.starter_code_generation_effect_threshold_met is True

    manifest = Path(receipt.starter_code_file_manifest_path)
    assert manifest.exists()
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(manifest_payload["files_written"]) == 9
    assert any(item["relative_path"].endswith("dossier_renderer.py") for item in manifest_payload["files_written"])

    starter_root = Path(receipt.starter_code_root_path)
    assert (starter_root / "dio_trust_dossier_studio" / "claim_boundary_checker.py").exists()
    assert (starter_root / "tests" / "test_acceptance_contract.py").exists()
    source = (starter_root / "dio_trust_dossier_studio" / "claim_boundary_checker.py").read_text(encoding="utf-8")
    assert "FORBIDDEN_CLAIM_TERMS" in source
    assert "product-market fit" in source


def test_build_gauntlet_plan_only_keeps_code_unwritten(tmp_path):
    readiness = _write_readiness_marketing_receipt(tmp_path / "capability_execution_readiness_marketing_proof_pack_receipt.json")
    receipt = build_controlled_starter_code_generation_gauntlet(readiness, tmp_path / "out", execute=False)

    assert receipt.status == READY_TOKEN
    assert receipt.execute_requested is False
    assert receipt.executed is False
    assert receipt.starter_code_written is False
    assert receipt.starter_code_claim_authorized is False
    assert receipt.source_files_written == 0
    assert receipt.test_files_written == 0


def test_build_gauntlet_refuses_wrong_readiness_status(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"status": "NOPE"}) + "\n", encoding="utf-8")

    try:
        build_controlled_starter_code_generation_gauntlet(bad, tmp_path / "out", execute=True)
    except ValueError as exc:
        assert "expected capability execution readiness marketing proof pack" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_cli_runner_writes_receipt(tmp_path):
    readiness = _write_readiness_marketing_receipt(tmp_path / "capability_execution_readiness_marketing_proof_pack_receipt.json")
    output = tmp_path / "gauntlet"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_controlled_starter_code_generation_gauntlet.py",
            "--capability-execution-readiness-marketing-pack",
            str(readiness),
            "--output",
            str(output),
            "--execute",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert READY_TOKEN in result.stdout
    written = output / "controlled_starter_code_generation_receipt.json"
    assert written.exists()
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["status"] == READY_TOKEN
    assert payload["starter_code_written"] is True
    assert payload["product_capability_execution_authorized"] is False
