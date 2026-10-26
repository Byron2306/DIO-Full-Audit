from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .customer_cases import load_case, update_case
from products.commercial_pricing_registry import (
    COMMERCIAL_TIER_POLICY,
    build_commercial_pricing_registry,
)
from .state import write_json


QUOTE_SCHEMA = "dio.customer_quote.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _quote_root(state_root: Path) -> Path:
    return Path(state_root) / "customer_cases" / "quotes"


def _quote_path(
    state_root: Path,
    quote_id: str,
) -> Path:
    safe_id = "".join(
        c for c in str(quote_id)
        if c.isalnum() or c in "-_"
    )

    if not safe_id:
        raise ValueError("invalid quote_id")

    return _quote_root(state_root) / f"{safe_id}.json"


def _canonical_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(payload).hexdigest()


def evaluate_bounded_quote_authority(
    dio_root: Path,
    case: dict[str, Any],
) -> dict[str, Any]:
    commercial = case.get("commercial") or {}
    scope = case.get("scope") or {}
    attachments = case.get("attachments") or []

    result = {
        "schema": "dio.bounded_quote_authority.v1",
        "decision": "NEEDS_YOU",
        "reason": None,
        "case_id": case.get("case_id"),
        "product_id": case.get("product_id"),
        "buyer_class": commercial.get("buyer_class"),
        "amount_zar": commercial.get("recommended_amount_zar"),
        "autonomous_ceiling_zar": None,
        "operator_review_required": True,
        "authority_created": False,
        "external_effects": False,
    }

    if case.get("stage") != "PRICE_RECOMMENDED":
        result["reason"] = "case_not_price_recommended"
        return result

    product_name = str(case.get("product_id") or "").strip()
    if not product_name:
        result["reason"] = "missing_product"
        return result

    registry = build_commercial_pricing_registry(
        Path(dio_root)
    )

    product = next(
        (
            row
            for row in registry.get("products") or []
            if str(row.get("name") or "").strip()
            == product_name
        ),
        None,
    )

    if product is None:
        result["reason"] = "product_not_in_commercial_registry"
        return result

    buyer_class = str(
        commercial.get("buyer_class") or ""
    ).strip()

    buyer_scope = str(
        commercial.get("buyer_scope") or ""
    ).strip()

    evaluated_classes: list[str] = []

    if buyer_class:
        evaluated_classes = [buyer_class]
    elif buyer_scope:
        tier = next(
            (
                row
                for row in COMMERCIAL_TIER_POLICY
                if str(row.get("tier_id") or "")
                == buyer_scope
            ),
            None,
        )

        if tier is None:
            result["reason"] = "unknown_buyer_scope"
            return result

        evaluated_classes = list(
            tier.get("buyer_classes") or []
        )
    else:
        result["reason"] = "missing_buyer_context"
        return result

    low_risk_classes = {"C0", "C1", "C2", "C3"}

    if (
        not evaluated_classes
        or not set(evaluated_classes).issubset(
            low_risk_classes
        )
    ):
        result["reason"] = "buyer_class_requires_operator"
        return result

    supported_classes = set(
        product.get("buyer_classes") or []
    )

    if not set(evaluated_classes).issubset(
        supported_classes
    ):
        result["reason"] = "buyer_class_not_supported"
        return result

    result["buyer_scope"] = buyer_scope or None
    result["buyer_classes_evaluated"] = (
        evaluated_classes
    )

    if not buyer_class and len(evaluated_classes) == 1:
        result["buyer_class"] = evaluated_classes[0]

    amount = int(
        commercial.get("recommended_amount_zar")
        or 0
    )

    band = (
        commercial.get("governed_reference_band_zar")
        or product.get("reference_band_zar")
        or {}
    )

    low = int(band.get("min") or 0)
    high = int(band.get("max") or 0)

    ceiling = int(
        product.get("autonomous_quote_ceiling_zar")
        or 0
    )

    result["autonomous_ceiling_zar"] = ceiling

    if amount < 1:
        result["reason"] = "missing_recommended_amount"
        return result

    if low < 1 or high < low:
        result["reason"] = "invalid_governed_reference_band"
        return result

    if not (low <= amount <= high):
        result["reason"] = "amount_outside_governed_band"
        return result

    if ceiling < 1 or amount > ceiling:
        result["reason"] = "amount_above_autonomous_ceiling"
        return result

    if not attachments:
        result["reason"] = "missing_attachment_truth"
        return result

    attachment = attachments[0]
    source_sha = str(
        attachment.get("sha256") or ""
    ).strip().lower()

    if len(source_sha) != 64:
        result["reason"] = "missing_source_hash"
        return result

    quantity = int(
        scope.get("quantity")
        or commercial.get("scope_quantity")
        or 0
    )

    scope_unit = str(
        scope.get("primary_scope_unit")
        or commercial.get("scope_unit")
        or ""
    ).strip()

    if quantity < 1 or not scope_unit:
        result["reason"] = "missing_governed_scope"
        return result

    scope_sha = str(
        scope.get("scope_scan_sha256")
        or source_sha
    ).strip().lower()

    if scope_sha != source_sha:
        result["reason"] = "scope_source_mismatch"
        return result

    if bool(
        commercial.get("custom_discount_requested")
    ):
        result["reason"] = "custom_discount_requires_operator"
        return result

    if bool(
        commercial.get("bespoke_terms_requested")
    ):
        result["reason"] = "bespoke_terms_require_operator"
        return result

    if bool(
        commercial.get("regulatory_exception")
    ):
        result["reason"] = "regulatory_exception_requires_operator"
        return result

    result["decision"] = "ALLOW"
    result["reason"] = "bounded_quote_policy_satisfied"
    result["operator_review_required"] = False

    return result


