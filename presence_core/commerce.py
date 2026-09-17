from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
import re

from presence_core.customer_cases import update_case
from scripts.sync_dio_edge_events import (
    edge_request,
    read_config,
)

DEFAULT_EDGE_CONFIG = Path("config/dio_edge.live.json")


class CommerceError(RuntimeError):
    pass


def _product_code(value: str) -> str:
    code = re.sub(
        r"[^A-Z0-9_-]+",
        "_",
        str(value).upper(),
    ).strip("_")[:40]

    if not re.fullmatch(r"[A-Z0-9_-]{2,40}", code):
        raise CommerceError("invalid product code")

    return code


def _amount_minor(quote: dict[str, Any]) -> int:
    try:
        value = Decimal(str(quote["amount"]))
    except (KeyError, InvalidOperation):
        raise CommerceError("quote amount is invalid")

    minor = value * 100

    if minor != minor.to_integral_value():
        raise CommerceError(
            "quote amount has unsupported precision"
        )

    amount = int(minor)

    if amount < 1:
        raise CommerceError("quote amount must be positive")

    return amount


def build_order_payload(
    case: dict[str, Any],
    quote: dict[str, Any],
    *,
    order_id: str,
) -> dict[str, Any]:
    if case.get("stage") != "QUOTE_READY":
        raise CommerceError(
            "case must be QUOTE_READY"
        )

    if quote.get("quote_state") != "approved":
        raise CommerceError(
            "quote must be approved"
        )

    if quote.get("case_id") != case.get("case_id"):
        raise CommerceError(
            "quote does not belong to customer case"
        )

    product_id = str(
        case.get("product_id")
        or quote.get("product")
        or ""
    ).strip()

    if not product_id:
        raise CommerceError("product identity missing")

    conversations = (
        quote.get("conversation_ids")
        or case.get("conversation_ids")
        or []
    )

    conversation_id = (
        str(conversations[0])
        if conversations
        else None
    )

    lineage = {
        "case_id": case["case_id"],
        "quote_id": quote["quote_id"],
        "product_id": product_id,
        "conversation_id": conversation_id,
        "attachment_id": quote.get("attachment_id"),
    }

    return {
        "order_id": order_id,
        "product_code": _product_code(product_id),
        "amount_minor": _amount_minor(quote),
        "currency": str(
            quote.get("currency") or ""
        ).upper(),
        "metadata": {
            "lineage": lineage,
        },
    }



def build_fx_settlement_payload(
    case: dict[str, Any],
    quote: dict[str, Any],
    fx_receipt: dict[str, Any],
    *,
    order_id: str,
) -> dict[str, Any]:
    quoted = build_order_payload(
        case,
        quote,
        order_id=order_id,
    )

    if fx_receipt.get("schema") != "dio.commercial_fx.v1":
        raise CommerceError("unsupported FX receipt")

    if fx_receipt.get("authority_created") is not False:
        raise CommerceError("FX receipt must not create authority")

    if (
        fx_receipt.get("quoted_amount_minor")
        != quoted["amount_minor"]
    ):
        raise CommerceError("FX quoted amount mismatch")

    if (
        fx_receipt.get("quoted_currency")
        != quoted["currency"]
    ):
        raise CommerceError("FX quoted currency mismatch")

    settlement_amount = fx_receipt.get(
        "settlement_amount_minor"
    )
    settlement_currency = fx_receipt.get(
        "settlement_currency"
    )
    receipt_sha = str(
        fx_receipt.get("receipt_sha256") or ""
    ).strip()

    if not isinstance(settlement_amount, int) or settlement_amount < 1:
        raise CommerceError("invalid FX settlement amount")

    if not isinstance(settlement_currency, str) or len(settlement_currency) != 3:
        raise CommerceError("invalid FX settlement currency")

    if len(receipt_sha) != 64:
        raise CommerceError("FX receipt hash missing")

    lineage = dict(
        quoted["metadata"]["lineage"]
    )

    lineage["fx_receipt_sha256"] = receipt_sha

    return {
        "order_id": order_id,
        "product_code": quoted["product_code"],
        "amount_minor": settlement_amount,
        "currency": settlement_currency.upper(),
        "metadata": {
            "lineage": lineage,
            "quoted_terms": {
                "amount_minor": quoted["amount_minor"],
                "currency": quoted["currency"],
            },
            "settlement_terms": {
                "amount_minor": settlement_amount,
                "currency": settlement_currency.upper(),
            },
            "fx": {
                "receipt_sha256": receipt_sha,
                "rate": fx_receipt.get("rate"),
                "rate_source": fx_receipt.get("rate_source"),
                "observed_at": fx_receipt.get("observed_at"),
            },
        },
    }


