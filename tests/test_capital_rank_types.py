from market_capital.ranking import score_opportunity


def test_grant_and_investor_use_different_score_components():
    grant = score_opportunity({
        "opportunity_id": "G-1",
        "opportunity_type": "GRANT",
        "atlas_fit_score": 82,
        "type_fit": {"eligibility": 90, "thematic": 85, "deadline": 70, "evidence": 80},
        "timing_score": 75,
        "route_quality": 80,
        "evidence_freshness": 90,
    })
    investor = score_opportunity({
        "opportunity_id": "I-1",
        "opportunity_type": "INVESTOR",
        "atlas_fit_score": 82,
        "type_fit": {"thesis": 92, "stage": 80, "cheque": 70, "capital_use": 85, "proof": 88},
        "timing_score": 75,
        "route_quality": 80,
        "evidence_freshness": 90,
    })
    assert "eligibility" in grant["score_components"]
    assert "thesis" not in grant["score_components"]
    assert "thesis" in investor["score_components"]
    assert "eligibility" not in investor["score_components"]
    assert grant["truth_class"] == "RANKED_PRIORITY_MODEL_OUTPUT"
    assert investor["truth_class"] == "RANKED_PRIORITY_MODEL_OUTPUT"
    assert grant["authority_created"] is False
    assert investor["authority_created"] is False


def test_rank_movement_explains_freshness_change_when_supplied():
    row = score_opportunity({
        "opportunity_id": "G-2",
        "opportunity_type": "GRANT",
        "atlas_fit_score": 80,
        "type_fit": {"eligibility": 80, "thematic": 80},
        "timing_score": 70,
        "route_quality": 70,
        "evidence_freshness": 95,
        "prior_score_components": {"evidence_freshness": 40},
    })
    assert any("freshness" in item.lower() for item in row["component_changes"])