def issue_bounded_quote(
    dio_root: Path,
    state_root: Path,
    *,
    case_id: str,
    quote_id: str,
    valid_until: str | None = None,
    payment_url: str | None = None,
) -> dict[str, Any]:
    state_root = Path(state_root)

    case = load_case(
        state_root,
        case_id,
    )

    if case is None:
        raise ValueError(
            f"customer case not found: {case_id}"
        )

    authority = evaluate_bounded_quote_authority(
        Path(dio_root),
        case,
    )

    if authority.get("decision") != "ALLOW":
        raise ValueError(
            "bounded quote authority denied: "
            + str(authority.get("reason") or "unknown")
        )

    commercial = case.get("commercial") or {}
    scope = case.get("scope") or {}
    attachments = case.get("attachments") or []

    attachment = attachments[0]

    amount = int(
        commercial.get("recommended_amount_zar")
        or 0
    )

    quantity = int(
        scope.get("quantity")
        or commercial.get("scope_quantity")
        or 0
    )

    scope_unit = str(
        scope.get("primary_scope_unit")
        or commercial.get("scope_unit")
        or ""
    ).strip()

    quote = {
        "schema": QUOTE_SCHEMA,
        "quote_id": quote_id,
        "case_id": case_id,
        "conversation_ids": list(
            case.get("conversation_ids") or []
        ),
        "customer_external_user_ids": list(
            (
                case.get("customer_identity")
                or {}
            ).get("external_user_ids")
            or []
        ),
        "product_id": case.get("product_id"),
        "attachment_id": attachment.get(
            "attachment_id"
        ),
        "original_file_name": attachment.get(
            "original_file_name"
        ),
        "source_sha256": attachment.get(
            "sha256"
        ),
        "scope_quantity": quantity,
        "scope_unit": scope_unit,
        "amount": amount,
        "currency": "ZAR",
        "pricing_state": commercial.get(
            "pricing_state"
        ),
        "quote_state": "approved",
        "approval": {
            "mode": "bounded_policy",
            "approved_by":
                "policy:bounded_quote_authority",
            "approved_at": _now(),
            "authority_basis": authority,
        },
        "valid_until": valid_until,
        "payment_url": (
            str(payment_url).strip()
            if payment_url
            else None
        ),
        "payment_state": "not_verified",
        "fulfilment_authority_created": False,
        "release_authority_created": False,
        "authority_created": False,
    }

    quote["quote_truth_sha256"] = (
        _canonical_hash(quote)
    )

    path = _quote_path(
        state_root,
        quote_id,
    )

    if path.exists():
        existing = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        if (
            existing.get("case_id") != case_id
            or existing.get("amount") != amount
            or existing.get("source_sha256")
            != attachment.get("sha256")
            or existing.get("scope_quantity")
            != quantity
        ):
            raise ValueError(
                "existing quote conflicts with "
                "current commercial truth"
            )

        return existing

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_json(path, quote)

    updated = update_case(
        state_root,
        case,
        stage="QUOTE_READY",
        patch={
            "commercial": {
                "quote_id": quote_id,
                "quote_state": "approved",
                "quote_recommendation": amount,
                "currency": "ZAR",
                "amount": amount,
                "quote_issue_authority": True,
                "operator_review_required": False,
                "quote_authority_basis":
                    authority,
            },
        },
        evidence_ref=f"quote:{quote_id}",
    )

    return {
        **quote,
        "case_stage": updated["stage"],
        "quote_path": str(path),
    }


