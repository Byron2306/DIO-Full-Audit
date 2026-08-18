from __future__ import annotations

import json
from pathlib import Path

from products.product_grade import _canned_final_copy, _internal_leaks
from products.product_grade_gauntlet import BASELINE_TOKEN, run_product_grade_gauntlet

ROOT = Path(__file__).resolve().parents[1]


def _manifest(name: str) -> dict:
    return json.loads((ROOT / "config" / "studio_harvest" / name).read_text(encoding="utf-8"))


def test_product_grade_standard_detects_canned_final_copy_shapes():
    assert _canned_final_copy(_manifest("site_studio.json")) is True
    assert _canned_final_copy(_manifest("professional_correspondence_studio.json")) is True
    assert _canned_final_copy(_manifest("article_publication_studio.json")) is True
    assert _canned_final_copy(_manifest("finance_readiness_studio.json")) is False


def test_lingua_visible_text_audit_detects_internal_proof_language():
    leaks = _internal_leaks("DIO // SITE STUDIO — CONTROLLED COMPOSITION PROOF — NEEDS_YOU")
    assert len(leaks) >= 3
    assert not _internal_leaks("A clear professional report prepared for customer review.")


def test_product_grade_portfolio_baseline_refuses_shortcuts_and_writes_review_packets(tmp_path: Path):
    receipt = run_product_grade_gauntlet(output_dir=tmp_path)
    assert receipt["acceptance_token"] == BASELINE_TOKEN
    assert receipt["studio_count"] == 4
    assert receipt["all_product_grade_verified"] is False
    assert receipt["product_grade_verified_count"] == 0
    assert receipt["product_grade_refuse_count"] == 4

    site = receipt["studios"]["site_studio"]
    correspondence = receipt["studios"]["professional_correspondence_studio"]
    finance = receipt["studios"]["finance_readiness_studio"]
    article = receipt["studios"]["article_publication_studio"]

    assert "CANNED_FINAL_COPY" in site["critical_blockers"]
    assert "INTERNAL_PROOF_LANGUAGE_LEAK" in site["critical_blockers"]
    assert "CANNED_FINAL_COPY" in correspondence["critical_blockers"]
    assert "CANNED_FINAL_COPY" not in finance["critical_blockers"]
    assert "INTERNAL_PROOF_LANGUAGE_LEAK" in finance["critical_blockers"]
    assert "CANNED_FINAL_COPY" in article["critical_blockers"]
    assert "INTERNAL_PROOF_LANGUAGE_LEAK" in article["critical_blockers"]

    for studio_id, row in receipt["studios"].items():
        assert row["customers_will_pay"] == "UNPROVED"
        assert row["verified_payment"] == "UNPROVED"
        assert row["buyer_grade_candidate"] is False
        assert row["beast_mechanical_pass"] is True
        assert (tmp_path / studio_id / "PRODUCT_GRADE_RECEIPT.json").is_file()
        assert (tmp_path / studio_id / "BLIND_BUYER_REVIEW_PACKET.json").is_file()
