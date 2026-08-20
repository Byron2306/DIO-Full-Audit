from __future__ import annotations

from pathlib import Path

from adapters.format_core.semantic_visual import SEMANTIC_VISUAL_SCHEMA
from adapters.format_core.site_visual_compositor import (
    PROCESS_SCENE_BUDGET,
    REQUIRED_ROLES,
    render_site_visual_assets,
)


_SCENES = [
    {
        "scene_id": "web_01_hook",
        "role": "site_hook",
        "semantic_focus": "problem_and_category",
        "screen_text": "Turn complex research into decisions people can actually use.",
        "narration": "Important research is often trapped in reports, disconnected evidence and unclear decision pathways.",
        "visual": "Open on the actual professional decision context, with research material visible as working evidence rather than decorative interface chrome.",
    },
    {
        "scene_id": "web_02_service",
        "role": "service_1",
        "semantic_focus": "service_1",
        "screen_text": "Research strategy",
        "narration": "Frame complex questions, evidence needs and decision contexts without pretending uncertainty has disappeared.",
        "visual": "Show the framing of a difficult question through real notes, source material and an active working surface.",
    },
    {
        "scene_id": "web_03_service",
        "role": "service_2",
        "semantic_focus": "service_2",
        "screen_text": "Evidence synthesis",
        "narration": "Turn supplied research and source material into reviewable, provenance-aware insight.",
        "visual": "Show source fragments being compared and synthesised into an inspectable evidence trail, with no fake dashboard treatment.",
    },
    {
        "scene_id": "web_04_service",
        "role": "service_3",
        "semantic_focus": "service_3",
        "screen_text": "Decision communication",
        "narration": "Translate governed meaning into clear reports, presentations and public-facing explanations.",
        "visual": "Show the handoff from evidence to a human decision artifact, with the reviewer or client visibly retaining judgment.",
    },
    {
        "scene_id": "web_method",
        "role": "method",
        "semantic_focus": "method",
        "screen_text": "From question to reviewable handoff",
        "narration": "The work begins with the decision context, binds supplied material, exposes uncertainty and prepares an inspectable handoff for professional review.",
        "visual": "Use a spatial process composition built from the real work objects, moving from question to evidence to reviewed handoff without turning the process into a SaaS diagram.",
    },
    {
        "scene_id": "web_proof",
        "role": "proof",
        "semantic_focus": "proof",
        "screen_text": "Inspect the trail behind the claim",
        "narration": "Evidence, reasoning and projection remain inspectable and source-bound.",
        "visual": "Make the proof object the protagonist: semantic law, source lineage, visual QA or provenance record shown as a tangible inspectable artifact.",
    },
    {
        "scene_id": "web_authority",
        "role": "human_authority",
        "semantic_focus": "authority",
        "screen_text": "Professional judgment stays human",
        "narration": "The site may explain evidence-bound work, but it cannot invent clients, outcomes, approval, publication authority or professional judgment.",
        "visual": "End the evidence sequence on a real human review moment where authority is visibly exercised rather than hidden in disclaimer text.",
    },
    {
        "scene_id": "web_cta",
        "role": "cta",
        "semantic_focus": "bounded_next_step",
        "screen_text": "Start with the decision context",
        "narration": "Bring one real job for a bounded review.",
        "visual": "Resolve on one calm, concrete next action with generous negative space and no urgency theatre.",
    },
]


def _inputs() -> tuple[dict, dict]:
    story_hash = "sha256:test-site-story"
    story = {
        "surface": "website",
        "story_hash": story_hash,
        "scenes": [dict(row) for row in _SCENES],
    }
    art = {
        "source_story_hash": story_hash,
        "art_direction_hash": "sha256:test-art-direction",
        "format_core_palette": {"accent": "5fd1d8", "accent_2": "f0b95b"},
        "scenes": [
            {
                "role": row["role"],
                "display_copy": row["screen_text"],
                "visual_subject": row["visual"],
                "layout_family": "editorial_semantic_test",
            }
            for row in _SCENES
        ],
    }
    return story, art


