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


def _lower_first(value: str) -> str:
    clean = _clean(value)
    return clean[:1].lower() + clean[1:] if clean else clean


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
    pattern = re.compile(r"\s*The bounded outcome is:\s*" + re.escape(bounded) + r"\.?\s*$", re.IGNORECASE)
    text = pattern.sub("", text).strip()
    return text if not text or text.endswith((".", "!", "?")) else text + "."


def _education_landscape_realisation(
    row: dict[str, Any],
    *,
    product: dict[str, Any],
    audience: dict[str, Any],
) -> dict[str, Any]:
    """Give the education explainer its own documentary semantics.

    The old landscape role names were aliases back to the vertical short-form copy.
    This realiser stays source-bound but makes the explainer develop the argument
    instead of replaying the ad with two extra scenes.
    """
    role = str(row.get("role") or "")
    name = _clean(product.get("short_name") or product.get("name") or "DIO")
    promise = _clean(product.get("promise"))
    proof = _clean(product.get("proof"))
    cta = _clean(product.get("cta"))
    audience_name = _clean(audience.get("name") or "the audience")
    pain = _clean(audience.get("pain"))
    outcome = _clean(audience.get("outcome"))

    realised: dict[str, tuple[str, str, str]] = {
        "opening_problem": (
            "Start with the real workload",
            f"For {audience_name}, the recurring burden is straightforward: {_lower_first(pain).rstrip('.')}.",
            "Open inside the real work environment and let the burden emerge from observable tasks rather than an abstract claim.",
        ),
        "day_in_the_life": (
            "The repetition compounds",
            "The cost is repetition: professional attention keeps getting pulled back into preparation work that still needs careful review.",
            "Follow the work across a realistic sequence of preparation moments so the friction accumulates visually.",
        ),
        "workflow_demo": (
            "What the governed assist actually does",
            f"{name} has one bounded job here: {_lower_first(promise).rstrip('.')}.",
            "Show the governed preparation path as work moving toward a reviewable handoff, not as a product architecture diagram.",
        ),
        "deliverable": (
            "The handoff is a draft, not a verdict",
            f"The reviewable result is {_lower_first(outcome).rstrip('.')}.",
            "Make the prepared artifact tangible and visibly unfinished enough that professional refinement remains legible.",
        ),
        "proof": (
            "What you can actually inspect",
            f"The evidence boundary is explicit: {_lower_first(proof).rstrip('.')}.",
            "Put the real proof object or bounded product surface in front of the viewer and make inspection the visual action.",
        ),
        "educator_authority": (
            "The final judgement stays human",
            "Preparation can be delegated; consequential judgement cannot. The educator remains the reviewer and final decision-maker.",
            "End the workflow on a human review moment where authority is visibly exercised rather than described in a disclaimer.",
        ),
        "cta": (
            "One bounded next step",
            f"The next step stays deliberately small: {_lower_first(cta).rstrip('.')}.",
            "Close on one concrete action with no extra promise, urgency fiction or publication implication.",
        ),
    }
    if role not in realised:
        return row
    screen, narration, visual = realised[role]
    updated = dict(row)
    updated["screen_text"] = screen
    updated["narration"] = narration
    updated["visual"] = visual
    updated["realisation_mode"] = "education_landscape_documentary_v1"
    return updated


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
            if len(normalised.split()) >= 7:
                significant.append(normalised)
    duplicates = sorted(sentence for sentence, count in Counter(significant).items() if count > 1)
    if duplicates:
        errors.append("duplicate_substantive_narration:" + "|".join(duplicates[:4]))

    normalised_outcome = _normalise(outcome)
    if normalised_outcome:
        exact_outcome_uses = sum(normalised_outcome in _normalise(narration) for narration in narrations)
        if story.get("surface") == "landscape_explainer" and exact_outcome_uses == 0:
            errors.append("bounded_outcome_missing")
        elif exact_outcome_uses > 1:
            errors.append(f"bounded_outcome_repeated:{exact_outcome_uses}")

    focuses = [str(scene.get("semantic_focus") or "") for scene in scenes]
    if story.get("surface") == "landscape_explainer":
        if len(set(focus for focus in focuses if focus)) < min(5, len(scenes)):
            errors.append("insufficient_semantic_focus_diversity")

    return errors


