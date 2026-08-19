from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .core import utc_now


def load_domain_rows(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        row for row in rows
        if row.get("domain_type") == "DOMAIN"
        and row.get("atlas_status") != "UNKNOWN_DOMAIN_TEST_ONLY"
    ]


def load_history(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema": "dio.market_sensorium.domain_query_history.v1", "domains": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema": "dio.market_sensorium.domain_query_history.v1", "domains": {}}


def build_query(domain: dict[str, str]) -> str:
    name = str(domain.get("domain_name") or "").strip()
    family = str(domain.get("domain_family") or "").strip().replace("_", " ").lower()
    return f'"{name}" South Africa {family} organisation services challenges'.strip()


def select_domain_query_batch(
    domain_registry: Path,
    history_path: Path,
    *,
    weak_domain_ids: set[str] | None = None,
    limit: int = 8,
) -> dict[str, Any]:
    domains = load_domain_rows(domain_registry)
    history = load_history(history_path)
    past = history.get("domains") or {}
    weak = weak_domain_ids or set()

    def order(row: dict[str, str]) -> tuple[int, str, str]:
        domain_id = row["domain_id"]
        last = str((past.get(domain_id) or {}).get("last_refreshed_at") or "")
        return (0 if domain_id in weak else 1, last, domain_id)

    selected = sorted(domains, key=order)[:max(1, int(limit))]
    return {
        "schema": "dio.market_sensorium.domain_query_batch.v1",
        "created_at": utc_now(),
        "region_code": "ZA",
        "relevance_language": "en",
        "published_after_days": 180,
        "max_results_per_source": 5,
        "domains": [
            {
                "domain_id": row["domain_id"],
                "domain_name": row["domain_name"],
                "domain_family": row["domain_family"],
                "query": build_query(row),
                "baseline_state": "WEAK_FAMILY_PRIOR" if row["domain_id"] in weak else "SEEDED_PRIOR",
            }
            for row in selected
        ],
        "authority_created": False,
        "external_effects": False,
    }


def mark_refreshed(history_path: Path, batch: dict[str, Any], result: dict[str, Any]) -> None:
    history = load_history(history_path)
    domains = history.setdefault("domains", {})
    result_by_id = {str(row.get("domain_id")): row for row in result.get("results") or []}
    for item in batch.get("domains") or []:
        domain_id = str(item.get("domain_id") or "")
        outcome = result_by_id.get(domain_id) or {}
        domains[domain_id] = {
            "last_refreshed_at": result.get("refreshed_at") or utc_now(),
            "state": outcome.get("state") or "unknown",
            "youtube_records": outcome.get("youtube_records", 0),
            "news_records": outcome.get("news_records", 0),
            "query": item.get("query"),
        }
    history["updated_at"] = utc_now()
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(history, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
