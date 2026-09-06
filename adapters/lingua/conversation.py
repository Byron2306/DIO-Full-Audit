from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

ALLOWED_CONVERSATION_ACTS = {
    "greeting",
    "answer",
    "explain",
    "compare",
    "clarify",
    "acknowledge",
    "confirm",
    "correct",
    "handoff_offer",
    "unknown",
}
ALLOWED_ACTION_INTENTS = {"none", "begin_intake", "status_lookup", "operator_summary"}
ALLOWED_SOURCES = {"primitive", "lingua_crystal", "knowledge", "provider", "fallback"}

FALLBACK_REPLY = (
    "I can help you work out the right DIO path. Tell me what you’re trying to achieve "
    "or what is currently getting in your way, and I’ll narrow it down with you."
)


def _resolution(
    reply: str,
    *,
    conversation_act: str,
    interpreted_need: str | None = None,
    candidate_products: list[str] | None = None,
    confidence: float = 1.0,
    clarification_needed: bool = False,
    clarification_question: str | None = None,
    action_intent: str = "none",
    action_product: str | None = None,
    source: str = "primitive",
) -> dict[str, Any]:
    return {
        "schema": "dio.vesper.conversation_resolution.v1",
        "reply": reply,
        "conversation_act": conversation_act,
        "interpreted_need": interpreted_need,
        "candidate_products": list(candidate_products or []),
        "confidence": float(confidence),
        "clarification_needed": bool(clarification_needed),
        "clarification_question": clarification_question,
        "action_intent": action_intent,
        "action_product": action_product,
        "source": source,
        "authority_created": False,
    }


def safe_fallback_resolution() -> dict[str, Any]:
    return _resolution(
        FALLBACK_REPLY,
        conversation_act="unknown",
        confidence=0.0,
        source="fallback",
    )


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _explicit_begin_confirmation(text: str) -> bool:
    value = _normalized(text)
    if not value:
        return False
    patterns = (
        r"\byes\b.*\b(start|begin)\b",
        r"\byes\b.*\bdo that\b",
        r"\bgo ahead\b(?:.*\b(that|it)\b)?",
        r"\b(start|begin) that\b",
        r"\bplease (start|begin)\b",
    )
    return any(re.search(pattern, value) for pattern in patterns)


def resolve_primitive(text: str, state: Mapping[str, Any]) -> dict[str, Any] | None:
    value = _normalized(text)
    if not value:
        return None

    if value in {"hi", "hello", "hey", "hiya", "good morning", "good afternoon", "good evening"}:
        return _resolution(
            "Hi. I’m Vesper, DIO’s guide. What are you trying to get done?",
            conversation_act="greeting",
        )

    if value in {"thanks", "thank you", "thankyou", "cheers", "thanks vesper"}:
        return _resolution(
            "You’re welcome. Tell me what you want to tackle next.",
            conversation_act="acknowledge",
        )

    if value in {"bye", "goodbye", "see you", "later"}:
        return _resolution(
            "Goodbye. I’ll be here when you need another DIO path.",
            conversation_act="acknowledge",
        )

    if value in {"who are you", "who are you?", "what are you", "what are you?"}:
        return _resolution(
            "I’m Vesper, DIO’s AI guide. I help you understand the portfolio, work out which path fits your problem, and move into governed DIO actions only when you explicitly choose to.",
            conversation_act="explain",
        )

    if value in {"what can you do", "what can you do?", "how can you help", "how can you help?"}:
        return _resolution(
            "I can explain DIO, compare products, help turn a messy problem into the right product path, and guide you into an intake or other governed next step when you ask for one.",
            conversation_act="explain",
        )

    proposal = state.get("action_proposal") if isinstance(state, Mapping) else None
    if _explicit_begin_confirmation(value):
        if isinstance(proposal, Mapping) and proposal.get("intent") == "begin_intake" and proposal.get("product"):
            return _resolution(
                "Understood. I’ll pass that request into DIO’s governed intake path.",
                conversation_act="confirm",
                candidate_products=[str(proposal["product"])],
                action_intent="begin_intake",
                action_product=str(proposal["product"]),
            )
        return _resolution(
            "I can do that once we’ve pinned down which DIO path you mean. Tell me which product or outcome you want to start with.",
            conversation_act="clarify",
            confidence=0.5,
            clarification_needed=True,
            clarification_question="Which DIO product or outcome should I start with?",
        )

    if value in {"yes", "yes please", "yep", "yeah", "correct", "right"}:
        return _resolution("Got it.", conversation_act="acknowledge")

    if value in {"no", "nope", "not that", "that’s not it", "that's not it"}:
        return _resolution(
            "Understood. Tell me what I got wrong and I’ll correct the path.",
            conversation_act="correct",
        )

    return None


