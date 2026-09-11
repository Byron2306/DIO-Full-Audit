from pathlib import Path

from presence_core.policy import authorize
from presence_core.router import route_message
from presence_core.capital_queries import answer_capital_query


ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "config" / "routes.json"


def _intent(text: str) -> str:
    return route_message(text, "operator", ROUTES).intent


def _state():
    return {
        "items": [
            {
                "rank": 1,
                "opportunity_id": "OPP-1",
                "opportunity_type": "INVESTOR",
                "organisation": "Example Ventures",
                "geography": "South Africa",
                "deadline": "2026-09-20",
                "rank_movement": 2,
                "rank_movement_reason": "Fresh thesis signal.",
                "atlas_fit": {
                    "domain_path": ["AI & Digital Trust", "Governed AI"],
                    "fit_reason": "Governed AI fit.",
                    "missing_proof": ["enterprise deployment reference"],
                },
                "action_recommendation": {
                    "recommendation": "APPROACH_NOW",
                    "why_target": "Governed AI fit.",
                    "why_now": "Fresh thesis signal.",
                },
            }
        ]
    }


def test_existing_vesper_router_exposes_full_capital_query_vocabulary():
    assert _intent("Find capital opportunities in the Governed AI domain") == "capital_find_domain"
    assert _intent("Show funding targets in South Africa") == "capital_find_geography"
    assert _intent("What capital deadlines are due soon?") == "capital_deadlines"
    assert _intent("Why did OPP-1 move in rank?") == "capital_rank_move"
    assert _intent("What proof is missing for OPP-1?") == "capital_missing_proof"


def test_new_capital_intents_remain_operator_only():
    for intent in (
        "capital_find_domain",
        "capital_find_geography",
        "capital_deadlines",
        "capital_rank_move",
        "capital_missing_proof",
    ):
        assert authorize("operator", intent) == (True, "allowed")
        assert authorize("public", intent)[0] is False


def test_presence_capital_query_wrapper_delegates_to_bounded_census_brain():
    state = _state()
    domain = answer_capital_query("capital_find_domain", "Governed AI", state)
    assert domain["items"][0]["opportunity_id"] == "OPP-1"

    geo = answer_capital_query("capital_find_geography", "South Africa", state)
    assert geo["items"][0]["opportunity_id"] == "OPP-1"

    movement = answer_capital_query("capital_rank_move", "Why did OPP-1 move in rank?", state)
    assert "Fresh thesis signal" in movement["text"]

    missing = answer_capital_query("capital_missing_proof", "What proof is missing for OPP-1?", state)
    assert "enterprise deployment reference" in missing["missing_proof"]

    for result in (domain, geo, movement, missing):
        assert result["send_authority"] is False
        assert result["submission_authority"] is False
        assert result["financial_commitment_authority"] is False
        assert result["authority_created"] is False
        assert result["external_effects"] is False