def test_site_visuals_are_owned_by_format_core(tmp_path: Path) -> None:
    story, art = _inputs()
    receipt = render_site_visual_assets(story=story, art=art, output_dir=tmp_path / "svg")

    assert receipt["schema"] == "dio.format_core.site_visual_compositor_receipt.v3"
    assert receipt["semantic_visual_schema"] == SEMANTIC_VISUAL_SCHEMA
    assert receipt["semantic_visual_compiler"] == "DIO_FORMAT_CORE"
    assert receipt["format_core_visual_composition"] == "PASS"
    assert receipt["site_semantic_authority"] == "DIO_SITE_STUDIO"
    assert receipt["geometry_authority"] == "DIO_FORMAT_CORE"
    assert receipt["text_projection_authority"] == "DIO_FORMAT_CORE"
    assert receipt["role_geometry_selection"] == "REFUSE"
    assert receipt["scene_count"] == 8
    assert receipt["semantic_visual_count"] == 8
    assert receipt["all_scene_roles_bound"] is True
    assert receipt["gamma_layout_authority"] == "REFUSE"
    assert receipt["gamma_text_authority"] == "REFUSE"
    assert receipt["authority_created"] is False
    assert receipt["publication"] == "REFUSE"

    assert tuple(row["role"] for row in receipt["assets"]) == REQUIRED_ROLES
    assert all(row["geometry_authority"] == "DIO_FORMAT_CORE" for row in receipt["assets"])
    assert all(row["text_authority"] == "DIO_FORMAT_CORE" for row in receipt["assets"])
    assert all(row["semantic_visual_role_selects_geometry"] is False for row in receipt["assets"])
    assert all((tmp_path / "svg" / row["path"]).is_file() for row in receipt["assets"])


def test_site_visual_grammar_is_semantic_not_shape_swapping(tmp_path: Path) -> None:
    story, art = _inputs()
    receipt = render_site_visual_assets(story=story, art=art, output_dir=tmp_path / "svg")

    assert receipt["timeline_default"] == "REFUSE"
    assert receipt["linear_process_scene_budget"] == PROCESS_SCENE_BUDGET == 1
    assert receipt["linear_process_scene_count"] == 0
    assert receipt["linear_process_budget_pass"] is True
    assert receipt["distinct_visual_kind_count"] == len(REQUIRED_ROLES)

    expected = {
        "site_hook": "research_workbench",
        "service_1": "decision_landscape",
        "service_2": "evidence_network",
        "service_3": "communication_outputs",
        "method": "method_map",
        "proof": "provenance_stack",
        "human_authority": "human_review_scene",
        "cta": "bounded_action",
    }
    assert {row["role"]: row["visual_kind"] for row in receipt["assets"]} == expected
    assert all(row["process_component_count"] == 0 for row in receipt["assets"])


def test_site_visual_composition_is_deterministic(tmp_path: Path) -> None:
    story, art = _inputs()
    first = render_site_visual_assets(story=story, art=art, output_dir=tmp_path / "first")
    second = render_site_visual_assets(story=story, art=art, output_dir=tmp_path / "second")

    assert first["profile_hash"] == second["profile_hash"]
    assert first["compositor_fingerprint"] == second["compositor_fingerprint"]
    assert first["visual_kind_counts"] == second["visual_kind_counts"]
    assert first["semantic_visual_hashes"] == second["semantic_visual_hashes"]
    assert [row["composition_hash"] for row in first["assets"]] == [row["composition_hash"] for row in second["assets"]]
    assert [row["svg_hash"] for row in first["assets"]] == [row["svg_hash"] for row in second["assets"]]
    assert [row["sha256"] for row in first["assets"]] == [row["sha256"] for row in second["assets"]]
