from __future__ import annotations

import csv
from pathlib import Path

from market_sensorium.queries import mark_refreshed, select_domain_query_batch


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_domain_query_scheduler_prioritises_weak_and_rotates(tmp_path: Path) -> None:
    domains = tmp_path / "domains.csv"
    write_csv(
        domains,
        ["domain_id", "domain_family", "domain_name", "domain_type", "atlas_status"],
        [
            {"domain_id": "D1", "domain_family": "EDUCATION", "domain_name": "Assessment", "domain_type": "DOMAIN", "atlas_status": "SEED"},
            {"domain_id": "D2", "domain_family": "HEALTH", "domain_name": "Public health", "domain_type": "DOMAIN", "atlas_status": "SEED"},
            {"domain_id": "D3", "domain_family": "FINANCE", "domain_name": "Banking", "domain_type": "DOMAIN", "atlas_status": "SEED"},
        ],
    )
    history = tmp_path / "history.json"
    batch = select_domain_query_batch(domains, history, weak_domain_ids={"D2"}, limit=2)
    assert batch["domains"][0]["domain_id"] == "D2"
    assert all("South Africa" in item["query"] for item in batch["domains"])
    mark_refreshed(
        history,
        batch,
        {
            "refreshed_at": "2026-08-18T00:00:00+00:00",
            "results": [
                {"domain_id": item["domain_id"], "state": "refreshed"}
                for item in batch["domains"]
            ],
        },
    )
    assert history.is_file()
    next_batch = select_domain_query_batch(domains, history, weak_domain_ids=set(), limit=1)
    assert next_batch["domains"][0]["domain_id"] == "D3"
