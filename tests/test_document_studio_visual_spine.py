from __future__ import annotations

import json
from pathlib import Path

from adapters.document_studio.art_direction import build_art_direction
from scripts.nichefoundry_visual_spine import build_art_directed_gamma_request

ROOT = Path(__file__).resolve().parents[1]


def _story(archetype: str = "education_practitioner") -> dict:
    roles = [
        "opening_problem",
        "day_in_the_life",
        "workflow_demo",
        "deliverable",
        "proof",
        "educator_authority",
        "cta",
    ]
    scenes = []
    for index, role in enumerate(roles, 1):
        scenes.append({
            "scene_id": f"landscape_{index:02d}_{role}",
            "role": role,
            "screen_text": [
                "Still doing this by hand?",
                "That friction is the job",
                "Trace it, then judge it",
                "What you get",
                "Show the proof",
                "You still decide",
                "Send one controlled assessment batch",
            ][index - 1],
            "narration": f"SECRET NARRATION PARAGRAPH {index}: this belongs in Leah audio and must never become visible visual body copy.",
            "visual": f"Scene {index} should show tactile human evidence rather than a corporate card grid.",
        })
    return {
        "schema": "dio.marketing.campaign_story.v2",
        "family_id": "HOMS_ASSESS--teachers_lecturers",
        "surface": "landscape_explainer",
        "title": "HOMS for Teachers and lecturers · landscape explainer",
        "story_hash": "sha256:story",
        "semantic_law_hash": "sha256:law",
        "projection_hash": "sha256:projection",
        "scenes": scenes,
        "creative_direction": {
            "audience_archetype": archetype,
            "tone": ["warm", "quick", "respectful"],
            "pacing": "steady",
            "visual_grammar": "energetic_education_editorial" if archetype == "education_practitioner" else "assurance_signal_noir",
            "motion_grammar": "documentary_pushes_diagrams_and_evidence_closeups",
        },
        "semantic_guardrails": {"must_preserve": ["human_authority"], "do_not_invent": ["invented_customer_result"]},
    }


def test_document_studio_art_direction_is_richer_than_formatting_profile() -> None:
    art = build_art_direction(_story())
    assert art["schema"] == "dio.document_studio.art_direction.v1"
    assert art["audience_archetype"] == "education_practitioner"
    assert art["format_core_profile"] == "caps_educator"
    assert "tactile educator reality" in art["art_language"]["aesthetic"]
    assert "four_quadrant_saas_card_grid" in art["anti_patterns"]
    assert "static_slide_deck_as_video" in art["anti_patterns"]
    layouts = [row["layout_family"] for row in art["scenes"]]
    assert len(set(layouts)) >= 6
    assert all(left != right for left, right in zip(layouts, layouts[1:], strict=False))
    assert all(row["max_display_words"] <= 8 for row in art["scenes"])
    assert art["governance"]["beast_memory_can_mint_authority"] is False
    assert art["governance"]["human_visual_release"] == "NEEDS_YOU"


def test_teacher_and_assurance_art_languages_are_visually_distinct() -> None:
    teacher = build_art_direction(_story("education_practitioner"))
    assurance = build_art_direction(_story("assurance"))
    assert teacher["art_direction_hash"] != assurance["art_direction_hash"]
    assert teacher["art_language"]["aesthetic"] != assurance["art_language"]["aesthetic"]
    assert teacher["scenes"][0]["layout_family"] != assurance["scenes"][0]["layout_family"]
    assert teacher["format_core_profile"] != assurance["format_core_profile"]


def test_visual_request_contains_sparse_copy_and_local_composition(tmp_path: Path) -> None:
    story = _story()
    request = build_art_directed_gamma_request(story, tmp_path)
    assert request["art_direction_hash"].startswith("sha256:")
    assert "SECRET NARRATION PARAGRAPH" not in request["input_text"]
    assert "Visual direction:" not in request["input_text"]
    assert "Story role:" not in request["input_text"]
    assert "Still doing this by hand?" in request["input_text"]
    assert len(request["creative_direction"]["scene_directions"]) == 7
    assert "four_quadrant_saas_card_grid" in request["creative_direction"]["anti_patterns"]
    assert request["visual_source_policy"] == {
        "primary": "document_studio_local_compositor",
        "gamma": "optional_candidate_only",
        "gamma_required_for_media": False,
    }
    assert (tmp_path / "DOCUMENT_STUDIO_ART_DIRECTION_LANDSCAPE_EXPLAINER.json").is_file()
    local_receipt_path = tmp_path / "DOCUMENT_STUDIO_LOCAL_COMPOSITION_LANDSCAPE_EXPLAINER.json"
    assert local_receipt_path.is_file()
    local_receipt = json.loads(local_receipt_path.read_text(encoding="utf-8"))
    assert local_receipt["state"] == "ready"
    assert local_receipt["frame_count"] == 7
    assert local_receipt["governance"]["gamma_required"] is False
    assert all(Path(row["path"]).is_file() for row in local_receipt["frames"])
    assert len({row["layout_family"] for row in local_receipt["frames"]}) >= 6


def test_active_factory_installs_local_primary_visual_spine_and_real_motion() -> None:
    active = (ROOT / "scripts" / "build_multichannel_campaign_factory.py").read_text(encoding="utf-8")
    spine = (ROOT / "scripts" / "nichefoundry_visual_spine.py").read_text(encoding="utf-8")
    runner = (ROOT / "scripts" / "run_gamma_art_directed_story.js").read_text(encoding="utf-8")
    motion = (ROOT / "scripts" / "cinematic_motion_renderer.py").read_text(encoding="utf-8")
    assert "install_visual_spine(_v3)" in active
    assert '"primary": "document_studio_local_compositor"' in spine
    assert '"gamma_required_for_media": False' in spine
    assert 'DIO_GAMMA_VISUAL_CANDIDATE' in spine
    assert '"optional_skipped"' in spine
    assert "VIDEO FRAME ART, NOT A PRESENTATION DECK" in runner
    assert "MAX_ADDITIONAL_INSTRUCTIONS = 4800" in runner
    assert "additionalInstructions.length > 5000" in runner
    assert "zoompan" in motion
    assert '"motion_state": "executed"' in motion
    assert '"static_slide_deck": False' in motion
