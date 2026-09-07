from __future__ import annotations

import json
from pathlib import Path

from experiments.metamorphic_adaptation.t23_html_proof_surface_dossier_linking_gate import (
    T23_HTML_PROOF_SURFACE_DOSSIER_LINKING_READY_TOKEN,
    link_t23_dossiers_into_html_proof_surface,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _valid_t22_receipt() -> dict:
    return {
        "status": "DIO_METAMORPHIC_ADAPTATION_T22_HTML_PROOF_SURFACE_GENERATION_READY",
        "allowed_claim_tier": "T22_INTERNAL_HTML_PROOF_SURFACE_GENERATED",
        "selected_product": "DIO_TRUST_DOSSIER_STUDIO",
        "source_bound": True,
        "html_proof_surface_generated": True,
        "local_html_preview_authorized": True,
        "human_decision_applied": "APPROVE_LOCAL_RC",
        "human_approval_state_after_decision": "APPROVED_LOCAL_RC_ONLY",
        "evidence_chain": ["T16", "T17", "T18", "T19", "T20", "T21", "T22"],
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
        "authority_expansion_authorized": False,
    }


def _seed_t22_surface(surface_dir: Path) -> None:
    surface_dir.mkdir(parents=True, exist_ok=True)
    (surface_dir / "index.html").write_text(
        """<!doctype html>
<html lang=\"en\"><body><section class=\"card\">
<h1>DIO_TRUST_DOSSIER_STUDIO</h1>
<p>External deployment authorized: false</p>
</section></body></html>
"""
    )
    _write_json(surface_dir / "proof_manifest.json", {"surface_type": "internal_local_static_html_proof"})
    (surface_dir / "README.md").write_text("# T22\nExternal deployment authorized: false\n")


def _seed_t18_dossiers(t18_dir: Path) -> None:
    dossiers = t18_dir / "human_gated_product_capability_dry_run" / "dio_trust_dossier_studio" / "draft_dossiers"
    dossiers.mkdir(parents=True, exist_ok=True)
    for idx in range(1, 4):
        (dossiers / f"synthetic-trust-dossier-00{idx}.md").write_text(
            f"# Synthetic Trust Dossier 00{idx}\n\nSelected product: DIO_TRUST_DOSSIER_STUDIO\n"
        )
    receipts = t18_dir / "human_gated_product_capability_dry_run" / "dio_trust_dossier_studio" / "receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    (receipts / "synthetic-trust-dossier-001_receipt.json").write_text("{}\n")


def test_t23_links_t18_dossiers_into_existing_t22_html_surface(tmp_path: Path) -> None:
    t22_receipt_path = tmp_path / "receipts" / "t22.json"
    t18_dir = tmp_path / "t18"
    surface_dir = tmp_path / "html-proof"
    receipt_output_path = tmp_path / "out" / "t23.json"

    _write_json(t22_receipt_path, _valid_t22_receipt())
    _seed_t22_surface(surface_dir)
    _seed_t18_dossiers(t18_dir)

    receipt = link_t23_dossiers_into_html_proof_surface(
        t22_receipt_path=t22_receipt_path,
        t18_dry_run_dir=t18_dir,
        proof_surface_dir=surface_dir,
        receipt_output_path=receipt_output_path,
    )

    assert receipt.status == T23_HTML_PROOF_SURFACE_DOSSIER_LINKING_READY_TOKEN
    assert receipt.allowed_claim_tier == "T23_INTERNAL_HTML_PROOF_SURFACE_DOSSIERS_LINKED"
    assert receipt.selected_product == "DIO_TRUST_DOSSIER_STUDIO"
    assert receipt.source_bound is True
    assert receipt.t18_dossier_source_bound is True
    assert receipt.t22_surface_source_bound is True
    assert receipt.dossiers_discovered == 3
    assert receipt.dossiers_linked == 3
    assert receipt.dossier_links_written is True
    assert receipt.local_html_preview_authorized is True
    assert receipt.external_deployment_authorized is False
    assert receipt.actual_product_execution_authorized is False
    assert receipt.commercial_validation_claim_authorized is False
    assert receipt.authority_expansion_authorized is False

    dossier_dir = surface_dir / "dossiers"
    assert len(list(dossier_dir.glob("*.md"))) == 3
    assert (surface_dir / "dossier_index.json").exists()
    html = (surface_dir / "index.html").read_text()
    assert "Draft dossiers" in html
    assert "synthetic-trust-dossier-001.md" in html
    assert "External deployment authorized: false" in html
    assert receipt_output_path.exists()


def test_t23_refuses_without_t22_ready_receipt(tmp_path: Path) -> None:
    t22_receipt_path = tmp_path / "receipts" / "t22.json"
    t18_dir = tmp_path / "t18"
    surface_dir = tmp_path / "html-proof"
    receipt_output_path = tmp_path / "out" / "t23.json"

    bad_receipt = _valid_t22_receipt()
    bad_receipt["status"] = "NOPE"
    _write_json(t22_receipt_path, bad_receipt)
    _seed_t22_surface(surface_dir)
    _seed_t18_dossiers(t18_dir)

    receipt = link_t23_dossiers_into_html_proof_surface(
        t22_receipt_path=t22_receipt_path,
        t18_dry_run_dir=t18_dir,
        proof_surface_dir=surface_dir,
        receipt_output_path=receipt_output_path,
    )

    assert receipt.status == "DIO_METAMORPHIC_ADAPTATION_T23_HTML_PROOF_SURFACE_DOSSIER_LINKING_REFUSED"
    assert receipt.dossiers_linked == 0
    assert receipt.local_html_preview_authorized is False
