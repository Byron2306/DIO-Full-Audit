from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any

from lingua import product_projection as legacy_projection


SEMANTIC_FOCUS_BY_ROLE: dict[str, str] = {
    "cold_open": "pain",
    "opening_problem": "pain",
    "recognition": "pain_context",
    "day_in_the_life": "pain_context",
    "transformation": "promise",
    "workflow_demo": "promise",
    "method": "promise",
    "deliverable": "outcome",
    "result": "outcome",
    "proof": "proof",
    "evidence": "proof",
    "human_gate": "authority",
    "educator_authority": "authority",
    "authority_boundary": "authority",
    "decision_boundary": "authority",
    "cta": "cta",
}


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean(value).casefold()).strip()


def _sentences(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", _clean(value)) if part.strip()]


def _strip_bounded_outcome_echo(narration: str, outcome: str) -> str:
    """Remove the legacy long-form invariant echo.

    Semantic invariants belong in the story contract. They do not need to be spoken
    after every scene. The bounded outcome may be realised by the scene whose focus
    is the outcome, but must not be mechanically appended to unrelated beats.
    """
    text = _clean(narration)
    bounded = _clean(outcome).rstrip(".")
    if not bounded:
        return text
    suffix = f"The bounded outcome is: {bounded}."
    if text.endswith(suffix):
        text = text[: -len(suffix)].rstrip()
        if text.endswith("."):
            return text
        return text.rstrip(". ") + "."
    # Defensive path for punctuation variants from older receipts.
    pattern = re.compile(r"\s*The bounded outcome is:\s*" + re.escape(bounded) + r"\.?\s*$", re.IGNORECASE)
    text = pattern.sub("", text).strip()
    return text if not text or text.endswith((".", "!", "?")) else text + "."


def validate_story_semantic_diversity(story: dict[str, Any], *, outcome: str = "") -> list[str]:
    errors: list[str] = []
    scenes = list(story.get("scenes") or [])
    narrations = [_clean(scene.get("narration")) for scene in scenes]

    if any("the bounded outcome is:" in narration.casefold() for narration in narrations):
        errors.append("bounded_outcome_invariant_leaked_into_narration")

    significant: list[str] = []
    for narration in narrations:
        for sentence in _sentences(narration):
            normalised = _normalise(sentence)
            # Ignore tiny connective phrases; repeated substantive sentences are the defect.
            if len(normalised.split()) >= 7:
                significant.append(normalised)
    duplicates = sorted(sentence for sentence, count in Counter(significant).items() if count > 1)
    if duplicates:
        errors.append("duplicate_substantive_narration:" + "|".join(duplicates[:4]))

    normalised_outcome = _normalise(outcome)
    if normalised_outcome:
        exact_outcome_uses = sum(normalised_outcome in _normalise(narration) for narration in narrations)
        if exact_outcome_uses > 1:
            errors.append(f"bounded_outcome_repeated:{exact_outcome_uses}")

    focuses = [str(scene.get("semantic_focus") or "") for scene in scenes]
    if story.get("surface") == "landscape_explainer":
        # Long-form should traverse meaning, not circle one semantic fact.
        if len(set(focus for focus in focuses if focus)) < min(5, len(scenes)):
            errors.append("insufficient_semantic_focus_diversity")

    return errors


def project_story(
    law: dict[str, Any],
    projection: dict[str, Any],
    product: dict[str, Any],
    audience: dict[str, Any],
    surface: str,
) -> dict[str, Any]:
    """Realise one LINGUA story while preventing semantic clone-loops.

    The legacy projection still chooses the lawful audience archetype, roles, voice,
    music, pacing and visual grammar. This layer owns semantic allocation across the
    selected beats and refuses repeated substantive narration.
    """
    story = legacy_projection.project_story(law, projection, product, audience, surface)
    outcome = _clean(audience.get("outcome"))

    scenes: list[dict[str, Any]] = []
    for scene in story.get("scenes") or []:
        row = dict(scene)
        if surface == "landscape_explainer":
            row["narration"] = _strip_bounded_outcome_echo(str(row.get("narration") or ""), outcome)
        role = str(row.get("role") or "")
        row["semantic_focus"] = SEMANTIC_FOCUS_BY_ROLE.get(role, role or "context")
        scenes.append(row)

    story["scenes"] = scenes
    story["storyline_strategy"] = {
        "schema": "dio.lingua.storyline_strategy.v1",
        "mode": "semantic_focus_allocation",
        "surface": surface,
        "semantic_invariants_are_contract_not_refrain": True,
        "anti_clone_gate": True,
        "focus_sequence": [scene["semantic_focus"] for scene in scenes],
        "concept_allocation": {
            "pain": "opening/context beats",
            "promise": "transformation/workflow beat",
            "outcome": "deliverable/result beat",
            "proof": "proof/evidence beat",
            "authority": "human decision beat",
            "cta": "final action beat",
        },
    }

    errors = validate_story_semantic_diversity(story, outcome=outcome)
    story["semantic_diversity"] = {"state": "PASS" if not errors else "REFUSE", "errors": errors}
    if errors:
        raise ValueError("LINGUA semantic anti-clone gate refused storyline: " + "; ".join(errors))

    core = {key: value for key, value in story.items() if key != "story_hash"}
    story["story_hash"] = _canonical_hash(core)
    return story
