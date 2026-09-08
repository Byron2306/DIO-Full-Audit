from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "products" / "control_deck_capital.py"


def load_capital_module():
    if not MODULE_PATH.is_file():
        pytest.fail("Control Deck capital projector is not implemented yet")
    spec = importlib.util.spec_from_file_location("control_deck_capital", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def investor_record(
    target_id: str,
    organisation: str,
    fit: float,
    timing: float,
    decision: str,
    route: str,
    pitch_id: str = "product_factory",
    legalis: str = "not_evaluated",
    outreach: str = "blocked",
) -> dict:
    return {
        "schema": "dio.hivenance.marketing_hypothesis.v1",
        "hypothesis_id": f"HYP-{target_id}",
        "campaign_id": f"CMP-{target_id}",
        "source": {"target_id": target_id, "observation_id": f"OBS-{target_id}"},
        "product": {"product_line_id": "DIO_CAPITAL", "target_type": "investor"},
        "audience": {
            "market_type": "investor",
            "internal_research_organisation": organisation,
            "investor_type": "seed VC",
            "partner": "Example Partner",
        },
        "investor_strategy": {
            "schema": "dio.investor_strategy_decision.v1",
            "target_type": "investor",
            "route_state": route,
            "route_score": 4,
            "fit_score": fit,
            "fit_breakdown": {"thesis_fit_score": fit},
            "timing_score": timing,
            "timing_breakdown": {"timing_score": timing},
            "timing_decision": decision,
            "pitch_thesis": {
                "id": pitch_id,
                "name": "Product Factory / Venture Studio OS",
                "hook": "Pitch the governed product factory.",
                "proof_focus": ["DIO CapitalRoom", "Product Compiler"],
                "matched_signals": ["venture studio"],
                "match_score": 1,
            },
            "explanation": {
                "route": "Existing route retained.",
                "fit": "Strong fit.",
                "timing": "Fresh deployment signal.",
                "pitch": "Product factory won.",
            },
            "permission_note": "Fit and timing never grant permission.",
        },
        "gates": {
            "legalis_verdict": legalis,
            "electronic_sales_outreach": outreach,
            "publication": "operator_approval_required",
            "timing_is_permission": False,
        },
        "experiment": {"proof_asset": "docs/FUSION_WAVE9_CAPITALROOM_EXTERNAL_PROOF.md"},
    }


def write_record(directory: Path, name: str, payload: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(payload), encoding="utf-8")


def test_empty_registry_projects_truthful_dormant_capital_plane(tmp_path: Path) -> None:
    capital = load_capital_module()
    projection = capital.build_capital_projection(tmp_path)

    assert projection["schema"] == "dio.control_deck.capital_projection.v1"
    assert projection["state"] == "DORMANT_NO_INVESTOR_RECEIPTS"
    assert projection["summary"] == {
        "investor_universe_count": 0,
        "approach_now_count": 0,
        "watch_count": 0,
        "hold_count": 0,
        "outreach_authorized_count": 0,
    }
    assert projection["targets"] == []
    assert projection["truth_boundaries"]["projection_only"] is True
    assert projection["truth_boundaries"]["external_effects"] is False


def test_projection_ranks_targets_and_preserves_who_when_pitch_and_gates(tmp_path: Path) -> None:
    capital = load_capital_module()
    write_record(tmp_path, "a.json", investor_record("INV-A", "Alpha Ventures", 91, 88, "APPROACH_NOW", "PARTNERSHIP_ROUTE_AVAILABLE"))
    write_record(tmp_path, "b.json", investor_record("INV-B", "Beta Capital", 86, 61, "WATCH", "INSTITUTIONAL_ROUTE_AVAILABLE"))
    write_record(tmp_path, "c.json", investor_record("INV-C", "Gamma Fund", 52, 44, "HOLD", "RESEARCH_ONLY"))

    projection = capital.build_capital_projection(tmp_path)

    assert projection["state"] == "INVESTOR_STRATEGY_AVAILABLE"
    assert projection["summary"]["investor_universe_count"] == 3
    assert projection["summary"]["approach_now_count"] == 1
    assert projection["summary"]["watch_count"] == 1
    assert projection["summary"]["hold_count"] == 1
    assert projection["summary"]["outreach_authorized_count"] == 0
    assert [item["organisation"] for item in projection["targets"]] == ["Alpha Ventures", "Beta Capital", "Gamma Fund"]

    first = projection["targets"][0]
    assert first["fit_score"] == 91
    assert first["timing_score"] == 88
    assert first["timing_decision"] == "APPROACH_NOW"
    assert first["route_state"] == "PARTNERSHIP_ROUTE_AVAILABLE"
    assert first["pitch_thesis"]["id"] == "product_factory"
    assert first["legalis_verdict"] == "not_evaluated"
    assert first["outreach_authorized"] is False
    assert first["market_command"]["campaign_id"] == "CMP-INV-A"
    assert first["market_command"]["may_execute"] is False


def test_outreach_count_requires_existing_gate_to_be_allowed(tmp_path: Path) -> None:
    capital = load_capital_module()
    allowed = investor_record(
        "INV-ALLOW", "Allowed Ventures", 95, 92, "APPROACH_NOW", "PARTNERSHIP_ROUTE_AVAILABLE", legalis="ALLOW", outreach="allowed"
    )
    blocked = investor_record(
        "INV-BLOCK", "Blocked Ventures", 99, 99, "APPROACH_NOW", "PARTNERSHIP_ROUTE_AVAILABLE", legalis="ALLOW", outreach="blocked"
    )
    write_record(tmp_path, "allowed.json", allowed)
    write_record(tmp_path, "blocked.json", blocked)

    projection = capital.build_capital_projection(tmp_path)

    assert projection["summary"]["outreach_authorized_count"] == 1
    by_name = {item["organisation"]: item for item in projection["targets"]}
    assert by_name["Allowed Ventures"]["outreach_authorized"] is True
    assert by_name["Blocked Ventures"]["outreach_authorized"] is False
    assert all(item["market_command"]["may_execute"] is False for item in projection["targets"])


def test_non_investor_and_malformed_records_do_not_become_targets(tmp_path: Path) -> None:
    capital = load_capital_module()
    buyer = investor_record("BUYER", "Buyer Org", 99, 99, "APPROACH_NOW", "PARTNERSHIP_ROUTE_AVAILABLE")
    buyer["product"] = {"product_line_id": "HOMS_ASSESS", "target_type": "buyer"}
    malformed = {"schema": "something.else"}
    write_record(tmp_path, "buyer.json", buyer)
    write_record(tmp_path, "bad.json", malformed)

    projection = capital.build_capital_projection(tmp_path)

    assert projection["summary"]["investor_universe_count"] == 0
    assert projection["targets"] == []
    assert projection["source"]["ignored_record_count"] == 2


def test_control_deck_ui_and_server_expose_read_only_capital_projection() -> None:
    html = (ROOT / "dashboard" / "goldeneye-portfolio.html").read_text(encoding="utf-8")
    js = (ROOT / "dashboard" / "goldeneye-portfolio.js").read_text(encoding="utf-8")
    server = (ROOT / "scripts" / "serve_goldeneye_portfolio.py").read_text(encoding="utf-8")

    assert 'id="capital"' in html
    assert "Capital intelligence" in html
    assert "/api/control-deck/capital" in js
    assert "renderCapital" in js
    assert "/api/control-deck/capital" in server
    assert "capital_projection_is_read_only" in server
    assert 'method: "POST"' not in js
