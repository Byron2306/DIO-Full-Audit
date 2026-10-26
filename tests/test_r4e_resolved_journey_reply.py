"""Captured live advisory must not contradict the canonical Journey response."""
from pathlib import Path

import pytest

from presence_core import router
from presence_core.config import load_config
from presence_core.engine import process_envelope


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("DIO_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("DIO_EVENT_LOG", str(tmp_path / "events.jsonl"))
    monkeypatch.setenv("DIO_PRESENCE_LLM_DRAFTS", "0")
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    # Only the provider boundary is supplied, using the exact live receipt.
    monkeypatch.setattr(router, "classify_with_ollama", lambda *args, **kwargs: {
        "confidence": 0.9, "intent": "intake_request", "product": None,
    })
    return load_config()


def turn(runtime, text):
    return process_envelope({"channel": "webchat", "external_user_id": "R4E-CUSTOMER",
                             "text": text, "message_type": "text", "metadata": {}},
                            ROOT, runtime)


def test_captured_null_product_intake_advisory_answers_from_resolved_case(runtime):
    result = turn(runtime, "What do you need from me for ContractProof?")
    assert result["decision"]["intent"] == "intake_request"
    assert result["decision"]["product"] is None
    assert result["commercial"]["product"]["name"] == "ContractProof"
    reply = result["reply"]["text"]
    assert "ContractProof" in reply
    assert "clause" in reply.lower()
    assert "outcome" in reply.lower() or "result" in reply.lower()
    assert "not confident enough" not in reply
    assert result["intake"] is None
    assert result["authority"]["executed_external_action"] is False
    assert result["customer_case"]["stage"] == "NEW_LEAD"


@pytest.mark.parametrize('followup_intent', ['intake_request','general_info','product_info','unknown','pricing_info'])
@pytest.mark.parametrize('followup_product', [None, 'HOMS'])
def test_customer_correction_keeps_product_without_creating_verified_buyer_scope(runtime, monkeypatch, followup_intent, followup_product):
    first = turn(runtime, "What do you need from me for ContractProof?")
    monkeypatch.setattr(router, 'classify_with_ollama', lambda *args, **kwargs: {
        'confidence': .9, 'intent': followup_intent, 'product': followup_product,
    })
    second = turn(runtime, "Actually, this is for a nonprofit. Does that change what you need?")
    assert second["customer_case"]["case_id"] == first["customer_case"]["case_id"]
    assert second["commercial"]["product"]["name"] == "ContractProof"
    assert "ContractProof" in second["reply"]["text"]
    assert "not confident enough" not in second["reply"]["text"]
    assert "clarifies who the work is for" in second["reply"]["text"]
    assert second["intake"] is None
    assert second["authority"]["financial_commitment_authorized"] is False


def test_unresolved_intake_advisory_does_not_invent_a_canonical_product(runtime):
    result = turn(runtime, "What do you need from me?")
    assert result["commercial"]["state"] != "RESOLVED"
    assert result["intake"] is None
    assert "ContractProof" not in result["reply"]["text"]


def test_buyer_context_does_not_override_an_explicit_product_ambiguity(runtime, monkeypatch):
    turn(runtime, 'What do you need from me for ContractProof?')
    monkeypatch.setattr(router, 'classify_with_ollama', lambda *a, **k: {
        'intent': 'general_info', 'product': None, 'confidence': .9,
    })
    result = turn(runtime, 'Actually this is for a nonprofit: ContractProof or GrantProof?')
    assert result['commercial']['state'] == 'NEEDS_CLARIFICATION'
    assert result['intake'] is None
    assert 'clarifies who the work is for' not in result['reply']['text']
    assert result['authority']['executed_external_action'] is False


@pytest.mark.parametrize('intent', ['pricing_info', 'general_info', 'intake_request'])
def test_buyer_scope_price_question_keeps_governed_reference_price_reply(runtime, monkeypatch, intent):
    first = turn(runtime, 'What do you need from me for ContractProof?')
    monkeypatch.setattr(router, 'classify_with_ollama', lambda *a, **k: {
        'intent': intent, 'product': None, 'confidence': .9,
    })
    result = turn(runtime, 'Actually, this is for a nonprofit. What is the price for ContractProof?')
    assert result['customer_case']['case_id'] == first['customer_case']['case_id']
    assert 'R750' in result['reply']['text'] and 'R3,500' in result['reply']['text']
    assert 'roughly how many' not in result['reply']['text']
    assert result['intake'] is None
    assert result['authority']['financial_commitment_authorized'] is False


def test_existing_expression_guard_rejects_intake_acceptance_without_a_real_record():
    from presence_core.llm import draft_claims_authorized
    assert not draft_claims_authorized("I've captured your intake for ContractProof.", "intake_created=false")
    assert draft_claims_authorized("I've captured your intake for human review.", "intake_created=true")
    assert not draft_claims_authorized("I have opened your intake.", "journey_intake_open=false")
    assert draft_claims_authorized("I have opened your intake.", "journey_intake_open=true")
    assert not draft_claims_authorized("I have opened your uploaded contract.", "journey_intake_open=true")
    for text in ("Your intake has been captured.", "I have created your intake.",
                 "I have received your intake.", "Intake received."):
        assert not draft_claims_authorized(text, "intake_created=false\njourney_intake_open=false")
    assert not draft_claims_authorized("I have opened your intake form.", "journey_intake_open=true\nattachment_processed=false")
