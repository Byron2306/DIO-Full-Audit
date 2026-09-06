import json
from presence_core.llm import resolve_conversation_with_ollama


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def args():
    return {
        "text": "I have 80 papers and need consistent marking",
        "state": {"candidate_products": [], "selected_product": None, "action_proposal": None},
        "recent_turns": [],
        "knowledge": {
            "products": [{
                "id": "homs_assess",
                "name": "HOMS Assess",
                "route_product": "homs",
                "source_maturity": "Internal proof",
                "route_auto_promotable": True,
            }]
        },
        "interaction": None,
        "persona_assignment": None,
        "allowed_products": ["homs"],
    }


def valid_payload():
    return {
        "reply": "That sounds like HOMS Assess territory. I can explain it or help you begin an intake.",
        "conversation_act": "handoff_offer",
        "interpreted_need": "consistent marking",
        "current_topic": "homs_assess",
        "candidate_products": ["homs"],
        "confidence": 0.91,
        "clarification_needed": False,
        "clarification_question": None,
        "action_intent": "none",
        "action_product": "homs",
        "source": "provider",
        "authority_created": False,
    }


def configure(monkeypatch, content):
    monkeypatch.setenv("DIO_PRESENCE_CONVERSATIONAL_GUIDE", "1")
    monkeypatch.setenv("OLLAMA_URL", "http://ollama.test")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen-test")
    fake = FakeResponse({"message": {"content": content}})
    monkeypatch.setattr("presence_core.llm.httpx.post", lambda *call_args, **call_kwargs: fake)


def test_valid_typed_result(monkeypatch):
    configure(monkeypatch, json.dumps(valid_payload()))
    result = resolve_conversation_with_ollama(**args())
    assert result["current_topic"] == "homs_assess"
    assert result["candidate_products"] == ["homs"]
    assert result["action_intent"] == "none"
    assert result["authority_created"] is False


def test_provider_payload_is_bounded_and_think_false(monkeypatch):
    calls = []
    monkeypatch.setenv("DIO_PRESENCE_CONVERSATIONAL_GUIDE", "1")
    monkeypatch.setenv("OLLAMA_URL", "http://ollama.test")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen-test")
    fake = FakeResponse({"message": {"content": json.dumps(valid_payload())}})
    monkeypatch.setattr("presence_core.llm.httpx.post", lambda *a, **kw: calls.append(kw) or fake)
    resolve_conversation_with_ollama(**args())
    payload = calls[0]["json"]
    assert payload["think"] is False
    assert payload["format"] == "json"
    assert payload["stream"] is False
    assert "80 papers" in payload["messages"][1]["content"]
    assert "send, spend" in payload["messages"][0]["content"].lower()


def test_malformed_json_returns_none(monkeypatch):
    configure(monkeypatch, "not-json")
    assert resolve_conversation_with_ollama(**args()) is None


def test_unknown_action_is_rejected(monkeypatch):
    payload = valid_payload()
    payload["action_intent"] = "send_mail"
    configure(monkeypatch, json.dumps(payload))
    assert resolve_conversation_with_ollama(**args()) is None
