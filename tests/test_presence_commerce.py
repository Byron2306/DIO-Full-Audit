from pathlib import Path

import pytest

from presence_core.commerce import (
    CommerceError,
    build_order_payload,
    reconcile_verified_payment,
)
from presence_core.customer_cases import (
    create_or_attach_case,
    update_case,
)


def make_case(tmp_path: Path):
    case = create_or_attach_case(
        tmp_path,
        conversation_id="CONV-TEST",
        channel="telegram",
        external_user_id="USER-1",
        product_id="Sophia Integrity",
    )

    return update_case(
        tmp_path,
        case,
        stage="QUOTE_READY",
    )


def make_quote(case):
    return {
        "quote_id": "DIO-Q-TEST-001",
        "case_id": case["case_id"],
        "quote_state": "approved",
        "product": "Sophia Integrity",
        "conversation_ids": ["CONV-TEST"],
        "attachment_id": "ATT-TEST-001",
        "amount": 750,
        "currency": "ZAR",
    }


def test_build_order_preserves_lineage(tmp_path):
    case = make_case(tmp_path)
    quote = make_quote(case)

    result = build_order_payload(
        case,
        quote,
        order_id="ORDER-TEST-001",
    )

    assert result["product_code"] == "SOPHIA_INTEGRITY"
    assert result["amount_minor"] == 75000
    assert result["currency"] == "ZAR"

    lineage = result["metadata"]["lineage"]

    assert lineage["case_id"] == case["case_id"]
    assert lineage["quote_id"] == "DIO-Q-TEST-001"
    assert lineage["conversation_id"] == "CONV-TEST"
    assert lineage["attachment_id"] == "ATT-TEST-001"


def test_unapproved_quote_refused(tmp_path):
    case = make_case(tmp_path)
    quote = make_quote(case)
    quote["quote_state"] = "draft"

    with pytest.raises(CommerceError):
        build_order_payload(
            case,
            quote,
            order_id="ORDER-TEST-001",
        )


def test_payment_does_not_release_fulfilment(
    tmp_path,
    monkeypatch,
):
    case = make_case(tmp_path)
    quote = make_quote(case)

    import presence_core.commerce as commerce

    monkeypatch.setattr(
        commerce,
        "_edge",
        lambda path: (
            "https://edge.example",
            "token",
        ),
    )

    monkeypatch.setattr(
        commerce,
        "edge_request",
        lambda *args, **kwargs: {
            "schema": "dio.commerce_order.v1",
            "order_id": "ORDER-TEST-001",
            "state": "paid",
            "product_code": "SOPHIA_INTEGRITY",
            "amount_minor": 75000,
            "currency": "ZAR",
            "metadata": {
                "lineage": {
                    "case_id": case["case_id"],
                    "quote_id": "DIO-Q-TEST-001",
                    "product_id": "Sophia Integrity",
                    "conversation_id": "CONV-TEST",
                    "attachment_id": "ATT-TEST-001",
                }
            },
        },
    )

    updated = reconcile_verified_payment(
        tmp_path,
        case,
        quote,
        order_id="ORDER-TEST-001",
    )

    assert updated["stage"] == "PAYMENT_VERIFIED"
    assert updated["commercial"]["payment_state"] == "verified"

    assert (
        updated["commercial"]["fulfilment_released"]
        is False
    )

    assert (
        updated["commercial"]["fulfilment_authority_created"]
        is False
    )

    assert updated["authority_created"] is False


def test_lineage_mismatch_refused(
    tmp_path,
    monkeypatch,
):
    case = make_case(tmp_path)
    quote = make_quote(case)

    import presence_core.commerce as commerce

    monkeypatch.setattr(
        commerce,
        "_edge",
        lambda path: (
            "https://edge.example",
            "token",
        ),
    )

    monkeypatch.setattr(
        commerce,
        "edge_request",
        lambda *args, **kwargs: {
            "state": "paid",
            "amount_minor": 75000,
            "currency": "ZAR",
            "metadata": {
                "lineage": {
                    "case_id": "WRONG-CASE",
                }
            },
        },
    )

    with pytest.raises(
        CommerceError,
        match="lineage mismatch",
    ):
        reconcile_verified_payment(
            tmp_path,
            case,
            quote,
            order_id="ORDER-TEST-001",
        )


