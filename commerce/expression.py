from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Callable

from .semantic import assert_valid_commercial_semantic_object


EXPRESSION_SCHEMA = "dio.commercial_expression.v1"
PLAN_SCHEMA = "dio.commercial_expression_plan.v1"


class CommunicativeAct(str, Enum):
    COLD_PERMISSION_REQUEST = "cold_permission_request"
    INBOUND_REPLY = "inbound_reply"
    QUALIFIED_LEAD_REPLY = "qualified_lead_reply"
    PILOT_INVITATION = "pilot_invitation"
    FOLLOW_UP = "follow_up"
    PROPOSAL = "proposal"
    QUOTE = "quote"
    INVOICE_NOTICE = "invoice_notice"
    INTAKE_REQUEST = "intake_request"
    DELIVERY = "delivery"
    REQUEST_FOR_QUOTATION = "request_for_quotation"
    LINKEDIN_POST = "linkedin_post"
    CLASSIFIED_LISTING = "classified_listing"
    PAID_AD = "paid_ad"
    VIDEO_CTA = "video_cta"


@dataclass(frozen=True)
class ActContract:
    channel: str
    objective: str
    relationship_mode: str
    max_words: int
    assumption_budget: int
    allow_inferred_need: bool
    allow_inferred_strategy: bool
    proof_mode: str
    cta_mode: str
    human_approval_required: bool
    personalisation: str


