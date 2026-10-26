from pathlib import Path

import pytest

from adapters.document_studio.quote_renderer import (
    QuoteRenderError,
    build_quote_semantic_content,
)


def quote():
    return {
        "quote_id": "DIO-Q-TEST",
        "case_id": "CASE-TEST",
        "product_id": "Sophia Integrity",
        "original_file_name": "test.pdf",
        "scope_quantity": 8,
        "scope_unit": "manuscript_page",
        "amount": 750,
        "currency": "ZAR",
        "quote_state": "not_prepared",
    }


def test_draft_quote_cannot_claim_official_authority():
    content = build_quote_semantic_content(
        quote(),
        official=False,
    )

    text = " ".join(
        str(row.get("text") or "")
        for row in content["blocks"]
    )

    assert "DRAFT QUOTE" in text
    assert "not yet an issued quote" in text
    assert "created no commercial" in text


def test_official_quote_requires_approval():
    with pytest.raises(
        QuoteRenderError,
        match="quote_state=approved",
    ):
        build_quote_semantic_content(
            quote(),
            official=True,
        )
