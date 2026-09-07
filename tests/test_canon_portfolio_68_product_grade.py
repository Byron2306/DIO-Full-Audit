from __future__ import annotations

from pathlib import Path

from products.canon_portfolio_product_grade import (
    HISTORICAL_53_SOURCE_BLOB,
    HISTORICAL_53_SOURCE_COMMIT,
    load_historical_53_anchor,
    validate_historical_53_anchor,
)


ROOT = Path(__file__).resolve().parents[1]
ANCHOR_PATH = ROOT / "evidence" / "historical" / "PROFESSIONAL_EVIDENCE_53_X3_ANCHOR.json"


def test_historical_anchor_matches_frozen_53x3_identity() -> None:
    anchor = load_historical_53_anchor(ANCHOR_PATH)
    assert anchor["schema"] == "dio.historical_evidence_anchor.v1"
    assert anchor["source_repository"] == "Byron2306/DIO-Workflows"
    assert anchor["source_commit"] == HISTORICAL_53_SOURCE_COMMIT == "3119e290efd62cdeccd3f4f5938cc5be85014464"
    assert anchor["source_path"] == "products/proof/receipts/PROFESSIONAL_EVIDENCE_53_X3_RECEIPT.json"
    assert anchor["source_git_blob_sha"] == HISTORICAL_53_SOURCE_BLOB == "7ffeb400a4ec0ffd51d0a10c3035d3303fd24c4e"
    assert anchor["acceptance_token"] == "DIO_PROFESSIONAL_EVIDENCE_53_X3_VERIFIED"
    assert anchor["receipt_schema"] == "dio.professional_evidence.multitier_53_receipt.v1"
    assert anchor["canonical_incarnation_count"] == 53
    assert anchor["variant_count"] == 3
    assert anchor["variants"] == ["normal", "messy", "adversarial"]
    assert anchor["journey_count"] == 159
    assert anchor["verified_journey_count"] == 159
    assert anchor["refused_journey_count"] == 0
    assert anchor["authority_created"] is False
    assert anchor["external_effects"] is False
    assert validate_historical_53_anchor(anchor) == []


def test_historical_anchor_refuses_count_or_blob_drift() -> None:
    anchor = {
        "schema": "dio.historical_evidence_anchor.v1",
        "source_repository": "Byron2306/DIO-Workflows",
        "source_commit": HISTORICAL_53_SOURCE_COMMIT,
        "source_path": "products/proof/receipts/PROFESSIONAL_EVIDENCE_53_X3_RECEIPT.json",
        "source_git_blob_sha": "0" * 40,
        "acceptance_token": "DIO_PROFESSIONAL_EVIDENCE_53_X3_VERIFIED",
        "receipt_schema": "dio.professional_evidence.multitier_53_receipt.v1",
        "canonical_incarnation_count": 53,
        "variant_count": 3,
        "variants": ["normal", "messy", "adversarial"],
        "journey_count": 158,
        "verified_journey_count": 158,
        "refused_journey_count": 0,
        "authority_created": False,
        "external_effects": False,
        "commercial_validation": "UNPROVED",
    }
    blockers = validate_historical_53_anchor(anchor)
    assert "historical_53_blob_identity_mismatch" in blockers
    assert "historical_53_journey_count_mismatch" in blockers
