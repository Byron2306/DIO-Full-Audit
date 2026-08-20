from __future__ import annotations

from pathlib import Path

from adapters.format_core.site_visual_compositor import (
    PROCESS_SCENE_BUDGET,
    REQUIRED_ROLES,
    render_site_visual_assets,
)


def _inputs() -> tuple[dict, dict]:
    story_hash = "sha256:test-site-story"
    story = {
        "surface": "website",
        "story_hash": story_hash,
        "scenes": [
            {
                "scene_id": f"SCENE-{index:02d}",
                "role": role,
                "screen_text": f"Controlled {role.replace('_', ' ')}",
                "visual": f"Visual evidence for {role}",
            }
            for index, role in enumerate(REQUIRED_ROLES, 1)
        ],
    }
    art = {
        "source_story_hash": story_hash,
        "art_direction_hash": "sha256:test-art-direction",
        "format_core_palette": {"accent": "5fd1d8", "accent_2": "f0b95b"},
        "scenes": [
            {
                "role": role,
                "display_copy": f"Professional {role.replace('_', ' ')}",
                "visual_subject": f"Governed composition for {role}",
                "layout_family": "editorial",
            }
            for role in REQUIRED_ROLES
        ],
    }
    return story, art


def test_site_visuals_are_owned_by_format_core(tmp_path: Path) -> None:
    story, art = _inputs()
    receipt = render_site_visual_assets(story=story, art=art, output_dir=tmp_path / "svg")

    assert receipt["schema"] == "dio.format_core.site_visual_compositor_receipt.v2"
    assert receipt["format_core_visual_composition"] == "PASS"
    assert receipt["site_semantic_authority"] == "DIO_SITE_STUDIO"
    assert receipt["geometry_authority"] == "DIO_FORMAT_CORE"
    assert receipt["text_projection_authority"] == "DIO_FORMAT_CORE"
    assert receipt["scene_count"] == 8
    assert receipt["all_scene_roles_bound"] is True
    assert receipt["gamma_layout_authority"] == "REFUSE"
    assert receipt["gamma_text_authority"] == "REFUSE"
    assert receipt["authority_created"] is False
    assert receipt["publication"] == "REFUSE"

    assert tuple(row["role"] for row in receipt["assets"]) == REQUIRED_ROLES
    assert all(row["geometry_authority"] == "DIO_FORMAT_CORE" for row in receipt["assets"])
    assert all(row["text_authority"] == "DIO_FORMAT_CORE" for row in receipt["assets"])
    assert all((tmp_path / "svg" / row["path"]).is_file() for row in receipt["assets"])


def test_site_visual_grammar_refuses_timeline_obsession(tmp_path: Path) -> None:
    story, art = _inputs()
    receipt = render_site_visual_assets(story=story, art=art, output_dir=tmp_path / "svg")

    assert receipt["timeline_default"] == "REFUSE"
    assert receipt["linear_process_scene_budget"] == PROCESS_SCENE_BUDGET == 1
    assert receipt["linear_process_scene_count"] == 1
    assert receipt["linear_process_budget_pass"] is True
    assert receipt["distinct_visual_family_count"] == len(REQUIRED_ROLES)

    process_roles = [row["role"] for row in receipt["assets"] if row["process_component_count"]]
    assert process_roles == ["method"]
    assert receipt["assets"][0]["visual_family"] == "editorial_problem_field"
    assert next(row for row in receipt["assets"] if row["role"] == "service_2")["visual_family"] == "evidence_constellation"
    assert next(row for row in receipt["assets"] if row["role"] == "service_3")["visual_family"] == "split_accountable_handoff"
    assert next(row for row in receipt["assets"] if row["role"] == "cta")["visual_family"] == "single_focal_action"


def test_site_visual_composition_is_deterministic(tmp_path: Path) -> None:
    story, art = _inputs()
    first = render_site_visual_assets(story=story, art=art, output_dir=tmp_path / "first")
    second = render_site_visual_assets(story=story, art=art, output_dir=tmp_path / "second")

    assert first["profile_hash"] == second["profile_hash"]
    assert first["compositor_fingerprint"] == second["compositor_fingerprint"]
    assert first["visual_family_counts"] == second["visual_family_counts"]
    assert [row["composition_hash"] for row in first["assets"]] == [row["composition_hash"] for row in second["assets"]]
    assert [row["svg_hash"] for row in first["assets"]] == [row["svg_hash"] for row in second["assets"]]
    assert [row["sha256"] for row in first["assets"]] == [row["sha256"] for row in second["assets"]]
