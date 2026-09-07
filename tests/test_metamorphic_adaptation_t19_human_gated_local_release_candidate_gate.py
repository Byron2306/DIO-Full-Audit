from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from experiments.metamorphic_adaptation.t19_human_gated_local_release_candidate_gate import (
    T18_MARKETING_PROOF_PACK_READY_TOKEN,
    T19_LOCAL_RELEASE_CANDIDATE_READY_TOKEN,
    T19_LOCAL_RELEASE_CANDIDATE_REFUSED_TOKEN,
    evaluate_t19_human_gated_local_release_candidate,
)


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def _valid_t18_pack() -> dict:
    return {
        "actual_product_execution_authorized": False,
        "agi_claim_authorized": False,
        "authority_expansion_authorized": False,
        "autonomous_action_claim_authorized": False,
        "autonomous_development_authorized": False,
        "boundary_checks_passed": 3,
        "commercial_validation_claim_authorized": False,
        "controlled_dry_run_mean_score": 0.98,
        "controlled_dry_run_minus_static_effect": 0.73,
        "draft_dossiers_written": 3,
        "dry_run_receipts_written": 3,
        "external_use_authorized": False,
        "fulfilment_authorized": False,
        "human_gate_checks_written": 3,
        "human_gated_product_capability_dry_run_status": "DIO_METAMORPHIC_ADAPTATION_HUMAN_GATED_PRODUCT_CAPABILITY_DRY_RUN_READY",
        "marketing_claim_tier": "T18_MARKETING_SAFE_HUMAN_GATED_PRODUCT_CAPABILITY_DRY_RUN",
        "product_capability_dry_run_claim_authorized": True,
        "product_capability_dry_run_marketing_language_authorized": True,
        "product_capability_execution_authorized": False,
        "product_market_fit_claim_authorized": False,
        "professional_approval_claim_authorized": False,
        "publication_authorized": False,
        "selected_product": "DIO_TRUST_DOSSIER_STUDIO",
        "spend_authorized": False,
        "static_dry_run_baseline_mean_score": 0.25,
        "status": T18_MARKETING_PROOF_PACK_READY_TOKEN,
        "synthetic_dry_run_evidence": True,
        "synthetic_inputs_processed": 3,
        "world_first_claim_authorized": False,
    }


def test_t19_ready_for_source_bound_human_gated_local_release_candidate(tmp_path: Path) -> None:
    t18_path = _write_json(tmp_path / "t18.json", _valid_t18_pack())
    output_path = tmp_path / "t19" / "receipt.json"

    receipt = evaluate_t19_human_gated_local_release_candidate(
        t18_marketing_proof_pack_path=t18_path,
        output_path=output_path,
    )
    payload = asdict(receipt)

    assert payload["status"] == T19_LOCAL_RELEASE_CANDIDATE_READY_TOKEN
    assert payload["selected_product"] == "DIO_TRUST_DOSSIER_STUDIO"
    assert payload["source_bound"] is True
    assert payload["t18_marketing_proof_pack_status"] == T18_MARKETING_PROOF_PACK_READY_TOKEN
    assert payload["release_candidate_packaging_authorized"] is True
    assert payload["local_release_candidate_claim_authorized"] is True
    assert payload["human_approval_required"] is True
    assert payload["human_approval_state"] == "NEEDS_YOU"
    assert payload["actual_product_execution_authorized"] is False
    assert payload["external_deployment_authorized"] is False
    assert payload["commercial_validation_claim_authorized"] is False
    assert payload["authority_expansion_authorized"] is False
    assert payload["controlled_dry_run_minus_static_effect"] == 0.73
    assert output_path.exists()


def test_t19_refuses_when_t18_boundary_promotes_external_use(tmp_path: Path) -> None:
    invalid_pack = _valid_t18_pack()
    invalid_pack["external_use_authorized"] = True
    t18_path = _write_json(tmp_path / "t18.json", invalid_pack)

    receipt = evaluate_t19_human_gated_local_release_candidate(
        t18_marketing_proof_pack_path=t18_path,
        output_path=tmp_path / "receipt.json",
    )
    payload = asdict(receipt)

    assert payload["status"] == T19_LOCAL_RELEASE_CANDIDATE_REFUSED_TOKEN
    assert payload["release_candidate_packaging_authorized"] is False
    assert payload["local_release_candidate_claim_authorized"] is False
    assert payload["external_deployment_authorized"] is False
    assert payload["human_approval_required"] is True


def test_t19_refuses_when_human_gates_are_missing(tmp_path: Path) -> None:
    invalid_pack = _valid_t18_pack()
    invalid_pack["human_gate_checks_written"] = 0
    t18_path = _write_json(tmp_path / "t18.json", invalid_pack)

    receipt = evaluate_t19_human_gated_local_release_candidate(
        t18_marketing_proof_pack_path=t18_path,
        output_path=tmp_path / "receipt.json",
    )
    payload = asdict(receipt)

    assert payload["status"] == T19_LOCAL_RELEASE_CANDIDATE_REFUSED_TOKEN
    assert payload["release_candidate_packaging_authorized"] is False
    assert payload["human_gates_preserved"] is False
    assert payload["actual_product_execution_authorized"] is False
