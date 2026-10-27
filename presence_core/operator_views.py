from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .customer_cases import list_cases, load_case
from .state import list_needs_you


def _open_needs_for_case(state_root: Path, case_id: str) -> list[dict[str, Any]]:
    return [row for row in list_needs_you(Path(state_root), 1000) if row.get("case_id") == case_id and row.get("state") == "open"]


def _commercial_card(case: dict[str, Any]) -> dict[str, Any]:
    commercial = dict(case.get("commercial") or {})
    return {
        "pricing_mode": commercial.get("pricing_mode"),
        "quote_state": commercial.get("quote_state"),
        "quote_recommendation": commercial.get("quote_recommendation"),
        "reference_band": commercial.get("reference_band"),
        "invoice_id": commercial.get("invoice_id"),
        "invoice_state": commercial.get("invoice_state"),
        "payment_state": commercial.get("payment_state"),
        "amount": commercial.get("amount"),
        "currency": commercial.get("currency"),
    }


def case_list_view(state_root: Path, limit: int = 100) -> dict[str, Any]:
    state_root = Path(state_root)
    rows = list_cases(state_root, max(1, int(limit)))
    items = []
    for case in rows:
        items.append({
            "case_id": case.get("case_id"),
            "product_id": case.get("product_id"),
            "stage": case.get("stage"),
            "contact_email": case.get("contact_email"),
            "channel_origins": list(case.get("channel_origins") or []),
            "updated_at": case.get("updated_at"),
            "last_customer_message_at": case.get("last_customer_message_at"),
            "commercial": _commercial_card(case),
            "needs_you_count": len(_open_needs_for_case(state_root, str(case.get("case_id") or ""))),
            "authority_created": False,
        })
    return {"schema": "dio.operator_case_list.v1", "count": len(items), "items": items, "authority_created": False, "external_effects": False}


def case_detail_view(state_root: Path, case_id: str) -> dict[str, Any]:
    state_root = Path(state_root)
    case = load_case(state_root, case_id)
    if case is None:
        raise KeyError(case_id)
    return {"schema": "dio.operator_case_detail.v1", "case": case, "open_needs_you": _open_needs_for_case(state_root, case_id), "authority_created": False, "external_effects": False}


def _amount(commercial: dict[str, Any], key: str) -> int:
    value = commercial.get(key)
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(round(float(value)))
    return 0


def commercial_pipeline_view(state_root: Path) -> dict[str, Any]:
    state_root = Path(state_root)
    cases = list_cases(state_root, 10000)
    stage_counts: Counter[str] = Counter()
    product_counts: Counter[str] = Counter()
    recommended = invoiced = verified_paid = 0
    for case in cases:
        stage_counts[str(case.get("stage") or "UNKNOWN")] += 1
        if case.get("product_id"):
            product_counts[str(case["product_id"])] += 1
        commercial = dict(case.get("commercial") or {})
        recommended += _amount(commercial, "quote_recommendation")
        amount = _amount(commercial, "amount")
        if str(commercial.get("invoice_state") or "") in {"drafted", "sent", "issued"}:
            invoiced += amount
        if str(commercial.get("payment_state") or "") == "verified":
            verified_paid += amount
    needs = list_needs_you(state_root, 10000)
    attention = [{"needs_you_id": row.get("needs_you_id"), "case_id": row.get("case_id"), "reason": row.get("reason"), "priority": row.get("priority"), "summary": row.get("summary"), "product": row.get("product")} for row in needs if row.get("state") == "open"]
    return {
        "schema": "dio.operator_commercial_pipeline.v1",
        "case_count": len(cases),
        "by_stage": dict(sorted(stage_counts.items())),
        "by_product": dict(sorted(product_counts.items())),
        "open_needs_you": len(attention),
        "attention": attention[:50],
        "values_zar": {"recommended": recommended, "invoiced": invoiced, "verified_paid": verified_paid},
        "value_boundary": "Recommended and invoiced values are not revenue. verified_paid includes only customer-case payment_state=verified.",
        "authority_created": False,
        "external_effects": False,
    }
