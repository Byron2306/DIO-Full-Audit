from __future__ import annotations

import json
from pathlib import Path

from adapters.format_core.visual_material_pack import evaluate_visual_material_pack, load_visual_material_pack
from adapters.format_core.visual_material_registry import MATERIAL_SCHEMA, REGISTRY_SCHEMA


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "config" / "visual_material_packs" / "research_consultancy_alpha.json"


def _native(material_id: str, visual_kind: str, subjects: list[str]) -> dict:
    return {
        "schema": MATERIAL_SCHEMA,
        "material_id": material_id,
        "material_kind": "native_renderer",
        "semantic_visual_kinds": [visual_kind],
        "surface_suitability": ["website"],
        "subjects": subjects,
        "activities": [],
        "mood": ["professional"],
        "composition": {"orientation": "landscape", "subject_bias": "balanced", "negative_space": "none", "crop_safe": True},
        "license": {"status": "INTERNAL_ORIGINAL", "commercial_use": True, "attribution_required": False},
        "approval": {"state": "SYSTEM"},
        "provenance": {"source": "TEST", "authority_created": False},
    }


def _file_material(
    material_id: str,
    kind: str,
    visual_kind: str,
    subjects: list[str],
    *,
    activities: list[str] | None = None,
    mood: list[str] | None = None,
) -> dict:
    license_state = "INTERNAL_ORIGINAL" if kind == "artifact_render" else "COMMERCIAL_ALLOWED"
    return {
        "schema": MATERIAL_SCHEMA,
        "material_id": material_id,
        "material_kind": kind,
        "semantic_visual_kinds": [visual_kind],
        "surface_suitability": ["website"],
        "subjects": subjects,
        "activities": list(activities or []),
        "mood": list(mood or ["professional"]),
        "composition": {"orientation": "landscape", "subject_bias": "balanced", "negative_space": "left", "crop_safe": True},
        "payload": {"path": f"assets/visual_materials/test/{material_id}.png", "sha256": "sha256:" + "a" * 64},
        "license": {"status": license_state, "commercial_use": True, "attribution_required": False},
        "approval": {"state": "APPROVED"},
        "provenance": {"source": "TEST", "authority_created": False},
    }


def _registry(materials: list[dict]) -> dict:
    return {"schema": REGISTRY_SCHEMA, "registry_id": "TEST", "materials": materials}


def _full_materials() -> list[dict]:
    return [
        _file_material("HERO", "curated_photo", "research_workbench", ["research", "documents"], mood=["editorial", "credible"]),
        _native("STRATEGY", "decision_landscape", ["research strategy", "decision context"]),
        _native("EVIDENCE", "evidence_network", ["evidence", "claims", "synthesis"]),
        _file_material("COMM", "artifact_render", "communication_outputs", ["report", "presentation"]),
        _file_material(
            "METHOD",
            "curated_photo",
            "method_map",
            ["professional workflow", "documents", "review"],
            activities=["reviewing documents"],
            mood=["tactile", "credible"],
        ),
        _file_material("PROOF", "artifact_render", "provenance_stack", ["provenance", "source lineage", "evidence"]),
        _file_material(
            "HUMAN",
            "curated_photo",
            "human_review_scene",
            ["human review", "documents", "professional judgement"],
            activities=["reviewing documents"],
            mood=["credible", "human", "professional"],
        ),
        _native("CTA", "bounded_action", ["client intake", "bounded next step"]),
        _file_material("TEXTURE", "texture", "research_workbench", ["paper", "document", "texture"], mood=["subtle", "editorial"]),
    ]


def test_default_customer_visual_pack_is_well_formed() -> None:
    pack = load_visual_material_pack(PACK)
    assert pack["pack_id"] == "RESEARCH_CONSULTANCY_ALPHA"
    assert len(pack["slots"]) == 9
    assert pack["minimum_distinct_material_kinds"] == 4
    assert pack["minimum_curated_primary_materials"] == 3
    assert pack["maximum_native_renderer_share"] == 0.5


def test_incomplete_pack_refuses_with_named_missing_slots() -> None:
    pack = load_visual_material_pack(PACK)
    materials = [
        _file_material("HERO", "curated_photo", "research_workbench", ["research", "documents"], mood=["editorial", "credible"]),
        _native("STRATEGY", "decision_landscape", ["research strategy", "decision context"]),
        _native("EVIDENCE", "evidence_network", ["evidence", "claims", "synthesis"]),
        _native("CTA", "bounded_action", ["client intake", "bounded next step"]),
    ]
    readiness = evaluate_visual_material_pack(pack, _registry(materials))
    assert readiness["state"] == "REFUSE"
    assert "HUMAN_REVIEW" in readiness["missing_required_slots"]
    assert "TACTILE_WORKFLOW" in readiness["missing_required_slots"]
    assert "COMMUNICATION_ARTIFACT" in readiness["missing_required_slots"]
    assert "EVIDENCE_OR_PROVENANCE_ARTIFACT" in readiness["missing_required_slots"]
    assert "EDITORIAL_TEXTURE" in readiness["missing_required_slots"]


def test_balanced_customer_visual_pack_reaches_ready_needs_you() -> None:
    pack = load_visual_material_pack(PACK)
    readiness = evaluate_visual_material_pack(pack, _registry(_full_materials()))
    assert readiness["state"] == "READY_NEEDS_YOU"
    assert readiness["missing_required_slots"] == []
    assert readiness["required_slots_satisfied"] == readiness["required_slot_count"] == 9
    assert readiness["curated_primary_material_count"] == 3
    assert readiness["distinct_selected_material_kind_count"] == 4
    assert readiness["native_primary_material_share"] <= 0.5
    assert all(readiness["checks"].values())
    assert readiness["human_visual_release"] == "NEEDS_YOU"
    assert readiness["commercial_validation"] == "UNPROVED"


def test_primary_external_material_cannot_satisfy_two_required_slots() -> None:
    pack = load_visual_material_pack(PACK)
    materials = _full_materials()
    shared = _file_material(
        "SHARED",
        "curated_photo",
        "method_map",
        ["professional workflow", "documents", "review", "human review", "professional judgement"],
        activities=["reviewing documents"],
        mood=["credible", "professional"],
    )
    shared["semantic_visual_kinds"] = ["method_map", "human_review_scene"]
    materials = [row for row in materials if row["material_id"] not in {"METHOD", "HUMAN"}] + [shared]
    readiness = evaluate_visual_material_pack(pack, _registry(materials))
    assert readiness["state"] == "REFUSE"
    failed = {row["slot_id"] for row in readiness["slots"] if row["state"] == "REFUSE"}
    assert failed & {"TACTILE_WORKFLOW", "HUMAN_REVIEW"}
