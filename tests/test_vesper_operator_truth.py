from presence_core import engine, llm


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_operator_draft_instruction_is_owner_facing(monkeypatch):
    monkeypatch.setenv("DIO_PRESENCE_LLM_DRAFTS", "1")
    monkeypatch.setenv("OLLAMA_URL", "http://ollama.test")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen-test")
    captured = {}

    def fake_post(url, json, timeout):
        captured["payload"] = json
        return _Response({"message": {"content": "DIO is your governed operating system."}})

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    result = llm.draft_with_ollama(
        {"intent": "general_info", "product": None, "confidence": 0.99},
        "role=operator; authority=bounded_presence",
        "DIO is available.",
        governed_context={"role": "operator", "audience": "operator"},
    )
    assert result == "DIO is your governed operating system."
    combined = "\n".join(message["content"] for message in captured["payload"]["messages"])
    assert "operator-facing" in combined.lower()
    assert "owner" in combined.lower() or "operator" in combined.lower()
    assert "customer-facing reply" not in combined.lower()
    assert "how can i assist you today" not in combined.lower()


def test_action_state_guard_rejects_processing_claim_without_processing_fact():
    assert llm.draft_claims_authorized(
        "I have received your file and will now process it through the Research Integrity workflow.",
        "attachment=ATT-1; state=quarantined; attachment_processed=false",
    ) is False


def test_action_state_guard_allows_processing_claim_when_facts_prove_processing():
    assert llm.draft_claims_authorized(
        "I am processing the file now.",
        "job_id=JOB-1; processing_state=processing; attachment_processed=true",
    ) is True


def test_operator_general_info_fallback_is_not_public_sales_copy():
    reply, facts = engine._reply({"intent": "general_info", "product": None, "confidence": 0.99}, "operator")
    assert "operator" in reply.lower()
    assert "capture a request" not in reply.lower()
    assert "customer" not in facts.lower()


def test_operator_product_info_does_not_pitch_for_intake():
    reply, facts = engine._reply({"intent": "product_info", "product": "sophia", "confidence": 0.99}, "operator")
    assert "sophia" in reply.lower()
    assert "operator" in reply.lower()
    assert "would you like" not in reply.lower()
    assert facts == "product=sophia"
