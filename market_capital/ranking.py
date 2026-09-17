from __future__ import annotations

from typing import Any

from .models import validate_opportunity_type


TYPE_COMPONENT_WEIGHTS: dict[str, dict[str, float]] = {
    "INVESTOR": {"thesis": 0.28, "stage": 0.18, "geography": 0.12, "cheque": 0.14, "capital_use": 0.16, "proof": 0.12},
    "GRANT": {"eligibility": 0.30, "thematic": 0.22, "geography": 0.12, "deadline": 0.12, "allowable_costs": 0.10, "reporting_burden": 0.07, "evidence": 0.07},
    "DONOR": {"mission": 0.26, "public_benefit": 0.18, "impact": 0.22, "stewardship": 0.10, "beneficiary": 0.12, "geography": 0.12},
    "SPONSOR": {"strategic_alignment": 0.28, "audience_overlap": 0.20, "ecosystem_value": 0.18, "brand_safety": 0.14, "activation": 0.20},
    "PATRONAGE": {"public_value": 0.26, "community_fit": 0.22, "repeatability": 0.20, "supporter_benefits": 0.16, "platform_fit": 0.16},
    "ACCELERATOR": {"eligibility": 0.24, "stage": 0.18, "geography": 0.12, "sector": 0.18, "network_value": 0.16, "programme_burden": 0.12},
    "PRIZE": {"eligibility": 0.28, "innovation_fit": 0.25, "impact": 0.18, "deadline": 0.12, "evidence": 0.17},
}


def _score(value: Any) -> float:
    try:
        return max(0.0, min(float(value), 100.0))
    except (TypeError, ValueError):
        return 0.0


def _type_fit_score(opportunity_type: str, components: dict[str, Any]) -> tuple[float, dict[str, float]]:
    normalized = {str(k): _score(v) for k, v in components.items()}
    weights = TYPE_COMPONENT_WEIGHTS[opportunity_type]
    used = [(name, weights[name], normalized[name]) for name in weights if name in normalized]
    if not used:
        if not normalized:
            return 0.0, normalized
        return sum(normalized.values()) / len(normalized), normalized
    total_weight = sum(weight for _, weight, _ in used)
    score = sum(weight * value for _, weight, value in used) / total_weight
    return score, normalized


def _next_action(total: float, route: float, freshness: float, row: dict[str, Any]) -> str:
    if bool(row.get("do_not_contact")) or str(row.get("contact_policy") or "").upper() == "DO_NOT_CONTACT":
        return "DO_NOT_CONTACT"
    if freshness < 35 or route < 25:
        return "NEEDS_RESEARCH"
    if total >= 70 and route >= 50 and freshness >= 50:
        return "DRAFT_READY"
    return "HOLD"


def _component_changes(row: dict[str, Any], current: dict[str, Any]) -> list[str]:
    previous = dict(row.get("prior_score_components") or {})
    changes: list[str] = []
    if not previous:
        return changes
    for key, value in current.items():
        if isinstance(value, dict):
            continue
        if key not in previous:
            continue
        before = _score(previous.get(key))
        after = _score(value)
        delta = round(after - before, 2)
        if delta:
            changes.append(f"{key} changed from {before:.2f} to {after:.2f} ({delta:+.2f}).")
    return changes


def score_opportunity(record: dict[str, Any]) -> dict[str, Any]:
    """Score one opportunity using the type-specific GoldenEye vocabulary.

    The returned score is a ranked-priority model output only. It never asserts
    funding intent, fundability, willingness to pay, contact authority, or any
    external-action authority.
    """
    row = dict(record)
    opportunity_type = validate_opportunity_type(str(row.get("opportunity_type") or ""))
    type_fit, type_components = _type_fit_score(opportunity_type, dict(row.get("type_fit") or {}))
    atlas = _score(row.get("atlas_fit_score") if row.get("atlas_fit_score") is not None else row.get("fit_score"))
    timing = _score(row.get("timing_score"))
    route = _score(row.get("route_quality"))
    freshness = _score(row.get("evidence_freshness"))
    total = round(0.25 * atlas + 0.45 * type_fit + 0.12 * timing + 0.10 * route + 0.08 * freshness, 2)

    # Keep the historical nested detail for compatibility while exposing the
    # type-specific vocabulary at the top level for transparent comparisons.
    score_components: dict[str, Any] = {
        **type_components,
        "atlas_fit": atlas,
        "type_specific_fit": round(type_fit, 2),
        "type_specific_detail": type_components,
        "timing": timing,
        "route_quality": route,
        "evidence_freshness": freshness,
    }
    changes = _component_changes(row, score_components)
    return {
        **row,
        "opportunity_type": opportunity_type,
        "priority_score": total,
        "score_components": score_components,
        "component_changes": changes,
        "next_action": _next_action(total, route, freshness, row),
        "truth_class": "RANKED_PRIORITY_MODEL_OUTPUT",
        "fundability": "UNPROVED",
        "willingness_to_fund": "UNPROVED",
        "authority_created": False,
        "external_effects": False,
    }


def rank_capital_opportunities(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = [score_opportunity(raw) for raw in records]
    scored.sort(
        key=lambda item: (
            float(item.get("priority_score") or 0),
            float(item.get("evidence_freshness") or 0),
        ),
        reverse=True,
    )
    for index, row in enumerate(scored, start=1):
        prior = row.get("prior_rank")
        row["rank"] = index
        explanations = list(row.get("component_changes") or [])
        if prior is None:
            row["rank_movement"] = 0
            row["rank_movement_reason"] = "No prior rank supplied; current position is model priority only."
        else:
            try:
                movement = int(prior) - index
            except (TypeError, ValueError):
                movement = 0
            row["rank_movement"] = movement
            if movement > 0:
                direction = f"rose {movement}"
            elif movement < 0:
                direction = f"fell {abs(movement)}"
            else:
                direction = "held position"
            base_reason = (
                f"{direction} from the supplied prior rank based on Atlas fit, type-specific fit, timing, route quality, and evidence freshness; "
                "rank movement is not funding intent."
            )
            if any("freshness" in item.lower() for item in explanations):
                base_reason += " Evidence freshness changed and contributed to the current model inputs."
            row["rank_movement_reason"] = base_reason
        row["movement_explanations"] = explanations or [row["rank_movement_reason"]]
    return scored
