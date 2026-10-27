from __future__ import annotations

from pathlib import Path

from products.canon_portfolio_product_grade import (
    HISTORICAL_53_SOURCE_BLOB,
    HISTORICAL_53_SOURCE_COMMIT,
    PORTFOLIO_BASELINE_TOKEN,
    PORTFOLIO_VERIFIED_TOKEN,
    load_historical_53_anchor,
    run_canon_portfolio_product_grade,
    validate_historical_53_anchor,
)


ROOT = Path(__file__).resolve().parents[1]
ANCHOR_PATH = ROOT / "evidence" / "historical" / "PROFESSIONAL_EVIDENCE_53_X3_ANCHOR.json"
EXTENSION_TOKEN = "DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_VERIFIED"


def _verified_extension_receipt() -> dict:
    return {
        "schema": "dio.product_grade.canon_extension_gauntlet_receipt.v2",
        "acceptance_token": EXTENSION_TOKEN,
        "extension_count": 15,
        "variants_per_extension": 3,
        "controlled_journey_count": 45,
        "verified_journey_count": 45,
        "refused_journey_count": 0,
        "product_grade_verified_count": 15,
        "product_grade_refuse_count": 0,
        "all_product_grade_verified": True,
        "external_effects": False,
        "authority_created": False,
        "commercial_validation": "UNPROVED",
        "portfolio_fingerprint": "sha256:" + "e" * 64,
    }


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


def test_verified_53x3_plus_verified_15x3_seals_68_products_and_204_journeys(tmp_path: Path) -> None:
    anchor_copy = tmp_path / "historical_53_anchor.json"
    anchor_copy.write_bytes(ANCHOR_PATH.read_bytes())
    before = anchor_copy.read_bytes()

    receipt = run_canon_portfolio_product_grade(
        historical_anchor_path=anchor_copy,
        extension_receipt=_verified_extension_receipt(),
        output_dir=tmp_path / "portfolio",
    )

    assert receipt["acceptance_token"] == PORTFOLIO_VERIFIED_TOKEN
    assert PORTFOLIO_VERIFIED_TOKEN == "DIO_CANON_PORTFOLIO_68_X3_PRODUCT_GRADE_VERIFIED"
    assert receipt["canon_product_count"] == 68
    assert receipt["base_canon_product_count"] == 53
    assert receipt["canon_extension_count"] == 15
    assert receipt["variants_per_product"] == 3
    assert receipt["base_canon_journey_count"] == 159
    assert receipt["canon_extension_journey_count"] == 45
    assert receipt["controlled_journey_count"] == 204
    assert receipt["verified_journey_count"] == 204
    assert receipt["refused_journey_count"] == 0
    assert receipt["product_grade_verified_count"] == 68
    assert receipt["all_product_grade_verified"] is True
    assert receipt["historical_53_receipt_mutated"] is False
    assert receipt["historical_53"]["source_git_blob_sha"] == HISTORICAL_53_SOURCE_BLOB
    assert receipt["canon_extensions_15x3"]["portfolio_fingerprint"] == _verified_extension_receipt()["portfolio_fingerprint"]
    assert receipt["external_effects"] is False
    assert receipt["authority_created"] is False
    assert anchor_copy.read_bytes() == before
    assert (tmp_path / "portfolio" / "CANON_PORTFOLIO_68_X3_PRODUCT_GRADE_RECEIPT.json").is_file()


def test_portfolio_refuses_wrong_extension_counts_or_token(tmp_path: Path) -> None:
    broken = _verified_extension_receipt()
    broken["acceptance_token"] = "DIO_CANON_EXTENSION_15_X3_PRODUCT_GRADE_BASELINE_MEASURED"
    broken["extension_count"] = 14
    broken["controlled_journey_count"] = 42
    broken["verified_journey_count"] = 42
    broken["product_grade_verified_count"] = 14
    broken["all_product_grade_verified"] = False

    receipt = run_canon_portfolio_product_grade(
        historical_anchor_path=ANCHOR_PATH,
        extension_receipt=broken,
        output_dir=tmp_path / "portfolio",
    )

    assert receipt["acceptance_token"] == PORTFOLIO_BASELINE_TOKEN
    assert receipt["all_product_grade_verified"] is False
    assert "canon_extension_acceptance_token_invalid" in receipt["critical_blockers"]
    assert "canon_extension_product_count_mismatch" in receipt["critical_blockers"]
    assert "canon_extension_journey_count_mismatch" in receipt["critical_blockers"]


def test_portfolio_refuses_invalid_historical_anchor_without_mutating_it(tmp_path: Path) -> None:
    anchor_copy = tmp_path / "historical_53_anchor.json"
    anchor_copy.write_bytes(ANCHOR_PATH.read_bytes())
    text = anchor_copy.read_text(encoding="utf-8").replace('"journey_count": 159', '"journey_count": 158')
    anchor_copy.write_text(text, encoding="utf-8")
    before = anchor_copy.read_bytes()

    receipt = run_canon_portfolio_product_grade(
        historical_anchor_path=anchor_copy,
        extension_receipt=_verified_extension_receipt(),
        output_dir=tmp_path / "portfolio",
    )

    assert receipt["acceptance_token"] == PORTFOLIO_BASELINE_TOKEN
    assert "historical_53_journey_count_mismatch" in receipt["critical_blockers"]
    assert receipt["historical_53_receipt_mutated"] is False
    assert anchor_copy.read_bytes() == before
