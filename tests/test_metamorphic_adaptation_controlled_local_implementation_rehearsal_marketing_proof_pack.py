import json
import subprocess
import sys
from pathlib import Path

from experiments.metamorphic_adaptation.controlled_local_implementation_rehearsal_marketing_proof_pack import (
    READY_TOKEN,
    build_controlled_implementation_rehearsal_marketing_proof_pack,
)


def _write_rehearsal_receipt(path: Path) -> Path:
    receipt = {
        "status": "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_LOCAL_IMPLEMENTATION_REHEARSAL_READY",
        "gauntlet_version": "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_LOCAL_IMPLEMENTATION_REHEARSAL_V1",
        "selected_product": "DIO_TRUST_DOSSIER_STUDIO",
        "modules_rehearsed": 5,
        "test_skeletons_rehearsed": 5,
        "receipt_schemas_rehearsed": 5,
        "acceptance_gate_bindings_rehearsed": 20,
        "controlled_rehearsal_mean_score": 1.0,
        "static_implementation_baseline_mean_score": 0.21,
        "controlled_rehearsal_minus_static_effect": 0.79,
        "implementation_rehearsal_evidence": True,
        "local_implementation_rehearsal_claim_authorized": True,
        "starter_code_claim_authorized": False,
        "starter_code_written": False,
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


def test_build_pack_authorizes_only_safe_rehearsal_language(tmp_path):
    rehearsal = _write_rehearsal_receipt(tmp_path / "controlled_local_implementation_rehearsal_receipt.json")
    receipt = build_controlled_implementation_rehearsal_marketing_proof_pack(rehearsal, tmp_path / "out")

    assert receipt.status == READY_TOKEN
    assert receipt.marketing_claim_tier == "T14_MARKETING_SAFE_CONTROLLED_LOCAL_IMPLEMENTATION_REHEARSAL"
    assert receipt.selected_product == "DIO_TRUST_DOSSIER_STUDIO"
    assert receipt.implementation_rehearsal_marketing_language_authorized is True
    assert receipt.local_implementation_rehearsal_claim_authorized is True
    assert receipt.starter_code_claim_authorized is False
    assert receipt.autonomous_development_authorized is False
    assert receipt.product_market_fit_claim_authorized is False
    assert receipt.commercial_validation_claim_authorized is False
    assert receipt.allowed_public_claims_count == 7
    assert receipt.forbidden_public_claims_count == 12
    assert Path(receipt.implementation_rehearsal_copy_path).exists()
    assert Path(receipt.implementation_rehearsal_claims_path).exists()

    copy = Path(receipt.implementation_rehearsal_copy_path).read_text(encoding="utf-8")
    assert "controlled local implementation rehearsal" in copy
    assert "not starter code completion" in copy
    assert "No autonomous development" in copy
    assert "DIO_TRUST_DOSSIER_STUDIO" in copy


def test_pack_refuses_wrong_rehearsal_status(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"status": "NOPE"}) + "\n", encoding="utf-8")

    try:
        build_controlled_implementation_rehearsal_marketing_proof_pack(bad, tmp_path / "out")
    except ValueError as exc:
        assert "expected controlled local implementation rehearsal" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_cli_runner_writes_receipt(tmp_path):
    rehearsal = _write_rehearsal_receipt(tmp_path / "controlled_local_implementation_rehearsal_receipt.json")
    output = tmp_path / "pack"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_controlled_local_implementation_rehearsal_marketing_proof_pack.py",
            "--controlled-local-implementation-rehearsal",
            str(rehearsal),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert READY_TOKEN in result.stdout
    written = output / "controlled_local_implementation_rehearsal_marketing_proof_pack_receipt.json"
    assert written.exists()
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["status"] == READY_TOKEN
    assert payload["starter_code_claim_authorized"] is False
