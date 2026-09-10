from __future__ import annotations

import json
from typing import Any

from .census import CapitalCensus
from .ranking import rank_capital_opportunities


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
        # Stored explicit model inputs may be reused, but database identity is authoritative.
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


def capital_support_projection(census: CapitalCensus, limit: int = 50) -> dict[str, Any]:
    """Return a bounded GoldenEye view over the full census.

    The census remains the registry of record. This projection deliberately
    surfaces only the highest model-priority rows and creates no authority.
    """
    cap = max(0, int(limit))
    records = _opportunity_records(census)
    ranked = rank_capital_opportunities(records) if records else []
    counts = census.snapshot_counts()
    return {
        "schema": "dio.market_capital.census_projection.v1",
        "census_counts": counts,
        "total_rankable_opportunities": len(ranked),
        "projection_limit": cap,
        "items": ranked[:cap],
        "truth_class": "RANKED_PRIORITY_MODEL_OUTPUT",
        "funding_intent": "UNPROVED",
        "authority_created": False,
        "external_effects": False,
    }
