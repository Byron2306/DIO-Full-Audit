from pathlib import Path

from scripts.refresh_all_market_intelligence import discover_campaigns, run_cycle


def test_market_intelligence_cycle_discovers_canonical_campaigns():
    campaigns = discover_campaigns()
    assert len(campaigns) == 5
    assert all(item["campaign_id"].startswith("CMP-") for item in campaigns)


def test_dry_run_has_no_release_authority():
    receipt = run_cycle(dry_run=True)
    assert receipt["summary"] == {"campaigns": 5, "refreshed": 0, "planned": 5, "failed": 0}
    assert receipt["publication"] == "not_authorised"
    assert receipt["outreach"] == "not_authorised"
    assert receipt["spend"] == "not_authorised"