ACT_CONTRACTS: dict[CommunicativeAct, ActContract] = {
    CommunicativeAct.COLD_PERMISSION_REQUEST: ActContract(
        channel="email",
        objective="ask permission to send one bounded proof example",
        relationship_mode="cold",
        max_words=170,
        assumption_budget=0,
        allow_inferred_need=False,
        allow_inferred_strategy=True,
        proof_mode="proof_reference_only",
        cta_mode="binary_permission",
        human_approval_required=True,
        personalisation="public_organisation_identity_only",
    ),
    CommunicativeAct.INBOUND_REPLY: ActContract(
        channel="email",
        objective="acknowledge the inbound message and answer only what is supported",
        relationship_mode="inbound",
        max_words=220,
        assumption_budget=1,
        allow_inferred_need=True,
        allow_inferred_strategy=True,
        proof_mode="relevant_proof",
        cta_mode="clarify_or_continue",
        human_approval_required=True,
        personalisation="verified_conversation_context",
    ),
    CommunicativeAct.QUALIFIED_LEAD_REPLY: ActContract(
        channel="email",
        objective="advance a qualified lead using verified need, scope and next action",
        relationship_mode="qualified",
        max_words=260,
        assumption_budget=1,
        allow_inferred_need=True,
        allow_inferred_strategy=True,
        proof_mode="relevant_proof",
        cta_mode="concrete_next_step",
        human_approval_required=True,
        personalisation="verified_and_explicitly_inferred_context",
    ),
    CommunicativeAct.PILOT_INVITATION: ActContract(
        channel="email",
        objective="offer a bounded pilot without implying an agreed purchase",
        relationship_mode="permissioned_or_inbound",
        max_words=240,
        assumption_budget=1,
        allow_inferred_need=True,
        allow_inferred_strategy=True,
        proof_mode="proof_first",
        cta_mode="accept_decline_or_adjust",
        human_approval_required=True,
        personalisation="verified_context",
    ),
    CommunicativeAct.FOLLOW_UP: ActContract(
        channel="email",
        objective="continue an existing thread without manufacturing urgency",
        relationship_mode="existing_thread",
        max_words=150,
        assumption_budget=0,
        allow_inferred_need=False,
        allow_inferred_strategy=True,
        proof_mode="minimal",
        cta_mode="continue_or_close",
        human_approval_required=True,
        personalisation="thread_bound",
    ),
    CommunicativeAct.PROPOSAL: ActContract(
        channel="document_or_email",
        objective="state problem, scope, proof, boundaries and next step without exceeding qualified facts",
        relationship_mode="qualified",
        max_words=700,
        assumption_budget=0,
        allow_inferred_need=True,
        allow_inferred_strategy=True,
        proof_mode="proof_and_boundaries",
        cta_mode="approve_revise_decline",
        human_approval_required=True,
        personalisation="qualified_context",
    ),
    CommunicativeAct.QUOTE: ActContract(
        channel="document_or_email",
        objective="communicate an operator-authorised price for a bounded scope",
        relationship_mode="qualified",
        max_words=360,
        assumption_budget=0,
        allow_inferred_need=False,
        allow_inferred_strategy=False,
        proof_mode="scope_reference",
        cta_mode="accept_or_query",
        human_approval_required=True,
        personalisation="verified_scope_only",
    ),
    CommunicativeAct.INVOICE_NOTICE: ActContract(
        channel="email",
        objective="notify a customer of an authorised invoice or payment request",
        relationship_mode="customer",
        max_words=220,
        assumption_budget=0,
        allow_inferred_need=False,
        allow_inferred_strategy=False,
        proof_mode="transaction_reference",
        cta_mode="pay_or_query",
        human_approval_required=True,
        personalisation="verified_transaction_only",
    ),
    CommunicativeAct.INTAKE_REQUEST: ActContract(
        channel="email",
        objective="request the exact material needed for an opened workflow",
        relationship_mode="customer_or_qualified",
        max_words=260,
        assumption_budget=0,
        allow_inferred_need=False,
        allow_inferred_strategy=False,
        proof_mode="workflow_reference",
        cta_mode="supply_material",
        human_approval_required=True,
        personalisation="verified_workflow_only",
    ),
    CommunicativeAct.DELIVERY: ActContract(
        channel="email",
        objective="deliver or announce an approved output without adding new claims",
        relationship_mode="customer",
        max_words=240,
        assumption_budget=0,
        allow_inferred_need=False,
        allow_inferred_strategy=False,
        proof_mode="approved_output_only",
        cta_mode="acknowledge_or_request_revision",
        human_approval_required=True,
        personalisation="verified_transaction_only",
    ),
    CommunicativeAct.REQUEST_FOR_QUOTATION: ActContract(
        channel="email",
        objective="request a bounded vendor quote without authorising spend",
        relationship_mode="vendor",
        max_words=320,
        assumption_budget=0,
        allow_inferred_need=False,
        allow_inferred_strategy=True,
        proof_mode="brief_reference",
        cta_mode="return_itemised_quote",
        human_approval_required=True,
        personalisation="verified_vendor_route",
    ),
    CommunicativeAct.LINKEDIN_POST: ActContract(
        channel="linkedin",
        objective="publish a proof-led professional post for a market segment",
        relationship_mode="public",
        max_words=260,
        assumption_budget=1,
        allow_inferred_need=True,
        allow_inferred_strategy=True,
        proof_mode="public_proof_only",
        cta_mode="inspect_or_enquire",
        human_approval_required=True,
        personalisation="none",
    ),
    CommunicativeAct.CLASSIFIED_LISTING: ActContract(
        channel="listing",
        objective="describe a bounded service offer in searchable factual language",
        relationship_mode="public",
        max_words=240,
        assumption_budget=0,
        allow_inferred_need=False,
        allow_inferred_strategy=True,
        proof_mode="public_proof_only",
        cta_mode="request_details",
        human_approval_required=True,
        personalisation="none",
    ),
    CommunicativeAct.PAID_AD: ActContract(
        channel="paid_media",
        objective="create a compact proof-led ad without guaranteed outcomes or customer-specific claims",
        relationship_mode="public",
        max_words=90,
        assumption_budget=0,
        allow_inferred_need=False,
        allow_inferred_strategy=True,
        proof_mode="public_proof_only",
        cta_mode="inspect_proof",
        human_approval_required=True,
        personalisation="segment_only",
    ),
    CommunicativeAct.VIDEO_CTA: ActContract(
        channel="video",
        objective="end proof content with one bounded next action",
        relationship_mode="public",
        max_words=45,
        assumption_budget=0,
        allow_inferred_need=False,
        allow_inferred_strategy=True,
        proof_mode="proof_reference_only",
        cta_mode="one_bounded_action",
        human_approval_required=True,
        personalisation="none",
    ),
}


def _act(value: CommunicativeAct | str) -> CommunicativeAct:
    return value if isinstance(value, CommunicativeAct) else CommunicativeAct(str(value))


