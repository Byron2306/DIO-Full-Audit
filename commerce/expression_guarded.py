from __future__ import annotations

from typing import Any

from conversation_core.context import expression_context_view

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

CONVERSATION_AWARE_ACTS = {
    CommunicativeAct.INBOUND_REPLY,
    CommunicativeAct.QUALIFIED_LEAD_REPLY,
    CommunicativeAct.PILOT_INVITATION,
    CommunicativeAct.FOLLOW_UP,
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


def _conversation_view(cso: dict[str, Any], context: dict[str, Any] | None) -> dict[str, Any] | None:
    raw = (context or {}).get("conversation_context")
    if raw is None:
        return None
    view = expression_context_view(raw)
    cso_conversation = str((cso.get("lineage") or {}).get("conversation_id") or "").strip()
    if cso_conversation and view["conversation_id"] != cso_conversation:
        raise ValueError(
            "conversation_context conversation_id does not match the Commercial Semantic Object lineage"
        )
    return view


def _attach_context_policy(plan: dict[str, Any], view: dict[str, Any] | None) -> dict[str, Any]:
    if view is None:
        return plan
    plan["conversation_context"] = view
    policy = plan.setdefault("generation_policy", {})
    policy.update({
        "conversation_context_may_shape_expression": True,
        "conversation_context_may_establish_fact": False,
        "conversation_context_may_grant_consent": False,
        "conversation_context_may_set_scope": False,
        "conversation_context_may_set_budget": False,
        "conversation_context_may_grant_execution_authority": False,
    })
    return plan


def plan_expression(
    cso: dict[str, Any],
    communicative_act: CommunicativeAct | str,
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assert_act_relationship(cso, communicative_act)
    plan = _plan_expression(cso, communicative_act, context=context)
    return _attach_context_policy(plan, _conversation_view(cso, context))


def _context_paragraph(act: CommunicativeAct, view: dict[str, Any]) -> str | None:
    request = view.get("last_requested_action") or {}
    request_text = str(request.get("text") or "").strip()[:260]
    questions = view.get("open_questions") or []
    question_text = str((questions[-1] if questions else {}).get("text") or "").strip()[:260]

    if act is CommunicativeAct.INBOUND_REPLY and request_text:
        return f"I’m keeping this reply focused on the request in your latest message: “{request_text}”"
    if act is CommunicativeAct.QUALIFIED_LEAD_REPLY and request_text:
        return f"Your latest message asks us to focus on: “{request_text}”"
    if act is CommunicativeAct.PILOT_INVITATION and request_text:
        return f"I’ve kept the pilot suggestion aligned to your latest recorded request: “{request_text}”"
    if act is CommunicativeAct.FOLLOW_UP and question_text:
        return (
            "The thread still contains this question with no later recorded sent reply from DIO: "
            f"“{question_text}”"
        )
    return None


def _rebuild_body(expression: dict[str, Any]) -> None:
    parts = [
        expression.get("greeting"),
        expression.get("intro"),
        *(expression.get("paragraphs") or []),
        expression.get("cta"),
        expression.get("secondary_cta"),
        expression.get("caution"),
    ]
    body = "\n\n".join(str(part).strip() for part in parts if str(part or "").strip())
    expression["body"] = body
    expression["word_count"] = len(body.split())


def _apply_conversation_expression(
    expression: dict[str, Any],
    act: CommunicativeAct,
    view: dict[str, Any] | None,
) -> dict[str, Any]:
    _attach_context_policy(expression["plan"], view)
    if view is None or act not in CONVERSATION_AWARE_ACTS:
        return expression
    paragraph = _context_paragraph(act, view)
    if paragraph:
        paragraphs = list(expression.get("paragraphs") or [])
        paragraphs.insert(0, paragraph)
        expression["paragraphs"] = paragraphs
        _rebuild_body(expression)
        max_words = ACT_CONTRACTS[act].max_words
        if expression["word_count"] > max_words:
            expression["paragraphs"] = paragraphs[1:]
            _rebuild_body(expression)
    return expression


def render_expression(
    cso: dict[str, Any],
    communicative_act: CommunicativeAct | str,
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    act = _act(communicative_act)
    assert_act_relationship(cso, act)
    expression = _render_expression(cso, act, context=context)
    return _apply_conversation_expression(expression, act, _conversation_view(cso, context))


__all__ = [
    "ACT_CONTRACTS",
    "CONVERSATION_AWARE_ACTS",
    "CommunicativeAct",
    "PUBLIC_ACTS",
    "RELATIONSHIP_ALLOWLIST",
    "assert_act_relationship",
    "expression_contract",
    "plan_expression",
    "render_expression",
]