def register_fx_checkout(
    case: dict[str, Any],
    quote: dict[str, Any],
    fx_receipt: dict[str, Any],
    *,
    order_id: str,
    edge_config_path: Path = DEFAULT_EDGE_CONFIG,
) -> dict[str, Any]:
    payload = build_fx_settlement_payload(
        case,
        quote,
        fx_receipt,
        order_id=order_id,
    )

    base_url, token = _edge(
        edge_config_path
    )

    order = edge_request(
        base_url + "/api/dio/orders",
        token,
        method="POST",
        payload=payload,
    )

    checkout = edge_request(
        base_url
        + f"/api/dio/orders/{order_id}"
        + "/checkout/paypal",
        token,
        method="POST",
    )

    return {
        "order": order,
        "checkout": checkout,
        "payload": payload,
        "authority_created": False,
        "fulfilment_released": False,
    }

def _edge(
    edge_config_path: Path,
) -> tuple[str, str]:
    config = read_config(
        Path(edge_config_path).resolve()
    )

    token = Path(
        config["edge_token_path"]
    ).expanduser().read_text(
        encoding="utf-8"
    ).strip()

    if not token:
        raise CommerceError(
            "edge token is empty"
        )

    return (
        str(config["base_url"]).rstrip("/"),
        token,
    )


def register_checkout(
    case: dict[str, Any],
    quote: dict[str, Any],
    *,
    order_id: str,
    edge_config_path: Path = DEFAULT_EDGE_CONFIG,
) -> dict[str, Any]:
    payload = build_order_payload(
        case,
        quote,
        order_id=order_id,
    )

    base_url, token = _edge(
        edge_config_path
    )

    order = edge_request(
        base_url + "/api/dio/orders",
        token,
        method="POST",
        payload=payload,
    )

    checkout = edge_request(
        base_url
        + f"/api/dio/orders/{order_id}"
        + "/checkout/paypal",
        token,
        method="POST",
    )

    return {
        "order": order,
        "checkout": checkout,
        "payload": payload,
        "authority_created": False,
        "fulfilment_released": False,
    }


def record_controlled_test_settlement(
    state_root: Path,
    case: dict[str, Any],
    quote: dict[str, Any],
    *,
    receipt_id: str,
    authorized_by: str,
) -> dict[str, Any]:
    if case.get("stage") != "QUOTE_READY":
        raise CommerceError(
            "controlled-test settlement requires QUOTE_READY case"
        )

    if quote.get("quote_state") != "approved":
        raise CommerceError(
            "controlled-test settlement requires approved quote"
        )

    if quote.get("case_id") != case.get("case_id"):
        raise CommerceError(
            "controlled-test quote does not belong to customer case"
        )

    receipt_id = str(receipt_id or "").strip()
    authorized_by = str(authorized_by or "").strip()

    if not receipt_id:
        raise CommerceError("receipt_id is required")

    if not authorized_by:
        raise CommerceError("authorized_by is required")

    expected = build_order_payload(
        case,
        quote,
        order_id=f"DIO-TEST-{receipt_id}",
    )

    lineage = expected["metadata"]["lineage"]

    receipt = {
        "schema": "dio.controlled_test_settlement.v1",
        "receipt_id": receipt_id,
        "provider": "dio_controlled_test",
        "controlled_test": True,
        "external_funds_moved": False,
        "revenue_recognised": False,
        "market_validation_eligible": False,
        "operator_self_transaction": True,
        "authorized_by": authorized_by,
        "case_id": lineage.get("case_id"),
        "quote_id": lineage.get("quote_id"),
        "product_id": lineage.get("product_id"),
        "conversation_id": lineage.get("conversation_id"),
        "attachment_id": lineage.get("attachment_id"),
        "amount_minor": expected["amount_minor"],
        "currency": expected["currency"],
        "authority_created": False,
    }

    return update_case(
        Path(state_root),
        case,
        stage="PAYMENT_VERIFIED",
        patch={
            "commercial": {
                "order_id": f"DIO-TEST-{receipt_id}",
                "payment_state": "verified_controlled_test",
                "payment_evidence_ref": (
                    f"controlled-test:{receipt_id}"
                ),
                "controlled_test_settlement": receipt,
                "fulfilment_released": False,
                "fulfilment_authority_created": False,
                "release_authority_created": False,
            },
            "authority_created": False,
        },
        evidence_ref=f"controlled-test-payment:{receipt_id}",
    )


