from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any


SUPPORTED_INTENTS = {
    "TOP_RECOMMENDATIONS",
    "FIND_BY_TYPE",
    "FIND_BY_DOMAIN",
    "FIND_BY_GEOGRAPHY",
    "DEADLINES_SOON",
    "EXPLAIN_RECOMMENDATION",
    "EXPLAIN_RANK_MOVE",
    "DRAFT_WITHOUT_SEND",
    "MISSING_PROOF",
}


def _authority() -> dict[str, bool]:
    return {
        "send_authority": False,
        "submission_authority": False,
        "financial_commitment_authority": False,
        "authority_created": False,
        "external_effects": False,
    }


def _result(*, text: str, truth_class: str, items: list[dict[str, Any]] | None = None, **extra: Any) -> dict[str, Any]:
    return {
        "text": text,
        "items": list(items or []),
        "truth_class": truth_class,
        **extra,
        **_authority(),
    }


def _find(state: dict[str, Any], opportunity_id: str) -> dict[str, Any] | None:
    wanted = str(opportunity_id or "").strip().upper()
    if not wanted:
        return None
    for row in state.get("items") or []:
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
        "geography": row.get("geography"),
        "deadline": row.get("deadline"),
        "priority_score": row.get("priority_score"),
        "recommendation": rec.get("recommendation") or row.get("next_action"),
        "fit_reason": fit.get("fit_reason"),
        "domain_path": fit.get("domain_path") or row.get("domain_path"),
        "rank_movement": row.get("rank_movement"),
        "rank_movement_reason": row.get("rank_movement_reason"),
    }


