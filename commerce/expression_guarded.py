from __future__ import annotations

from typing import Any

from .expression import (
    ACT_CONTRACTS,
    CommunicativeAct,
    expression_contract,
    plan_expression as _plan_expression,
    render_expression as _render_expression,
)


PUBLIC_ACTS = {
    CommunicativeAct.LINKEDIN_POST,
    CommunicativeAct.CLASSIFIED_LISTING,
    CommunicativeAct.PAID_AD,
    CommunicativeAct.VIDEO_CTA,
}

RELATIONSHIP_ALLOWLIST: dict[CommunicativeAct, set[str]] = {
    CommunicativeAct.COLD_PERMISSION_REQUEST: {"cold"},
    CommunicativeAct.INBOUND_REPLY: {"inbound", "new", "pending", "qualified", "customer", "active_product_workflow"},
    CommunicativeAct.QUALIFIED_LEAD_REPLY: {"qualified", "customer", "active_product_workflow"},
    CommunicativeAct.PILOT_INVITATION: {"inbound", "pending", "qualified", "customer"},
    CommunicativeAct.FOLLOW_UP: {"inbound", "pending", "qualified", "customer", "active_product_workflow"},
    CommunicativeAct.PROPOSAL: {"qualified", "customer"},
    CommunicativeAct.QUOTE: {"qualified", "customer"},
    CommunicativeAct.INVOICE_NOTICE: {"customer", "active_product_workflow"},
    CommunicativeAct.INTAKE_REQUEST: {"qualified", "customer", "active_product_workflow"},
    CommunicativeAct.DELIVERY: {"customer", "active_product_workflow"},
    CommunicativeAct.REQUEST_FOR_QUOTATION: {"vendor"},
}


def _act(value: CommunicativeAct | str) -> CommunicativeAct:
    return value if isinstance(value, CommunicativeAct) else CommunicativeAct(str(value))


def _relationship(cso: dict[str, Any]) -> tuple[str | None, str]:
    item = ((cso.get("subject") or {}).get("relationship_state") or {})
    return (str(item.get("value") or "").strip().lower() or None, str(item.get("status") or "unknown"))


def assert_act_relationship(cso: dict[str, Any], communicative_act: CommunicativeAct | str) -> None:
    act = _act(communicative_act)
    if act in PUBLIC_ACTS:
        return
    allowed = RELATIONSHIP_ALLOWLIST.get(act)
    if not allowed:
        return
    relationship, status = _relationship(cso)
    if status != "verified":
        raise ValueError(f"{act.value} requires a verified relationship state")
    if relationship not in allowed:
        raise ValueError(
            f"{act.value} is incompatible with relationship_state={relationship}; "
            f"allowed={sorted(allowed)}"
        )


def plan_expression(
    cso: dict[str, Any],
    communicative_act: CommunicativeAct | str,
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assert_act_relationship(cso, communicative_act)
    return _plan_expression(cso, communicative_act, context=context)


def render_expression(
    cso: dict[str, Any],
    communicative_act: CommunicativeAct | str,
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assert_act_relationship(cso, communicative_act)
    return _render_expression(cso, communicative_act, context=context)


__all__ = [
    "ACT_CONTRACTS",
    "CommunicativeAct",
    "PUBLIC_ACTS",
    "RELATIONSHIP_ALLOWLIST",
    "assert_act_relationship",
    "expression_contract",
    "plan_expression",
    "render_expression",
]