def _semantic_at(cso: dict[str, Any], path: str) -> dict[str, Any]:
    current: Any = cso
    for part in path.split("."):
        if not isinstance(current, dict):
            return {"value": None, "status": "unknown", "source_refs": []}
        current = current.get(part)
    if not isinstance(current, dict) or "status" not in current:
        return {"value": None, "status": "unknown", "source_refs": []}
    return current


def _usable(item: dict[str, Any], *, allow_inferred: bool) -> bool:
    status = item.get("status")
    return status == "verified" or (allow_inferred and status == "inferred")


def _field(
    cso: dict[str, Any],
    path: str,
    *,
    allow_inferred: bool,
) -> dict[str, Any] | None:
    item = _semantic_at(cso, path)
    if not _usable(item, allow_inferred=allow_inferred):
        return None
    return {
        "path": path,
        "value": item.get("value"),
        "status": item.get("status"),
        "source_refs": list(item.get("source_refs") or []),
        "authority": item.get("authority"),
        "method": item.get("method"),
    }


def _market_field(cso: dict[str, Any], path: str, *, allow_inferred: bool = True) -> dict[str, Any] | None:
    return _field(cso, f"market_context.{path}", allow_inferred=allow_inferred)


def _safe_context(context: dict[str, Any] | None) -> dict[str, Any]:
    context = context or {}
    allowed: dict[str, Any] = {}
    verified_context = context.get("verified_context") or {}
    if not isinstance(verified_context, dict):
        raise ValueError("verified_context must be a mapping")
    for name, item in verified_context.items():
        if not isinstance(item, dict):
            raise ValueError(f"verified_context.{name} must be an object")
        value = item.get("value")
        refs = item.get("source_refs")
        if value in (None, "") or not isinstance(refs, list) or not refs:
            raise ValueError(f"verified_context.{name} requires value and source_refs")
        allowed[name] = {
            "value": value,
            "source_refs": [str(ref) for ref in refs if str(ref).strip()],
            "authority": item.get("authority") or "caller_verified_context",
        }
    return allowed