def approve_quote(
    state_root: Path,
    *,
    case_id: str,
    quote_id: str,
    approved_by: str,
    valid_until: str | None = None,
    payment_url: str | None = None,
) -> dict[str, Any]:
    state_root = Path(state_root)

    case = load_case(state_root, case_id)

    if case is None:
        raise ValueError(
            f"customer case not found: {case_id}"
        )

    if case.get("stage") != "PRICE_RECOMMENDED":
        raise ValueError(
            "quote approval requires "
            "PRICE_RECOMMENDED stage"
        )

    commercial = case.get("commercial") or {}
    scope = case.get("scope") or {}
    attachments = case.get("attachments") or []

    if not attachments:
        raise ValueError(
            "quote approval requires attachment truth"
        )

    attachment = attachments[0]

    amount = int(
        commercial.get("recommended_amount_zar")
        or 0
    )

    quantity = int(
        scope.get("quantity")
        or commercial.get("scope_quantity")
        or 0
    )

    scope_unit = str(
        scope.get("primary_scope_unit")
        or commercial.get("scope_unit")
        or ""
    ).strip()

    if amount < 1:
        raise ValueError(
            "quote approval requires "
            "recommended amount"
        )

    if quantity < 1 or not scope_unit:
        raise ValueError(
            "quote approval requires governed scope"
        )

    if not bool(
        commercial.get("operator_review_required")
    ):
        raise ValueError(
            "quote approval requires "
            "operator-review pricing state"
        )

    approved_by = str(approved_by or "").strip()

    if not approved_by:
        raise ValueError("approved_by is required")

    quote = {
        "schema": QUOTE_SCHEMA,
        "quote_id": quote_id,
        "case_id": case_id,
        "conversation_ids": list(
            case.get("conversation_ids") or []
        ),
        "customer_external_user_ids": list(
            (
                case.get("customer_identity")
                or {}
            ).get("external_user_ids")
            or []
        ),
        "product_id": case.get("product_id"),
        "attachment_id": attachment.get(
            "attachment_id"
        ),
        "original_file_name": attachment.get(
            "original_file_name"
        ),
        "source_sha256": attachment.get(
            "sha256"
        ),
        "scope_quantity": quantity,
        "scope_unit": scope_unit,
        "amount": amount,
        "currency": "ZAR",
        "pricing_state": commercial.get(
            "pricing_state"
        ),
        "quote_state": "approved",
        "approval": {
            "approved_by": approved_by,
            "approved_at": _now(),
        },
        "valid_until": valid_until,
        "payment_url": (
            str(payment_url).strip()
            if payment_url
            else None
        ),
        "payment_state": "not_verified",
        "fulfilment_authority_created": False,
        "release_authority_created": False,
        "authority_created": False,
    }

    quote["quote_truth_sha256"] = (
        _canonical_hash(quote)
    )

    path = _quote_path(
        state_root,
        quote_id,
    )

    if path.exists():
        existing = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        comparable_existing = dict(existing)
        comparable_existing.pop(
            "quote_truth_sha256",
            None,
        )

        comparable_quote = dict(quote)
        comparable_quote.pop(
            "quote_truth_sha256",
            None,
        )

        # Existing approval is authoritative.
        # Never silently rewrite it.
        if (
            existing.get("case_id") != case_id
            or existing.get("amount") != amount
            or existing.get(
                "source_sha256"
            ) != attachment.get("sha256")
            or existing.get(
                "scope_quantity"
            ) != quantity
        ):
            raise ValueError(
                "existing quote conflicts with "
                "current commercial truth"
            )

        return existing

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_json(path, quote)

    updated = update_case(
        state_root,
        case,
        stage="QUOTE_READY",
        patch={
            "commercial": {
                "quote_id": quote_id,
                "quote_state": "approved",
                "quote_recommendation": amount,
                "currency": "ZAR",
                "amount": amount,
                "quote_issue_authority": True,
            },
            "last_operator_action_at": (
                quote["approval"][
                    "approved_at"
                ]
            ),
        },
        evidence_ref=f"quote:{quote_id}",
    )

    return {
        **quote,
        "case_stage": updated["stage"],
        "quote_path": str(path),
    }
