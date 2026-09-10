from pathlib import Path

from market_capital.cockpit import capital_support_cockpit


def test_capital_support_cockpit_empty_state_is_truthful(tmp_path: Path):
    state = capital_support_cockpit(tmp_path)
    assert state["schema"] == "dio.business.capital_support_cockpit.v1"
    assert state["state"] == "EMPTY"
    assert state["summary"]["opportunity_count"] == 0
    assert state["summary"]["draft_ready"] == 0
    assert state["summary"]["engaged_cases"] == 0
    assert state["by_type"] == {
        "INVESTOR": 0,
        "GRANT": 0,
        "DONOR": 0,
        "SPONSOR": 0,
        "PATRONAGE": 0,
        "ACCELERATOR": 0,
        "PRIZE": 0,
    }
    assert state["authority_created"] is False
    assert state["external_effects"] is False


def test_control_deck_exposes_and_injects_slice3_capital_support_ui():
    source = Path("scripts/serve_business_workbench.py").read_text(encoding="utf-8")
    assert '"/api/business/capital-support"' in source
    assert 'dashboard/capital_support_slice3.js' in source


def test_goldeneye_page_renders_capital_support_priority_plane():
    page = Path("dashboard/goldeneye-ms10.html").read_text(encoding="utf-8")
    assert "Capital & Support" in page
    assert "/api/goldeneye/capital-support" in page
    assert "capital-support-priority" in page


def test_market_command_injects_capital_support_draft_ui():
    source = Path("scripts/serve_market_command_ms10.py").read_text(encoding="utf-8")
    assert 'dashboard/market_capital_support_slice3.js' in source
    ui = Path("dashboard/market_capital_support_slice3.js").read_text(encoding="utf-8")
    assert "/api/market/capital-support/draft" in ui
    assert "LINGUA" in ui
    assert "send_authority" in ui
