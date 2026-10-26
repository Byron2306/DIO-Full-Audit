from __future__ import annotations

from typing import Any

from adapters.format_core.visual_material_registry import content_hash
from adapters.format_core.visual_material_resolver import REQUEST_SCHEMA, validate_visual_material_request


SITE_MATERIAL_POLICY: dict[str, dict[str, Any]] = {
    "research_workbench": {
        "preferred_material_kinds": ["curated_photo", "generated_editorial", "native_renderer"],
        "desired_subjects": ["research", "documents", "decision context"],
        "desired_activities": ["reviewing evidence"],
        "desired_mood": ["credible", "editorial", "human"],
        "composition": {"orientation": "landscape", "subject_bias": "right", "negative_space": "left", "crop_safe": True},
    },
    "decision_landscape": {
        "preferred_material_kinds": ["native_renderer", "curated_illustration"],
        "desired_subjects": ["research strategy", "decision context", "uncertainty"],
        "desired_activities": ["planning"],
        "desired_mood": ["analytical", "editorial"],
        "composition": {"orientation": "landscape", "subject_bias": "balanced", "negative_space": "none", "crop_safe": True},
    },
    "evidence_network": {
        "preferred_material_kinds": ["artifact_render", "native_renderer"],
        "desired_subjects": ["evidence", "claims", "synthesis"],
        "desired_activities": ["synthesising evidence"],
        "desired_mood": ["analytical", "credible"],
        "composition": {"orientation": "landscape", "subject_bias": "balanced", "negative_space": "none", "crop_safe": True},
    },
    "communication_outputs": {
        "preferred_material_kinds": ["artifact_render", "curated_photo", "native_renderer"],
        "desired_subjects": ["report", "presentation", "public explanation"],
        "desired_activities": ["communicating decisions"],
        "desired_mood": ["professional", "editorial"],
        "composition": {"orientation": "landscape", "subject_bias": "balanced", "negative_space": "none", "crop_safe": True},
    },
    "method_map": {
        "preferred_material_kinds": ["curated_photo", "generated_editorial", "native_renderer"],
        "desired_subjects": ["professional workflow", "documents", "review"],
        "desired_activities": ["reviewing documents"],
        "desired_mood": ["tactile", "credible", "professional"],
        "composition": {"orientation": "landscape", "subject_bias": "right", "negative_space": "left", "crop_safe": True},
    },
    "provenance_stack": {
        "preferred_material_kinds": ["artifact_render", "native_renderer"],
        "desired_subjects": ["provenance", "source lineage", "evidence"],
        "desired_activities": ["inspecting evidence"],
        "desired_mood": ["analytical", "credible"],
        "composition": {"orientation": "landscape", "subject_bias": "balanced", "negative_space": "none", "crop_safe": True},
    },
    "human_review_scene": {
        "preferred_material_kinds": ["curated_photo", "generated_editorial", "native_renderer"],
        "desired_subjects": ["human review", "documents", "professional judgement"],
        "desired_activities": ["reviewing documents"],
        "desired_mood": ["credible", "human", "professional"],
        "composition": {"orientation": "landscape", "subject_bias": "right", "negative_space": "left", "crop_safe": True},
    },
    "bounded_action": {
        "preferred_material_kinds": ["native_renderer"],
        "desired_subjects": ["client intake", "bounded next step"],
        "desired_activities": ["starting a controlled review"],
        "desired_mood": ["calm", "professional"],
        "composition": {"orientation": "landscape", "subject_bias": "left", "negative_space": "right", "crop_safe": True},
    },
}


class SiteVisualMaterialPolicyError(RuntimeError):
    pass


def compile_site_visual_material_request(
    *,
    semantic_visual: dict[str, Any],
    scene: dict[str, Any],
    directed: dict[str, Any],
) -> dict[str, Any]:
    visual_kind = str(semantic_visual.get("visual_kind") or "")
    policy = SITE_MATERIAL_POLICY.get(visual_kind)
    if policy is None:
        raise SiteVisualMaterialPolicyError(f"No Site material policy for semantic visual kind: {visual_kind or '(missing)'}")

    scene_id = str(scene.get("scene_id") or visual_kind)
    request_core = {
        "schema": REQUEST_SCHEMA,
        "request_id": f"SITE-MATERIAL-{scene_id}",
        "surface": "website",
        "semantic_visual_kind": visual_kind,
        "semantic_visual_hash": semantic_visual.get("semantic_visual_hash"),
        "semantic_intent": semantic_visual.get("semantic_intent"),
        "preferred_material_kinds": list(policy["preferred_material_kinds"]),
        "required_subjects": [],
        "desired_subjects": list(policy.get("desired_subjects") or []),
        "desired_activities": list(policy.get("desired_activities") or []),
        "desired_mood": list(policy.get("desired_mood") or []),
        "composition": dict(policy.get("composition") or {}),
        "source": {
            "scene_id": scene.get("scene_id"),
            "role": scene.get("role"),
            "directed_layout_family": directed.get("layout_family"),
            "role_selects_material": False,
        },
        "fallback_policy": "ordered_material_kind_fallback_fail_closed",
        "automatic_publication": "REFUSE",
        "authority_created": False,
    }
    request = {**request_core, "request_hash": content_hash(request_core)}
    validation = validate_visual_material_request(request)
    if not validation["passed"]:
        raise SiteVisualMaterialPolicyError("Invalid Site visual material request: " + "; ".join(validation["errors"]))
    return request


__all__ = [
    "SITE_MATERIAL_POLICY",
    "SiteVisualMaterialPolicyError",
    "compile_site_visual_material_request",
]
