from __future__ import annotations

import json
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
            "SELECT opportunity_id, organisation_id, opportunity_type, title, payload_json, first_observed_at, last_observed_at FROM opportunities"
        ).fetchall()
    records: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        try:
            payload = json.loads(item.pop("payload_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            payload = {}
        record = {
            **payload,
            "opportunity_id": item["opportunity_id"],
            "organisation_id": item.get("organisation_id"),
            "opportunity_type": item["opportunity_type"],
            "title": item["title"],
            "first_observed_at": item.get("first_observed_at"),
            "last_observed_at": item.get("last_observed_at"),
        }
        records.append(record)
    return records


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
    return row


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
