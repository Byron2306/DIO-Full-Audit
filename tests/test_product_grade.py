from __future__ import annotations

import json
from pathlib import Path

from products.product_grade import _canned_final_copy, _internal_leaks
from products.product_grade_gauntlet import VERIFIED_TOKEN, run_product_grade_gauntlet

ROOT = Path(__file__).resolve().parents[1]


def _manifest(name: str) -> dict:
    return json.loads((ROOT / "config" / "studio_harvest" / name).read_text(encoding="utf-8"))


def test_legacy_proof_manifests_still_disclose_canned_fixture_shapes():
    assert _canned_final_copy(_manifest("site_studio.json")) is True
    assert _canned_final_copy(_manifest("professional_correspondence_studio.json")) is True
    assert _canned_final_copy(_manifest("article_publication_studio.json")) is True
    assert _canned_final_copy(_manifest("finance_readiness_studio.json")) is False


def test_lingua_visible_text_audit_detects_internal_proof_language():
    leaks = _internal_leaks("DIO // SITE STUDIO — CONTROLLED COMPOSITION PROOF — NEEDS_YOU")
    assert len(leaks) >= 3
    assert not _internal_leaks("A clear professional report prepared for customer review.")


def test_product_grade_portfolio_verifies_separate_buyer_deliveries(tmp_path: Path):
    receipt = run_product_grade_gauntlet(output_dir=tmp_path)
    assert receipt["acceptance_token"] == VERIFIED_TOKEN
    assert receipt["studio_count"] == 4
    assert receipt["all_product_grade_verified"] is True
    assert receipt["product_grade_verified_count"] == 4
    assert receipt["product_grade_refuse_count"] == 0

    for studio_id, row in receipt["studios"].items():
        assert row["critical_blockers"] == []
        assert row["buyer_grade_candidate"] is True
        assert row["beast_mechanical_pass"] is True
        assert row["lingua_semantic_custody"] is True
        assert row["legacy_final_copy_used"] is False
        assert row["customers_will_pay"] == "UNPROVED"
        assert row["verified_payment"] == "UNPROVED"
        assert (tmp_path / studio_id / "PRODUCT_GRADE_RECEIPT.json").is_file()
        assert (tmp_path / studio_id / "BLIND_BUYER_REVIEW_PACKET.json").is_file()
        assert (tmp_path / studio_id / "customer_delivery" / "CUSTOMER_DELIVERY_RECEIPT.json").is_file()
