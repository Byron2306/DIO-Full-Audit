from __future__ import annotations

import base64
from pathlib import Path

from adapters.format_core.site_mixed_media import MIXED_MEDIA_SCHEMA, render_site_visual_with_material
from adapters.format_core.visual_composer import load_visual_profiles
from adapters.format_core.visual_material_registry import MATERIAL_SCHEMA, sha256_file


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WlN3YQAAAAASUVORK5CYII="
)


def _photo(root: Path) -> dict:
    path = root / "assets" / "visual_materials" / "hero.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PNG_1X1)
    return {
        "schema": MATERIAL_SCHEMA,
        "material_id": "CURATED-HERO-001",
        "material_kind": "curated_photo",
        "semantic_visual_kinds": ["research_workbench"],
        "surface_suitability": ["website"],
        "subjects": ["research", "documents", "decision context"],
        "activities": ["reviewing evidence"],
        "mood": ["credible", "editorial", "human"],
        "composition": {"orientation": "landscape", "subject_bias": "right", "negative_space": "left", "crop_safe": True},
        "license": {"status": "COMMERCIAL_ALLOWED", "commercial_use": True, "attribution_required": False},
        "approval": {"state": "APPROVED"},
        "payload": {"path": "assets/visual_materials/hero.png", "sha256": sha256_file(path)},
        "provenance": {"source_url": "https://example.invalid/fixture"},
    }


def _spec() -> dict:
    return {
        "schema": "dio.format_core.semantic_visual.v1",
        "visual_id": "SITE-MIXED-MEDIA-FIXTURE",
        "visual_kind": "research_workbench",
        "semantic_visual_hash": "sha256:semantic-fixture",
        "semantic_intent": "show professional research work as real material",
        "title": "Turn complex research into decisions people can actually use.",
        "summary": "Professional research material should feel tangible and credible.",
        "source": {"role": "site_hook", "role_selects_geometry": False},
    }


def test_approved_photo_is_embedded_inside_self_contained_svg(tmp_path: Path) -> None:
    material = _photo(tmp_path)
    resolution = {
        "resolution_hash": "sha256:resolution-fixture",
        "fallback_used": False,
    }
    rendered = render_site_visual_with_material(
        semantic_visual=_spec(),
        material=material,
        resolution=resolution,
        profile_id="site_editorial_dark",
        profiles=load_visual_profiles(),
        material_root=tmp_path,
        binding={"role": "site_hook"},
    )

    assert rendered["mixed_media"] is True
    assert rendered["material_kind"] == "curated_photo"
    svg = rendered["svg"]
    assert "<image " in svg
    assert "data:image/png;base64," in svg
    assert 'href="http://' not in svg
    assert 'href="https://' not in svg
    assert "<script" not in svg.casefold()
    assert "<foreignobject" not in svg.casefold()

    binding = rendered["composition"]["binding"]
    assert binding["mixed_media_schema"] == MIXED_MEDIA_SCHEMA
    assert binding["selected_material_id"] == material["material_id"]
    assert binding["selected_material_kind"] == "curated_photo"
    assert binding["role_selects_geometry"] is False
    assert binding["material_layout_authority"] == "REFUSE"
