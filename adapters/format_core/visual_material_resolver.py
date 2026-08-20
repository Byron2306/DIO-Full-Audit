from __future__ import annotations

import re
from typing import Any

from adapters.format_core.visual_material_registry import MATERIAL_KINDS, content_hash, validate_visual_material


REQUEST_SCHEMA = "dio.format_core.visual_material_request.v1"
RESOLUTION_SCHEMA = "dio.format_core.visual_material_resolution.v1"
NONREPEATING_MATERIAL_KINDS = {
    "artifact_render",
    "curated_photo",
    "curated_illustration",
    "generated_editorial",
}


class VisualMaterialResolutionError(RuntimeError):
    pass


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _clean(value).casefold()).strip()


def _norm_set(values: Any) -> set[str]:
    return {_token(value) for value in values or [] if _token(value)}


def validate_visual_material_request(request: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if request.get("schema") != REQUEST_SCHEMA:
        errors.append(f"schema must be {REQUEST_SCHEMA}")
    if not _clean(request.get("request_id")):
        errors.append("request_id is required")
    if not _clean(request.get("semantic_visual_kind")):
        errors.append("semantic_visual_kind is required")
    if not _clean(request.get("surface")):
        errors.append("surface is required")
    preferences = [str(value) for value in request.get("preferred_material_kinds") or []]
    if not preferences:
        errors.append("preferred_material_kinds must not be empty")
    for kind in preferences:
        if kind not in MATERIAL_KINDS:
            errors.append(f"unsupported preferred material kind: {kind}")
    if len(preferences) != len(set(preferences)):
        errors.append("preferred_material_kinds must not contain duplicates")
    return {"passed": not errors, "errors": errors}


def _candidate_score(material: dict[str, Any], request: dict[str, Any], preference_index: int) -> tuple[int, dict[str, int]]:
    required_subjects = _norm_set(request.get("required_subjects"))
    desired_subjects = _norm_set(request.get("desired_subjects"))
    desired_activities = _norm_set(request.get("desired_activities"))
    desired_mood = _norm_set(request.get("desired_mood"))
    material_subjects = _norm_set(material.get("subjects"))
    material_activities = _norm_set(material.get("activities"))
    material_mood = _norm_set(material.get("mood"))

    if required_subjects and not required_subjects <= material_subjects:
        return -1, {"preference": 0, "subjects": 0, "activities": 0, "mood": 0, "composition": 0}

    preference_score = max(0, 1000 - preference_index * 150)
    subject_score = len(desired_subjects & material_subjects) * 30
    activity_score = len(desired_activities & material_activities) * 24
    mood_score = len(desired_mood & material_mood) * 18

    composition_score = 0
    request_composition = dict(request.get("composition") or {})
    material_composition = dict(material.get("composition") or {})
    for key, weight in (("orientation", 18), ("subject_bias", 14), ("negative_space", 14)):
        requested = _token(request_composition.get(key))
        actual = _token(material_composition.get(key))
        if requested and actual and requested == actual:
            composition_score += weight
    if request_composition.get("crop_safe") is True and material_composition.get("crop_safe") is True:
        composition_score += 16

    breakdown = {
        "preference": preference_score,
        "subjects": subject_score,
        "activities": activity_score,
        "mood": mood_score,
        "composition": composition_score,
    }
    return sum(breakdown.values()), breakdown


def resolve_visual_material(
    request: dict[str, Any],
    registry: dict[str, Any],
    *,
    root=None,
    exclude_material_ids: set[str] | None = None,
) -> dict[str, Any]:
    validation = validate_visual_material_request(request)
    if not validation["passed"]:
        raise VisualMaterialResolutionError("Invalid visual material request: " + "; ".join(validation["errors"]))

    visual_kind = _clean(request.get("semantic_visual_kind"))
    surface = _clean(request.get("surface"))
    preferences = [str(value) for value in request.get("preferred_material_kinds") or []]
    preference_lookup = {kind: index for index, kind in enumerate(preferences)}
    excluded = set(exclude_material_ids or set())

    evaluated: list[dict[str, Any]] = []
    excluded_reuse_count = 0
    for material in registry.get("materials") or []:
        material = dict(material)
        material_validation = validate_visual_material(material, root=root)
        if not material_validation["selectable"]:
            continue
        kind = str(material.get("material_kind") or "")
        material_id = str(material.get("material_id") or "")
        if kind in NONREPEATING_MATERIAL_KINDS and material_id in excluded:
            excluded_reuse_count += 1
            continue
        if kind not in preference_lookup:
            continue
        if visual_kind not in set(material.get("semantic_visual_kinds") or []):
            continue
        if surface not in set(material.get("surface_suitability") or []):
            continue
        score, breakdown = _candidate_score(material, request, preference_lookup[kind])
        if score < 0:
            continue
        evaluated.append(
            {
                "material_id": material_id,
                "material_kind": kind,
                "score": score,
                "score_breakdown": breakdown,
                "preference_index": preference_lookup[kind],
            }
        )

    if not evaluated:
        raise VisualMaterialResolutionError(
            f"No selectable visual material for {visual_kind!r} on {surface!r} under requested material policy"
        )

    evaluated.sort(key=lambda row: (-int(row["score"]), int(row["preference_index"]), str(row["material_id"])))
    selected = evaluated[0]
    first_preference = preferences[0]
    resolution_core = {
        "schema": RESOLUTION_SCHEMA,
        "request_id": request["request_id"],
        "request_hash": content_hash(request),
        "semantic_visual_kind": visual_kind,
        "surface": surface,
        "candidate_count": len(evaluated),
        "excluded_reuse_candidate_count": excluded_reuse_count,
        "selected_material_id": selected["material_id"],
        "selected_material_kind": selected["material_kind"],
        "selected_score": selected["score"],
        "selected_score_breakdown": selected["score_breakdown"],
        "preferred_material_kinds": preferences,
        "preferred_kind_satisfied": selected["material_kind"] == first_preference,
        "fallback_used": selected["material_kind"] != first_preference,
        "candidate_summary": evaluated,
        "selection_law": "semantic_visual_kind_then_medium_policy_then_governed_metadata_score_no_repeated_primary_material",
        "reuse_policy": "nonrepeating_primary_material_once_per_surface",
        "authority_created": False,
        "external_material_layout_authority": "REFUSE",
        "automatic_publication": "REFUSE",
    }
    return {**resolution_core, "resolution_hash": content_hash(resolution_core)}


__all__ = [
    "NONREPEATING_MATERIAL_KINDS",
    "REQUEST_SCHEMA",
    "RESOLUTION_SCHEMA",
    "VisualMaterialResolutionError",
    "resolve_visual_material",
    "validate_visual_material_request",
]
