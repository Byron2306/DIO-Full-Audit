#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_sensorium.resolution import resolve_identity  # noqa: E402


def _json(value: str | None) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _record(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("record")
    return value if isinstance(value, dict) else payload


def _text(value: Any) -> str:
    return str(value or "").strip()


def classify_blocker(row: sqlite3.Row) -> list[str]:
    payload = _json(row["payload_json"])
    record = _record(payload)
    blockers: list[str] = []
    explicit_keys = {
        "organisation", "organization", "organisation_name", "organization_name",
        "company", "company_name", "institution", "institution_name", "employer",
        "employer_name", "agency", "agency_name", "buyer_organisation",
        "buyer_organization", "entity_name",
    }
    if not any(_text(record.get(key) or payload.get(key)) for key in explicit_keys):
        blockers.append("NO_EXPLICIT_ORGANISATION_FIELD")
    if float(row["score"] or 0.0) < 0.50:
        blockers.append("SCORE_BELOW_HEURISTIC_THRESHOLD")
    if resolve_identity(row) is None:
        blockers.append("CURRENT_RESOLVER_NO_IDENTITY")
    if not _text(record.get("description") or record.get("extract") or record.get("summary")):
        blockers.append("NO_CONTEXT_TEXT")
    if not _text(record.get("link") or record.get("url") or record.get("source_url") or record.get("canonical_url")):
        blockers.append("NO_SOURCE_LINK")
    return blockers


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit unresolved Market Sensorium discovery candidates without promoting any target.")
    parser.add_argument("--db", default="state/market_sensorium/market_sensorium.sqlite")
    parser.add_argument("--limit", type=int, default=53)
    parser.add_argument("--samples", type=int, default=30)
    args = parser.parse_args()

    db = (ROOT / args.db).resolve() if not Path(args.db).is_absolute() else Path(args.db)
    if not db.is_file():
        raise SystemExit(f"Market Sensorium DB not found: {db}")

    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT * FROM discovery_candidates
        WHERE state='UNRESOLVED_ENTITY'
        ORDER BY score DESC, last_seen_at DESC, candidate_id
        LIMIT ?
        """,
        (max(1, int(args.limit)),),
    ).fetchall()

    source_counts: Counter[str] = Counter()
    candidate_kind_counts: Counter[str] = Counter()
    blocker_counts: Counter[str] = Counter()
    record_key_counts: Counter[str] = Counter()
    payload_key_counts: Counter[str] = Counter()
    score_buckets: Counter[str] = Counter()
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        payload = _json(row["payload_json"])
        record = _record(payload)
        source_kind = _text(row["source_kind"])
        source_counts[source_kind] += 1
        candidate_kind_counts[_text(row["candidate_kind"])] += 1
        for key in payload:
            payload_key_counts[key] += 1
        for key in record:
            record_key_counts[key] += 1
        for blocker in classify_blocker(row):
            blocker_counts[blocker] += 1
        score = float(row["score"] or 0.0)
        if score >= 0.80:
            score_buckets["0.80-1.00"] += 1
        elif score >= 0.60:
            score_buckets["0.60-0.79"] += 1
        elif score >= 0.50:
            score_buckets["0.50-0.59"] += 1
        else:
            score_buckets["0.00-0.49"] += 1

        by_source[source_kind].append({
            "candidate_id": row["candidate_id"],
            "domain_id": row["domain_id"],
            "score": score,
            "display_name": row["display_name"],
            "record_keys": sorted(record.keys()),
            "title": record.get("title") or record.get("name"),
            "description": record.get("description") or record.get("extract") or record.get("summary"),
            "author": record.get("author"),
            "publisher": record.get("publisher"),
            "feed_title": record.get("feed_title"),
            "channel_title": record.get("channel_title"),
            "link": record.get("link") or record.get("url") or record.get("source_url") or record.get("canonical_url"),
            "blockers": classify_blocker(row),
        })

    samples: list[dict[str, Any]] = []
    remaining = max(1, int(args.samples))
    for source_kind in sorted(by_source):
        if remaining <= 0:
            break
        source_rows = by_source[source_kind]
        take = min(max(1, remaining // max(1, len(by_source))), len(source_rows))
        samples.extend(source_rows[:take])
        remaining -= take
    if remaining > 0:
        already = {item["candidate_id"] for item in samples}
        for source_kind in sorted(by_source):
            for item in by_source[source_kind]:
                if item["candidate_id"] in already:
                    continue
                samples.append(item)
                remaining -= 1
                if remaining <= 0:
                    break
            if remaining <= 0:
                break

    receipt = {
        "schema": "dio.market_sensorium.unresolved_source_shape_audit.v1",
        "db": str(db),
        "unresolved_examined": len(rows),
        "source_kind_counts": dict(source_counts),
        "candidate_kind_counts": dict(candidate_kind_counts),
        "score_buckets": dict(score_buckets),
        "blocker_counts": dict(blocker_counts),
        "record_key_frequency": dict(record_key_counts.most_common()),
        "payload_key_frequency": dict(payload_key_counts.most_common()),
        "samples": samples,
        "interpretation": {
            "purpose": "Reveal the actual source record morphology before widening entity resolution.",
            "target_created": False,
            "lead_created": False,
            "market_demand_claimed": False,
            "authority_created": False,
            "external_effects": False,
        },
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
