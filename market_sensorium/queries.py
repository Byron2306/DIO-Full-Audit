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


def load_learned_plan(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


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
    learned_plan_path: Path | None = None,
) -> dict[str, Any]:
    domains = load_domain_rows(domain_registry)
    by_id = {row["domain_id"]: row for row in domains}
    history = load_history(history_path)
    past = history.get("domains") or {}
    weak = weak_domain_ids or set()
    learned_plan = load_learned_plan(learned_plan_path)
    learned_items = [
        item for item in learned_plan.get("domains") or []
        if isinstance(item, dict)
        and item.get("domain_id") in by_id
        and str(item.get("query") or "").strip()
    ]

    def order(row: dict[str, str]) -> tuple[int, str, str]:
        domain_id = row["domain_id"]
        last = str((past.get(domain_id) or {}).get("last_refreshed_at") or "")
        return (0 if domain_id in weak else 1, last, domain_id)

    cap = max(1, int(limit))
    selected: list[tuple[dict[str, str], dict[str, Any] | None]] = []
    seen: set[str] = set()

    # Learned selection order is already evidence-ranked by MS-7. Preserve it.
    for item in learned_items:
        domain_id = str(item.get("domain_id") or "")
        if domain_id in seen or len(selected) >= cap:
            continue
        selected.append((by_id[domain_id], item))
        seen.add(domain_id)

    # Fill any unused slots with the prior bounded rotating scheduler.
    for row in sorted(domains, key=order):
        if len(selected) >= cap:
            break
        domain_id = row["domain_id"]
        if domain_id in seen:
            continue
        selected.append((row, None))
        seen.add(domain_id)

    batch_domains: list[dict[str, Any]] = []
    for row, learned in selected:
        domain_id = row["domain_id"]
        if learned is None:
            batch_domains.append({
                "domain_id": domain_id,
                "domain_name": row["domain_name"],
                "domain_family": row["domain_family"],
                "query": build_query(row),
                "query_origin": "STATIC_DOMAIN_TEMPLATE",
                "learned_query_id": None,
                "query_kind": "STATIC_FALLBACK",
                "evidence_digest": None,
                "source_driver_count": 0,
                "novelty_score": None,
                "baseline_state": "WEAK_FAMILY_PRIOR" if domain_id in weak else "SEEDED_PRIOR",
            })
            continue
        batch_domains.append({
            "domain_id": domain_id,
            "domain_name": row["domain_name"],
            "domain_family": row["domain_family"],
            "query": str(learned.get("query") or "").strip(),
            "query_origin": "MS7_LEARNED_DISCOVERY_QUERY",
            "learned_query_id": learned.get("learned_query_id"),
            "query_kind": learned.get("query_kind"),
            "evidence_digest": learned.get("evidence_digest"),
            "source_driver_count": int(learned.get("source_driver_count") or 0),
            "novelty_score": learned.get("novelty_score"),
            "baseline_state": learned.get("baseline_state") or (
                "WEAK_FAMILY_PRIOR" if domain_id in weak else "EVIDENCE_ADAPTIVE"
            ),
        })

    learned_count = sum(1 for item in batch_domains if item["query_origin"] == "MS7_LEARNED_DISCOVERY_QUERY")
    return {
        "schema": "dio.market_sensorium.domain_query_batch.v2",
        "created_at": utc_now(),
        "region_code": "ZA",
        "relevance_language": "en",
        "published_after_days": 180,
        "max_results_per_source": 5,
        "query_policy": "MS7_LEARNED_WHEN_AVAILABLE_FALLBACK_STATIC",
        "learned_query_count": learned_count,
        "static_fallback_count": len(batch_domains) - learned_count,
        "domains": batch_domains,
        "query_execution_requires_refresh_public": True,
        "query_selection_is_market_truth": False,
        "market_demand_claimed": False,
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
            "query_origin": item.get("query_origin") or "UNKNOWN",
            "learned_query_id": item.get("learned_query_id"),
            "query_kind": item.get("query_kind"),
            "evidence_digest": item.get("evidence_digest"),
            "source_driver_count": int(item.get("source_driver_count") or 0),
            "novelty_score": item.get("novelty_score"),
        }
    history["updated_at"] = utc_now()
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(history, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