def validate_cross_surface_semantic_distance(short_story: dict[str, Any], long_story: dict[str, Any]) -> list[str]:
    """Refuse fake diversity where role names differ but realised copy is the same."""
    errors: list[str] = []
    short_screens = {_normalise(scene.get("screen_text", "")) for scene in short_story.get("scenes") or []}
    long_screens = {_normalise(scene.get("screen_text", "")) for scene in long_story.get("scenes") or []}
    short_screens.discard("")
    long_screens.discard("")
    overlap = short_screens & long_screens
    denominator = max(1, min(len(short_screens), len(long_screens)))
    overlap_ratio = len(overlap) / denominator
    if overlap_ratio > 0.34:
        errors.append(f"cross_surface_screen_clone_ratio:{overlap_ratio:.3f}")

    short_sentences = {
        _normalise(sentence)
        for scene in short_story.get("scenes") or []
        for sentence in _sentences(str(scene.get("narration") or ""))
        if len(_normalise(sentence).split()) >= 7
    }
    long_sentences = {
        _normalise(sentence)
        for scene in long_story.get("scenes") or []
        for sentence in _sentences(str(scene.get("narration") or ""))
        if len(_normalise(sentence).split()) >= 7
    }
    duplicate_sentences = sorted(short_sentences & long_sentences)
    if duplicate_sentences:
        errors.append("cross_surface_duplicate_narration:" + "|".join(duplicate_sentences[:4]))
    return errors


def _realise_story(
    law: dict[str, Any],
    projection: dict[str, Any],
    product: dict[str, Any],
    audience: dict[str, Any],
    surface: str,
) -> dict[str, Any]:
    story = legacy_projection.project_story(law, projection, product, audience, surface)
    outcome = _clean(audience.get("outcome"))
    archetype = str(projection.get("audience_archetype") or "general_professional")

    scenes: list[dict[str, Any]] = []
    for scene in story.get("scenes") or []:
        row = dict(scene)
        if surface == "landscape_explainer":
            row["narration"] = _strip_bounded_outcome_echo(str(row.get("narration") or ""), outcome)
            if archetype == "education_practitioner":
                row = _education_landscape_realisation(row, product=product, audience=audience)
        role = str(row.get("role") or "")
        row["semantic_focus"] = SEMANTIC_FOCUS_BY_ROLE.get(role, role or "context")
        scenes.append(row)

    story["scenes"] = scenes
    story["storyline_strategy"] = {
        "schema": "dio.lingua.storyline_strategy.v1",
        "mode": "semantic_focus_allocation",
        "surface": surface,
        "semantic_invariants_are_contract_not_refrain": True,
        "surface_specific_realisation": True,
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
    return story


def project_story(
    law: dict[str, Any],
    projection: dict[str, Any],
    product: dict[str, Any],
    audience: dict[str, Any],
    surface: str,
) -> dict[str, Any]:
    """Realise one LINGUA story while preventing semantic clone-loops."""
    story = _realise_story(law, projection, product, audience, surface)
    outcome = _clean(audience.get("outcome"))

    errors = validate_story_semantic_diversity(story, outcome=outcome)
    if surface == "landscape_explainer":
        short_story = _realise_story(law, projection, product, audience, "vertical_short")
        errors.extend(validate_cross_surface_semantic_distance(short_story, story))
    errors = sorted(set(errors))

    story["semantic_diversity"] = {"state": "PASS" if not errors else "REFUSE", "errors": errors}
    if errors:
        raise ValueError("LINGUA semantic anti-clone gate refused storyline: " + "; ".join(errors))

    core = {key: value for key, value in story.items() if key != "story_hash"}
    story["story_hash"] = _canonical_hash(core)
    return story