def validate_conversation_resolution(
    payload: Mapping[str, Any],
    allowed_products: set[str],
) -> dict[str, Any]:
    if bool(payload.get("authority_created")):
        raise ValueError("conversation resolution cannot create authority")

    act = str(payload.get("conversation_act") or "unknown")
    if act not in ALLOWED_CONVERSATION_ACTS:
        raise ValueError(f"unsupported conversation act: {act}")

    action_intent = str(payload.get("action_intent") or "none")
    if action_intent not in ALLOWED_ACTION_INTENTS:
        raise ValueError(f"unsupported action intent: {action_intent}")

    source = str(payload.get("source") or "fallback")
    if source not in ALLOWED_SOURCES:
        raise ValueError(f"unsupported conversation source: {source}")

    raw_products = payload.get("candidate_products") or []
    if not isinstance(raw_products, (list, tuple)):
        raise ValueError("candidate_products must be a list")
    products: list[str] = []
    for raw in raw_products:
        product = str(raw).strip()
        if not product:
            continue
        if product not in allowed_products:
            raise ValueError(f"unknown conversation product: {product}")
        if product not in products:
            products.append(product)

    action_product_raw = payload.get("action_product")
    action_product = str(action_product_raw).strip() if action_product_raw is not None else None
    if action_product == "":
        action_product = None
    if action_product is not None and action_product not in allowed_products:
        raise ValueError(f"unknown action product: {action_product}")
    if action_intent == "begin_intake" and not action_product:
        raise ValueError("begin_intake requires an action product")

    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = min(1.0, max(0.0, confidence))

    reply = str(payload.get("reply") or "").strip()
    if not reply:
        raise ValueError("conversation resolution reply is required")

    interpreted_need_raw = payload.get("interpreted_need")
    interpreted_need = str(interpreted_need_raw).strip() if interpreted_need_raw is not None else None
    if interpreted_need == "":
        interpreted_need = None

    clarification_needed = bool(payload.get("clarification_needed", False))
    clarification_raw = payload.get("clarification_question")
    clarification_question = str(clarification_raw).strip() if clarification_raw is not None else None
    if clarification_question == "":
        clarification_question = None

    result = {
        "schema": "dio.vesper.conversation_resolution.v1",
        "reply": reply,
        "conversation_act": act,
        "interpreted_need": interpreted_need,
        "candidate_products": products,
        "confidence": confidence,
        "clarification_needed": clarification_needed,
        "clarification_question": clarification_question,
        "action_intent": action_intent,
        "action_product": action_product,
        "source": source,
        "authority_created": False,
    }
    topic_raw = payload.get("current_topic")
    topic = str(topic_raw).strip() if topic_raw is not None else None
    if topic == "":
        topic = None
    if topic is not None and len(topic) > 160:
        raise ValueError("current_topic is too long")
    result["current_topic"] = topic
    result["route_auto_promotable"] = bool(payload.get("route_auto_promotable", False))
    crystal_id = payload.get("crystal_id")
    if crystal_id:
        result["crystal_id"] = str(crystal_id)[:160]
    reuse_digest = payload.get("reuse_receipt_digest")
    if reuse_digest:
        result["reuse_receipt_digest"] = str(reuse_digest)[:160]
    result["provider_called"] = bool(payload.get("provider_called", source == "provider"))
    return result


