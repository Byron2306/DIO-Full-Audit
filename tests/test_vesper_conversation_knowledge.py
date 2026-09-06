from pathlib import Path

from adapters.lingua.conversation_knowledge import (
    answer_from_governed_knowledge,
    load_public_product_knowledge,
)


def test_atlas_builds_homs_family_from_canonical_incarnations():
    project_root = Path(__file__).parents[1]
    knowledge = load_public_product_knowledge(project_root)
    assert "homs" in knowledge
    homs = knowledge["homs"]
    assert homs["label"] == "HOMS"
    assert "HOMS Assess" in homs["incarnations"]
    assert "HOMS Exam" in homs["incarnations"]
    assert homs["suite"] == "Education & Research"
    assert "Internal proof" in homs["maturity_states"]
    assert homs["authority_created"] is False


def test_evidex_knowledge_uses_atlas_maturity_not_model_memory():
    project_root = Path(__file__).parents[1]
    knowledge = load_public_product_knowledge(project_root)
    evidex = knowledge["evidex"]
    assert evidex["label"] == "Evidex"
    assert evidex["incarnations"] == ["Evidex EvidenceOps"]
    assert evidex["maturity_states"] == ["Controlled transaction proof"]
    assert "Evidence" in evidex["work_patterns"]


def test_direct_homs_question_is_answered_without_provider():
    project_root = Path(__file__).parents[1]
    knowledge = load_public_product_knowledge(project_root)
    calls = []
    result = answer_from_governed_knowledge(
        "What is HOMS?",
        knowledge,
        provider=lambda *_args, **_kwargs: calls.append(True),
    )
    assert result is not None
    assert result["source"] == "knowledge"
    assert result["action_intent"] == "none"
    assert result["authority_created"] is False
    assert "HOMS Assess" in result["reply"]
    assert "Education & Research" in result["reply"]
    assert calls == []


def test_unknown_question_returns_none_for_next_resolution_layer():
    project_root = Path(__file__).parents[1]
    knowledge = load_public_product_knowledge(project_root)
    assert answer_from_governed_knowledge("Can you explain quantum chromodynamics?", knowledge) is None
