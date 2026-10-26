import json
from pathlib import Path

from pypdf import PdfWriter

from presence_core.scope_scan import scan_pdf_scope
from products.commercial_pricing_registry import (
    scope_pricing_recommendation,
)


def test_pdf_scope_scan_counts_pages_without_execution(tmp_path):
    aid = "ATT-TEST"
    qdir = tmp_path / "quarantine" / aid
    qdir.mkdir(parents=True)

    blob = qdir / "content.blob"

    writer = PdfWriter()
    for _ in range(8):
        writer.add_blank_page(width=612, height=792)

    with blob.open("wb") as handle:
        writer.write(handle)

    import hashlib

    sha = hashlib.sha256(blob.read_bytes()).hexdigest()

    (qdir / "ATTACHMENT.json").write_text(
        json.dumps(
            {
                "attachment_id": aid,
                "conversation_id": "CONV-TEST",
                "original_file_name": "sample.pdf",
                "sha256": sha,
                "blob_path": str(blob),
                "safe_to_parse": False,
                "safe_to_execute": False,
            }
        )
    )

    receipt = scan_pdf_scope(
        tmp_path,
        case_id="CASE-TEST",
        attachment_id=aid,
        product_id="Sophia Integrity",
    )

    assert receipt["page_count"] == 8
    assert receipt["semantic_analysis_performed"] is False
    assert receipt["embedded_content_executed"] is False
    assert receipt["safe_to_execute"] is False
    assert receipt["authority_created"] is False


def test_sophia_integrity_scope_pricing():
    expected = {
        1: 750,
        8: 750,
        10: 750,
        11: 1200,
        25: 1200,
        26: 2100,
        50: 2100,
        51: 2800,
        100: 2800,
        101: 3500,
        500: 3500,
    }

    for pages, amount in expected.items():
        result = scope_pricing_recommendation(
            "Sophia Integrity",
            scope_unit="manuscript_page",
            quantity=pages,
        )

        assert result["state"] == "PRICE_RECOMMENDED"
        assert result["scope_quantity"] == pages
        assert result["recommended_amount_zar"] == amount
        assert result["operator_review_required"] is True
        assert result["quote_issue_authority"] is False
