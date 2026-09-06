from __future__ import annotations

import json

from products.canon_extension_summary import persist_verified_summary


def _verified_receipt() -> dict:
    extensions = {}
    for i in range(15):
        slug = f"ext-{i}"
        extensions[slug] = {
            "canon_id": f"CANON-EXT-{i}",
            "slug": slug,
            "status": "PRODUCT_GRADE_VERIFIED",
            "proof_status": "CANON_EXTENSION_PROOF_VERIFIED",
            "critical_blockers": [],
            "customers_will_pay": "UNPROVED",
            "verified_payment": "UNPROVED",
        }
    return {
        "schema": "dio.product_grade.canon_extension_gauntlet_receipt.v1",
        "acceptance_token": "DIO_CANON_EXTENSION_PRODUCT_GRADE_VERIFIED",
        "proof_acceptance_token": "DIO_CANON_EXTENSION_PROOF_VERIFIED",
        "extension_count": 15,
        "product_grade_verified_count": 15,
        "canon_extension_proof_verified_count": 15,
        "all_product_grade_verified": True,
        "all_canon_extension_proof_verified": True,
        "extensions": extensions,
        "commercial_validation": "UNPROVED",
        "authority_created": False,
        "external_effects": False,
    }


def test_verified_summary_persists_for_control_deck(tmp_path):
    target = tmp_path / "CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json"
    receipt = _verified_receipt()

    assert persist_verified_summary(receipt, target) is True
    assert json.loads(target.read_text(encoding="utf-8")) == receipt


def test_summary_refuses_commercial_or_authority_overclaim(tmp_path):
    target = tmp_path / "CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json"
    receipt = _verified_receipt()
    receipt["commercial_validation"] = "PROVED"
    assert persist_verified_summary(receipt, target) is False
    assert not target.exists()

    receipt = _verified_receipt()
    receipt["authority_created"] = True
    assert persist_verified_summary(receipt, target) is False
    assert not target.exists()
