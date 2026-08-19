from __future__ import annotations

from pathlib import Path

from lingua.product_projection import build_projection_plan
from lingua.semantic_law import build_semantic_law
from lingua.storyline_planner import (
    project_story,
    validate_cross_surface_semantic_distance,
    validate_story_semantic_diversity,
)

ROOT = Path(__file__).resolve().parents[1]


def _product() -> dict[str, str]:
    return {
        "id": "HOMS_ASSESS--HOMS Assess",
        "name": "HOMS Assess",
        "short_name": "HOMS Assess",
        "offer": "assessment_desk",
        "promise": "Prepare marking, feedback and CAPS-aware assessment material for educator review.",
        "proof": "The assessment route produces reviewable marking and term-aware papers while the educator remains final authority.",
        "cta": "Send one controlled assessment batch",
    }


def _audience() -> dict[str, str]:
    return {
        "id": "tutors_publishers",
        "name": "Tutors and education publishers",
        "pain": "Creating credible activities, memos and feedback repeatedly is slow.",
        "outcome": "Curriculum-aware assessment drafts that can be professionally refined.",
    }


def _projection():
    product = _product()
    audience = _audience()
    law = build_semantic_law(product, audience)
    projection = build_projection_plan(law, product, audience, {})
    return product, audience, law, projection


def test_landscape_does_not_repeat_bounded_outcome_after_every_scene() -> None:
    product, audience, law, projection = _projection()
    story = project_story(law, projection, product, audience, "landscape_explainer")
    narration = "\n".join(str(scene["narration"]) for scene in story["scenes"])
    assert "The bounded outcome is:" not in narration
    assert narration.count(audience["outcome"].rstrip(".")) == 1
    assert story["semantic_diversity"] == {"state": "PASS", "errors": []}
    assert story["storyline_strategy"]["semantic_invariants_are_contract_not_refrain"] is True
    assert story["storyline_strategy"]["surface_specific_realisation"] is True
    assert len(set(story["storyline_strategy"]["focus_sequence"])) >= 5


def test_vertical_story_remains_semantically_distinct_and_governed() -> None:
    product, audience, law, projection = _projection()
    story = project_story(law, projection, product, audience, "vertical_short")
    assert story["semantic_diversity"]["state"] == "PASS"
    assert [scene["role"] for scene in story["scenes"]] == [
        "cold_open", "recognition", "transformation", "proof", "human_gate", "cta"
    ]
    assert [scene["semantic_focus"] for scene in story["scenes"]] == [
        "pain", "pain_context", "promise", "proof", "authority", "cta"
    ]
    assert story["governance"]["publication"] == "held"
    assert story["governance"]["spend"] == "disabled"
    assert story["governance"]["authority_created"] is False


def test_education_short_and_explainer_do_not_collapse_to_same_realised_story() -> None:
    product, audience, law, projection = _projection()
    short_story = project_story(law, projection, product, audience, "vertical_short")
    long_story = project_story(law, projection, product, audience, "landscape_explainer")
    assert validate_cross_surface_semantic_distance(short_story, long_story) == []
    short_screens = {scene["screen_text"] for scene in short_story["scenes"]}
    long_screens = {scene["screen_text"] for scene in long_story["scenes"]}
    assert len(short_screens & long_screens) <= 2
    assert long_story["scenes"][0]["screen_text"] == "Start with the real workload"
    assert long_story["scenes"][-2]["screen_text"] == "The final judgement stays human"


def test_semantic_diversity_gate_refuses_duplicate_substantive_sentences() -> None:
    story = {
        "surface": "landscape_explainer",
        "scenes": [
            {"semantic_focus": "pain", "narration": "This exact substantive sentence repeats across two different story beats for no reason."},
            {"semantic_focus": "promise", "narration": "This exact substantive sentence repeats across two different story beats for no reason."},
            {"semantic_focus": "outcome", "narration": "A bounded result belongs here."},
            {"semantic_focus": "proof", "narration": "Proof belongs here."},
            {"semantic_focus": "authority", "narration": "Human judgement belongs here."},
        ],
    }
    errors = validate_story_semantic_diversity(story)
    assert any(error.startswith("duplicate_substantive_narration:") for error in errors)


def test_active_factory_wires_semantic_anti_clone_planner() -> None:
    active = (ROOT / "scripts" / "build_multichannel_campaign_factory.py").read_text(encoding="utf-8")
    assert "from lingua.storyline_planner import project_story as project_story_semantic_anti_clone" in active
    assert "_v3.project_story = project_story_semantic_anti_clone" in active