def apply_resolution_to_state(
    state: Mapping[str, Any],
    resolution: Mapping[str, Any],
) -> dict[str, Any]:
    updated = dict(state)
    act = str(resolution.get("conversation_act") or "unknown")
    products = [str(p) for p in (resolution.get("candidate_products") or []) if str(p).strip()]
    action_product_raw = resolution.get("action_product")
    action_product = str(action_product_raw).strip() if action_product_raw is not None else None
    confidence = float(resolution.get("confidence") or 0.0)

    interpreted_need = resolution.get("interpreted_need")
    if interpreted_need:
        updated["current_need"] = str(interpreted_need)
    if resolution.get("current_topic") is not None:
        updated["current_topic"] = str(resolution.get("current_topic"))
    updated["candidate_products"] = products
    updated["last_vesper_act"] = act
    updated["open_question"] = resolution.get("clarification_question") if resolution.get("clarification_needed") else None

    if action_product and (action_product in products or not products):
        updated["selected_product"] = action_product
    elif len(products) == 1 and confidence >= 0.8:
        updated["selected_product"] = products[0]

    if (
        act == "handoff_offer"
        and str(resolution.get("action_intent") or "none") == "none"
        and action_product
        and confidence >= 0.8
        and resolution.get("route_auto_promotable", True) is not False
    ):
        updated["action_proposal"] = {"intent": "begin_intake", "product": action_product}
    elif str(resolution.get("action_intent") or "none") != "none":
        updated["action_proposal"] = None

    return updated


def _allowed_products(knowledge: Mapping[str, Any]) -> set[str]:
    return {str(key) for key in knowledge if not str(key).startswith("_")}


def _named_products(text: str, knowledge: Mapping[str, Any]) -> list[str]:
    low = str(text or "").lower()
    found: list[str] = []
    for product, item in knowledge.items():
        if str(product).startswith("_") or not isinstance(item, Mapping):
            continue
        label = str(item.get("label") or product)
        aliases = {str(product).replace("_", " "), label}
        if any(alias.strip() and alias.lower() in low for alias in aliases):
            found.append(str(product))
    return found


def _resolve_other_one(text: str, state: Mapping[str, Any]) -> dict[str, Any] | None:
    value = _normalized(text)
    if "other one" not in value and "the other" not in value:
        return None
    candidates = [str(item) for item in (state.get("candidate_products") or []) if str(item).strip()]
    if len(candidates) != 2:
        return _resolution(
            "I can correct that, but I need you to name which option you mean because there isn’t exactly one unambiguous alternative.",
            conversation_act="clarify",
            candidate_products=candidates,
            confidence=0.5,
            clarification_needed=True,
            clarification_question="Which product did you mean?",
        )
    selected = str(state.get("selected_product") or "")
    if selected in candidates:
        other = candidates[1] if candidates[0] == selected else candidates[0]
    else:
        return _resolution(
            "I have two candidates in view. Which one do you mean?",
            conversation_act="clarify",
            candidate_products=candidates,
            confidence=0.5,
            clarification_needed=True,
            clarification_question="Which of the two products did you mean?",
        )
    return _resolution(
        f"Understood. I’ll keep the focus on {other}.",
        conversation_act="correct",
        candidate_products=[other],
        confidence=1.0,
    )


def _resolve_comparison(text: str, knowledge: Mapping[str, Any]) -> dict[str, Any] | None:
    products = _named_products(text, knowledge)
    unique = list(dict.fromkeys(products))
    if len(unique) != 2:
        return None
    if " or " not in str(text).lower() and "compare" not in str(text).lower() and "difference" not in str(text).lower():
        return None
    left, right = unique
    left_item = knowledge[left]
    right_item = knowledge[right]
    reply = (
        f"{left_item.get('label', left)}: {left_item.get('one_liner', '')} "
        f"{right_item.get('label', right)}: {right_item.get('one_liner', '')} "
        "Tell me which outcome matters more and I can narrow the choice without starting anything."
    )
    result = _resolution(reply, conversation_act="compare", candidate_products=unique, confidence=1.0, source="knowledge")
    result["current_topic"] = None
    result["route_auto_promotable"] = False
    return result


