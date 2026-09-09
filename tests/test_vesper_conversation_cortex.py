from presence_core import llm


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


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
