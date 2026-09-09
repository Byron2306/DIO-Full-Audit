from pathlib import Path

from market_capital.ranking import rank_capital_opportunities

ROOT = Path(__file__).resolve().parents[1]


def test_ranking_preserves_type_specific_components_and_truth_class():
    rows = rank_capital_opportunities([
        {
            "opportunity_id": "inv1",
            "opportunity_type": "INVESTOR",
            "atlas_fit_score": 88,
            "type_fit": {"thesis": 90, "stage": 85, "geography": 80, "route": 70},
            "timing_score": 75,
            "route_quality": 70,
            "evidence_freshness": 95,
        },
        {
            "opportunity_id": "grant1",
            "opportunity_type": "GRANT",
            "atlas_fit_score": 92,
            "type_fit": {"eligibility": 100, "thematic": 95, "deadline": 60, "reporting_burden": 80},
            "timing_score": 65,
            "route_quality": 100,
            "evidence_freshness": 90,
        },
    ])
    assert {r["opportunity_type"] for r in rows} == {"INVESTOR", "GRANT"}
    assert all(r["truth_class"] == "RANKED_PRIORITY_MODEL_OUTPUT" for r in rows)
    assert all("score_components" in r for r in rows)
    assert all(r["authority_created"] is False for r in rows)
    assert all(r["next_action"] in {"DRAFT_READY", "NEEDS_RESEARCH", "HOLD", "DO_NOT_CONTACT"} for r in rows)


def test_rank_movement_explains_change_without_claiming_fundability():
    rows = rank_capital_opportunities([
        {
            "opportunity_id": "opp1",
            "opportunity_type": "DONOR",
            "atlas_fit_score": 90,
            "type_fit": {"mission": 90, "impact": 85},
            "timing_score": 80,
            "route_quality": 75,
            "evidence_freshness": 90,
            "prior_rank": 4,
        }
    ])
    assert rows[0]["rank"] == 1
    assert rows[0]["rank_movement"] == 3
    assert rows[0]["rank_movement_reason"]
    assert rows[0]["willingness_to_fund"] == "UNPROVED"


def test_goldeneye_exposes_read_only_capital_support_route():
    source = (ROOT / "scripts/serve_goldeneye_ms10.py").read_text(encoding="utf-8")
    assert '"/api/goldeneye/capital-support"' in source
    assert "CAPITAL_SUPPORT_PRIORITY.json" in source
