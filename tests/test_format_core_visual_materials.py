from __future__ import annotations

import base64
import copy
from pathlib import Path

from adapters.format_core.site_visual_material import compile_site_visual_material_request
from adapters.format_core.visual_material_registry import (
    MATERIAL_SCHEMA,
    REGISTRY_SCHEMA,
    material_data_uri,
    sha256_file,
    validate_visual_material,
    validate_visual_material_registry,
)
from adapters.format_core.visual_material_resolver import resolve_visual_material


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WlN3YQAAAAASUVORK5CYII="
)


def _native(kind: str) -> dict:
    return {
        "schema": MATERIAL_SCHEMA,
        "material_id": f"NATIVE-{kind}",
        "material_kind": "native_renderer",
        "semantic_visual_kinds": [kind],
        "surface_suitability": ["website"],
        "subjects": ["research", "documents", "human review"],
        "activities": ["reviewing evidence", "reviewing documents"],
        "mood": ["credible", "editorial", "human"],
        "composition": {"orientation": "landscape", "subject_bias": "balanced", "negative_space": "none", "crop_safe": True},
        "license": {"status": "INTERNAL_ORIGINAL", "commercial_use": True, "attribution_required": False},
        "approval": {"state": "SYSTEM"},
        "provenance": {"source": "DIO_FORMAT_CORE"},
    }


def _photo(tmp_path: Path, *, approved: bool) -> dict:
    path = tmp_path / "assets" / "visual_materials" / "research-review.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PNG_1X1)
    return {
        "schema": MATERIAL_SCHEMA,
        "material_id": "CURATED-RESEARCH-REVIEW-001",
        "material_kind": "curated_photo",
        "semantic_visual_kinds": ["research_workbench", "human_review_scene"],
        "surface_suitability": ["website"],
        "subjects": ["research", "documents", "decision context", "human review", "professional judgement"],
        "activities": ["reviewing evidence", "reviewing documents"],
        "mood": ["credible", "editorial", "human", "professional"],
        "composition": {"orientation": "landscape", "subject_bias": "right", "negative_space": "left", "crop_safe": True},
        "license": {
            "status": "COMMERCIAL_ALLOWED",
            "commercial_use": True,
            "attribution_required": False,
            "provider": "fixture",
        },
        "approval": {"state": "APPROVED" if approved else "NEEDS_REVIEW"},
        "payload": {
            "path": "assets/visual_materials/research-review.png",
            "sha256": sha256_file(path),
        },
        "provenance": {"source_url": "https://example.invalid/fixture", "imported_by": "test"},
    }


def _request(kind: str) -> dict:
    scene = {
        "scene_id": "fixture-scene",
        "role": "site_hook",
        "semantic_focus": "problem_and_category",
    }
    directed = {"layout_family": "fixture"}
    semantic_visual = {
        "visual_kind": kind,
        "semantic_visual_hash": "sha256:fixture",
        "semantic_intent": "fixture semantic intent",
    }
    return compile_site_visual_material_request(
        semantic_visual=semantic_visual,
        scene=scene,
        directed=directed,
    )


def test_registry_accepts_review_queue_but_does_not_make_it_selectable(tmp_path: Path) -> None:
    native = _native("research_workbench")
    pending = _photo(tmp_path, approved=False)
    registry = {"schema": REGISTRY_SCHEMA, "materials": [native, pending]}

    validation = validate_visual_material_registry(registry, root=tmp_path)
    assert validation["passed"], validation["errors"]
    assert validation["material_count"] == 2
    assert validation["selectable_count"] == 1
    pending_validation = validate_visual_material(pending, root=tmp_path)
    assert pending_validation["passed"] is True
    assert pending_validation["selectable"] is False
    assert pending_validation["warnings"]


def test_approved_photo_beats_native_for_research_workbench(tmp_path: Path) -> None:
    native = _native("research_workbench")
    photo = _photo(tmp_path, approved=True)
    registry = {"schema": REGISTRY_SCHEMA, "materials": [native, photo]}
    request = _request("research_workbench")

    resolution = resolve_visual_material(request, registry, root=tmp_path)
    assert resolution["selected_material_id"] == photo["material_id"]
    assert resolution["selected_material_kind"] == "curated_photo"
    assert resolution["preferred_kind_satisfied"] is True
    assert resolution["fallback_used"] is False

    uri = material_data_uri(photo, root=tmp_path)
    assert uri.startswith("data:image/png;base64,")
    assert "http" not in uri


def test_pending_photo_is_skipped_and_native_fallback_is_explicit(tmp_path: Path) -> None:
    native = _native("research_workbench")
    pending = _photo(tmp_path, approved=False)
    registry = {"schema": REGISTRY_SCHEMA, "materials": [pending, native]}
    request = _request("research_workbench")

    resolution = resolve_visual_material(request, registry, root=tmp_path)
    assert resolution["selected_material_id"] == native["material_id"]
    assert resolution["selected_material_kind"] == "native_renderer"
    assert resolution["fallback_used"] is True


def test_tampered_curated_asset_is_refused(tmp_path: Path) -> None:
    photo = _photo(tmp_path, approved=True)
    path = tmp_path / photo["payload"]["path"]
    path.write_bytes(PNG_1X1 + b"tamper")

    validation = validate_visual_material(photo, root=tmp_path)
    assert validation["passed"] is False
    assert any("hash mismatch" in error for error in validation["errors"])


def test_role_does_not_select_material_policy() -> None:
    first = _request("research_workbench")
    second = copy.deepcopy(first)
    second["source"]["role"] = "service_3"

    assert first["preferred_material_kinds"] == ["curated_photo", "generated_editorial", "native_renderer"]
    assert second["preferred_material_kinds"] == first["preferred_material_kinds"]
    assert first["source"]["role_selects_material"] is False
