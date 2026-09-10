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
        census.upsert_opportunity({
            "opportunity_id": f"OPP-{index}",
            "organisation_id": f"ORG-{index}",
            "opportunity_type": "GRANT" if index % 2 == 0 else "INVESTOR",
            "title": f"Opportunity {index}",
            "atlas_fit_score": 70 + index,
            "type_fit": {"eligibility": 75, "thematic": 80} if index % 2 == 0 else {"thesis": 80, "stage": 75},
            "timing_score": 70,
            "route_quality": 65,
            "evidence_freshness": 90,
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
