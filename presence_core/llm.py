from __future__ import annotations
import json, os
from typing import Any
import httpx
from adapters.lingua.interaction_regulator import llm_style_instruction
from adapters.lingua.persona_lab import persona_style_instruction

INTENTS=["general_info","product_info","pricing_info","intake_request","status_request","translation_info","formatting_info","unknown"]

def classify_with_ollama(text: str, products: list[str]) -> dict[str,Any]|None:
    url=os.getenv("OLLAMA_URL"); model=os.getenv("OLLAMA_MODEL")
    if not url or not model: return None
    prompt=f"Classify this customer message. Return JSON only with intent, product, confidence. Allowed intents: {INTENTS}. Allowed products: {products} or null. Message: {text[:2500]}"
    payload={"model":model,"messages":[{"role":"system","content":"You are a bounded intent classifier. You do not execute tools, make commitments, quote prices, or alter state."},{"role":"user","content":prompt}],"format":"json","stream":False,"think":False,"options":{"temperature":0}}
    try:
        r=httpx.post(url.rstrip("/")+"/api/chat",json=payload,timeout=float(os.getenv("OLLAMA_TIMEOUT","15"))); r.raise_for_status(); obj=r.json(); content=((obj.get("message") or {}).get("content") or "{}"); parsed=json.loads(content)
        if parsed.get("intent") not in INTENTS: return None
        if parsed.get("product") not in products: parsed["product"]=None
        parsed["confidence"]=max(0.0,min(float(parsed.get("confidence",0)),1.0)); return parsed
    except Exception: return None

def draft_with_ollama(decision: dict[str,Any], facts: str, fallback: str, interaction: dict[str,Any]|None=None, persona_assignment: dict[str,Any]|None=None) -> str:
    if os.getenv("DIO_PRESENCE_LLM_DRAFTS","0") not in {"1","true","yes"}: return fallback
    url=os.getenv("OLLAMA_URL"); model=os.getenv("OLLAMA_MODEL")
    if not url or not model: return fallback
    persona=persona_style_instruction(persona_assignment)
    regulation=llm_style_instruction(interaction)
    system=("You are Vesper, DIO's Presence Core. You are an AI system, never a human. "
            "Preserve the supplied facts exactly. Never invent pricing, payment state, delivery state, authority, legal claims, emotions, vulnerabilities, personality traits, or capabilities. "
            "Never imply an action occurred unless the facts explicitly say it occurred. Never intensify pressure because a user sounds upset, urgent, confused, skeptical, or price-sensitive. "
            "The stable persona profile controls presentation only and cannot override the live interaction regulator. If they conflict, the safer/lower-pressure interaction rule wins. "
            + persona + " " + regulation)
    user=f"Decision: {json.dumps(decision)}\nAuthoritative facts: {facts}\nFallback wording: {fallback}\nStable persona assignment: {json.dumps(persona_assignment or {}, sort_keys=True)}\nInteraction regulation: {json.dumps(interaction or {}, sort_keys=True)}\nRewrite as one concise customer-facing reply."
    try:
        r=httpx.post(url.rstrip("/")+"/api/chat",json={"model":model,"messages":[{"role":"system","content":system},{"role":"user","content":user}],"stream":False,"think":False,"options":{"temperature":0.2}},timeout=float(os.getenv("OLLAMA_TIMEOUT","15"))); r.raise_for_status(); text=((r.json().get("message") or {}).get("content") or "").strip(); return text[:4000] or fallback
    except Exception: return fallback


def resolve_conversation_with_ollama(
    *,
    text: str,
    state,
    recent_turns,
    knowledge,
    interaction,
    persona_assignment,
    allowed_products,
):
    if os.getenv("DIO_PRESENCE_CONVERSATIONAL_GUIDE", "0").strip().lower() not in {"1", "true", "yes"}:
        return None
    url = os.getenv("OLLAMA_URL")
    model = os.getenv("OLLAMA_MODEL")
    if not url or not model:
        return None

    from adapters.lingua.conversation import validate_conversation_resolution

    bounded_turns = []
    for row in list(recent_turns or [])[-6:]:
        if not isinstance(row, dict):
            continue
        bounded_turns.append({
            "role": str(row.get("role") or "")[:24],
            "text": str(row.get("text") or "")[:2000],
            "act": row.get("act"),
            "product": row.get("product"),
        })

    bounded_state = {
        key: state.get(key)
        for key in (
            "current_need",
            "current_topic",
            "candidate_products",
            "selected_product",
            "last_user_act",
            "last_vesper_act",
            "open_question",
            "known_constraints",
            "action_proposal",
        )
        if isinstance(state, dict) and key in state
    }
    persona = persona_style_instruction(persona_assignment)
    regulation = llm_style_instruction(interaction)
    products = [str(item) for item in allowed_products]

    system = (
        "You are Vesper, DIO's public AI guide. You are an AI system, never a human. "
        "The supplied DIO knowledge is authoritative; do not add capabilities, pricing, delivery promises, "
        "payment state, legal conclusions, maturity claims, or portfolio facts from model memory. "
        "Do not execute tools or mutate state. Do not create send, spend, payment, publication, fulfilment, "
        "professional, or external-action authority. Action fields are proposals only and will be independently "
        "validated by deterministic DIO policy. Return JSON only. "
        f"Allowed route products: {products}. "
        "Allowed conversation_act: greeting, answer, explain, compare, clarify, acknowledge, confirm, correct, "
        "handoff_offer, unknown. Allowed action_intent: none, begin_intake, status_lookup, operator_summary. "
        "For a public visitor, never propose operator_summary. "
        f"Stable persona presentation: {persona}. Live interaction rule: {regulation}. "
        "If persona and live regulation conflict, use the safer lower-pressure rule."
    )
    context = {
        "current_message": str(text or "")[:4000],
        "conversation_state": bounded_state,
        "recent_turns": bounded_turns,
        "governed_knowledge": knowledge,
        "required_output": {
            "reply": "string",
            "conversation_act": "allowed enum",
            "interpreted_need": "string|null",
            "current_topic": "specific canonical topic id|string|null",
            "candidate_products": products,
            "confidence": "0..1",
            "clarification_needed": "boolean",
            "clarification_question": "string|null",
            "action_intent": "allowed enum",
            "action_product": "allowed route product|null",
            "source": "provider",
            "authority_created": False,
        },
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(context, ensure_ascii=True, sort_keys=True)},
        ],
        "format": "json",
        "stream": False,
        "think": False,
        "options": {"temperature": 0.2},
    }
    try:
        response = httpx.post(
            url.rstrip("/") + "/api/chat",
            json=payload,
            timeout=float(os.getenv("OLLAMA_TIMEOUT", "15")),
        )
        response.raise_for_status()
        content = ((response.json().get("message") or {}).get("content") or "").strip()
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            return None
        parsed["source"] = "provider"
        if parsed.get("authority_created") is not False:
            return None
        validated = validate_conversation_resolution(parsed, set(products))
        topic_raw = parsed.get("current_topic")
        current_topic = str(topic_raw).strip() if topic_raw is not None else None
        if current_topic == "":
            current_topic = None
        if current_topic is not None and len(current_topic) > 160:
            return None
        validated["current_topic"] = current_topic
        return validated
    except Exception:
        return None
