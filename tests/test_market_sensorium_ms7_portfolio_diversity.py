from __future__ import annotations

import csv
from pathlib import Path

from market_sensorium.core import MarketSensoriumStore
from market_sensorium.query_learning import learn_discovery_queries


def _write_domains(path: Path, count: int = 10) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["domain_id", "domain_name", "domain_family", "domain_type", "atlas_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(1, count + 1):
            writer.writerow({
                "domain_id": f"D{index}",
                "domain_name": f"Domain {index}",
                "domain_family": "test_family",
                "domain_type": "DOMAIN",
                "atlas_status": "ACTIVE",
            })


def test_ms7_reserves_one_portfolio_slot_without_overriding_local_identity_precedence(tmp_path: Path) -> None:
    root = tmp_path
    _write_domains(root / "config" / "atlas" / "dio_atlas_universal_domain_registry.csv")
    db = root / "state" / "market_sensorium" / "market_sensorium.sqlite"

    with MarketSensoriumStore(db) as store:
        for index in range(1, 10):
            store.record_discovery_candidate(
                source_kind="DOMAIN_GOOGLE_NEWS_RSS",
                source_ref=f"state/market_sensorium/domain_signals/D{index}.json",
                candidate_kind="PUBLIC_DOMAIN_SIGNAL",
                display_name=f"Unresolved organisation {index}",
                domain_id=f"D{index}",
                morphology=f"Domain {index}",
                score=0.7,
                state="UNRESOLVED_ENTITY",
                payload={"market_demand_claimed": False, "authority_created": False},
            )
        summary = learn_discovery_queries(root, store, max_domains=8)

    counts = summary["query_kind_counts"]
    assert summary["selected_queries"] == 8
    assert summary["selected_domains"] == 8
    assert counts["ENTITY_RESOLUTION"] == 7
    assert counts["BROADEN_DISCOVERY"] == 1
    assert summary["portfolio_diversity_reserve_applied"] is True
    assert summary["portfolio_diversity_reserve_kind"] == "BROADEN_DISCOVERY"
    assert summary["local_driver_precedence_preserved"] is True
    assert summary["bounded_exploration"] is True
    assert summary["authority_created"] is False

    entity_examples = [item for item in summary["examples"] if item["query_kind"] == "ENTITY_RESOLUTION"]
    assert entity_examples
    assert all(int(item["driver_precedence"]) == 6 for item in entity_examples)
