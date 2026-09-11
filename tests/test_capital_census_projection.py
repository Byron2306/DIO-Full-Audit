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


def test_live_observation_projection_derives_model_inputs_without_inventing_eligibility(tmp_path: Path):
    census = CapitalCensus(tmp_path / "capital.sqlite")
    census.initialize()
    census.upsert_organisation({
        "organisation_id": "ORG-DGMT",
        "canonical_name": "DG Murray Trust",
        "observed_at": "2026-09-10T17:55:00Z",
    })
    census.upsert_opportunity({
        "opportunity_id": "OPP-DGMT",
        "organisation_id": "ORG-DGMT",
        "opportunity_type": "GRANT",
        "title": "Digital education access grant",
        "description": "Teacher development and digital learning access.",
        "route_state": "APPLICATION_ROUTE_VERIFIED",
        "public_contact_route": "https://example.org/apply",
        "truth_class": "PUBLIC_CAPITAL_SIGNAL_VERIFIED",
        "observed_at": "2026-09-10T17:55:00Z",
    })

    state = capital_support_projection(census, limit=5, root=Path("."))
    row = state["items"][0]

    assert row["organisation_name"] == "DG Murray Trust"
    assert row["evidence_freshness"] > 0
    assert row["route_quality"] >= 50
    assert row["timing_score"] > 0
    assert row["type_fit"]["thematic"] > 0
    assert row.get("eligibility_state") not in {"ELIGIBLE", "VERIFIED_ELIGIBLE"}
    assert row["priority_score"] > 17.25
    assert row["action_recommendation"]["recommendation"] == "RESEARCH_FIRST"


def test_live_projection_differentiates_distinct_atlas_evidence(tmp_path: Path):
    census = CapitalCensus(tmp_path / "capital.sqlite")
    census.initialize()
    for org_id, name in (("ORG-EDU", "Education Foundation"), ("ORG-AI", "AI Ventures")):
        census.upsert_organisation({"organisation_id": org_id, "canonical_name": name})

    census.upsert_opportunity({
        "opportunity_id": "OPP-EDU",
        "organisation_id": "ORG-EDU",
        "opportunity_type": "GRANT",
        "title": "Teacher development and digital learning fund",
        "description": "Open education and teacher development programme.",
        "status": "posted",
        "close_date": "2026-12-31",
        "route_state": "PUBLIC_ROUTE_VERIFIED",
        "observed_at": "2026-09-10T17:55:00Z",
    })
    census.upsert_opportunity({
        "opportunity_id": "OPP-AI",
        "organisation_id": "ORG-AI",
        "opportunity_type": "INVESTOR",
        "title": "Responsible AI infrastructure investment",
        "description": "We invest in governed AI and enterprise AI infrastructure.",
        "route_state": "APPLICATION_ROUTE_VERIFIED",
        "observed_at": "2026-09-10T17:55:00Z",
    })

    state = capital_support_projection(census, limit=5, root=Path("."))
    rows = {row["opportunity_id"]: row for row in state["items"]}

    assert rows["OPP-EDU"]["atlas_fit"]["recommended_pitch_family"] == "EDUCATION_OER_PUBLIC_GOOD"
    assert rows["OPP-AI"]["atlas_fit"]["recommended_pitch_family"] == "GOVERNED_AI_INFRASTRUCTURE"
    assert rows["OPP-EDU"]["priority_score"] != rows["OPP-AI"]["priority_score"]
