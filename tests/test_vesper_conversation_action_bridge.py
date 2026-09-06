from pathlib import Path
from presence_core.router import decision_from_conversation_action

REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTES = REPO_ROOT / "config" / "routes.json"


def test_none_never_creates_decision():
    result = decision_from_conversation_action(
        resolution={"action_intent": "none", "action_product": None},
        state={"selected_product": "homs", "action_proposal": None},
        text="tell me more",
        role="public",
        routes_path=ROUTES,
    )
    assert result is None


def test_intake_requires_matching_pending_proposal_and_explicit_confirmation():
    resolution = {"action_intent": "begin_intake", "action_product": "homs", "confidence": 0.95}
    state = {"selected_product": "homs", "action_proposal": {"intent": "begin_intake", "product": "homs"}}
    refused = decision_from_conversation_action(
        resolution=resolution, state=state, text="tell me more", role="public", routes_path=ROUTES,
    )
    assert refused is None
    accepted = decision_from_conversation_action(
        resolution=resolution, state=state, text="yes, start that for me", role="public", routes_path=ROUTES,
    )
    assert accepted.intent == "intake_request"
    assert accepted.product == "homs"
    assert accepted.source == "conversation_bridge"


def test_mismatched_product_proposal_is_refused():
    resolution = {"action_intent": "begin_intake", "action_product": "evidex", "confidence": 0.95}
    state = {"selected_product": "homs", "action_proposal": {"intent": "begin_intake", "product": "homs"}}
    assert decision_from_conversation_action(
        resolution=resolution, state=state, text="yes, start that for me", role="public", routes_path=ROUTES,
    ) is None


def test_public_operator_summary_proposal_is_refused():
    result = decision_from_conversation_action(
        resolution={"action_intent": "operator_summary", "action_product": None, "confidence": 1.0},
        state={}, text="show me the internal summary", role="public", routes_path=ROUTES,
    )
    assert result is None
