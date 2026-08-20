from __future__ import annotations

from pathlib import Path

from adapters.document_studio.site_svg_compositor import render_site_svg_assets


def _story_and_art():
    roles = ["site_hook", "service_1", "service_2", "service_3", "method", "proof", "human_authority", "cta"]
    story = {
        "schema": "dio.lingua.website_story.v1",
        "surface": "website",
        "story_hash": "sha256:story",
        "scenes": [
            {
                "scene_id": f"web-{index:02d}",
                "role": role,
                "screen_text": role.replace("_", " ").title(),
                "visual": f"Purpose-bound visual for {role}",
            }
            for index, role in enumerate(roles, 1)
        ],
    }
    layouts = [
        "forensic_full_bleed_hook",
        "consequence_evidence_split",
        "missing_trace_negative_space",
        "controlled_workflow_map",
        "macro_proof_closeup",
        "authority_boundary_portrait",
        "hard_resolve_cta",
        "forensic_full_bleed_hook",
    ]
    art = {
        "source_story_hash": "sha256:story",
        "art_direction_hash": "sha256:art",
        "format_core_palette": {
            "ink": "17212B",
            "accent": "146A6F",
            "accent_2": "A13D2D",
            "muted": "5F6B76",
            "line": "A8B7B5",
            "paper": "FFFFFF",
            "fill": "E8F0EE",
        },
        "scenes": [
            {
                "scene_id": f"web-{index:02d}",
                "role": role,
                "layout_family": layout,
                "display_copy": role.replace("_", " ").title(),
                "visual_subject": f"Purpose-bound visual for {role}",
            }
            for index, (role, layout) in enumerate(zip(roles, layouts), 1)
        ],
    }
    return story, art


def test_site_svg_compositor_renders_all_semantic_roles(tmp_path: Path):
    story, art = _story_and_art()
    receipt = render_site_svg_assets(story=story, art=art, output_dir=tmp_path)

    assert receipt["scene_count"] == 8
    assert receipt["all_scene_roles_bound"] is True
    assert receipt["gamma_layout_authority"] == "REFUSE"
    assert receipt["gamma_text_authority"] == "REFUSE"
    assert receipt["gamma_role"] == "OPTIONAL_IMAGE_MATERIAL_ONLY"
    assert receipt["automatic_selection"] == "REFUSE"
    assert receipt["human_visual_release"] == "NEEDS_YOU"
    assert len({row["sha256"] for row in receipt["assets"]}) == 8

    for asset in receipt["assets"]:
        path = tmp_path / asset["path"]
        text = path.read_text(encoding="utf-8")
        assert path.is_file()
        assert '<svg xmlns="http://www.w3.org/2000/svg"' in text
        assert "<script" not in text.casefold()
        assert "<foreignobject" not in text.casefold()
        assert asset["text_authority"] == "DIO_DOCUMENT_STUDIO"
        assert asset["geometry_authority"] == "DIO_DOCUMENT_STUDIO"


def test_site_svg_compositor_is_deterministic(tmp_path: Path):
    story, art = _story_and_art()
    first = render_site_svg_assets(story=story, art=art, output_dir=tmp_path / "a")
    second = render_site_svg_assets(story=story, art=art, output_dir=tmp_path / "b")

    assert first["compositor_fingerprint"] == second["compositor_fingerprint"]
    assert [row["sha256"] for row in first["assets"]] == [row["sha256"] for row in second["assets"]]
