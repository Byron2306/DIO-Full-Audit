from __future__ import annotations

from adapters.format_core.visual_material_registry import MATERIAL_SCHEMA, REGISTRY_SCHEMA
from adapters.format_core.visual_material_resolver import REQUEST_SCHEMA, resolve_visual_material


def _photo(material_id: str) -> dict:
    return {
        "schema": MATERIAL_SCHEMA,
        "material_id": material_id,
        "material_kind": "curated_photo",
        "semantic_visual_kinds": ["research_workbench"],
        "surface_suitability": ["website"],
        "subjects": ["research", "documents"],
        "activities": ["reviewing evidence"],
        "mood": ["credible", "editorial"],
        "composition": {"orientation": "landscape", "subject_bias": "right", "negative_space": "left", "crop_safe": True},
        "license": {"status": "COMMERCIAL_ALLOWED", "commercial_use": True, "attribution_required": False},
        "approval": {"state": "APPROVED"},
        "payload": {"path": f"assets/visual_materials/{material_id}.jpg", "sha256": "sha256:" + "a" * 64},
        "provenance": {"source_url": "https://example.invalid/fixture"},
    }


def test_primary_curated_material_can_be_excluded_after_first_surface_use() -> None:
    registry = {"schema": REGISTRY_SCHEMA, "materials": [_photo("PHOTO-A"), _photo("PHOTO-B")]}
    request = {
        "schema": REQUEST_SCHEMA,
        "request_id": "REUSE-FIXTURE",
        "surface": "website",
        "semantic_visual_kind": "research_workbench",
        "preferred_material_kinds": ["curated_photo"],
        "desired_subjects": ["research", "documents"],
        "desired_activities": ["reviewing evidence"],
        "desired_mood": ["credible", "editorial"],
        "composition": {"orientation": "landscape", "subject_bias": "right", "negative_space": "left", "crop_safe": True},
    }

    first = resolve_visual_material(request, registry)
    second = resolve_visual_material(request, registry, exclude_material_ids={first["selected_material_id"]})

    assert first["selected_material_id"] == "PHOTO-A"
    assert second["selected_material_id"] == "PHOTO-B"
    assert second["excluded_reuse_candidate_count"] == 1
    assert second["reuse_policy"] == "nonrepeating_primary_material_once_per_surface"
