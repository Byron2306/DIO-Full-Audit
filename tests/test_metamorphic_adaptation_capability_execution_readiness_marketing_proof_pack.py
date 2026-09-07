import json
import subprocess
import sys
from pathlib import Path

from experiments.metamorphic_adaptation.capability_execution_readiness_marketing_proof_pack import (
    READY_TOKEN,
    build_capability_execution_readiness_marketing_proof_pack,
)


def _write_readiness_receipt(path: Path) -> Path:
    receipt = {
        "status": "DIO_METAMORPHIC_ADAPTATION_CAPABILITY_EXECUTION_READINESS_MAP_READY",
        "gauntlet_version": "DIO_METAMORPHIC_ADAPTATION_CAPABILITY_EXECUTION_READINESS_MAP_V1",
        "selected_product": "DIO_TRUST_DOSSIER_STUDIO",
        "capabilities_mapped": 12,
        "can_execute_now_count": 4,
        "could_execute_with_local_dependency_count": 3,
        "could_execute_with_config_count": 2,
        "human_gate_required_count": 2,
        "authority_refused_count": 1,
        "not_implemented_yet_count": 0,
        "could_execute_total_count": 11,
        "capability_execution_readiness_evidence": True,
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


def test_build_pack_authorizes_only_could_execute_language(tmp_path):
    readiness = _write_readiness_receipt(tmp_path / "capability_execution_readiness_map_receipt.json")
    receipt = build_capability_execution_readiness_marketing_proof_pack(readiness, tmp_path / "out")

    assert receipt.status == READY_TOKEN
    assert receipt.marketing_claim_tier == "T15_MARKETING_SAFE_CAPABILITY_EXECUTION_READINESS_MAP"
    assert receipt.selected_product == "DIO_TRUST_DOSSIER_STUDIO"
    assert receipt.capability_execution_readiness_marketing_language_authorized is True
    assert receipt.could_execute_claim_authorized is True
    assert receipt.actual_execution_authorized is False
    assert receipt.starter_code_claim_authorized is False
    assert receipt.autonomous_development_authorized is False
    assert receipt.product_market_fit_claim_authorized is False
    assert receipt.commercial_validation_claim_authorized is False
    assert receipt.allowed_public_claims_count == 7
    assert receipt.forbidden_public_claims_count == 12
    assert Path(receipt.capability_readiness_copy_path).exists()
    assert Path(receipt.capability_readiness_claims_path).exists()

    copy = Path(receipt.capability_readiness_copy_path).read_text(encoding="utf-8")
    assert "could execute" in copy
    assert "actual execution" in copy
    assert "Could-execute does not mean authorized-to-execute" in copy
    assert "No actual execution" in copy
    assert "DIO_TRUST_DOSSIER_STUDIO" in copy


def test_pack_refuses_wrong_readiness_status(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"status": "NOPE"}) + "\n", encoding="utf-8")

    try:
        build_capability_execution_readiness_marketing_proof_pack(bad, tmp_path / "out")
    except ValueError as exc:
        assert "expected capability execution readiness map" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_cli_runner_writes_receipt(tmp_path):
    readiness = _write_readiness_receipt(tmp_path / "capability_execution_readiness_map_receipt.json")
    output = tmp_path / "pack"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_capability_execution_readiness_marketing_proof_pack.py",
            "--capability-execution-readiness-map",
            str(readiness),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert READY_TOKEN in result.stdout
    written = output / "capability_execution_readiness_marketing_proof_pack_receipt.json"
    assert written.exists()
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["status"] == READY_TOKEN
    assert payload["actual_execution_authorized"] is False
