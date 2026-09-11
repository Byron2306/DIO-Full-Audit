from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from market_capital.cockpit import capital_support_cockpit
from market_capital.vesper import answer_capital_query as answer_census_capital_query


CAPITAL_INTENTS = {
    "capital_priority",
    "capital_explain",
    "capital_draft",
    "capital_grants",
    "capital_patronage",
    "capital_find_type",
    "capital_find_domain",
    "capital_find_geography",
    "capital_deadlines",
    "capital_rank_move",
    "capital_missing_proof",
}


def _opportunity_id(text: str) -> str:
    match = re.search(r"\bOPP[-_A-Z0-9]+\b", str(text or ""), re.IGNORECASE)
    return match.group(0).upper() if match else ""


def _type_from_text(text: str) -> str:
    low = str(text or "").lower()
    for value in ("INVESTOR", "GRANT", "DONOR", "SPONSOR", "PATRONAGE", "ACCELERATOR", "PRIZE"):
        token = value.lower()
        if token in low or (value == "PATRONAGE" and "patreon" in low):
            return value
    return ""


def _request_for_intent(intent: str, text: str) -> dict[str, Any]:
    if intent == "capital_priority":
        return {"intent": "TOP_RECOMMENDATIONS", "limit": 5}
    if intent == "capital_explain":
        return {"intent": "EXPLAIN_RECOMMENDATION", "opportunity_id": _opportunity_id(text)}
    if intent == "capital_draft":
        return {"intent": "DRAFT_WITHOUT_SEND", "opportunity_id": _opportunity_id(text)}
    if intent == "capital_grants":
        return {"intent": "FIND_BY_TYPE", "opportunity_type": "GRANT", "limit": 10}
    if intent == "capital_patronage":
        return {"intent": "FIND_BY_TYPE", "opportunity_type": "PATRONAGE", "limit": 10}
    if intent == "capital_find_type":
        return {"intent": "FIND_BY_TYPE", "opportunity_type": _type_from_text(text), "limit": 10}
    if intent == "capital_find_domain":
        cleaned = re.sub(r"(?i)\b(find|show|which|capital|funding|fund|opportunities?|targets?|in|the|domain)\b", " ", str(text or ""))
        domain = " ".join(cleaned.split()) or str(text or "").strip()
        return {"intent": "FIND_BY_DOMAIN", "domain": domain, "limit": 10}
    if intent == "capital_find_geography":
        low = str(text or "").lower()
        known = (
            "South Africa", "Africa", "Global", "Worldwide", "Europe", "European Union",
            "United States", "USA", "United Kingdom", "UK", "Asia", "Latin America", "Middle East",
        )
        geography = next((value for value in known if value.lower() in low), str(text or "").strip())
        return {"intent": "FIND_BY_GEOGRAPHY", "geography": geography, "limit": 10}
    if intent == "capital_deadlines":
        return {"intent": "DEADLINES_SOON", "days": 30, "limit": 10}
    if intent == "capital_rank_move":
        return {"intent": "EXPLAIN_RANK_MOVE", "opportunity_id": _opportunity_id(text)}
    if intent == "capital_missing_proof":
        return {"intent": "MISSING_PROOF", "opportunity_id": _opportunity_id(text)}
    raise ValueError(f"unsupported capital query intent: {intent}")


def _patronage_overlay(result: dict[str, Any]) -> dict[str, Any]:
    propositions = [
        "Support open educational tools and public learning resources.",
        "Support governed, evidence-first AI research and public demonstrations.",
        "Support the public DIO build journey and selected open releases.",
        "Offer a bounded early-access or community-lab supporter tier without implying equity or investment.",
    ]
    enriched = dict(result)
    enriched["propositions"] = propositions
    enriched["text"] = (
        "Patreon-style support belongs to patronage, not investment. I can test propositions around open education, governed AI research, "
        "the public DIO build journey, and bounded supporter access. No equity, funding commitment, or supporter demand is assumed."
    )
    enriched["truth_class"] = "PATRONAGE_PROPOSITION_MODEL_OUTPUT"
    return enriched


def answer_capital_query(intent: str, text: str, state: dict[str, Any]) -> dict[str, Any]:
    if intent not in CAPITAL_INTENTS:
        raise ValueError(f"unsupported capital query intent: {intent}")
    result = answer_census_capital_query(state, _request_for_intent(intent, text))
    if intent == "capital_patronage":
        return _patronage_overlay(result)
    return result


def capital_query(dio_root: Path, intent: str, text: str) -> dict[str, Any]:
    state = capital_support_cockpit(Path(dio_root))
    return answer_capital_query(intent, text, state)
