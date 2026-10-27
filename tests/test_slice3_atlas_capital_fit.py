from pathlib import Path

from market_capital.atlas_fit import adjacent_search_suggestions, build_capital_support_fit


def test_atlas_maps_grant_to_narrow_product_and_proof_wedge(tmp_path: Path):
    fit = build_capital_support_fit(tmp_path, {
        "opportunity_id": "opp_edu",
        "opportunity_type": "GRANT",
        "domains": ["education", "OER", "teacher development", "Africa"],
        "criteria": ["SDG4", "digital learning"],
    })
    assert fit["truth_class"] == "STRATEGIC_FIT_MODEL_OUTPUT"
    assert fit["authority_created"] is False
    assert fit["primary_products"]
    assert "HOMS Learning Studio" in fit["primary_products"]
    assert "funding_modes" in fit
    assert len(fit["primary_products"]) <= 6
    suggestions = adjacent_search_suggestions(fit)
    assert suggestions
    assert all(item["authority_created"] is False for item in suggestions)


def test_atlas_investor_ai_governance_fit_uses_governed_ai_wedge(tmp_path: Path):
    fit = build_capital_support_fit(tmp_path, {
        "opportunity_id": "opp_ai",
        "opportunity_type": "INVESTOR",
        "domains": ["AI governance", "enterprise AI", "regtech"],
        "criteria": ["B2B software", "Africa"],
    })
    assert "DIO AI Assurance" in fit["primary_products"]
    assert fit["recommended_pitch_family"] in {
        "GOVERNED_AI_INFRASTRUCTURE",
        "EVIDENCE_FIRST_TRUST_REGTECH",
    }
    assert fit["truth_class"] != "MARKET_DEMAND"
