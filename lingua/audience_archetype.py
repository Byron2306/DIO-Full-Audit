from __future__ import annotations

import re
from typing import Any

# Classification is identity-first. An audience's declared id/name is stronger
# semantic evidence than incidental nouns appearing in its pain or outcome.
ARCHETYPE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("learner_support", ("parent", "learner", "school learner")),
    ("education_practitioner", ("teacher", "lecturer", "tutor", "education publisher", "school", "assessment coordinator")),
    ("academic_research", ("postgraduate", "research supervisor", "research office", "research group", "writing centre", "academic library")),
    ("assurance", ("audit", "compliance", "monitoring", "evaluation", "grant manager", "evidence", "assurance")),
    ("executive_operations", ("hr", "performance administrator", "line manager", "hod", "institution leader", "organisation leader")),
    ("public_programme", ("ngo", "npo", "public programme", "government", "public facing", "donor")),
    ("professional_services", ("consultant", "professional firm", "sme", "independent reporting")),
]


def _normalise(value: Any) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).split())


def _word_matches(actual: str, expected: str) -> bool:
    if actual == expected:
        return True
    # Very short role tokens such as HR must remain exact. Otherwise words
    # such as "three" can accidentally become HR evidence.
    if len(expected) <= 2:
        return False
    inflections = {expected + "s", expected + "es"}
    if expected.endswith("y") and len(expected) > 2:
        inflections.add(expected[:-1] + "ies")
    return actual in inflections


def _matches(text: str, needle: str) -> bool:
    candidate = _normalise(needle)
    if not candidate:
        return False
    actual_words = text.split()
    expected_words = candidate.split()
    if len(expected_words) == 1:
        return any(_word_matches(actual, expected_words[0]) for actual in actual_words)
    width = len(expected_words)
    return any(
        all(_word_matches(actual, expected) for actual, expected in zip(actual_words[index : index + width], expected_words, strict=True))
        for index in range(0, len(actual_words) - width + 1)
    )


def _classify(text: str) -> str | None:
    for archetype, needles in ARCHETYPE_RULES:
        if any(_matches(text, needle) for needle in needles):
            return archetype
    return None


def classify_audience_archetype(audience: dict[str, Any]) -> str:
    """Resolve the audience's creative archetype with semantic precedence.

    Declared identity (id + name) is primary. Pain/outcome text is only a
    fallback when the audience identity itself is semantically uninformative.
    This prevents phrases such as "learner feedback" in a teacher outcome from
    recasting teachers as learners.
    """
    identity = _normalise(f"{audience.get('id') or ''} {audience.get('name') or ''}")
    primary = _classify(identity)
    if primary:
        return primary

    context = _normalise(f"{audience.get('pain') or ''} {audience.get('outcome') or ''}")
    secondary = _classify(context)
    return secondary or "general_professional"