def _parse_day(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def _query_text(request: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = request.get(key)
        if value is not None and str(value).strip():
            return str(value).strip().lower()
    return ""


def answer_capital_query(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    intent = str(request.get("intent") or "").strip().upper()
    if intent not in SUPPORTED_INTENTS:
        raise ValueError(f"unsupported capital Vesper intent: {intent or '<empty>'}")

    items = list(state.get("items") or [])
    limit = max(1, min(int(request.get("limit") or 10), 50))

    if intent == "TOP_RECOMMENDATIONS":
        selected = items[:limit]
        text = "No ranked Capital & Support recommendations are currently available."
        if selected:
            rendered = "; ".join(
                f"#{row.get('rank', '?')} {row.get('organisation') or row.get('title') or row.get('opportunity_id')} "
                f"({(row.get('action_recommendation') or {}).get('recommendation') or row.get('next_action') or 'review'})"
                for row in selected
            )
            text = f"Current Capital & Support recommendation queue: {rendered}. Rankings are model guidance, not evidence of funding intent."
        return _result(text=text, truth_class="RANKED_PRIORITY_MODEL_OUTPUT", items=[_compact(row) for row in selected])

    if intent == "FIND_BY_TYPE":
        wanted = _query_text(request, "opportunity_type", "type")
        selected = [row for row in items if str(row.get("opportunity_type") or "").strip().lower() == wanted][:limit]
        return _result(text=f"Found {len(selected)} ranked Capital & Support record(s) matching type {wanted or 'unspecified'}.", truth_class="CAPITAL_DISCOVERY_VIEW", items=[_compact(row) for row in selected])

    if intent == "FIND_BY_DOMAIN":
        wanted = _query_text(request, "domain", "query")
        selected = []
        for row in items:
            fit = dict(row.get("atlas_fit") or {})
            domain_values = fit.get("domain_path") or row.get("domain_path") or []
            if not isinstance(domain_values, (list, tuple)):
                domain_values = [domain_values]
            haystack = " ".join(str(x) for x in domain_values).lower()
            if wanted and wanted in haystack:
                selected.append(row)
        selected = selected[:limit]
        return _result(text=f"Found {len(selected)} ranked record(s) matching Atlas domain {wanted or 'unspecified'}.", truth_class="CAPITAL_DISCOVERY_VIEW", items=[_compact(row) for row in selected])

    if intent == "FIND_BY_GEOGRAPHY":
        wanted = _query_text(request, "geography", "query")
        selected = [row for row in items if wanted and wanted in str(row.get("geography") or "").lower()][:limit]
        return _result(text=f"Found {len(selected)} ranked record(s) matching geography {wanted or 'unspecified'}.", truth_class="CAPITAL_DISCOVERY_VIEW", items=[_compact(row) for row in selected])

    if intent == "DEADLINES_SOON":
        start = _parse_day(request.get("as_of")) or date.today()
        days = max(0, min(int(request.get("days") or 30), 365))
        end = start + timedelta(days=days)
        dated = []
        for row in items:
            deadline = _parse_day(row.get("deadline") or row.get("deadline_at") or row.get("close_date"))
            if deadline is not None and start <= deadline <= end:
                dated.append((deadline, row))
        dated.sort(key=lambda pair: (pair[0], int(pair[1].get("rank") or 10**9)))
        selected = [row for _, row in dated[:limit]]
        return _result(text=f"Found {len(selected)} ranked opportunity or opportunities with deadlines in the next {days} day(s).", truth_class="CAPITAL_DEADLINE_VIEW", items=[_compact(row) for row in selected])

    opportunity_id = str(request.get("opportunity_id") or "").strip()
    row = _find(state, opportunity_id)
    if row is None:
        return _result(text="I need a current Capital & Support opportunity ID before I can answer that safely.", truth_class="CAPITAL_QUERY_UNRESOLVED")

    fit = dict(row.get("atlas_fit") or {})
    rec = dict(row.get("action_recommendation") or {})
    target = row.get("organisation") or row.get("title") or opportunity_id

    if intent == "EXPLAIN_RECOMMENDATION":
        why_target = str(rec.get("why_target") or fit.get("fit_reason") or "Atlas has not recorded a target-fit explanation.")
        why_now = str(rec.get("why_now") or row.get("rank_movement_reason") or "No timing explanation is currently recorded.")
        recommendation = rec.get("recommendation") or row.get("next_action") or "REVIEW"
        return _result(
            text=f"{target}: {recommendation}. Why this target: {why_target} Why now: {why_now} This is recommendation model output, not evidence that the target wants to fund DIO.",
            truth_class="ACTION_RECOMMENDATION_MODEL_OUTPUT",
            items=[_compact(row)],
            why_target=why_target,
            why_now=why_now,
            recommendation=recommendation,
        )

    if intent == "EXPLAIN_RANK_MOVE":
        movement = str(row.get("rank_movement_reason") or "No rank-movement explanation is currently recorded.")
        return _result(text=f"{target} rank movement: {movement}", truth_class="RANK_EXPLANATION_MODEL_OUTPUT", items=[_compact(row)], rank_movement=row.get("rank_movement"), rank_movement_reason=movement)

    if intent == "DRAFT_WITHOUT_SEND":
        draft = dict(rec.get("outreach_bundle") or row.get("draft") or {})
        if not draft:
            return _result(text=f"There is no governed outreach draft for {target} yet.", truth_class="DRAFT_UNAVAILABLE", items=[_compact(row)], draft=None)
        safe_draft = dict(draft)
        safe_draft.update(_authority())
        return _result(text=f"Governed draft for {target}. I can show or revise it here, but I cannot send or submit it.", truth_class="DRAFT_RECOMMENDATION", items=[_compact(row)], draft=safe_draft)

    missing = fit.get("missing_proof") or row.get("missing_proof") or []
    if not isinstance(missing, list):
        missing = [missing]
    missing = [str(x) for x in missing if str(x).strip()]
    return _result(text=f"{target} has {len(missing)} recorded proof gap(s).", truth_class="MISSING_PROOF_VIEW", items=[_compact(row)], missing_proof=missing)
