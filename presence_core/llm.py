from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from adapters.lingua.interaction_regulator import llm_style_instruction
from adapters.lingua.persona_lab import persona_style_instruction


INTENTS = ["general_info", "product_info", "pricing_info", "intake_request", "status_request", "translation_info", "formatting_info", "unknown"]

_ACTOR_PREFIX = r"\b(?:i|we)\s+(?:(?:have|['’]ve|will(?:\s+now)?|am|are|['’]m|['’]re)\s+)?"
_PROCESS_ACTION = r"(?:process(?:ed|ing)?|analy[sz](?:e|ed|ing)|pars(?:e|ed|ing)|open(?:ed|ing)?)"
_PROCESS_CLAIM_RE = re.compile(
    rf"(?:{_ACTOR_PREFIX}{_PROCESS_ACTION}\b|\b(?:i|we)\b[^.!?\n]{{0,180}}\bwill(?:\s+now)?\s+{_PROCESS_ACTION}\b)",
    re.IGNORECASE,
)

_ACTION_CLAIM_RULES = (
    (
        _PROCESS_CLAIM_RE,
        re.compile(r"(?:attachment_processed\s*=\s*true|processing_state\s*=\s*(?:processing|processed|complete|completed)|\bstate\s*=\s*(?:processing|processed|complete|completed)\b)", re.IGNORECASE),
    ),
    (
        re.compile(_ACTOR_PREFIX + r"(?:start(?:ed|ing)?|queue(?:d|ing)?|generat(?:e|ed|ing))\b", re.IGNORECASE),
        re.compile(r"(?:work_queued\s*=\s*true|generation_state\s*=\s*(?:started|generated|complete|completed)|processing_state\s*=\s*(?:queued|processing|processed|complete|completed)|\bstate\s*=\s*(?:work_queued|queued|processing|processed|review_ready)\b)", re.IGNORECASE),
    ),
    (
        re.compile(_ACTOR_PREFIX + r"(?:invoice(?:d|ing)?|charg(?:e|ed|ing))\b", re.IGNORECASE),
        re.compile(r"(?:invoice_state\s*=\s*(?:sent|issued)|payment_state\s*=\s*(?:paid|succeeded|charged|verified))", re.IGNORECASE),
    ),
    (
        re.compile(_ACTOR_PREFIX + r"(?:sent|send(?:ing)?|publish(?:ed|ing)?|approv(?:e|ed|ing)|releas(?:e|ed|ing)|refund(?:ed|ing)?|deliver(?:ed|ing)?|submit(?:ted|ting)?|fil(?:e|ed|ing)|fulfil(?:led|ling)?|fulfill(?:ed|ing)?)\b", re.IGNORECASE),
        re.compile(r"(?:send_state\s*=\s*sent|publication_state\s*=\s*(?:released|published)|approval_state\s*=\s*approved|fulfilment_released\s*=\s*true|release_state\s*=\s*released|payment_state\s*=\s*refunded|delivery_state\s*=\s*delivered|submission_state\s*=\s*(?:submitted|filed)|fulfilment_state\s*=\s*fulfilled|\bstate\s*=\s*(?:sent|published|approved|released|refunded|delivered|submitted|filed|fulfilled)\b)", re.IGNORECASE),
    ),
    (
        re.compile(r"\b(?:i|we)\s+will\s+(?:provide|share|send|deliver|return|give)\b", re.IGNORECASE),
        re.compile(r"(?:delivery_authorized\s*=\s*true|delivery_state\s*=\s*(?:ready|approved|delivered)|release_state\s*=\s*(?:approved|released)|output_state\s*=\s*(?:ready|approved))", re.IGNORECASE),
    ),
    (
        re.compile(r"\b(?:check|visit|use|open|log\s+in(?:to)?|sign\s+in(?:to)?)\b[^.!?\n]{0,80}\b(?:dio\s+)?account\s+portal\b", re.IGNORECASE),
        re.compile(r"\baccount_portal\s*=\s*(?:available|true|verified)\b", re.IGNORECASE),
    ),
    (
        re.compile(r"\b(?:contact|call|reach|speak\s+(?:to|with))\b[^.!?\n]{0,80}\b(?:our\s+)?billing\s+(?:team|department)\b", re.IGNORECASE),
        re.compile(r"\bbilling_team\s*=\s*(?:available|true|verified)\b", re.IGNORECASE),
    ),
)


