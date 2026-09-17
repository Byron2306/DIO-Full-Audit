from pathlib import Path

import presence_core.customer_cases as customer_cases

from presence_core.customer_cases import (
    create_or_attach_case,
    find_case_for_conversation,
    load_case,
    update_case,
)


def test_different_source_after_quote_creates_fresh_successor_case(
    tmp_path: Path,
):
    root = tmp_path / "state" / "presence"
    root.mkdir(parents=True)

    conversation_id = "CONV-SOURCE-SUCCESSION"

    case_a = create_or_attach_case(
        root,
        conversation_id=conversation_id,
        channel="telegram",
        external_user_id="TEST-USER",
        product_id="Sophia Review",
        contact_email="test@example.com",
        customer_id=None,
    )

    case_a = update_case(
        root,
        case_a,
        stage="QUOTE_READY",
        patch={
            "scope": {
                "source": "bounded_scope_scan",
                "attachment_id": "ATT-SOURCE-A",
                "scope_scan_sha256": "a" * 64,
                "page_count": 8,
                "quantity": 8,
                "primary_scope_unit": "manuscript_page",
            },
            "commercial": {
                "quote_state": "approved",
                "quote_id": "DIO-Q-SOURCE-A",
                "quote_recommendation": 750,
                "amount": 750,
                "currency": "ZAR",
                "payment_state": "awaiting_payment",
                "checkout_url": (
                    "https://example.invalid/checkout/source-a"
                ),
            },
            "order_ids": [
                "ORDER-SOURCE-A",
            ],
        },
        evidence_ref="scope-and-quote:source-a",
    )

    create_successor_case = getattr(
        customer_cases,
        "create_successor_case",
        None,
    )

    assert callable(create_successor_case), (
        "create_successor_case is not implemented"
    )

    case_b = create_successor_case(
        root,
        case_a,
        conversation_id=conversation_id,
        source_sha256="b" * 64,
    )

    assert case_b["case_id"] != case_a["case_id"]
    assert (
        case_b["predecessor_case_id"]
        == case_a["case_id"]
    )

    assert case_b["scope"] == {}

    assert (
        case_b["commercial"]["quote_state"]
        == "not_prepared"
    )
    assert (
        case_b["commercial"]["payment_state"]
        == "unverified"
    )

    assert "checkout_url" not in case_b["commercial"]
    assert case_b["order_ids"] == []

    assert case_b["authority_created"] is False
    assert case_b["stage"] == "NEW_LEAD"

    current = find_case_for_conversation(
        root,
        conversation_id,
    )

    assert current is not None
    assert current["case_id"] == case_b["case_id"]

    stored_a = load_case(
        root,
        case_a["case_id"],
    )

    assert stored_a is not None
    assert stored_a["stage"] == "QUOTE_READY"
    assert (
        stored_a["commercial"]["quote_id"]
        == "DIO-Q-SOURCE-A"
    )
    assert (
        stored_a["commercial"]["checkout_url"]
        == "https://example.invalid/checkout/source-a"
    )
    assert (
        stored_a["scope"]["scope_scan_sha256"]
        == "a" * 64
    )


def test_predecessor_records_forward_successor_link(
    tmp_path: Path,
):
    root = tmp_path / "state" / "presence"
    root.mkdir(parents=True)

    conversation_id = "CONV-FORWARD-SUCCESSOR"

    case_a = create_or_attach_case(
        root,
        conversation_id=conversation_id,
        channel="telegram",
        external_user_id="TEST-USER",
        product_id="Sophia Review",
        contact_email="test@example.com",
        customer_id=None,
    )

    case_a = update_case(
        root,
        case_a,
        stage="QUOTE_READY",
        patch={
            "scope": {
                "source": "bounded_scope_scan",
                "attachment_id": "ATT-FORWARD-A",
                "scope_scan_sha256": "a" * 64,
            },
            "commercial": {
                "quote_state": "approved",
                "quote_id": "DIO-Q-FORWARD-A",
                "payment_state": "awaiting_payment",
            },
        },
        evidence_ref="scope-and-quote:forward-a",
    )

    case_b = customer_cases.create_successor_case(
        root,
        case_a,
        conversation_id=conversation_id,
        source_sha256="b" * 64,
    )

    stored_a = load_case(
        root,
        case_a["case_id"],
    )

    assert stored_a is not None

    assert (
        stored_a["successor_case_id"]
        == case_b["case_id"]
    )

    assert (
        case_b["predecessor_case_id"]
        == case_a["case_id"]
    )
