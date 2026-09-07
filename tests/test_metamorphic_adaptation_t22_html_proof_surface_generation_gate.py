from __future__ import annotations

import json
from pathlib import Path

from experiments.metamorphic_adaptation.t22_html_proof_surface_generation_gate import (
    T22_HTML_PROOF_SURFACE_GENERATION_READY_TOKEN,
    T22_HTML_PROOF_SURFACE_GENERATION_REFUSED_TOKEN,
    build_t22_html_proof_surface,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _valid_t21_receipt() -> dict:
    return {
        "status": "DIO_METAMORPHIC_ADAPTATION_T21_HUMAN_DECISION_APPLICATION_READY",
        "allowed_claim_tier": "T21_HUMAN_APPROVED_LOCAL_RC_ONLY",
        "selected_product": "DIO_TRUST_DOSSIER_STUDIO",
        "human_decision_applied": "APPROVE_LOCAL_RC",
        "valid_human_decision": True,
        "human_approval_state_after_decision": "APPROVED_LOCAL_RC_ONLY",
        "local_rc_approved": True,
        "release_approved": True,
        "local_release_candidate_claim_authorized": True,
        "release_candidate_packaging_authorized": True,
        "synthetic_dry_run_evidence": True,
        "synthetic_inputs_processed": 3,
        "draft_dossiers_written": 3,
        "dry_run_receipts_written": 3,
        "human_gate_checks_written": 3,
        "human_gates_preserved": True,
        "actual_product_execution_authorized": False,
        "product_capability_execution_authorized": False,
        "external_use_authorized": False,
        "external_deployment_authorized": False,
        "commercial_validation_claim_authorized": False,
        "product_market_fit_claim_authorized": False,
        "professional_approval_claim_authorized": False,
        "publication_authorized": False,
        "spend_authorized": False,
        "fulfilment_authorized": False,
        "agi_claim_authorized": False,
        "world_first_claim_authorized": False,
        "authority_expansion_authorized": False,
    }


def test_t22_generates_source_bound_html_proof_surface(tmp_path: Path) -> None:
    t21_path = tmp_path / "t21" / "t21_human_decision_application_receipt.json"
    output_dir = tmp_path / "html-proof"
    receipt_path = tmp_path / "receipt" / "t22_html_proof_surface_generation_receipt.json"
    _write_json(t21_path, _valid_t21_receipt())

    receipt = build_t22_html_proof_surface(
        t21_receipt_path=t21_path,
        output_dir=output_dir,
        receipt_output_path=receipt_path,
    )

    assert receipt.status == T22_HTML_PROOF_SURFACE_GENERATION_READY_TOKEN
    assert receipt.allowed_claim_tier == "T22_INTERNAL_HTML_PROOF_SURFACE_GENERATED"
    assert receipt.selected_product == "DIO_TRUST_DOSSIER_STUDIO"
    assert receipt.source_bound is True
    assert receipt.html_proof_surface_generated is True
    assert receipt.local_html_preview_authorized is True
    assert receipt.actual_product_execution_authorized is False
    assert receipt.external_deployment_authorized is False
    assert receipt.commercial_validation_claim_authorized is False
    assert receipt.authority_expansion_authorized is False
    assert receipt.index_html_path.endswith("index.html")
    assert receipt.proof_manifest_path.endswith("proof_manifest.json")
    assert receipt_path.exists()

    index_html = output_dir / "index.html"
    proof_manifest = output_dir / "proof_manifest.json"
    readme = output_dir / "README.md"

    assert index_html.exists()
    assert proof_manifest.exists()
    assert readme.exists()

    html = index_html.read_text()
    assert "DIO_TRUST_DOSSIER_STUDIO" in html
    assert "T16 → T17 → T18 → T19 → T20 → T21 → T22" in html
    assert "Internal local HTML proof surface" in html
    assert "External deployment authorized: false" in html
    assert "Commercial validation authorized: false" in html
    assert "Authority expansion authorized: false" in html

    manifest = json.loads(proof_manifest.read_text())
    assert manifest["status"] == "DIO_METAMORPHIC_ADAPTATION_T22_HTML_PROOF_SURFACE_GENERATION_READY"
    assert manifest["selected_product"] == "DIO_TRUST_DOSSIER_STUDIO"
    assert manifest["evidence_chain"] == ["T16", "T17", "T18", "T19", "T20", "T21", "T22"]
    assert manifest["external_deployment_authorized"] is False
    assert manifest["commercial_validation_claim_authorized"] is False


def test_t22_refuses_if_t21_did_not_apply_approve_local_rc(tmp_path: Path) -> None:
    t21_path = tmp_path / "t21" / "t21_human_decision_application_receipt.json"
    output_dir = tmp_path / "html-proof"
    receipt_path = tmp_path / "receipt" / "t22_html_proof_surface_generation_receipt.json"
    payload = _valid_t21_receipt()
    payload["allowed_claim_tier"] = "T21_CHANGES_REQUESTED"
    payload["human_decision_applied"] = "REQUEST_CHANGES"
    payload["local_rc_approved"] = False
    payload["release_approved"] = False
    payload["human_approval_state_after_decision"] = "CHANGES_REQUESTED"
    _write_json(t21_path, payload)

    receipt = build_t22_html_proof_surface(
        t21_receipt_path=t21_path,
        output_dir=output_dir,
        receipt_output_path=receipt_path,
    )

    assert receipt.status == T22_HTML_PROOF_SURFACE_GENERATION_REFUSED_TOKEN
    assert receipt.html_proof_surface_generated is False
    assert receipt.local_html_preview_authorized is False
    assert receipt.actual_product_execution_authorized is False
    assert receipt.external_deployment_authorized is False
    assert not (output_dir / "index.html").exists()
    assert receipt_path.exists()
