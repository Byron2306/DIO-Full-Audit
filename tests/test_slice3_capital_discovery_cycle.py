from pathlib import Path

from scripts.run_capital_support_discovery_cycle import run_cycle


def test_cycle_refreshes_discovers_maps_hypothesises_ranks_without_contact(tmp_path: Path):
    receipt = run_cycle(tmp_path, observations=[{
        "adapter": {
            "source_type": "public_web",
            "permitted_discovery_mode": "public_web",
            "source_url": "https://example.org/opportunity",
            "last_seen": "2026-09-09T19:00:00Z",
        },
        "organisation": {"organisation_id": "org1", "name": "Example Org", "organisation_type": "foundation"},
        "opportunity": {"opportunity_id": "opp1", "opportunity_type": "DONOR", "domains": ["education", "OER"]},
    }], search_budget=5)
    assert receipt["processed"] == 1
    assert receipt["ranked"] >= 1
    assert receipt["drafts_created"] >= 1
    assert receipt["external_contacts_sent"] == 0
    assert receipt["authority_created"] is False
    assert receipt["search_budget_used"] <= 5
    assert (tmp_path / "state" / "market_capital" / "rankings" / "CAPITAL_SUPPORT_PRIORITY.json").is_file()
    assert (tmp_path / "state" / "market_capital" / "drafts" / "opp1.json").is_file()


def test_cycle_uses_bounded_atlas_search_expansion_only(tmp_path: Path):
    receipt = run_cycle(tmp_path, observations=[{
        "adapter": {
            "source_type": "public_web",
            "permitted_discovery_mode": "public_web",
            "source_url": "https://example.org/ai-fund",
            "last_seen": "2026-09-09T19:00:00Z",
        },
        "organisation": {"organisation_id": "org2", "name": "AI Fund", "organisation_type": "venture_fund"},
        "opportunity": {"opportunity_id": "opp2", "opportunity_type": "INVESTOR", "domains": ["AI governance", "enterprise AI"]},
    }], search_budget=2)
    assert len(receipt["search_expansion_suggestions"]) <= 2
    assert receipt["external_searches_executed"] == 0
    assert receipt["external_contacts_sent"] == 0
