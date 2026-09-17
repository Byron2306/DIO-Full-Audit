from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .customer_cases import load_case, update_case
from .journey_core import transition_case


SETTLEMENT_RECEIPT_SCHEMA = "dio.settlement_receipt.v1"
REAL_SETTLEMENT = "REAL_SETTLEMENT"
CONTROLLED_TEST_SETTLEMENT = "CONTROLLED_TEST_SETTLEMENT"
WAIVED = "WAIVED"


def _canonical_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _required(value: str | None, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _quote_amount_minor(quote: dict[str, Any]) -> int:
    try:
        amount = Decimal(str(quote["amount"])) * 100
    except (KeyError, InvalidOperation):
        raise ValueError("canonical quote amount is invalid")
    if amount != amount.to_integral_value() or amount < 1:
        raise ValueError("canonical quote amount is invalid")
    return int(amount)


def _canonical_quote(case: dict[str, Any]) -> dict[str, Any]:
    if str(case.get("stage") or "") != "QUOTE_READY":
        raise ValueError("canonical Phase 2 quote truth is required")

    commercial = case.get("commercial") or {}
    quote_result = commercial.get("quote_result") or {}
    quote = quote_result.get("quote") or {}

    if (
        quote.get("schema") != "dio.customer_quote.v2"
        or quote_result.get("decision") != "ALLOW_PRESENTATION"
        or str(quote.get("case_id") or "") != str(case.get("case_id") or "")
        or not str(quote.get("quote_id") or "").strip()
        or len(str(quote.get("quote_truth_sha256") or "")) != 64
    ):
        raise ValueError("canonical Phase 2 quote truth is required")

    if str(quote.get("product_name") or "") != str(case.get("product_id") or ""):
        raise ValueError("canonical quote product does not match customer case")

    return deepcopy(quote)


def _receipt_basis(
    case: dict[str, Any],
    quote: dict[str, Any],
    *,
    settlement_class: str,
    provider: str,
    provider_receipt_id: str,
    external_funds_moved: bool,
    revenue_recognised: bool,
    market_validation_eligible: bool,
    fulfilment_eligible: bool,
    evidence_ref: str,
    reason: str | None = None,
    authorized_by: str | None = None,
    waived_by: str | None = None,
    operator_self_transaction: bool = False,
) -> dict[str, Any]:
    basis = {
        "schema": SETTLEMENT_RECEIPT_SCHEMA,
        "settlement_class": settlement_class,
        "case_id": str(case["case_id"]),
        "quote_id": str(quote["quote_id"]),
        "quote_truth_sha256": str(quote["quote_truth_sha256"]),
        "product_id": str(quote.get("product_id") or ""),
        "product_name": str(quote.get("product_name") or ""),
        "amount_minor": _quote_amount_minor(quote),
        "currency": str(quote.get("currency") or "").upper(),
        "provider": provider,
        "provider_receipt_id": provider_receipt_id,
        "evidence_ref": evidence_ref,
        "external_funds_moved": bool(external_funds_moved),
        "revenue_recognised": bool(revenue_recognised),
        "market_validation_eligible": bool(market_validation_eligible),
        "fulfilment_eligible": bool(fulfilment_eligible),
        "operator_self_transaction": bool(operator_self_transaction),
        "release_authority_created": False,
        "authority_created": False,
    }
    if reason is not None:
        basis["reason"] = reason
    if authorized_by is not None:
        basis["authorized_by"] = authorized_by
    if waived_by is not None:
        basis["waived_by"] = waived_by
    return basis


def _persist_receipt(
    state_root: Path,
    case: dict[str, Any],
    receipt: dict[str, Any],
) -> dict[str, Any]:
    existing = case.get("settlement")
    if isinstance(existing, dict) and existing:
        if existing.get("settlement_receipt_sha256") == receipt.get(
            "settlement_receipt_sha256"
        ):
            return deepcopy(existing)
        raise ValueError("customer case already has different settlement truth")

    case = transition_case(
        Path(state_root),
        str(case["case_id"]),
        "PAYMENT_PENDING",
        evidence_ref=f"settlement-pending:{receipt['settlement_receipt_sha256']}",
    )
    case = transition_case(
        Path(state_root),
        str(case["case_id"]),
        "PAYMENT_VERIFIED",
        evidence_ref=f"settlement:{receipt['settlement_receipt_sha256']}",
    )

    payment_state = {
        REAL_SETTLEMENT: "verified_real_settlement",
        CONTROLLED_TEST_SETTLEMENT: "verified_controlled_test",
        WAIVED: "waived",
    }[str(receipt["settlement_class"])]

    update_case(
        Path(state_root),
        case,
        patch={
            "settlement": deepcopy(receipt),
            "commercial": {
                "payment_state": payment_state,
                "payment_evidence_ref": receipt["evidence_ref"],
                "settlement_class": receipt["settlement_class"],
                "settlement_receipt_sha256": receipt[
                    "settlement_receipt_sha256"
                ],
                "external_funds_moved": receipt["external_funds_moved"],
                "revenue_recognised": receipt["revenue_recognised"],
                "market_validation_eligible": receipt[
                    "market_validation_eligible"
                ],
                "fulfilment_eligible": receipt["fulfilment_eligible"],
                "fulfilment_released": False,
                "fulfilment_authority_created": False,
                "release_authority_created": False,
            },
            "authority_created": False,
        },
        evidence_ref=f"settlement:{receipt['settlement_receipt_sha256']}",
    )
    return deepcopy(receipt)


def record_real_settlement(
    state_root: Path,
    case_id: str,
    *,
    provider: str,
    provider_receipt_id: str,
    amount_minor: int,
    currency: str,
    external_funds_moved: bool,
    evidence_ref: str,
) -> dict[str, Any]:
    case = load_case(Path(state_root), str(case_id))
    if case is None:
        raise ValueError(f"customer case not found: {case_id}")
    quote = _canonical_quote(case)

    provider = _required(provider, "provider")
    provider_receipt_id = _required(provider_receipt_id, "provider_receipt_id")
    evidence_ref = _required(evidence_ref, "evidence_ref")

    if external_funds_moved is not True:
        raise ValueError("external funds must be verified as moved")

    expected_amount = _quote_amount_minor(quote)
    try:
        received_amount = int(amount_minor)
    except (TypeError, ValueError):
        raise ValueError("settlement amount does not match quote")
    if received_amount < 1 or received_amount != expected_amount:
        raise ValueError("settlement amount does not match quote")

    received_currency = str(currency or "").strip().upper()
    expected_currency = str(quote.get("currency") or "").strip().upper()
    if received_currency != expected_currency:
        raise ValueError("settlement currency does not match quote")

    receipt = _receipt_basis(
        case,
        quote,
        settlement_class=REAL_SETTLEMENT,
        provider=provider,
        provider_receipt_id=provider_receipt_id,
        external_funds_moved=True,
        revenue_recognised=True,
        market_validation_eligible=True,
        fulfilment_eligible=True,
        evidence_ref=evidence_ref,
    )
    receipt["settlement_receipt_sha256"] = _canonical_hash(receipt)
    return _persist_receipt(Path(state_root), case, receipt)


def record_controlled_test_settlement(
    state_root: Path,
    case_id: str,
    *,
    receipt_id: str,
    authorized_by: str,
    reason: str,
) -> dict[str, Any]:
    case = load_case(Path(state_root), str(case_id))
    if case is None:
        raise ValueError(f"customer case not found: {case_id}")
    quote = _canonical_quote(case)

    receipt_id = _required(receipt_id, "receipt_id")
    authorized_by = _required(authorized_by, "authorized_by")
    reason = _required(reason, "reason")
    evidence_ref = f"controlled-test:{receipt_id}"

    receipt = _receipt_basis(
        case,
        quote,
        settlement_class=CONTROLLED_TEST_SETTLEMENT,
        provider="dio_controlled_test",
        provider_receipt_id=receipt_id,
        external_funds_moved=False,
        revenue_recognised=False,
        market_validation_eligible=False,
        fulfilment_eligible=True,
        evidence_ref=evidence_ref,
        reason=reason,
        authorized_by=authorized_by,
        operator_self_transaction=True,
    )
    receipt["settlement_receipt_sha256"] = _canonical_hash(receipt)
    return _persist_receipt(Path(state_root), case, receipt)


def record_waived_settlement(
    state_root: Path,
    case_id: str,
    *,
    receipt_id: str,
    waived_by: str,
    reason: str,
) -> dict[str, Any]:
    case = load_case(Path(state_root), str(case_id))
    if case is None:
        raise ValueError(f"customer case not found: {case_id}")
    quote = _canonical_quote(case)

    receipt_id = _required(receipt_id, "receipt_id")
    waived_by = _required(waived_by, "waived_by")
    reason = _required(reason, "reason")
    evidence_ref = f"waiver:{receipt_id}"

    receipt = _receipt_basis(
        case,
        quote,
        settlement_class=WAIVED,
        provider="operator_waiver",
        provider_receipt_id=receipt_id,
        external_funds_moved=False,
        revenue_recognised=False,
        market_validation_eligible=False,
        fulfilment_eligible=True,
        evidence_ref=evidence_ref,
        reason=reason,
        waived_by=waived_by,
        operator_self_transaction=False,
    )
    receipt["settlement_receipt_sha256"] = _canonical_hash(receipt)
    return _persist_receipt(Path(state_root), case, receipt)


def settlement_truth(case: dict[str, Any]) -> dict[str, Any] | None:
    receipt = case.get("settlement") if isinstance(case, dict) else None
    if not isinstance(receipt, dict) or receipt.get("schema") != SETTLEMENT_RECEIPT_SCHEMA:
        return None
    return deepcopy(receipt)
