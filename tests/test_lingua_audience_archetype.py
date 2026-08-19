from __future__ import annotations

from lingua.product_projection import audience_archetype


def test_declared_teacher_identity_outranks_learner_word_in_outcome() -> None:
    audience = {
        "id": "teachers_lecturers",
        "name": "Teachers and lecturers",
        "pain": "Marking and paper preparation consume evenings and weekends.",
        "outcome": "Structured drafts and learner feedback ready for educator review.",
    }
    assert audience_archetype(audience) == "education_practitioner"


def test_parent_and_learner_identity_remains_learner_support() -> None:
    audience = {
        "id": "parents_learners",
        "name": "Parents supporting school learners",
        "pain": "Generic online material often misses the classroom need.",
        "outcome": "A focused learning pack.",
    }
    assert audience_archetype(audience) == "learner_support"


def test_context_is_used_only_when_identity_is_uninformative() -> None:
    audience = {
        "id": "team_alpha",
        "name": "Operational team",
        "pain": "Audit evidence and compliance records are difficult to reconcile.",
        "outcome": "A reviewable assurance trail.",
    }
    assert audience_archetype(audience) == "assurance"


def test_short_tokens_are_word_matched_not_substring_matched() -> None:
    audience = {
        "id": "three_person_team",
        "name": "Three person team",
        "pain": "Routine workflow friction.",
        "outcome": "A cleaner handoff.",
    }
    assert audience_archetype(audience) == "general_professional"
