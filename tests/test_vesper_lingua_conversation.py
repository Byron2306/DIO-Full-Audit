import pytest
from adapters.lingua.conversation import (
    apply_resolution_to_state,
    resolve_primitive,
    validate_conversation_resolution,
)
from presence_core import llm


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


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


def test_ollama_draft_receives_bounded_conversation_context(monkeypatch):
    monkeypatch.setenv("DIO_PRESENCE_LLM_DRAFTS", "1")
    monkeypatch.setenv("OLLAMA_URL", "http://ollama.test")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3.5:4b")
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["payload"] = json
        return _Response({"message": {"content": "That sounds like a marking-workflow problem. HOMS is the likely fit."}})

    monkeypatch.setattr(llm.httpx, "post", fake_post)

    result = llm.draft_with_ollama(
        {"intent": "product_info", "product": "homs", "confidence": 0.92},
        "product=homs; educator_review_required=true",
        "HOMS can help with governed assessment work.",
        interaction=None,
        persona_assignment=None,
        conversation_state={
            "current_need": "mark 80 student papers consistently",
            "selected_product": "homs",
            "action_proposal": None,
        },
        recent_turns=[
            {"role": "user", "text": "I have 80 student papers to mark."},
            {"role": "vesper", "text": "We can narrow down the right assessment workflow."},
            {"role": "user", "text": "I need consistency if marks are challenged."},
        ],
    )

    assert result.startswith("That sounds like")
    prompt = captured["payload"]["messages"][1]["content"]
    assert "I have 80 student papers to mark." in prompt
    assert "I need consistency if marks are challenged." in prompt
    assert "mark 80 student papers consistently" in prompt
    assert "qwen3.5:4b" not in prompt