def plan_expression(
    cso: dict[str, Any],
    communicative_act: CommunicativeAct | str,
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an act-specific expression plan from one immutable semantic truth object.

    The planner does not grant authority and does not turn unknowns into prose. It tells
    a deterministic or probabilistic renderer which meaning it may express and how.
    """
    assert_valid_commercial_semantic_object(cso)
    act = _act(communicative_act)
    contract = ACT_CONTRACTS[act]
    verified_context = _safe_context(context)

    product = _field(cso, "commercial.product", allow_inferred=False)
    offer = _field(cso, "commercial.offer", allow_inferred=contract.allow_inferred_strategy)
    organisation = _field(cso, "subject.organisation", allow_inferred=False)
    relationship = _field(cso, "subject.relationship_state", allow_inferred=False)
    consent = _field(cso, "subject.consent_state", allow_inferred=False)
    job = _field(cso, "need.job_to_be_done", allow_inferred=contract.allow_inferred_need)
    pain = _field(cso, "need.workflow_pain", allow_inferred=contract.allow_inferred_need)
    trigger = _field(cso, "need.trigger", allow_inferred=contract.allow_inferred_need)
    why_now = _field(cso, "need.why_now", allow_inferred=contract.allow_inferred_need)
    next_action = _field(cso, "strategy.desired_next_action", allow_inferred=contract.allow_inferred_strategy)
    channel = _field(cso, "strategy.channel", allow_inferred=contract.allow_inferred_strategy)
    public_segment = _market_field(cso, "audience.public_segment", allow_inferred=False)
    desired_reward = _market_field(cso, "audience.desired_reward", allow_inferred=True)
    likely_next_action = _market_field(cso, "audience.likely_next_action", allow_inferred=True)

    if product is None and "product" not in verified_context:
        raise ValueError(f"{act.value} requires a verified product")

    direct_external = {
        CommunicativeAct.COLD_PERMISSION_REQUEST,
        CommunicativeAct.INBOUND_REPLY,
        CommunicativeAct.QUALIFIED_LEAD_REPLY,
        CommunicativeAct.PILOT_INVITATION,
        CommunicativeAct.FOLLOW_UP,
        CommunicativeAct.PROPOSAL,
        CommunicativeAct.QUOTE,
        CommunicativeAct.INVOICE_NOTICE,
        CommunicativeAct.INTAKE_REQUEST,
        CommunicativeAct.DELIVERY,
        CommunicativeAct.REQUEST_FOR_QUOTATION,
    }
    authority_state = str((cso.get("authority") or {}).get("authority_state") or "")
    if act in direct_external and authority_state in {"market_strategy_public_content_only", "research_only"}:
        raise ValueError(f"{act.value} is not permitted by authority_state={authority_state}")
    if act is CommunicativeAct.COLD_PERMISSION_REQUEST and consent:
        consent_value = str(consent.get("value") or "").lower()
        if "do_not_contact" in consent_value or "blocked" in consent_value:
            raise ValueError("cold permission request is blocked by consent state")

    facts = [row for row in (product, organisation, relationship, consent, channel, public_segment) if row]
    hypotheses = [row for row in (offer, job, pain, trigger, why_now, next_action, desired_reward, likely_next_action) if row and row.get("status") == "inferred"]
    verified_need = [row for row in (job, pain, trigger, why_now) if row and row.get("status") == "verified"]
    facts.extend(verified_need)

    unknowns: list[str] = []
    for path in (
        "subject.organisation",
        "subject.buyer_role",
        "need.job_to_be_done",
        "need.workflow_pain",
        "need.trigger",
        "need.why_now",
        "commercial.scope",
    ):
        if _semantic_at(cso, path).get("status") == "unknown":
            unknowns.append(path)

    plan = {
        "schema": PLAN_SCHEMA,
        "semantic_object_id": cso["object_id"],
        "communicative_act": act.value,
        "contract": asdict(contract),
        "authority_state": authority_state,
        "facts": facts,
        "hypotheses": hypotheses,
        "unknowns": unknowns,
        "proof": list((cso.get("proof") or {}).get("relevant_proof") or []),
        "permitted_claims": list((cso.get("proof") or {}).get("permitted_claims") or []),
        "prohibited_claims": list((cso.get("proof") or {}).get("prohibited_claims") or []),
        "verified_context": verified_context,
        "generation_policy": {
            "may_paraphrase": True,
            "may_add_facts": False,
            "may_promote_inference_to_fact": False,
            "may_fill_unknowns": False,
            "must_preserve_claim_status": True,
            "must_preserve_source_refs": True,
            "human_approval_required": contract.human_approval_required,
        },
    }
    return plan


def _plan_value(plan: dict[str, Any], path: str, default: str = "") -> str:
    for group in ("facts", "hypotheses"):
        for row in plan.get(group) or []:
            if row.get("path") == path and row.get("value") not in (None, ""):
                value = row["value"]
                if isinstance(value, dict):
                    return str(value.get("name") or value.get("label") or value.get("id") or default)
                return str(value)
    return default


def _context_value(plan: dict[str, Any], name: str, default: str = "") -> str:
    item = (plan.get("verified_context") or {}).get(name) or {}
    return str(item.get("value") or default)


def _product(plan: dict[str, Any]) -> str:
    return _plan_value(plan, "commercial.product") or _context_value(plan, "product") or "the workflow"


def _organisation(plan: dict[str, Any]) -> str:
    return _plan_value(plan, "subject.organisation") or _context_value(plan, "organisation")


def _job(plan: dict[str, Any]) -> str:
    return _plan_value(plan, "need.job_to_be_done")


def _pain(plan: dict[str, Any]) -> str:
    return _plan_value(plan, "need.workflow_pain")


def _scope(plan: dict[str, Any]) -> str:
    return _plan_value(plan, "commercial.scope") or _context_value(plan, "scope")


def _proof_line(plan: dict[str, Any]) -> str:
    proof_summary = _context_value(plan, "proof_summary")
    if proof_summary:
        return proof_summary
    proof = plan.get("proof") or []
    if proof:
        return "A reviewable proof artefact is available for inspection."
    return "The next step can remain bounded and reviewable."


def _expression(
    plan: dict[str, Any],
    *,
    subject: str | None,
    greeting: str | None,
    intro: str,
    paragraphs: list[str],
    bullets: list[str] | None = None,
    cta: str,
    secondary_cta: str | None = None,
    caution: str | None = None,
    format_name: str = "message",
) -> dict[str, Any]:
    parts = [greeting, intro, *paragraphs, cta, secondary_cta, caution]
    body = "\n\n".join(str(part).strip() for part in parts if str(part or "").strip())
    word_count = len(body.split())
    max_words = int((plan.get("contract") or {}).get("max_words") or 0)
    if max_words and word_count > max_words:
        raise ValueError(f"{plan['communicative_act']} renderer exceeded max_words ({word_count}>{max_words})")
    return {
        "schema": EXPRESSION_SCHEMA,
        "semantic_object_id": plan["semantic_object_id"],
        "communicative_act": plan["communicative_act"],
        "channel": (plan.get("contract") or {}).get("channel"),
        "format": format_name,
        "subject": subject,
        "greeting": greeting,
        "intro": intro,
        "paragraphs": paragraphs,
        "bullets": bullets or [],
        "cta": cta,
        "secondary_cta": secondary_cta,
        "caution": caution,
        "body": body,
        "word_count": word_count,
        "claim_sources": [
            {"path": row.get("path"), "status": row.get("status"), "source_refs": row.get("source_refs") or []}
            for row in [*(plan.get("facts") or []), *(plan.get("hypotheses") or [])]
        ],
        "prohibited_claims": list(plan.get("prohibited_claims") or []),
        "human_approval_required": bool((plan.get("generation_policy") or {}).get("human_approval_required")),
        "plan": plan,
    }


def _cold_permission(plan: dict[str, Any]) -> dict[str, Any]:
    product = _product(plan)
    organisation = _organisation(plan)
    subject = f"May I send {organisation + ' ' if organisation else ''}a {product} proof example?"
    greeting = f"Hello {organisation} team," if organisation else "Hello,"
    return _expression(
        plan,
        subject=subject,
        greeting=greeting,
        intro=f"I am writing once to ask permission to send a short {product} proof example.",
        paragraphs=[
            "The example is intended to be inspected quickly and keeps the next step bounded rather than assuming a sale or a need.",
            "If it is relevant, you can opt in to receive the proof. If it is not relevant, no further marketing message is required.",
        ],
        bullets=["One proof example", "No mailing-list enrolment", "Human review remains explicit"],
        cta="Reply YES if you would like the proof example.",
        secondary_cta="Reply NO if you would prefer no further marketing contact.",
        caution="This is a once-off permission request, not a sales commitment.",
    )


def _inbound_reply(plan: dict[str, Any]) -> dict[str, Any]:
    product = _product(plan)
    job = _job(plan)
    context_sentence = f"Based on your message, the working interpretation is: {job}." if job else "I will keep the next step limited to what you have actually asked for."
    return _expression(
        plan,
        subject=f"Re: {product} enquiry",
        greeting="Hello,",
        intro=f"Thank you for getting in touch about {product}.",
        paragraphs=[context_sentence, _proof_line(plan)],
        cta="Reply with any missing detail you want included, or confirm that this interpretation is correct.",
    )


def _qualified_reply(plan: dict[str, Any]) -> dict[str, Any]:
    product = _product(plan)
    pain = _pain(plan)
    job = _job(plan)
    detail = pain or job
    paragraph = f"The current qualified need is: {detail}." if detail else "The lead is qualified, but I will not invent missing scope."
    return _expression(
        plan,
        subject=f"Next step for {product}",
        greeting="Hello,",
        intro=f"We can now move the {product} conversation to a concrete next step.",
        paragraphs=[paragraph, _proof_line(plan)],
        cta="Confirm the bounded input and desired output, and I will prepare the next commercial step for review.",
    )


def _pilot_invitation(plan: dict[str, Any]) -> dict[str, Any]:
    product = _product(plan)
    return _expression(
        plan,
        subject=f"Bounded {product} pilot",
        greeting="Hello,",
        intro=f"A sensible next step is a bounded {product} pilot rather than a broad commitment.",
        paragraphs=[_proof_line(plan), "The pilot should define the input, review point, deliverable and stop condition before work begins."],
        cta="If that approach suits you, confirm the pilot input or suggest an adjustment.",
        secondary_cta="If not, we can stop here without creating an obligation.",
    )


def _follow_up(plan: dict[str, Any]) -> dict[str, Any]:
    product = _product(plan)
    return _expression(
        plan,
        subject=f"Following up: {product}",
        greeting="Hello,",
        intro=f"I am following up on the existing {product} conversation.",
        paragraphs=["I am not assuming that timing or priority has changed since the last message."],
        cta="If you would like to continue, reply with the next step. If not, I will close the loop.",
    )


def _proposal(plan: dict[str, Any]) -> dict[str, Any]:
    product = _product(plan)
    scope = _scope(plan)
    need = _pain(plan) or _job(plan)
    paragraphs = [
        f"Problem / job: {need}" if need else "Problem / job: not yet verified beyond the qualified conversation.",
        f"Proposed scope: {scope}" if scope else "Proposed scope: must be confirmed before commercial commitment.",
        f"Proof: {_proof_line(plan)}",
        "Boundary: customer facts, scope and outcomes not supported by the semantic record are excluded.",
    ]
    return _expression(
        plan,
        subject=f"Proposal: {product}",
        greeting=None,
        intro=f"{product} proposal",
        paragraphs=paragraphs,
        cta="Approve, revise or decline the bounded scope before any execution or payment request.",
        format_name="proposal",
    )


def _quote(plan: dict[str, Any]) -> dict[str, Any]:
    product = _product(plan)
    scope = _scope(plan)
    price = _context_value(plan, "price")
    if not scope or not price:
        raise ValueError("quote requires verified_context.scope and verified_context.price or verified CSO scope")
    return _expression(
        plan,
        subject=f"Quote: {product}",
        greeting="Hello,",
        intro=f"Here is the operator-authorised quote for {product}.",
        paragraphs=[f"Scope: {scope}", f"Price: {price}", "This quote does not expand the agreed scope or guarantee an outcome."],
        cta="Reply to accept the quote or ask a scope or pricing question.",
        format_name="quote",
    )


def _invoice(plan: dict[str, Any]) -> dict[str, Any]:
    product = _product(plan)
    reference = _context_value(plan, "invoice_reference")
    amount = _context_value(plan, "amount")
    if not reference or not amount:
        raise ValueError("invoice_notice requires verified_context.invoice_reference and verified_context.amount")
    return _expression(
        plan,
        subject=f"Invoice {reference}: {product}",
        greeting="Hello,",
        intro=f"An authorised invoice has been prepared for {product}.",
        paragraphs=[f"Invoice reference: {reference}", f"Amount: {amount}"],
        cta="Use the authorised payment route in the invoice, or reply if any commercial detail is incorrect.",
        format_name="invoice_notice",
    )


def _intake(plan: dict[str, Any]) -> dict[str, Any]:
    product = _product(plan)
    reference = _context_value(plan, "job_reference")
    requested = _context_value(plan, "requested_material")
    paragraphs = []
    if reference:
        paragraphs.append(f"Workflow reference: {reference}")
    paragraphs.append(requested or "Please provide the source material listed in the accepted workflow scope.")
    paragraphs.append("Supplying material does not transfer final professional authority to the system.")
    return _expression(
        plan,
        subject=f"{product} source material request" + (f" ({reference})" if reference else ""),
        greeting="Hello,",
        intro=f"Your {product} workflow is open and ready for the required source material.",
        paragraphs=paragraphs,
        cta="Reply with the requested material or identify anything that is unavailable.",
        format_name="intake_request",
    )


def _delivery(plan: dict[str, Any]) -> dict[str, Any]:
    product = _product(plan)
    reference = _context_value(plan, "job_reference")
    return _expression(
        plan,
        subject=f"Your reviewed {product} output is ready" + (f" ({reference})" if reference else ""),
        greeting="Hello,",
        intro=f"Your reviewed {product} output is ready for inspection.",
        paragraphs=[
            f"Workflow reference: {reference}" if reference else "The delivery remains bound to its recorded workflow.",
            "Please retain the source material and review record for audit or revision requests.",
        ],
        cta="Reply with the workflow reference if you need a correction or revision.",
        format_name="delivery",
    )


def _rfq(plan: dict[str, Any]) -> dict[str, Any]:
    product = _product(plan)
    placement = _context_value(plan, "placement") or "the most suitable measurable placement"
    objective = _context_value(plan, "objective") or "a measurable bounded pilot"
    audience = _context_value(plan, "audience") or _plan_value(plan, "market_context.audience.public_segment")
    return _expression(
        plan,
        subject=f"RFQ: bounded pilot for {product}",
        greeting="Hello,",
        intro=f"We are requesting a quotation for a small, controlled {product} campaign pilot.",
        paragraphs=[
            f"Audience: {audience}" if audience else "Audience: defined in the attached brief.",
            f"Objective: {objective}",
            f"Placement interest: {placement}",
            "Please separate agency fees, media spend and third-party costs. This is a quotation request only, not spend authorisation.",
        ],
        cta="Return an itemised minimum-viable-pilot quote against the supplied brief.",
        format_name="rfq",
    )


def _linkedin(plan: dict[str, Any]) -> dict[str, Any]:
    product = _product(plan)
    segment = _plan_value(plan, "market_context.audience.public_segment")
    intro = f"{product} is built around a simple commercial rule: show the work before asking anyone to trust the promise."
    paragraphs = [
        _proof_line(plan),
        f"The current audience strategy is aimed at {segment}." if segment else "The audience is defined at segment level, not by invented customer stories.",
    ]
    return _expression(
        plan,
        subject=None,
        greeting=None,
        intro=intro,
        paragraphs=paragraphs,
        cta="Inspect the proof or ask about one bounded pilot.",
        format_name="social_post",
    )


def _listing(plan: dict[str, Any]) -> dict[str, Any]:
    product = _product(plan)
    offer = _plan_value(plan, "commercial.offer")
    return _expression(
        plan,
        subject=product,
        greeting=None,
        intro=f"{product}: a bounded, review-led workflow service.",
        paragraphs=[f"Offer: {offer}" if offer else "Offer details are confirmed before work begins.", _proof_line(plan)],
        cta="Request the current proof example and bounded service details.",
        format_name="listing",
    )


def _paid_ad(plan: dict[str, Any]) -> dict[str, Any]:
    product = _product(plan)
    return _expression(
        plan,
        subject=None,
        greeting=None,
        intro=f"Before you buy {product}, inspect the proof.",
        paragraphs=[_proof_line(plan)],
        cta="See the proof. Then decide whether a bounded pilot is worth discussing.",
        format_name="paid_ad",
    )


def _video_cta(plan: dict[str, Any]) -> dict[str, Any]:
    product = _product(plan)
    return _expression(
        plan,
        subject=None,
        greeting=None,
        intro=f"That is the {product} proof.",
        paragraphs=[],
        cta="If you want to test the workflow, nominate one bounded pilot input and inspect the result before scaling.",
        format_name="video_cta",
    )


_RENDERERS: dict[CommunicativeAct, Callable[[dict[str, Any]], dict[str, Any]]] = {
    CommunicativeAct.COLD_PERMISSION_REQUEST: _cold_permission,
    CommunicativeAct.INBOUND_REPLY: _inbound_reply,
    CommunicativeAct.QUALIFIED_LEAD_REPLY: _qualified_reply,
    CommunicativeAct.PILOT_INVITATION: _pilot_invitation,
    CommunicativeAct.FOLLOW_UP: _follow_up,
    CommunicativeAct.PROPOSAL: _proposal,
    CommunicativeAct.QUOTE: _quote,
    CommunicativeAct.INVOICE_NOTICE: _invoice,
    CommunicativeAct.INTAKE_REQUEST: _intake,
    CommunicativeAct.DELIVERY: _delivery,
    CommunicativeAct.REQUEST_FOR_QUOTATION: _rfq,
    CommunicativeAct.LINKEDIN_POST: _linkedin,
    CommunicativeAct.CLASSIFIED_LISTING: _listing,
    CommunicativeAct.PAID_AD: _paid_ad,
    CommunicativeAct.VIDEO_CTA: _video_cta,
}


def render_expression(
    cso: dict[str, Any],
    communicative_act: CommunicativeAct | str,
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Render the deterministic fallback for an explicit communicative act.

    A probabilistic generator may later consume the same plan, but it must obey the
    identical act contract and generation policy. The fallback exists so DIO never
    needs a universal prose template in order to remain operational.
    """
    act = _act(communicative_act)
    plan = plan_expression(cso, act, context=context)
    return _RENDERERS[act](plan)


def expression_contract(communicative_act: CommunicativeAct | str) -> dict[str, Any]:
    return asdict(ACT_CONTRACTS[_act(communicative_act)])
