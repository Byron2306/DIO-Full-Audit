from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_business_workbench_exposes_census_and_recommendation_endpoints():
    source = (ROOT / "scripts" / "serve_business_workbench.py").read_text(encoding="utf-8")
    assert "/api/business/capital-support/census" in source
    assert "/api/business/capital-support/recommendations" in source


def test_control_deck_capital_ui_exposes_census_counts_and_recommendations():
    ui = (ROOT / "dashboard" / "capital_support_slice3.js").read_text(encoding="utf-8")
    for token in (
        "Census organisations",
        "Census people",
        "Census relationships",
        "Recommendation",
        "Rank movement",
    ):
        assert token in ui
    assert "authority_created" in ui


def test_market_ui_contains_review_draft_and_ask_vesper_affordances():
    ui = (ROOT / "dashboard" / "market_capital_support_slice3.js").read_text(encoding="utf-8")
    assert "Review draft" in ui
    assert "Ask Vesper why" in ui
    assert "Why this target" in ui
    assert "Why now" in ui
    assert "send_authority" in ui


def test_goldeneye_ui_exposes_recommendation_and_movement_explanation():
    ui = (ROOT / "dashboard" / "goldeneye_capital_slice3.js").read_text(encoding="utf-8")
    assert "Recommendation" in ui
    assert "Movement" in ui
    assert "movement_explanations" in ui
    assert "route_state" in ui


def test_atlas_capital_census_surface_exists_with_search_lineage():
    ui = (ROOT / "dashboard" / "atlas_capital_census.js").read_text(encoding="utf-8")
    assert "Atlas capital census" in ui
    assert "Search signature" in ui
    assert "Matched domain" in ui
    assert "Adjacent search" in ui
    assert "authority_created" in ui
