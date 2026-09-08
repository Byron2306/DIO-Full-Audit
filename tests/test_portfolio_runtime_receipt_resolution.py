from __future__ import annotations

import json
from pathlib import Path

import portfolio_runtime


def _verified_receipt() -> dict:
    extensions = {}
    for index in range(15):
        slug = f"extension-{index + 1}"
        extensions[slug] = {
            "canon_id": f"CANON-EXT-{index + 1}",
            "name": f"Extension {index + 1}",
            "slug": slug,
            "proof_status": "CANON_EXTENSION_PROOF_VERIFIED",
            "status": "PRODUCT_GRADE_VERIFIED",
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


def test_runtime_prefers_proven_aggregate_receipt(monkeypatch, tmp_path: Path):
    aggregate = tmp_path / "state/product_grade/canon_extension_aggregate/CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json"
    legacy = tmp_path / "state/product_grade/canon_extensions/CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json"
    aggregate.parent.mkdir(parents=True)
    legacy.parent.mkdir(parents=True)
    aggregate.write_text(json.dumps(_verified_receipt()), encoding="utf-8")
    legacy.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(portfolio_runtime, "EXTENSION_RECEIPT_PATH", aggregate)
    monkeypatch.setattr(portfolio_runtime, "LEGACY_EXTENSION_RECEIPT_PATH", legacy)

    state, _, _ = portfolio_runtime._load_extension_summary()
    assert state == "VERIFIED"
    assert portfolio_runtime._active_extension_receipt_path() == aggregate


def test_runtime_falls_back_to_legacy_receipt_when_aggregate_is_absent(monkeypatch, tmp_path: Path):
    aggregate = tmp_path / "state/product_grade/canon_extension_aggregate/CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json"
    legacy = tmp_path / "state/product_grade/canon_extensions/CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(json.dumps(_verified_receipt()), encoding="utf-8")

    monkeypatch.setattr(portfolio_runtime, "EXTENSION_RECEIPT_PATH", aggregate)
    monkeypatch.setattr(portfolio_runtime, "LEGACY_EXTENSION_RECEIPT_PATH", legacy)

    state, _, _ = portfolio_runtime._load_extension_summary()
    assert state == "VERIFIED"
    assert portfolio_runtime._active_extension_receipt_path() == legacy
