from pathlib import Path

from market_capital.vesper import answer_capital_query


ROOT = Path(__file__).resolve().parents[1]


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
                "priority_score": 91,
                "rank_movement": 2,
                "rank_movement_reason": "Fresh published thesis signal increased timing score.",
                "atlas_fit": {
                    "fit_score": 92,
                    "fit_reason": "Published AI thesis overlaps DIO governance and evidence capabilities.",
                    "domain_path": ["AI & Digital Trust", "Governed AI"],
                    "primary_products": ["Evidex"],
                    "proof_bundle": ["proof/evidex.json"],
                    "missing_proof": ["verified enterprise deployment reference"],
                },
                "action_recommendation": {
                    "recommendation": "APPROACH_NOW",
                    "why_target": "Strong governed-AI thesis fit.",
                    "why_now": "Fresh thesis signal and verified public route.",
                    "reasoning": {"route_state": "PUBLIC_ROUTE_VERIFIED"},
                    "outreach_bundle": {
                        "draft_subject": "DIO | governed AI",
                        "draft_outreach": "A bounded draft.",
                        "send_authority": False,
                        "submission_authority": False,
                        "financial_commitment_authority": False,
                        "authority_created": False,
                        "external_effects": False,
                    },
                },
            },
            {
                "rank": 2,
                "opportunity_id": "OPP-GRANT",
                "opportunity_type": "GRANT",
                "organisation": "Education Foundation",
                "geography": "Global",
                "deadline": "2026-09-15",
                "atlas_fit": {
                    "fit_reason": "Education and OER fit.",
                    "domain_path": ["Education & Research", "Open Education"],
                    "missing_proof": ["current learner impact metric"],
                },
                "action_recommendation": {
                    "recommendation": "RESEARCH_FIRST",
                    "why_target": "Strong OER mandate overlap.",
                    "why_now": "Deadline is near but eligibility needs verification.",
                },
            },
        ],
        "authority_created": False,
        "external_effects": False,
    }


def _assert_safe(result):
    assert result["send_authority"] is False
    assert result["submission_authority"] is False
    assert result["financial_commitment_authority"] is False
    assert result["authority_created"] is False
    assert result["external_effects"] is False


def test_vesper_can_return_top_recommendations_without_send_authority():
    result = answer_capital_query(_state(), {"intent": "TOP_RECOMMENDATIONS", "limit": 5})
    assert len(result["items"]) <= 5
    assert result["items"][0]["opportunity_id"] == "OPP-1"
    _assert_safe(result)


def test_vesper_explains_why_target_is_recommended():
    result = answer_capital_query(_state(), {"intent": "EXPLAIN_RECOMMENDATION", "opportunity_id": "OPP-1"})
    assert result["why_target"]
    assert result["why_now"]
    assert result["truth_class"] == "ACTION_RECOMMENDATION_MODEL_OUTPUT"
    _assert_safe(result)


def test_vesper_supports_required_bounded_find_and_reasoning_intents():
    state = _state()
    by_type = answer_capital_query(state, {"intent": "FIND_BY_TYPE", "opportunity_type": "GRANT"})
    assert [row["opportunity_id"] for row in by_type["items"]] == ["OPP-GRANT"]

    by_domain = answer_capital_query(state, {"intent": "FIND_BY_DOMAIN", "domain": "Open Education"})
    assert [row["opportunity_id"] for row in by_domain["items"]] == ["OPP-GRANT"]

    by_geo = answer_capital_query(state, {"intent": "FIND_BY_GEOGRAPHY", "geography": "South Africa"})
    assert [row["opportunity_id"] for row in by_geo["items"]] == ["OPP-1"]

    deadlines = answer_capital_query(state, {"intent": "DEADLINES_SOON", "as_of": "2026-09-10", "days": 10})
    assert [row["opportunity_id"] for row in deadlines["items"]] == ["OPP-GRANT", "OPP-1"]

    movement = answer_capital_query(state, {"intent": "EXPLAIN_RANK_MOVE", "opportunity_id": "OPP-1"})
    assert "Fresh published thesis signal" in movement["text"]

    missing = answer_capital_query(state, {"intent": "MISSING_PROOF", "opportunity_id": "OPP-1"})
    assert "verified enterprise deployment reference" in missing["missing_proof"]

    for result in (by_type, by_domain, by_geo, deadlines, movement, missing):
        _assert_safe(result)


def test_vesper_draft_intent_returns_governed_draft_without_send():
    result = answer_capital_query(_state(), {"intent": "DRAFT_WITHOUT_SEND", "opportunity_id": "OPP-1"})
    assert result["draft"]["draft_subject"] == "DIO | governed AI"
    assert result["draft"]["send_authority"] is False
    _assert_safe(result)


def test_existing_presence_runtime_is_still_the_only_vesper_runtime():
    source = (ROOT / "presence_core" / "engine.py").read_text(encoding="utf-8")
    bridge = (ROOT / "scripts" / "serve_presence_bridge.py").read_text(encoding="utf-8")
    assert "process_envelope" in bridge
    assert "from presence_core.engine import process_envelope" in bridge
    assert "serve_vesper_capital" not in source
    assert "serve_vesper_capital" not in bridge
