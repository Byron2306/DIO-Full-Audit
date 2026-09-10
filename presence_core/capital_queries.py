from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from market_capital.cockpit import capital_support_cockpit


CAPITAL_INTENTS = {
    "capital_priority",
    "capital_explain",
    "capital_draft",
    "capital_grants",
    "capital_patronage",
}


def _authority() -> dict[str, bool]:
    return {
        "send_authority": False,
        "submission_authority": False,
        "financial_commitment_authority": False,
        "authority_created": False,
        "external_effects": False,
    }


def _opportunity_id(text: str) -> str:
    match = re.search(r"\bOPP[-_A-Z0-9]+\b", str(text or ""), re.IGNORECASE)
    return match.group(0).upper() if match else ""


def _find(items: list[dict[str, Any]], opportunity_id: str) -> dict[str, Any] | None:
    wanted = str(opportunity_id or "").strip().upper()
    if not wanted:
        return None
    for row in items:
        if str(row.get("opportunity_id") or "").strip().upper() == wanted:
            return row
    return None


def _compact(row: dict[str, Any]) -> dict[str, Any]:
    rec = dict(row.get("action_recommendation") or {})
    fit = dict(row.get("atlas_fit") or {})
    return {
        "rank": row.get("rank"),
        "opportunity_id": row.get("opportunity_id"),
        "opportunity_type": row.get("opportunity_type"),
        "organisation": row.get("organisation"),
        "title": row.get("title"),
        "priority_score": row.get("priority_score"),
        "recommendation": rec.get("recommendation") or row.get("next_action"),
        "fit_reason": fit.get("fit_reason"),
        "rank_movement": row.get("rank_movement"),
        "rank_movement_reason": row.get("rank_movement_reason"),
    }


def answer_capital_query(intent: str, text: str, state: dict[str, Any]) -> dict[str, Any]:
    if intent not in CAPITAL_INTENTS:
        raise ValueError(f"unsupported capital query intent: {intent}")
    items = list(state.get("items") or [])
    authority = _authority()

    if intent == "capital_priority":
        selected = items[:5]
        if selected:
            names = "; ".join(
                f"#{row.get('rank', '?')} {row.get('organisation') or row.get('title') or row.get('opportunity_id')} "
                f"({(row.get('action_recommendation') or {}).get('recommendation') or row.get('next_action') or 'review'})"
                for row in selected
            )
            message = f"Current Capital & Support priority queue: {names}. Rankings are model guidance, not evidence of funding intent."
        else:
            message = "The Capital & Support census has no ranked opportunities to recommend right now."
        return {"text": message, "items": [_compact(row) for row in selected], "truth_class": "RANKED_PRIORITY_MODEL_OUTPUT", **authority}

    opportunity_id = _opportunity_id(text)
    row = _find(items, opportunity_id)

    if intent in {"capital_explain", "capital_draft"}:
        if row is None:
            return {
                "text": "I need a current opportunity ID from the Capital & Support census before I can answer that safely.",
                "items": [],
                "truth_class": "CAPITAL_QUERY_UNRESOLVED",
                **authority,
            }
        rec = dict(row.get("action_recommendation") or {})
        fit = dict(row.get("atlas_fit") or {})
        reasoning = dict(rec.get("reasoning") or {})
        target = row.get("organisation") or row.get("title") or opportunity_id
        if intent == "capital_explain":
            fit_reason = str(fit.get("fit_reason") or "Atlas has not recorded a fit explanation.")
            movement = str(row.get("rank_movement_reason") or "No rank-movement explanation is recorded.")
            route = reasoning.get("route_state") or row.get("route_state") or "UNKNOWN"
            text_out = (
                f"{target} is currently ranked #{row.get('rank', '?')}. {fit_reason} "
                f"Recommendation: {rec.get('recommendation') or row.get('next_action') or 'review'}. "
                f"Route state: {route}. Rank context: {movement} This is strategic-priority model output, not evidence that the target wants to fund DIO."
            )
            return {"text": text_out, "items": [_compact(row)], "truth_class": "RANK_EXPLANATION_MODEL_OUTPUT", **authority}
        draft = dict(rec.get("outreach_bundle") or row.get("draft") or {})
        if not draft:
            return {
                "text": f"There is no governed outreach draft for {target} yet. The current recommendation is {rec.get('recommendation') or row.get('next_action') or 'research first'}.",
                "items": [_compact(row)],
                "draft": None,
                "truth_class": "DRAFT_UNAVAILABLE",
                **authority,
            }
        safe_draft = dict(draft)
        safe_draft.update(_authority())
        return {
            "text": f"I found the governed draft for {target}. I can show or revise it here, but I cannot send or submit it.",
            "items": [_compact(row)],
            "draft": safe_draft,
            "truth_class": "DRAFT_RECOMMENDATION",
            **authority,
        }

    if intent == "capital_grants":
        selected = [row for row in items if str(row.get("opportunity_type") or "").upper() == "GRANT"][:10]
        text_out = (
            f"I found {len(selected)} currently ranked grant opportunity or opportunities in the Capital & Support census. "
            "These are discovery/ranking results; eligibility and award intent remain unproved."
        )
        return {"text": text_out, "items": [_compact(row) for row in selected], "truth_class": "CAPITAL_DISCOVERY_VIEW", **authority}

    selected = [row for row in items if str(row.get("opportunity_type") or "").upper() == "PATRONAGE"][:10]
    propositions = [
        "Support open educational tools and public learning resources.",
        "Support governed, evidence-first AI research and public demonstrations.",
        "Support the public DIO build journey and selected open releases.",
        "Offer a bounded early-access or community-lab supporter tier without implying equity or investment.",
    ]
    text_out = (
        "Patreon-style support belongs to patronage, not investment. I can test propositions around open education, governed AI research, "
        "the public build journey, and bounded supporter access. No equity, funding commitment, or supporter demand is assumed."
    )
    return {
        "text": text_out,
        "items": [_compact(row) for row in selected],
        "propositions": propositions,
        "truth_class": "PATRONAGE_PROPOSITION_MODEL_OUTPUT",
        **authority,
    }


def capital_query(dio_root: Path, intent: str, text: str) -> dict[str, Any]:
    state = capital_support_cockpit(Path(dio_root))
    return answer_capital_query(intent, text, state)
