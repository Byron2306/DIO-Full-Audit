#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_capital.census import CapitalCensus
from market_capital.projection import capital_support_projection


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _rows(census: CapitalCensus, table: str) -> list[dict[str, Any]]:
    with census.connect() as conn:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    return [dict(row) for row in rows]


def _write_csv(path: Path, rows: list[dict[str, Any]], *, metadata: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    enriched = [{**metadata, **row} for row in rows]
    if enriched:
        fields: list[str] = []
        for row in enriched:
            for key in row:
                if key not in fields:
                    fields.append(key)
    else:
        fields = list(metadata)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(enriched)


def export_census(*, root: Path, census: CapitalCensus | None = None) -> dict[str, str]:
    root = Path(root).resolve()
    census_root = root / "state" / "market_capital" / "census"
    census = census or CapitalCensus(census_root / "capital_support.sqlite")
    census.initialize()
    generated_at = _now()
    metadata = {
        "census_version": "1",
        "generated_at": generated_at,
        "authority_created": False,
        "external_effects": False,
    }

    outputs: dict[str, str] = {}
    for table, filename in (
        ("organisations", "organisations.csv"),
        ("opportunities", "opportunities.csv"),
        ("relationships", "relationships.csv"),
    ):
        path = census_root / filename
        _write_csv(path, _rows(census, table), metadata=metadata)
        outputs[table] = str(path)

    source_health = census_root / "source_health.json"
    if not source_health.is_file():
        source_health.write_text(json.dumps({**metadata, "sources": {}}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    outputs["source_health"] = str(source_health)

    atlas_registry = root / "config" / "atlas" / "dio_atlas_universal_domain_registry.csv"
    projection = capital_support_projection(census, limit=100, root=root if atlas_registry.is_file() else None)
    recommendations = {
        "schema": "dio.market_capital.recommendation_export.v1",
        **metadata,
        "count": len(projection.get("items") or []),
        "items": [
            {
                "rank": row.get("rank"),
                "opportunity_id": row.get("opportunity_id"),
                "opportunity_type": row.get("opportunity_type"),
                "organisation": row.get("organisation"),
                "organisation_name": row.get("organisation_name"),
                "title": row.get("title"),
                "priority_score": row.get("priority_score"),
                "route_state": row.get("route_state"),
                "route_quality": row.get("route_quality"),
                "evidence_freshness": row.get("evidence_freshness"),
                "timing_score": row.get("timing_score"),
                "type_fit": row.get("type_fit"),
                "score_components": row.get("score_components"),
                "scoring_input_truth_class": row.get("scoring_input_truth_class"),
                "atlas_fit": row.get("atlas_fit"),
                "leading_hypothesis": row.get("leading_hypothesis"),
                "action_recommendation": row.get("action_recommendation"),
                "rank_movement": row.get("rank_movement"),
                "rank_movement_reason": row.get("rank_movement_reason"),
            }
            for row in projection.get("items") or []
        ],
        "truth_class": "RANKED_PRIORITY_MODEL_OUTPUT",
        "funding_intent": "UNPROVED",
        "willingness_to_fund": "UNPROVED",
    }
    recommendations_path = census_root / "recommendations.json"
    recommendations_path.write_text(json.dumps(recommendations, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    outputs["recommendations"] = str(recommendations_path)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the Capital & Support census and bounded recommendation view")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(export_census(root=args.root), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
