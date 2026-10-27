from __future__ import annotations

from pathlib import Path
from typing import Any

from .customer_cases import CASE_STAGES, load_case, update_case
from .state import create_needs_you, list_needs_you, write_json


COMMERCIAL_NEEDS_YOU_REASONS = {
    "scope_approval_required",
    "quote_approval_required",
    "invoice_send_approval",
    "attachment_review",
    "release_approval",
}

_REASON_STAGE = {
    "scope_approval_required": "NEEDS_YOU",
    "quote_approval_required": "NEEDS_YOU",
    "invoice_send_approval": "INVOICE_SEND_APPROVAL",
    "attachment_review": "NEEDS_YOU",
    "release_approval": "RELEASE_APPROVAL",
}
_STAGE_INDEX = {stage: index for index, stage in enumerate(CASE_STAGES)}


def _load_required_case(state_root: Path, case_id: str) -> dict[str, Any]:
    case = load_case(Path(state_root), case_id)
    if case is None:
        raise ValueError(f"customer case not found: {case_id}")
    return case


def _safe_advance(state_root: Path, case: dict[str, Any], *, target_stage: str | None, patch: dict[str, Any] | None = None, evidence_ref: str | None = None) -> dict[str, Any]:
    current = str(case.get("stage") or "NEW_LEAD")
    stage = None
    if target_stage in _STAGE_INDEX and current in _STAGE_INDEX and _STAGE_INDEX[str(target_stage)] >= _STAGE_INDEX[current]:
        stage = target_stage
    return update_case(Path(state_root), case, stage=stage, patch=patch, evidence_ref=evidence_ref)


def ensure_commercial_needs_you(state_root: Path, *, case_id: str, reason: str, summary: str, product: str | None, priority: str = "normal") -> dict[str, Any]:
    if reason not in COMMERCIAL_NEEDS_YOU_REASONS:
        raise ValueError(f"unsupported commercial Needs You reason: {reason}")
    state_root = Path(state_root)
    case = _load_required_case(state_root, case_id)
    for item in list_needs_you(state_root, 1000):
        if item.get("case_id") == case_id and item.get("reason") == reason and item.get("state") == "open":
            needs_ids = list(case.get("needs_you_ids") or [])
            if item["needs_you_id"] not in needs_ids:
                needs_ids.append(item["needs_you_id"])
                _safe_advance(state_root, case, target_stage=_REASON_STAGE.get(reason), patch={"needs_you_ids": needs_ids}, evidence_ref=f"needs_you:{item['needs_you_id']}")
            return item
    item = create_needs_you(state_root, reason=reason, conversation_id=str((case.get("conversation_ids") or [case_id])[0]), product=product or case.get("product_id"), summary=summary, priority=priority)
    item["case_id"] = case_id
    item["commercial_gate"] = True
    item["authority_created"] = False
    write_json(state_root / "needs_you" / f"{item['needs_you_id']}.json", item)
    needs_ids = list(case.get("needs_you_ids") or [])
    if item["needs_you_id"] not in needs_ids:
        needs_ids.append(item["needs_you_id"])
    _safe_advance(state_root, case, target_stage=_REASON_STAGE.get(reason), patch={"needs_you_ids": needs_ids, "authority_created": False}, evidence_ref=f"needs_you:{item['needs_you_id']}")
    return item


def _need_reason(recommendation: dict[str, Any]) -> str:
    reason = str(recommendation.get("reason") or "")
    if reason in {"scope_exceeds_governed_offer", "enterprise_or_industrial_scope"}:
        return "scope_approval_required"
    return "quote_approval_required"


def _commercial_patch(recommendation: dict[str, Any]) -> dict[str, Any]:
    reference_band = recommendation.get("reference_band_zar")
    if not isinstance(reference_band, dict):
        low = recommendation.get("min_amount")
        high = recommendation.get("max_amount")
        reference_band = {"min": low, "max": high} if low is not None and high is not None else None
    return {
        "pricing_mode": recommendation.get("mode"),
        "reference_offer": recommendation.get("offer_id") or recommendation.get("product_name"),
        "reference_band": reference_band,
        "quote_recommendation": recommendation.get("recommended_amount"),
        "quote_reasoning": [str(recommendation.get("reasoning") or recommendation.get("reason") or "")],
        "quote_state": "needs_operator" if recommendation.get("mode") == "needs_operator" else "recommended_not_issued",
        "currency": recommendation.get("currency") or ("ZAR" if reference_band else None),
        "pricing_state": recommendation.get("pricing_state"),
        "estimate_not_invoice": bool(recommendation.get("estimate_not_invoice", True)),
    }


def apply_quote_recommendation(state_root: Path, case_id: str, recommendation: dict[str, Any]) -> dict[str, Any]:
    state_root = Path(state_root)
    case = _load_required_case(state_root, case_id)
    mode = str(recommendation.get("mode") or "")
    commercial = _commercial_patch(recommendation)
    if mode == "needs_operator":
        reason = _need_reason(recommendation)
        band = recommendation.get("reference_band_zar") or {}
        band_text = ""
        if isinstance(band, dict) and band.get("min") is not None and band.get("max") is not None:
            band_text = f" Reference hypothesis R{band['min']}-R{band['max']}."
        item = ensure_commercial_needs_you(state_root, case_id=case_id, reason=reason, product=str(recommendation.get("product_id") or case.get("product_id") or "") or None, summary=f"Review pricing/scope for case {case_id}.{band_text} Reason: {recommendation.get('reason') or 'operator review required'}", priority="normal")
        case = _load_required_case(state_root, case_id)
        case = _safe_advance(state_root, case, target_stage="NEEDS_YOU", patch={"commercial": commercial, "authority_created": False}, evidence_ref=f"pricing:{item['needs_you_id']}")
        return {"schema": "dio.customer_case_quote_projection.v1", "case_id": case_id, "stage": case["stage"], "needs_you_id": item["needs_you_id"], "quote_issued": False, "invoice_created": False, "authority_created": False}
    target_stage = "PRICE_RECOMMENDED" if mode in {"registry_estimate", "known_band", "scope_sensitive"} else None
    case = _safe_advance(state_root, case, target_stage=target_stage, patch={"commercial": commercial, "authority_created": False}, evidence_ref=f"pricing:{mode or 'unresolved'}")
    return {"schema": "dio.customer_case_quote_projection.v1", "case_id": case_id, "stage": case["stage"], "needs_you_id": None, "quote_issued": False, "invoice_created": False, "authority_created": False}