def test_fx_settlement_preserves_quoted_truth(tmp_path):
    from presence_core.commerce import build_fx_settlement_payload

    case = make_case(tmp_path)
    quote = make_quote(case)

    fx = {
        "schema": "dio.commercial_fx.v1",
        "quoted_amount_minor": 75000,
        "quoted_currency": "ZAR",
        "settlement_amount_minor": 4607,
        "settlement_currency": "USD",
        "rate": "0.0614293",
        "rate_source": "current-market-observation",
        "observed_at": "2026-09-16T13:23:00+00:00",
        "receipt_sha256": "a" * 64,
        "authority_created": False,
    }

    payload = build_fx_settlement_payload(
        case,
        quote,
        fx,
        order_id="ORDER-TEST-USD",
    )

    assert payload["amount_minor"] == 4607
    assert payload["currency"] == "USD"

    assert payload["metadata"]["quoted_terms"] == {
        "amount_minor": 75000,
        "currency": "ZAR",
    }

    assert (
        payload["metadata"]["lineage"]["fx_receipt_sha256"]
        == "a" * 64
    )


def test_controlled_test_settlement_verifies_without_real_money(
    tmp_path: Path,
) -> None:
    import presence_core.commerce as commerce

    assert hasattr(
        commerce,
        "record_controlled_test_settlement",
    ), "controlled-test settlement seam is missing"

    case = make_case(tmp_path)
    quote = make_quote(case)

    result = commerce.record_controlled_test_settlement(
        tmp_path,
        case,
        quote,
        receipt_id="CTS-TEST-001",
        authorized_by="operator:test",
    )

    assert result["stage"] == "PAYMENT_VERIFIED"

    commercial = result["commercial"]

    assert (
        commercial["payment_state"]
        == "verified_controlled_test"
    )

    assert (
        commercial["payment_evidence_ref"]
        == "controlled-test:CTS-TEST-001"
    )

    assert commercial["fulfilment_released"] is False
    assert (
        commercial["fulfilment_authority_created"]
        is False
    )
    assert (
        commercial["release_authority_created"]
        is False
    )

    assert result["authority_created"] is False

    receipt = commercial["controlled_test_settlement"]

    assert receipt["schema"] == "dio.controlled_test_settlement.v1"
    assert receipt["receipt_id"] == "CTS-TEST-001"
    assert receipt["provider"] == "dio_controlled_test"
    assert receipt["controlled_test"] is True
    assert receipt["external_funds_moved"] is False
    assert receipt["revenue_recognised"] is False
    assert receipt["market_validation_eligible"] is False
    assert receipt["operator_self_transaction"] is True
    assert receipt["authorized_by"] == "operator:test"

    assert receipt["case_id"] == case["case_id"]
    assert receipt["quote_id"] == quote["quote_id"]
    assert receipt["product_id"] == "Sophia Integrity"
    assert receipt["amount_minor"] == 75000
    assert receipt["currency"] == "ZAR"
    assert receipt["attachment_id"] == "ATT-TEST-001"


def test_controlled_test_settlement_refuses_wrong_quote_lineage(
    tmp_path: Path,
) -> None:
    import json

    from presence_core.commerce import (
        CommerceError,
        record_controlled_test_settlement,
    )

    case = make_case(tmp_path)
    quote = make_quote(case)

    quote["case_id"] = "CASE-WRONG"

    with pytest.raises(
        CommerceError,
        match="does not belong",
    ):
        record_controlled_test_settlement(
            tmp_path,
            case,
            quote,
            receipt_id="CTS-WRONG-001",
            authorized_by="operator:test",
        )

    stored_path = (
        tmp_path
        / "customer_cases"
        / "cases"
        / f"{case['case_id']}.json"
    )

    stored = json.loads(
        stored_path.read_text(
            encoding="utf-8"
        )
    )

    assert stored["stage"] == "QUOTE_READY"

    commercial = stored.get("commercial") or {}

    assert (
        commercial.get("payment_state")
        != "verified_controlled_test"
    )

    assert (
        commercial.get("controlled_test_settlement")
        is None
    )
