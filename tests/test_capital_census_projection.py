from pathlib import Path

from market_capital.census import CapitalCensus
from market_capital.projection import capital_support_projection


def test_projection_is_small_ranked_view_over_large_registry(tmp_path: Path):
    census = CapitalCensus(tmp_path / "capital.sqlite")
    census.initialize()
    for index in range(60):
        census.upsert_organisation({
            "organisation_id": f"ORG-{index}",
            "canonical_name": f"Organisation {index}",
            "country": "ZA",
        })
    for index in range(8):
        is_grant = index % 2 == 0
        census.upsert_opportunity({
            "opportunity_id": f"OPP-{index}",
            "organisation_id": f"ORG-{index}",
            "opportunity_type": "GRANT" if is_grant else "INVESTOR",
            "title": f"Opportunity {index}",
            "atlas_fit_score": 70 + index,
            "type_fit": {"eligibility": 75, "thematic": 80} if is_grant else {"thesis": 80, "stage": 75},
            "timing_score": 80,
            "route_state": "APPLICATION_ROUTE_VERIFIED" if is_grant else "PUBLIC_ROUTE_VERIFIED",
            "route_quality": 65,
            "evidence_freshness": 90,
            "eligibility_state": "VERIFIED_ELIGIBLE" if is_grant else None,
        })
    state = capital_support_projection(census, limit=5)
    assert state["census_counts"]["organisations"] > len(state["items"])
    assert len(state["items"]) == 5
    assert state["total_rankable_opportunities"] == 8
    assert state["truth_class"] == "RANKED_PRIORITY_MODEL_OUTPUT"
    assert state["authority_created"] is False


def test_projection_preserves_census_count_truth_when_empty(tmp_path: Path):
    census = CapitalCensus(tmp_path / "capital.sqlite")
    census.initialize()
    census.upsert_organisation({"organisation_id": "ORG-1", "canonical_name": "Only Organisation"})
    state = capital_support_projection(census, limit=10)
    assert state["census_counts"]["organisations"] == 1
    assert state["census_counts"]["opportunities"] == 0
    assert state["items"] == []


def test_projection_carries_governed_action_recommendation(tmp_path: Path):
    census = CapitalCensus(tmp_path / "capital.sqlite")
    census.initialize()
    census.upsert_organisation({"organisation_id": "ORG-INV", "canonical_name": "Example Ventures"})
    census.upsert_opportunity({
        "opportunity_id": "OPP-INV",
        "organisation_id": "ORG-INV",
        "opportunity_type": "INVESTOR",
        "title": "Published AI investment thesis",
        "atlas_fit_score": 90,
        "type_fit": {"thesis": 90, "stage": 85, "proof": 90},
        "timing_score": 90,
        "route_state": "PUBLIC_ROUTE_VERIFIED",
        "route_quality": 90,
        "evidence_freshness": 90,
    })
    state = capital_support_projection(census, limit=5)
    row = state["items"][0]
    assert row["action_recommendation"]["recommendation"] == "APPROACH_NOW"
    assert row["action_recommendation"]["truth_class"] == "ACTION_RECOMMENDATION_MODEL_OUTPUT"
    assert row["action_recommendation"]["send_authority"] is False
    assert row["action_recommendation"]["authority_created"] is False
