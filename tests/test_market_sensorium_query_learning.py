from __future__ import annotations

import csv
import json
from pathlib import Path

from market_sensorium.core import MarketSensoriumStore
from market_sensorium.queries import select_domain_query_batch
from market_sensorium.query_learning import learn_discovery_queries


def _write_domains(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["domain_id", "domain_name", "domain_family", "domain_type", "atlas_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow({
            "domain_id": "D1",
            "domain_name": "Evidence operations",
            "domain_family": "professional_services",
            "domain_type": "DOMAIN",
            "atlas_status": "ACTIVE",
        })
        writer.writerow({
            "domain_id": "D2",
            "domain_name": "Learning support",
            "domain_family": "education",
            "domain_type": "DOMAIN",
            "atlas_status": "ACTIVE",
        })


def _write_baseline(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["domain_id", "provenance_kind"])
        writer.writeheader()
        writer.writerow({"domain_id": "D1", "provenance_kind": "FAMILY_FALLBACK"})
        writer.writerow({"domain_id": "D2", "provenance_kind": "TAG_MATCH"})


def test_ms7_builds_bounded_source_bound_queries_and_scheduler_consumes_them(tmp_path: Path) -> None:
    root = tmp_path
    domain_registry = root / "config" / "atlas" / "dio_atlas_universal_domain_registry.csv"
    _write_domains(domain_registry)
    _write_baseline(root / "state" / "market_sensorium" / "domain_baseline_candidates.csv")
    history = root / "state" / "market_sensorium" / "domain_query_history.json"
    history.write_text(json.dumps({
        "schema": "dio.market_sensorium.domain_query_history.v1",
        "domains": {
            "D1": {"query": '"Evidence operations" South Africa professional services organisation services challenges'}
        },
    }) + "\n", encoding="utf-8")

    db = root / "state" / "market_sensorium" / "market_sensorium.sqlite"
    with MarketSensoriumStore(db) as store:
        store.record_discovery_candidate(
            source_kind="DOMAIN_GOOGLE_NEWS_RSS",
            source_ref="state/market_sensorium/domain_signals/D1.json",
            candidate_kind="PUBLIC_DOMAIN_SIGNAL",
            display_name="Evidence reporting organisation update",
            domain_id="D1",
            morphology="Evidence operations",
            score=0.7,
            state="UNRESOLVED_ENTITY",
            payload={"market_demand_claimed": False, "authority_created": False},
        )
        summary = learn_discovery_queries(root, store, max_domains=2)

    assert summary["selected_queries"] == 2
    assert summary["selected_domains"] == 2
    assert summary["source_bound_selected_queries"] == 2
    assert summary["adaptive_selected_queries"] >= 1
    assert summary["bounded_exploration"] is True
    assert summary["query_execution_performed"] is False
    assert summary["market_demand_claimed"] is False
    assert summary["authority_created"] is False
    d1 = next(item for item in summary["examples"] if item["domain_id"] == "D1")
    assert d1["query_kind"] == "ENTITY_RESOLUTION"
    assert d1["query"] != '"Evidence operations" South Africa professional services organisation services challenges'

    batch = select_domain_query_batch(
        domain_registry,
        history,
        weak_domain_ids={"D1"},
        limit=2,
    )
    assert batch["schema"] == "dio.market_sensorium.domain_query_batch.v2"
    assert batch["learned_query_count"] == 2
    assert batch["static_fallback_count"] == 0
    assert all(item["query_origin"] == "MS7_LEARNED_DISCOVERY_QUERY" for item in batch["domains"])
    assert batch["query_execution_requires_refresh_public"] is True
    assert batch["authority_created"] is False


def test_scheduler_falls_back_to_static_queries_without_ms7_plan(tmp_path: Path) -> None:
    domain_registry = tmp_path / "domains.csv"
    _write_domains(domain_registry)
    history = tmp_path / "domain_query_history.json"
    batch = select_domain_query_batch(domain_registry, history, limit=1)
    assert batch["learned_query_count"] == 0
    assert batch["static_fallback_count"] == 1
    assert batch["domains"][0]["query_origin"] == "STATIC_DOMAIN_TEMPLATE"
    assert batch["authority_created"] is False