def _resolve_problem_guidance(text: str, knowledge: Mapping[str, Any]) -> dict[str, Any] | None:
    low = str(text or "").lower()
    scores: list[tuple[int, int, str]] = []
    for product, item in knowledge.items():
        if str(product).startswith("_") or not isinstance(item, Mapping):
            continue
        matched = [
            str(term).lower()
            for term in (item.get("route_keywords") or [])
            if str(term).strip() and str(term).lower() in low
        ]
        if not matched:
            continue
        specific = max((len(term.split()) for term in matched), default=0)
        scores.append((len(matched), specific, str(product)))
    if not scores:
        return None
    scores.sort(reverse=True)
    best_hits, best_specificity, product = scores[0]
    if len(scores) > 1 and scores[1][:2] == scores[0][:2]:
        return None
    item = knowledge[product]
    confidence = min(0.95, 0.78 + 0.06 * best_hits + 0.03 * max(0, best_specificity - 1))
    auto = bool(item.get("route_auto_promotable", False))
    label = str(item.get("label") or product)
    if auto:
        reply = (
            f"That sounds aligned with {label}. {item.get('one_liner', '')} "
            "I can explain the fit in more detail, or help you begin a governed intake if you choose to."
        )
        act = "handoff_offer"
        action_product = product
    else:
        reply = (
            f"That sounds related to {label}. {item.get('one_liner', '')} "
            "I can explain the fit and alternatives, but this route is not automatically promoted into execution."
        )
        act = "answer"
        action_product = None
    result = _resolution(
        reply,
        conversation_act=act,
        interpreted_need=str(text or "")[:500],
        candidate_products=[product],
        confidence=confidence,
        action_product=action_product,
        source="knowledge",
    )
    result["current_topic"] = product
    result["route_auto_promotable"] = auto
    return result


def resolve_conversation(
    *,
    root: Path,
    text: str,
    state: Mapping[str, Any],
    recent_turns: Sequence[Mapping[str, Any]],
    knowledge: Mapping[str, Any],
    interaction: Mapping[str, Any] | None,
    persona: Mapping[str, Any] | None,
    provider_resolver: Callable[..., Mapping[str, Any] | None],
) -> dict[str, Any]:
    allowed = _allowed_products(knowledge)

    correction = _resolve_other_one(text, state)
    if correction is not None:
        return validate_conversation_resolution(correction, allowed)

    primitive = resolve_primitive(text, state)
    if primitive is not None:
        return validate_conversation_resolution(primitive, allowed)

    try:
        from adapters.lingua.conversation_crystals import resolve_conversation_crystal
        crystal = resolve_conversation_crystal(root=root, text=text)
    except Exception:
        crystal = None
    if crystal is not None:
        payload = _resolution(str(crystal.get("reply") or ""), conversation_act="answer", confidence=1.0, source="lingua_crystal")
        payload["crystal_id"] = crystal.get("crystal_id")
        payload["reuse_receipt_digest"] = crystal.get("reuse_receipt_digest")
        payload["provider_called"] = False
        return validate_conversation_resolution(payload, allowed)

    from adapters.lingua.conversation_knowledge import answer_from_governed_knowledge

    knowledge_answer = answer_from_governed_knowledge(text, dict(knowledge))
    if knowledge_answer is not None:
        return validate_conversation_resolution(knowledge_answer, allowed)

    comparison = _resolve_comparison(text, knowledge)
    if comparison is not None:
        return validate_conversation_resolution(comparison, allowed)

    guidance = _resolve_problem_guidance(text, knowledge)
    if guidance is not None:
        return validate_conversation_resolution(guidance, allowed)

    try:
        provider = provider_resolver(
            text=text,
            state=state,
            recent_turns=recent_turns,
            knowledge=knowledge,
            interaction=interaction,
            persona_assignment=persona,
            allowed_products=sorted(allowed),
        )
    except Exception:
        provider = None
    if provider is not None:
        try:
            return validate_conversation_resolution(provider, allowed)
        except (ValueError, TypeError):
            pass

    return validate_conversation_resolution(safe_fallback_resolution(), allowed)
