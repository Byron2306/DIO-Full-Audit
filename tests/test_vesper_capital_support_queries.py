from pathlib import Path

from presence_core.authority import authorize_external_reply
from presence_core.policy import authorize
from presence_core.router import route_message


ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "config" / "routes.json"


def _intent(text: str) -> str:
    return route_message(text, "operator", ROUTES).intent


def test_routes_capital_priority_question_to_existing_vesper_cortex():
    assert _intent("Vesper, who should I approach for funding right now?") == "capital_priority"


def test_routes_rank_explanation_and_ui_event_intent():
    assert _intent("Why is OPP-123 ranked first?") == "capital_explain"
    assert _intent("EXPLAIN_RECOMMENDATION OPP-123") == "capital_explain"


def test_routes_draft_without_send_to_governed_capital_draft():
    assert _intent("Draft an email to OPP-123 without sending it") == "capital_draft"


def test_routes_grant_discovery_query():
    assert _intent("Find grants for education and OER") == "capital_grants"


def test_routes_patronage_query():
    assert _intent("Suggest Patreon or patronage propositions") == "capital_patronage"


def test_capital_queries_are_operator_read_only_intents():
    for intent in (
        "capital_priority",
        "capital_explain",
        "capital_draft",
        "capital_grants",
        "capital_patronage",
    ):
        assert authorize("operator", intent) == (True, "allowed")
        assert authorize("public", intent)[0] is False


def test_capital_operator_replies_are_safe_external_reply_intents(monkeypatch):
    monkeypatch.setenv("DIO_PRESENCE_CORE_TELEGRAM_REPLIES", "1")
    envelope = {"channel": "telegram"}
    for intent in (
        "capital_priority",
        "capital_explain",
        "capital_draft",
        "capital_grants",
        "capital_patronage",
    ):
        result = {
            "decision": {"intent": intent},
            "reply": {"text": "Read-only capital guidance."},
            "authority": {
                "spend_authorized": False,
                "fulfilment_released": False,
                "attachment_processed": False,
                "send_authorized": False,
                "submission_authorized": False,
                "financial_commitment_authorized": False,
            },
        }
        receipt = authorize_external_reply(envelope, result)
        assert receipt["authorized"] is True
        assert "intent_not_reply_authorized" not in receipt["reasons"]
        assert receipt["spend_authorized"] is False
        assert receipt["fulfilment_release_authorized"] is False
        assert receipt["attachment_processing_authorized"] is False


def test_existing_presence_engine_is_the_capital_query_runtime():
    source = (ROOT / "presence_core" / "engine.py").read_text(encoding="utf-8")
    bridge = (ROOT / "scripts" / "serve_presence_bridge.py").read_text(encoding="utf-8")
    assert "capital_query" in source
    assert "process_envelope" in bridge
    assert "from presence_core.engine import process_envelope" in bridge
    assert "serve_vesper_capital" not in source
    assert "serve_vesper_capital" not in bridge


def test_capital_query_response_contract_is_non_authoritative():
    from presence_core.capital_queries import answer_capital_query

    state = {
        "items": [
            {
                "rank": 1,
                "opportunity_id": "OPP-1",
                "opportunity_type": "INVESTOR",
                "organisation": "Example Ventures",
                "priority_score": 91,
                "rank_movement": 2,
                "rank_movement_reason": "Fresh published thesis signal.",
                "atlas_fit": {
                    "fit_score": 92,
                    "fit_reason": "Published AI thesis overlaps DIO governance and evidence capabilities.",
                    "primary_products": ["Evidex"],
                    "proof_bundle": ["proof/a.json"],
                },
                "action_recommendation": {
                    "recommendation": "APPROACH_NOW",
                    "reasoning": {
                        "route_state": "PUBLIC_ROUTE_VERIFIED",
                        "timing_score": 88,
                        "evidence_freshness": 90,
                    },
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
                "title": "Open education programme",
                "atlas_fit": {"fit_reason": "Education and OER fit."},
                "action_recommendation": {"recommendation": "RESEARCH_FIRST"},
            },
            {
                "rank": 3,
                "opportunity_id": "OPP-PAT",
                "opportunity_type": "PATRONAGE",
                "organisation": "Public Support",
                "atlas_fit": {"fit_reason": "Public build and open-resource fit."},
                "action_recommendation": {"recommendation": "TEST_PROPOSITION"},
            },
        ],
        "authority_created": False,
        "external_effects": False,
    }

    priority = answer_capital_query("capital_priority", "", state)
    assert priority["items"][0]["opportunity_id"] == "OPP-1"
    explain = answer_capital_query("capital_explain", "OPP-1", state)
    assert "Published AI thesis" in explain["text"]
    draft = answer_capital_query("capital_draft", "OPP-1", state)
    assert draft["draft"]["send_authority"] is False
    grants = answer_capital_query("capital_grants", "education OER", state)
    assert [x["opportunity_id"] for x in grants["items"]] == ["OPP-GRANT"]
    patronage = answer_capital_query("capital_patronage", "Patreon", state)
    assert [x["opportunity_id"] for x in patronage["items"]] == ["OPP-PAT"]
    for result in (priority, explain, draft, grants, patronage):
        assert result["authority_created"] is False
        assert result["external_effects"] is False
        assert result["send_authority"] is False
        assert result["submission_authority"] is False
        assert result["financial_commitment_authority"] is False