def reconcile_verified_payment(
    state_root: Path,
    case: dict[str, Any],
    quote: dict[str, Any],
    *,
    order_id: str,
    edge_config_path: Path = DEFAULT_EDGE_CONFIG,
) -> dict[str, Any]:
    base_url, token = _edge(
        edge_config_path
    )

    order = edge_request(
        base_url
        + f"/api/dio/orders/{order_id}",
        token,
    )

    if order.get("state") != "paid":
        raise CommerceError(
            "payment is not verified"
        )

    expected = build_order_payload(
        case,
        quote,
        order_id=order_id,
    )

    if order.get("amount_minor") != expected["amount_minor"]:
        raise CommerceError(
            "verified order amount mismatch"
        )

    if order.get("currency") != expected["currency"]:
        raise CommerceError(
            "verified order currency mismatch"
        )

    lineage = (
        order.get("metadata") or {}
    ).get("lineage") or {}

    expected_lineage = (
        expected["metadata"]["lineage"]
    )

    for key in (
        "case_id",
        "quote_id",
        "product_id",
        "conversation_id",
        "attachment_id",
    ):
        if lineage.get(key) != expected_lineage.get(key):
            raise CommerceError(
                f"verified order lineage mismatch: {key}"
            )

    return update_case(
        Path(state_root),
        case,
        stage="PAYMENT_VERIFIED",
        patch={
            "commercial": {
                "order_id": order_id,
                "payment_state": "verified",
                "payment_evidence_ref":
                    f"edge-order:{order_id}",
                "fulfilment_released": False,
                "fulfilment_authority_created": False,
                "release_authority_created": False,
            },
            "authority_created": False,
        },
        evidence_ref=f"payment:{order_id}",
    )



def commercial_surface_state(
    case: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(case, dict):
        return None

    commercial = case.get("commercial") or {}

    order_id = str(
        commercial.get("order_id") or ""
    ).strip()

    checkout_url = str(
        commercial.get("checkout_url") or ""
    ).strip()

    if not order_id or not checkout_url:
        return None

    quoted = commercial.get("quoted_terms") or {}
    settlement = commercial.get("settlement_terms") or {}

    stage = str(case.get("stage") or "")

    payment_verified = stage == "PAYMENT_VERIFIED"

    state = (
        "PAYMENT_VERIFIED"
        if payment_verified
        else "PAYMENT_PENDING"
    )

    return {
        "schema": "dio.presence.commercial_action.v1",
        "state": state,
        "product_id": case.get("product_id"),
        "order_id": order_id,
        "quote_id": commercial.get("quote_id"),
        "quoted": {
            "amount_minor": quoted.get("amount_minor"),
            "currency": quoted.get("currency"),
            "display": commercial.get("quoted_display"),
        },
        "settlement": {
            "amount_minor": settlement.get("amount_minor"),
            "currency": settlement.get("currency"),
            "display": commercial.get("settlement_display"),
        },
        "checkout": {
            "provider": "paypal",
            "approval_url": checkout_url,
        },
        "quote_artifact_ref": commercial.get(
            "quote_artifact_ref"
        ),
        "payment_verified": payment_verified,
        "fulfilment_released": bool(
            commercial.get("fulfilment_released", False)
        ),
        "authority_created": False,
    }
