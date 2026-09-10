from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .census import CapitalCensus
from .models import OPPORTUNITY_TYPES
from .projection import capital_support_projection


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _json_files(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_dir():
        return rows
    for candidate in sorted(path.glob("*.json")):
        value = _read_json(candidate, {})
        if isinstance(value, dict):
            rows.append(value)
    return rows


def capital_support_cockpit(root: Path) -> dict[str, Any]:
    root = Path(root)
    capital_root = root / "state" / "market_capital"
    census_path = capital_root / "census" / "capital_support.sqlite"
    census_projection: dict[str, Any] = {}
    if census_path.is_file():
        census = CapitalCensus(census_path)
        census.initialize()
        census_projection = capital_support_projection(census, limit=50, root=root)

    priority = _read_json(capital_root / "rankings" / "CAPITAL_SUPPORT_PRIORITY.json", {})
    legacy_ranked = list(priority.get("items") or []) if isinstance(priority, dict) else []
    ranked = list(census_projection.get("items") or []) or legacy_ranked

    opportunities = _json_files(capital_root / "opportunities")
    opportunity_by_id = {
        str(row.get("opportunity_id") or ""): row
        for row in opportunities
        if str(row.get("opportunity_id") or "").strip()
    }
    fits = {
        str(row.get("opportunity_id") or ""): row
        for row in _json_files(capital_root / "fits")
        if str(row.get("opportunity_id") or "").strip()
    }
    hypotheses = {
        str(row.get("opportunity_id") or ""): row
        for row in _json_files(capital_root / "hypotheses")
        if str(row.get("opportunity_id") or "").strip()
    }
    drafts = {
        str(row.get("opportunity_id") or ""): row
        for row in _json_files(capital_root / "drafts")
        if str(row.get("opportunity_id") or "").strip()
    }

    cases_root = root / "state" / "presence" / "customer_cases" / "cases"
    engaged_cases = 0
    for case in _json_files(cases_root):
        if str((case.get("capital_support") or {}).get("opportunity_id") or "").strip():
            engaged_cases += 1

    by_type = {kind: 0 for kind in sorted(OPPORTUNITY_TYPES)}
    source_rows = ranked or opportunities
    for row in source_rows:
        kind = str(row.get("opportunity_type") or "").upper()
        if kind in by_type:
            by_type[kind] += 1

    items: list[dict[str, Any]] = []
    for row in ranked:
        opportunity_id = str(row.get("opportunity_id") or "").strip()
        fit = dict(row.get("atlas_fit") or fits.get(opportunity_id) or {})
        hypothesis_set = hypotheses.get(opportunity_id) or {}
        hypothesis_items = list(row.get("hypotheses") or hypothesis_set.get("items") or [])
        draft = drafts.get(opportunity_id) or {}
        source = opportunity_by_id.get(opportunity_id) or {}
        score_components = dict(row.get("score_components") or {})
        items.append({
            "rank": row.get("rank"),
            "opportunity_id": opportunity_id,
            "opportunity_type": row.get("opportunity_type") or source.get("opportunity_type"),
            "organisation": row.get("organisation_name") or row.get("organisation") or source.get("organisation_name") or source.get("organisation") or source.get("organisation_id"),
            "title": row.get("title") or source.get("title"),
            "priority_score": row.get("priority_score"),
            "atlas_fit_score": score_components.get("atlas_fit") if score_components else fit.get("fit_score"),
            "timing_score": score_components.get("timing"),
            "route_quality": score_components.get("route_quality"),
            "evidence_freshness": score_components.get("evidence_freshness"),
            "next_action": row.get("next_action"),
            "rank_movement": row.get("rank_movement"),
            "rank_movement_reason": row.get("rank_movement_reason"),
            "movement_explanations": list(row.get("movement_explanations") or []),
            "leading_hypothesis": row.get("leading_hypothesis") or (hypothesis_items[0] if hypothesis_items else None),
            "atlas_fit": fit,
            "draft": draft,
            "lingua_projection": draft.get("lingua_projection") if isinstance(draft, dict) else None,
            "truth_class": "RANKED_PRIORITY_MODEL_OUTPUT",
            "authority_created": False,
            "external_effects": False,
        })

    high_fit = sum(1 for row in ranked if float(row.get("priority_score") or 0) >= 70)
    draft_ready = sum(1 for row in ranked if str(row.get("next_action") or "") == "DRAFT_READY")
    if not ranked:
        draft_ready = len(drafts)

    census_counts = dict(census_projection.get("census_counts") or {})
    opportunity_count = int(census_projection.get("total_rankable_opportunities") or 0) if census_projection else (len(ranked) if ranked else len(opportunities))
    state = "PRESENT" if opportunity_count else "EMPTY"
    return {
        "schema": "dio.business.capital_support_cockpit.v2",
        "state": state,
        "summary": {
            "opportunity_count": opportunity_count,
            "high_fit": high_fit,
            "draft_ready": draft_ready,
            "engaged_cases": engaged_cases,
            "census_organisations": int(census_counts.get("organisations") or 0),
            "census_people": int(census_counts.get("people") or 0),
            "census_relationships": int(census_counts.get("relationships") or 0),
            "projection_count": len(items),
        },
        "census_counts": census_counts,
        "by_type": by_type,
        "items": items,
        "message": "No capital or support opportunities ranked yet." if state == "EMPTY" else "Capital & Support census priority field loaded.",
        "truth_class": "RANKED_PRIORITY_MODEL_OUTPUT",
        "authority_created": False,
        "external_effects": False,
    }