def classify_with_ollama(text: str, products: list[str]) -> dict[str, Any] | None:
    url = os.getenv("OLLAMA_URL")
    model = os.getenv("OLLAMA_MODEL")
    if not url or not model:
        return None
    prompt = f"Classify this customer message. Return JSON only with intent, product, confidence. Allowed intents: {INTENTS}. Allowed products: {products} or null. Message: {text[:2500]}"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a bounded intent classifier. You do not execute tools, make commitments, quote prices, or alter state."},
            {"role": "user", "content": prompt},
        ],
        "format": "json",
        "stream": False,
        "think": False,
        "options": {"temperature": 0},
    }
    try:
        response = httpx.post(url.rstrip("/") + "/api/chat", json=payload, timeout=float(os.getenv("OLLAMA_TIMEOUT", "15")))
        response.raise_for_status()
        obj = response.json()
        content = ((obj.get("message") or {}).get("content") or "{}")
        parsed = json.loads(content)
        if parsed.get("intent") not in INTENTS:
            return None
        if parsed.get("product") not in products:
            parsed["product"] = None
        parsed["confidence"] = max(0.0, min(float(parsed.get("confidence", 0)), 1.0))
        return parsed
    except Exception:
        return None


def draft_claims_authorized(text: str, facts: str) -> bool:
    candidate = str(text or "")
    authoritative = str(facts or "")
    for claim_re, support_re in _ACTION_CLAIM_RULES:
        if claim_re.search(candidate) and support_re.search(authoritative) is None:
            return False
    return True


def _draft_messages(
    decision: dict[str, Any],
    facts: str,
    fallback: str,
    *,
    interaction: dict[str, Any] | None = None,
    persona_assignment: dict[str, Any] | None = None,
    governed_context: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    persona = persona_style_instruction(persona_assignment)
    regulation = llm_style_instruction(interaction)
    context = dict(governed_context or {})
    role = str(context.get("role") or "public").strip().lower()
    audience = str(context.get("audience") or role or "public").strip().lower()
    operator = role == "operator" or audience == "operator"
    if operator:
        channel_contract = (
            "This is an authenticated DIO operator conversation with DIO's owner/operator. "
            "Write an operator-facing reply as an operational chief-of-staff: concise, direct, state-first, and already familiar with DIO terminology. "
            "Do not pitch products, ask sales-closing questions, or use generic customer-service closers. "
        )
        audience_instruction = "Write one concise, natural operator-facing reply that preserves the authoritative facts."
    else:
        channel_contract = (
            "This is a public customer conversation. Be clear, useful, commercially natural, and low-pressure while staying strictly inside governed product, pricing, payment, delivery, and authority facts. "
        )
        audience_instruction = "Write one concise, natural customer-facing reply that preserves the authoritative facts."
    system = (
        "You are Vesper, DIO's Presence Core. You are an AI system, never a human. "
        "Preserve the supplied authoritative facts exactly. Governed descriptive context is read-only and creates no execution authority. "
        "Never invent pricing, payment state, delivery state, authority, legal claims, emotions, vulnerabilities, personality traits, or capabilities. "
        "Never imply an action occurred or has started unless the facts explicitly say it occurred or started. "
        "Never promise a future external action merely because the conversation requests it. "
        "Never invent an account portal, billing team, department, support desk, or other service surface unless the authoritative facts establish it. "
        "Never intensify pressure because a user sounds upset, urgent, confused, skeptical, or price-sensitive. "
        + channel_contract + persona + " " + regulation
    )
    user = (
        f"Decision: {json.dumps(decision)}\n"
        f"Authoritative facts: {facts}\n"
        f"Governed descriptive context: {json.dumps(context, sort_keys=True)}\n"
        f"Fallback wording: {fallback}\n"
        + audience_instruction
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def draft_with_ollama(
    decision: dict[str, Any],
    facts: str,
    fallback: str,
    interaction: dict[str, Any] | None = None,
    persona_assignment: dict[str, Any] | None = None,
    governed_context: dict[str, Any] | None = None,
) -> str:
    if os.getenv("DIO_PRESENCE_LLM_DRAFTS", "0") not in {"1", "true", "yes"}:
        return fallback
    url = os.getenv("OLLAMA_URL")
    model = os.getenv("OLLAMA_MODEL")
    if not url or not model:
        return fallback
    messages = _draft_messages(
        decision,
        facts,
        fallback,
        interaction=interaction,
        persona_assignment=persona_assignment,
        governed_context=governed_context,
    )
    try:
        response = httpx.post(
            url.rstrip("/") + "/api/chat",
            json={"model": model, "messages": messages, "stream": False, "think": False, "options": {"temperature": 0.2}},
            timeout=float(os.getenv("OLLAMA_TIMEOUT", "15")),
        )
        response.raise_for_status()
        text = ((response.json().get("message") or {}).get("content") or "").strip()[:4000]
        if not text or not draft_claims_authorized(text, facts):
            return fallback
        return text
    except Exception:
        return fallback
