from pathlib import Path

from adapters.lingua.conversation import resolve_conversation
from adapters.lingua.conversation_knowledge import load_public_product_knowledge

ROOT = Path(__file__).resolve().parents[1]


def state(**kw):
    base = {
        "candidate_products": [],
        "selected_product": None,
        "action_proposal": None,
        "current_topic": None,
    }
    base.update(kw)
    return base


def test_resolver_uses_primitive_before_provider():
    calls = []
    result = resolve_conversation(
        root=ROOT, text="Hi", state=state(), recent_turns=[],
        knowledge=load_public_product_knowledge(ROOT),
        interaction=None, persona=None,
        provider_resolver=lambda **kwargs: calls.append(kwargs),
    )
    assert result["conversation_act"] == "greeting"
    assert result["source"] == "primitive"
    assert calls == []


def test_problem_guidance_uses_route_semantics_without_provider():
    calls = []
    result = resolve_conversation(
        root=ROOT, text="I have 80 student papers and need consistent marking.",
        state=state(), recent_turns=[],
        knowledge=load_public_product_knowledge(ROOT),
        interaction=None, persona=None,
        provider_resolver=lambda **kwargs: calls.append(kwargs),
    )
    assert result["conversation_act"] == "handoff_offer"
    assert result["candidate_products"] == ["homs"]
    assert result["action_product"] == "homs"
    assert result["route_auto_promotable"] is True
    assert calls == []


def test_two_product_comparison_keeps_both_candidates():
    result = resolve_conversation(
        root=ROOT, text="HOMS or Evidex?", state=state(), recent_turns=[],
        knowledge=load_public_product_knowledge(ROOT),
        interaction=None, persona=None,
        provider_resolver=lambda **kwargs: None,
    )
    assert result["conversation_act"] == "compare"
    assert set(result["candidate_products"]) == {"homs", "evidex"}
    assert result["action_intent"] == "none"


def test_other_one_correction_uses_exactly_two_candidates():
    result = resolve_conversation(
        root=ROOT, text="No, I meant the other one.",
        state=state(candidate_products=["homs", "evidex"], selected_product="homs"),
        recent_turns=[], knowledge=load_public_product_knowledge(ROOT),
        interaction=None, persona=None,
        provider_resolver=lambda **kwargs: None,
    )
    assert result["conversation_act"] == "correct"
    assert result["candidate_products"] == ["evidex"]
    assert result["action_intent"] == "none"


def test_other_one_with_three_candidates_clarifies_instead_of_guessing():
    result = resolve_conversation(
        root=ROOT, text="No, I meant the other one.",
        state=state(candidate_products=["homs", "evidex", "sophia"], selected_product="homs"),
        recent_turns=[], knowledge=load_public_product_knowledge(ROOT),
        interaction=None, persona=None,
        provider_resolver=lambda **kwargs: None,
    )
    assert result["conversation_act"] == "clarify"
    assert result["clarification_needed"] is True
    assert result["action_intent"] == "none"


def test_provider_is_only_used_after_local_layers_miss():
    calls = []
    def provider(**kwargs):
        calls.append(kwargs)
        return {
            "reply": "I can help narrow that down.",
            "conversation_act": "clarify",
            "interpreted_need": "novel DIO need",
            "current_topic": None,
            "candidate_products": [],
            "confidence": 0.7,
            "clarification_needed": True,
            "clarification_question": "What outcome matters most?",
            "action_intent": "none",
            "action_product": None,
            "source": "provider",
            "authority_created": False,
        }
    result = resolve_conversation(
        root=ROOT, text="I have a strange cross-system DIO problem.",
        state=state(), recent_turns=[], knowledge=load_public_product_knowledge(ROOT),
        interaction=None, persona=None, provider_resolver=provider,
    )
    assert result["source"] == "provider"
    assert len(calls) == 1


def test_provider_failure_degrades_to_safe_fallback():
    result = resolve_conversation(
        root=ROOT, text="I have a strange cross-system DIO problem.",
        state=state(), recent_turns=[], knowledge=load_public_product_knowledge(ROOT),
        interaction=None, persona=None, provider_resolver=lambda **kwargs: None,
    )
    assert result["source"] == "fallback"
    assert result["action_intent"] == "none"
    assert result["authority_created"] is False
