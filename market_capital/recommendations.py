from __future__ import annotations

from typing import Any

from .models import validate_opportunity_type
from .outreach import build_outreach_bundle


POSITIVE_DRAFT_RECOMMENDATIONS = {
    "APPROACH_NOW",
    "APPLY_NOW",
    "PARTNERSHIP_INQUIRY",
    "CULTIVATE",
}

VERIFIED_ROUTE_STATES = {
    "PUBLIC_ROUTE_VERIFIED",
    "APPLICATION_ROUTE_VERIFIED",
}


def _score(value: Any) -> float:
    try:
        return max(0.0, min(float(value), 100.0))
    except (TypeError, ValueError):
        return 0.0


def _route_state(row: dict[str, Any]) -> str:
    return str(row.get("route_state") or "").strip().upper()


def _has_verified_route(row: dict[str, Any]) -> bool:
    return _route_state(row) in VERIFIED_ROUTE_STATES and _score(row.get("route_quality")) >= 50


def _evidence_sufficient(row: dict[str, Any]) -> bool:
    return _score(row.get("evidence_freshness")) >= 50


def _hard_block(row: dict[str, Any]) -> str | None:
    if bool(row.get("do_not_contact")) or str(row.get("contact_policy") or "").strip().upper() == "DO_NOT_CONTACT":
        return "DO_NOT_CONTACT"
    if _route_state(row) == "POLICY_BLOCKED":
        return "DO_NOT_CONTACT"
    return None


def _recommend_by_type(row: dict[str, Any], opportunity_type: str) -> str:
    priority = _score(row.get("priority_score"))
    timing = _score(row.get("timing_score"))
    verified_route = _has_verified_route(row)
    fresh = _evidence_sufficient(row)
    route_state = _route_state(row)

    if not fresh:
        return "RESEARCH_FIRST"
    if route_state in {"NO_PUBLIC_ROUTE", "STALE_ROUTE", "NEEDS_REVIEW", ""} or not verified_route:
        return "RESEARCH_FIRST"

    if opportunity_type == "INVESTOR":
        if priority >= 70 and timing >= 75:
            return "APPROACH_NOW"
        if priority >= 60:
            return "CULTIVATE"
        return "WATCH"

    if opportunity_type == "GRANT":
        eligibility = str(row.get("eligibility_state") or "").strip().upper()
        if eligibility not in {"VERIFIED_ELIGIBLE", "ELIGIBLE"}:
            return "RESEARCH_FIRST"
        if priority >= 70 and timing >= 70:
            return "APPLY_NOW"
        if priority >= 60:
            return "WATCH"
        return "HOLD"

    if opportunity_type == "DONOR":
        active_programme = bool(row.get("active_programme")) or str(row.get("programme_state") or "").strip().upper() in {
            "OPEN",
            "ACTIVE",
            "CURRENT",
        }
        if priority >= 75 and active_programme:
            return "PARTNERSHIP_INQUIRY"
        if priority >= 60:
            return "CULTIVATE"
        return "WATCH"

    if opportunity_type == "SPONSOR":
        if priority >= 72 and timing >= 65:
            return "PARTNERSHIP_INQUIRY"
        if priority >= 60:
            return "CULTIVATE"
        return "WATCH"

    if opportunity_type == "PATRONAGE":
        if priority >= 70:
            return "PARTNERSHIP_INQUIRY"
        if priority >= 55:
            return "CULTIVATE"
        return "WATCH"

    if opportunity_type in {"ACCELERATOR", "PRIZE"}:
        eligibility = str(row.get("eligibility_state") or "").strip().upper()
        if eligibility not in {"VERIFIED_ELIGIBLE", "ELIGIBLE"}:
            return "RESEARCH_FIRST"
        if priority >= 70 and timing >= 70:
            return "APPLY_NOW"
        if priority >= 60:
            return "WATCH"
        return "HOLD"

    return "HOLD"


def _operator_question(recommendation: str, row: dict[str, Any]) -> str:
    name = str(
        row.get("organisation_name")
        or row.get("organisation")
        or row.get("title")
        or row.get("opportunity_id")
        or "this opportunity"
    ).strip()
    questions = {
        "APPROACH_NOW": f"Consider reviewing a governed outreach draft for {name}?",
        "APPLY_NOW": f"Consider reviewing an evidence-bound application draft for {name}?",
        "PARTNERSHIP_INQUIRY": f"Consider reviewing a bounded partnership inquiry for {name}?",
        "CULTIVATE": f"Consider preparing a low-pressure cultivation draft for {name}?",
        "RESEARCH_FIRST": f"Consider gathering the missing route, eligibility, or freshness evidence for {name} first?",
        "WATCH": f"Consider keeping {name} on the monitored opportunity list?",
        "HOLD": f"Consider holding {name} until stronger evidence appears?",
        "DO_NOT_CONTACT": f"Consider leaving {name} blocked from outreach?",
    }
    return questions[recommendation]


def build_action_recommendation(row: dict[str, Any]) -> dict[str, Any]:
    opportunity_type = validate_opportunity_type(str(row.get("opportunity_type") or ""))
    opportunity_id = str(row.get("opportunity_id") or "").strip()
    if not opportunity_id:
        raise ValueError("opportunity_id is required")

    recommendation = _hard_block(row) or _recommend_by_type(row, opportunity_type)
    draft_available = recommendation in POSITIVE_DRAFT_RECOMMENDATIONS
    outreach_bundle: dict[str, Any] | None = None

    if draft_available:
        atlas_fit = dict(row.get("atlas_fit") or {})
        hypothesis = dict(row.get("leading_hypothesis") or {})
        if not hypothesis:
            hypothesis = {
                "family": str(atlas_fit.get("recommended_pitch_family") or "").strip(),
                "statement": "This proposition may fit the target's published mandate or audience; genuine interest remains unproved.",
            }
        outreach_bundle = build_outreach_bundle(row, atlas_fit, hypothesis)

    return {
        "schema": "dio.market_capital.action_recommendation.v1",
        "opportunity_id": opportunity_id,
        "opportunity_type": opportunity_type,
        "recommendation": recommendation,
        "draft_available": draft_available,
        "operator_question": _operator_question(recommendation, row),
        "reasoning": {
            "priority_score": _score(row.get("priority_score")),
            "timing_score": _score(row.get("timing_score")),
            "route_state": _route_state(row),
            "route_quality": _score(row.get("route_quality")),
            "evidence_freshness": _score(row.get("evidence_freshness")),
            "do_not_contact": bool(row.get("do_not_contact")),
        },
        "outreach_bundle": outreach_bundle,
        "truth_class": "ACTION_RECOMMENDATION_MODEL_OUTPUT",
        "send_authority": False,
        "submission_authority": False,
        "financial_commitment_authority": False,
        "authority_created": False,
        "external_effects": False,
    }
