from __future__ import annotations

from pathlib import Path

from market_capital.public_research import load_public_research_registry, pages_for_source


ROOT = Path(__file__).resolve().parents[1]


def test_public_research_registry_is_broad_global_and_multi_class():
    rows = load_public_research_registry(ROOT)
    assert len(rows) >= 40
    source_ids = {row.source_id for row in rows}
    assert {
        "SRC-FIRST-PARTY-PROGRAMME",
        "SRC-INVESTOR-PUBLIC-WEB",
        "SRC-PHILANTHROPY-PUBLIC-WEB",
        "SRC-PATRONAGE-PUBLIC-WEB",
    } <= source_ids
    capital_types = {value for row in rows for value in row.capital_types}
    assert {"INVESTOR", "GRANT", "DONOR", "SPONSOR", "PATRONAGE", "ACCELERATOR", "PRIZE"} <= capital_types
    geographies = {value for row in rows for value in row.geographies}
    assert "ZA" in geographies
    assert "AFRICA" in geographies
    assert "GLOBAL" in geographies
    assert all(row.url.startswith("https://") for row in rows)
    assert all(row.organisation_name for row in rows)


def test_registry_pages_are_injected_only_for_matching_source_and_budget():
    rows = load_public_research_registry(ROOT)
    pages = pages_for_source(rows, "SRC-INVESTOR-PUBLIC-WEB", limit=3)
    assert len(pages) == 3
    assert all(page["facts"]["organisation_name"] for page in pages)
    assert all(page["facts"]["opportunity_type"] in {"INVESTOR", "ACCELERATOR", "PRIZE", "SPONSOR"} for page in pages)
    assert all(page["policy_state"] == "READY" for page in pages)
    assert all(page["facts"]["route_requires_review"] is True for page in pages)
    assert all("public_email" not in page["facts"] for page in pages)
