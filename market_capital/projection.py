from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .atlas_fit import build_capital_support_fit
from .census import CapitalCensus
from .hypotheses import generate_hypotheses
from .ranking import rank_capital_opportunities
from .recommendations import build_action_recommendation


def _opportunity_records(census: CapitalCensus) -> list[dict[str, Any]]:
    with census.connect() as conn:
        rows = conn.execute(
            """
            SELECT
                o.opportunity_id,
                o.organisation_id,
                o.opportunity_type,
                o.title,
                o.payload_json,
                o.first_observed_at,
                o.last_observed_at,
                org.canonical_name AS census_organisation_name
            FROM opportunities o
            LEFT JOIN organisations org ON org.organisation_id = o.organisation_id
            """
        ).fetchall()
    records: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        try:
            payload = json.loads(item.pop("payload_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            payload = {}
        organisation_name = (
            payload.get("organisation_name")
            or payload.get("organisation")
            or payload.get("agency_name")
            or item.get("census_organisation_name")
        )
        record = {
            **payload,
            "opportunity_id": item["opportunity_id"],
            "organisation_id": item.get("organisation_id"),
            "organisation_name": organisation_name,
            "organisation": organisation_name,
            "opportunity_type": item["opportunity_type"],
            "title": item["title"],
            "first_observed_at": item.get("first_observed_at"),
            "last_observed_at": item.get("last_observed_at"),
        }
        records.append(record)
    return records



def _parse_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _freshness_score(value: Any) -> float:
    dt = _parse_dt(value)
    if dt is None:
        return 0.0
    age_hours = max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600.0)
    if age_hours <= 24:
        return 100.0
    if age_hours <= 168:
        return 90.0
    if age_hours <= 720:
        return 75.0
    if age_hours <= 2160:
        return 50.0
    return 25.0


def _route_score(row: dict[str, Any]) -> float:
    state = str(row.get("route_state") or "").strip().upper()
    if state == "APPLICATION_ROUTE_VERIFIED":
        return 90.0
    if state == "PUBLIC_ROUTE_VERIFIED":
        return 75.0
    if state == "NO_PUBLIC_ROUTE":
        return 10.0
    return 0.0


def _timing_score(row: dict[str, Any]) -> float:
    status = str(row.get("status") or row.get("programme_state") or "").strip().casefold()
    if status in {"closed", "expired", "archived"}:
        return 10.0
    close_dt = _parse_dt(row.get("close_date") or row.get("deadline"))
    if close_dt is not None:
        days = (close_dt.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds() / 86400.0
        if days < 0:
            return 10.0
        if days <= 30:
            return 95.0
        if days <= 90:
            return 85.0
        if days <= 180:
            return 75.0
        return 65.0
    if status in {"posted", "open", "current", "active"}:
        return 75.0
    if str(row.get("truth_class") or "").upper() == "PUBLIC_CAPITAL_SIGNAL_VERIFIED":
        return 35.0
    return 0.0


def _type_fit_from_atlas(row: dict[str, Any], atlas_fit: dict[str, Any], freshness: float, timing: float) -> dict[str, float]:
    atlas = float(atlas_fit.get("fit_score") or 0.0)
    kind = str(row.get("opportunity_type") or "").upper()
    if kind == "INVESTOR":
        return {"thesis": atlas, "proof": min(100.0, 50.0 + 5.0 * len(atlas_fit.get("proof_bundle") or []))}
    if kind == "GRANT":
        result = {"thematic": atlas, "evidence": freshness}
        if row.get("close_date") or row.get("deadline"):
            result["deadline"] = timing
        return result
    if kind == "DONOR":
        return {"mission": atlas, "impact": atlas, "public_benefit": min(100.0, atlas + 5.0)}
    if kind == "SPONSOR":
        return {"strategic_alignment": atlas, "ecosystem_value": atlas}
    if kind == "PATRONAGE":
        return {"public_value": atlas, "community_fit": atlas}
    if kind == "ACCELERATOR":
        return {"sector": atlas, "stage": max(0.0, atlas - 10.0)}
    if kind == "PRIZE":
        return {"innovation_fit": atlas, "impact": atlas, "evidence": freshness}
    return {}


def _derive_scoring_inputs(row: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(row)
    atlas_fit = dict(enriched.get("atlas_fit") or {})
    freshness = float(enriched.get("evidence_freshness") or _freshness_score(enriched.get("last_observed_at") or enriched.get("first_observed_at")))
    timing = float(enriched.get("timing_score") or _timing_score(enriched))
    route = float(enriched.get("route_quality") or _route_score(enriched))
    enriched["evidence_freshness"] = freshness
    enriched["timing_score"] = timing
    enriched["route_quality"] = route
    if not enriched.get("type_fit") and atlas_fit:
        enriched["type_fit"] = _type_fit_from_atlas(enriched, atlas_fit, freshness, timing)
    enriched["scoring_input_truth_class"] = "DERIVED_FROM_OBSERVED_EVIDENCE"
    enriched["eligibility_state"] = enriched.get("eligibility_state")
    enriched["funding_intent"] = enriched.get("funding_intent") or "UNPROVED"
    enriched["willingness_to_fund"] = enriched.get("willingness_to_fund") or "UNPROVED"
    return enriched


def _enrich_with_existing_organs(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    """Reuse Atlas and HiveNance when repo context is available.

    Observed source fields remain untouched. Atlas fit and HiveNance hypotheses
    are attached as explicit model outputs, never promoted into observations.
    """
    row = dict(record)
    atlas_fit = dict(row.get("atlas_fit") or {})
    if not atlas_fit:
        atlas_fit = build_capital_support_fit(root, row)
    row["atlas_fit"] = atlas_fit
    if row.get("atlas_fit_score") is None and row.get("fit_score") is None:
        row["atlas_fit_score"] = atlas_fit.get("fit_score", 0)

    hypotheses = list(row.get("hypotheses") or [])
    if not hypotheses:
        hypotheses = generate_hypotheses(row, atlas_fit)
    row["hypotheses"] = hypotheses
    if hypotheses and not row.get("leading_hypothesis"):
        row["leading_hypothesis"] = hypotheses[0]
    return _derive_scoring_inputs(row)


def capital_support_projection(
    census: CapitalCensus,
    limit: int = 50,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Return a bounded GoldenEye view over the full census.

    The census remains the registry of record. If a repository root is supplied,
    existing Atlas and HiveNance functions enrich the rows before GoldenEye ranks
    them. Governed action recommendations are derived from ranked model output and
    create no send, submission, or financial authority.
    """
    cap = max(0, int(limit))
    records = _opportunity_records(census)
    if root is not None:
        records = [_enrich_with_existing_organs(Path(root), row) for row in records]
    ranked = rank_capital_opportunities(records) if records else []
    for row in ranked:
        row["action_recommendation"] = build_action_recommendation(row)
    counts = census.snapshot_counts()
    return {
        "schema": "dio.market_capital.census_projection.v1",
        "census_counts": counts,
        "total_rankable_opportunities": len(ranked),
        "projection_limit": cap,
        "items": ranked[:cap],
        "truth_class": "RANKED_PRIORITY_MODEL_OUTPUT",
        "funding_intent": "UNPROVED",
        "willingness_to_fund": "UNPROVED",
        "authority_created": False,
        "external_effects": False,
    }
