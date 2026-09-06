import pytest
from adapters.lingua.conversation import (
    apply_resolution_to_state,
    resolve_primitive,
    validate_conversation_resolution,
)


def test_plain_hi_is_a_greeting_not_unknown():
    result = resolve_primitive("Hi", {"selected_product": None, "candidate_products": [], "action_proposal": None})
    assert result["conversation_act"] == "greeting"
    assert result["action_intent"] == "none"
    assert result["authority_created"] is False
    assert "what are you trying" in result["reply"].lower()


def test_plain_yes_without_open_action_does_not_create_action():
    result = resolve_primitive("yes", {"action_proposal": None, "selected_product": "homs"})
    assert result["conversation_act"] == "acknowledge"
    assert result["action_intent"] == "none"


def test_explicit_confirmation_uses_existing_pending_proposal_only():
    result = resolve_primitive("yes, start that for me", {
        "action_proposal": {"intent": "begin_intake", "product": "homs"},
        "selected_product": "homs",
    })
    assert result["action_intent"] == "begin_intake"
    assert result["action_product"] == "homs"
    assert result["authority_created"] is False


def test_provider_resolution_with_authority_is_rejected():
    with pytest.raises(ValueError, match="authority"):
        validate_conversation_resolution({
            "reply": "Done",
            "conversation_act": "answer",
            "interpreted_need": None,
            "candidate_products": [],
            "confidence": 0.9,
            "clarification_needed": False,
            "clarification_question": None,
            "action_intent": "none",
            "action_product": None,
            "source": "provider",
            "authority_created": True,
        }, {"homs"})


def test_handoff_offer_creates_pending_proposal_not_action():
    state = {
        "schema": "dio.vesper.conversation_state.v1",
        "conversation_id": "CONV-1",
        "turn_count": 1,
        "candidate_products": [],
        "selected_product": None,
        "action_proposal": None,
    }
    updated = apply_resolution_to_state(state, {
        "reply": "HOMS Assess looks like a fit. I can help you begin an intake.",
        "conversation_act": "handoff_offer",
        "interpreted_need": "consistent marking",
        "candidate_products": ["homs"],
        "confidence": 0.91,
        "clarification_needed": False,
        "clarification_question": None,
        "action_intent": "none",
        "action_product": "homs",
        "source": "provider",
        "authority_created": False,
    })
    assert updated["action_proposal"] == {"intent": "begin_intake", "product": "homs"}
    assert updated["selected_product"] == "homs"
