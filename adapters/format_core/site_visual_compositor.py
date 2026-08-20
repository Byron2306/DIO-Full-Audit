from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from adapters.format_core.semantic_visual import SEMANTIC_VISUAL_SCHEMA
from adapters.format_core.site_mixed_media import MIXED_MEDIA_SCHEMA, render_site_visual_with_material
from adapters.format_core.site_native_illustration import SITE_ILLUSTRATION_RENDERER_VERSION
from adapters.format_core.site_semantic_visual import compile_site_semantic_visual
from adapters.format_core.site_visual_material import compile_site_visual_material_request
from adapters.format_core.visual_composer import (
    content_hash,
    load_visual_profiles,
    resolve_profile,
    text_hash,
)
from adapters.format_core.visual_material_registry import (
    REGISTRY_SCHEMA,
    load_visual_material_registry,
    material_index,
)
from adapters.format_core.visual_material_resolver import resolve_visual_material


ROOT = Path(__file__).resolve().parents[2]
WIDTH = 1280
HEIGHT = 720
PROFILE_ID = "site_editorial_dark"
PROCESS_SCENE_BUDGET = 1
MIN_REPRESENTATIONAL_MODES = 6
REQUIRED_ROLES = (
    "site_hook",
    "service_1",
    "service_2",
    "service_3",
    "method",
    "proof",
    "human_authority",
    "cta",
)


class SiteFormatVisualCompositorError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _clean(value: Any, limit: int = 260) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit].rstrip()


def _safe_colour(value: Any) -> str | None:
    raw = str(value or "").strip().lstrip("#")
    return "#" + raw if re.fullmatch(r"[0-9A-Fa-f]{6}", raw) else None


def _site_profiles(art: dict[str, Any]) -> dict[str, Any]:
    """Resolve Format Core site law with bounded brand-accent overrides."""
    profiles = copy.deepcopy(load_visual_profiles())
    profile = profiles["profiles"][PROFILE_ID]
    palette = profile["palette"]
    directed = dict(art.get("format_core_palette") or {})
    mapping = {"accent": "accent", "accent_2": "warning", "muted": "muted", "line": "line"}
    for source_key, target_key in mapping.items():
        colour = _safe_colour(directed.get(source_key))
        if colour:
            palette[target_key] = colour
    return profiles


def render_site_visual_assets(
    *,
    story: dict[str, Any],
    art: dict[str, Any],
    output_dir: Path,
    material_registry_path: Path | None = None,
    material_root: Path | None = None,
) -> dict[str, Any]:
    """Compile Site semantics through governed medium selection into customer visuals."""
    scenes = list(story.get("scenes") or [])
    art_scenes = list(art.get("scenes") or [])
    if story.get("surface") != "website":
        raise SiteFormatVisualCompositorError("Format Core site compositor requires a website story surface")
    if len(scenes) != len(art_scenes) or not scenes:
        raise SiteFormatVisualCompositorError("website story and art direction must expose the same non-zero scene count")
    if art.get("source_story_hash") != story.get("story_hash"):
        raise SiteFormatVisualCompositorError("art direction is not bound to the supplied website story")

    roles = tuple(str(row.get("role") or "") for row in scenes)
    if roles != REQUIRED_ROLES:
        raise SiteFormatVisualCompositorError(f"website roles do not match the canonical Site Studio contract: {roles}")

    material_root = (material_root or ROOT).resolve()
    registry = load_visual_material_registry(material_registry_path, root=material_root)
    materials = material_index(registry)

    output_dir.mkdir(parents=True, exist_ok=True)
    profiles = _site_profiles(art)
    resolved_profile = resolve_profile(PROFILE_ID, profiles)
    assets: list[dict[str, Any]] = []
    semantic_visuals: list[dict[str, Any]] = []
    material_requests: list[dict[str, Any]] = []
    material_resolutions: list[dict[str, Any]] = []
    linear_process_scene_count = 0

    for index, (semantic, directed) in enumerate(zip(scenes, art_scenes), 1):
        role = str(semantic.get("role") or "")
        if role != str(directed.get("role") or ""):
            raise SiteFormatVisualCompositorError(f"scene role mismatch at index {index}: {role!r}")

        spec = compile_site_semantic_visual(scene=semantic, story=story, directed=directed)
        if (spec.get("source") or {}).get("role_selects_geometry") is not False:
            raise SiteFormatVisualCompositorError("semantic visual compiler allowed role-selected geometry")
        if (spec.get("source") or {}).get("role") != role:
            raise SiteFormatVisualCompositorError(f"semantic visual role provenance mismatch at index {index}")

        material_request = compile_site_visual_material_request(semantic_visual=spec, scene=semantic, directed=directed)
        if (material_request.get("source") or {}).get("role_selects_material") is not False:
            raise SiteFormatVisualCompositorError("Site material policy allowed role-selected material")
        material_resolution = resolve_visual_material(material_request, registry, root=material_root)
        material = materials.get(str(material_resolution.get("selected_material_id") or ""))
        if not material:
            raise SiteFormatVisualCompositorError("material resolver selected an unknown registry material")

        rendered = render_site_visual_with_material(
            semantic_visual=spec,
            material=material,
            resolution=material_resolution,
            profile_id=PROFILE_ID,
            profiles=profiles,
            material_root=material_root,
            width=WIDTH,
            height=HEIGHT,
            binding={
                "surface": "website",
                "role": role,
                "scene_id": semantic.get("scene_id"),
                "story_hash": story.get("story_hash"),
                "art_direction_hash": art.get("art_direction_hash"),
                "directed_layout_family": directed.get("layout_family"),
                "selection_law": "semantic_visual_to_governed_material_to_format_core_composition",
            },
        )
        composition = rendered["composition"]
        svg = rendered["svg"]
        process_components = sum(component.get("kind") == "process" for component in composition["components"])
        if process_components:
            linear_process_scene_count += 1

        lowered = svg.casefold()
        if "<script" in lowered or "<foreignobject" in lowered:
            raise SiteFormatVisualCompositorError("Format Core emitted forbidden executable/foreign SVG content")
        remote_href_tokens = ('href="http://', 'href="https://', 'xlink:href="http://', 'xlink:href="https://')
        if any(token in lowered for token in remote_href_tokens):
            raise SiteFormatVisualCompositorError("Site visual contains a remote runtime asset href")

        path = output_dir / f"{index:02d}-{role.replace('_', '-')}.svg"
        path.write_text(svg, encoding="utf-8")
        semantic_visuals.append(spec)
        material_requests.append(material_request)
        material_resolutions.append(material_resolution)

        native_mode = str((composition.get("binding") or {}).get("representational_mode") or "")
        representational_mode = native_mode or f"mixed_media_{spec['visual_kind']}_{material['material_kind']}"
        license_row = dict(material.get("license") or {})
        approval_row = dict(material.get("approval") or {})
        assets.append(
            {
                "scene_id": semantic.get("scene_id"),
                "role": role,
                "semantic_focus": semantic.get("semantic_focus"),
                "directed_layout_family": directed.get("layout_family"),
                "visual_kind": spec["visual_kind"],
                "visual_family": spec["visual_kind"],
                "representational_mode": representational_mode,
                "illustration_renderer_version": (composition.get("binding") or {}).get("illustration_renderer_version"),
                "mixed_media_schema": MIXED_MEDIA_SCHEMA if rendered["mixed_media"] else None,
                "mixed_media": bool(rendered["mixed_media"]),
                "material_request_hash": material_request.get("request_hash"),
                "material_resolution_hash": material_resolution.get("resolution_hash"),
                "selected_material_id": material.get("material_id"),
                "selected_material_kind": material.get("material_kind"),
                "material_fallback_used": material_resolution.get("fallback_used"),
                "material_approval_state": approval_row.get("state"),
                "material_license_status": license_row.get("status"),
                "material_commercial_use": license_row.get("commercial_use"),
                "material_attribution_required": license_row.get("attribution_required"),
                "display_copy": directed.get("display_copy"),
                "visual_subject": directed.get("visual_subject"),
                "semantic_intent": spec["semantic_intent"],
                "semantic_visual_schema": spec["schema"],
                "semantic_visual_hash": spec["semantic_visual_hash"],
                "semantic_visual_role_selects_geometry": (spec.get("source") or {}).get("role_selects_geometry"),
                "path": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
                "alt_text": _clean(semantic.get("visual") or directed.get("visual_subject"), 500),
                "composition_hash": content_hash(composition),
                "profile_id": PROFILE_ID,
                "profile_hash": content_hash(resolved_profile),
                "svg_hash": text_hash(svg),
                "process_component_count": process_components,
                "text_authority": "DIO_FORMAT_CORE",
                "geometry_authority": "DIO_FORMAT_CORE",
                "material_layout_authority": "REFUSE",
                "external_visual_provider_layout_authority": "REFUSE",
            }
        )

    if linear_process_scene_count > PROCESS_SCENE_BUDGET:
        raise SiteFormatVisualCompositorError(
            f"Site visual grammar exceeded linear process budget: {linear_process_scene_count}>{PROCESS_SCENE_BUDGET}"
        )

    kind_counts = dict(sorted(Counter(row["visual_kind"] for row in assets).items()))
    if len(kind_counts) < 6:
        raise SiteFormatVisualCompositorError(
            f"Site semantic visual compiler collapsed the page into too few visual kinds: {len(kind_counts)}"
        )
    mode_counts = dict(sorted(Counter(row["representational_mode"] for row in assets).items()))
    if len(mode_counts) < MIN_REPRESENTATIONAL_MODES:
        raise SiteFormatVisualCompositorError(
            f"Site visual production collapsed the page into too few representational modes: {len(mode_counts)}<{MIN_REPRESENTATIONAL_MODES}"
        )
    if any(row["semantic_visual_role_selects_geometry"] is not False for row in assets):
        raise SiteFormatVisualCompositorError("role-selected geometry leaked into Site visual assets")
    if any(row["material_commercial_use"] is not True for row in assets):
        raise SiteFormatVisualCompositorError("a selected visual material is not approved for commercial use")
    if any(row["material_approval_state"] not in {"SYSTEM", "APPROVED"} for row in assets):
        raise SiteFormatVisualCompositorError("an unapproved visual material reached Site production")

    material_kind_counts = dict(sorted(Counter(str(row["selected_material_kind"]) for row in assets).items()))
    mixed_media_scene_count = sum(bool(row["mixed_media"]) for row in assets)
    native_scene_count = sum(row["selected_material_kind"] == "native_renderer" for row in assets)
    fallback_scene_count = sum(bool(row["material_fallback_used"]) for row in assets)

    receipt = {
        "schema": "dio.format_core.site_visual_compositor_receipt.v5",
        "source": "homs_semantic_visual_plus_governed_visual_materials_promoted_into_format_core",
        "surface": "website",
        "story_hash": story.get("story_hash"),
        "art_direction_hash": art.get("art_direction_hash"),
        "profile_id": PROFILE_ID,
        "profile_hash": content_hash(resolved_profile),
        "scene_count": len(assets),
        "assets": assets,
        "semantic_visual_schema": SEMANTIC_VISUAL_SCHEMA,
        "semantic_visual_count": len(semantic_visuals),
        "semantic_visual_hashes": [row["semantic_visual_hash"] for row in semantic_visuals],
        "semantic_visual_compiler": "DIO_FORMAT_CORE",
        "visual_material_registry_schema": REGISTRY_SCHEMA,
        "visual_material_request_count": len(material_requests),
        "visual_material_resolution_count": len(material_resolutions),
        "visual_material_resolution_state": "PASS",
        "selected_material_ids": [row["selected_material_id"] for row in assets],
        "material_kind_counts": material_kind_counts,
        "mixed_media_scene_count": mixed_media_scene_count,
        "native_material_scene_count": native_scene_count,
        "fallback_material_scene_count": fallback_scene_count,
        "all_selected_materials_commercially_allowed": all(row["material_commercial_use"] is True for row in assets),
        "all_selected_materials_approved": all(row["material_approval_state"] in {"SYSTEM", "APPROVED"} for row in assets),
        "external_material_authority": "REFUSE",
        "illustration_renderer": "DIO_FORMAT_CORE_SITE_NATIVE",
        "illustration_renderer_version": SITE_ILLUSTRATION_RENDERER_VERSION,
        "all_scene_roles_bound": tuple(row["role"] for row in assets) == REQUIRED_ROLES,
        "visual_kind_counts": kind_counts,
        "visual_family_counts": kind_counts,
        "distinct_visual_kind_count": len(kind_counts),
        "distinct_visual_family_count": len(kind_counts),
        "representational_mode_counts": mode_counts,
        "distinct_representational_mode_count": len(mode_counts),
        "minimum_representational_mode_count": MIN_REPRESENTATIONAL_MODES,
        "representational_diversity_pass": len(mode_counts) >= MIN_REPRESENTATIONAL_MODES,
        "linear_process_scene_count": linear_process_scene_count,
        "linear_process_scene_budget": PROCESS_SCENE_BUDGET,
        "linear_process_budget_pass": linear_process_scene_count <= PROCESS_SCENE_BUDGET,
        "timeline_default": "REFUSE",
        "generic_node_link_default": "REFUSE",
        "role_geometry_selection": "REFUSE",
        "role_material_selection": "REFUSE",
        "remote_runtime_asset_fetch": "REFUSE",
        "selection_law": "semantic_intent_to_visual_kind_to_material_policy_to_governed_resolver_to_format_core",
        "format_core_visual_composition": "PASS",
        "site_semantic_authority": "DIO_SITE_STUDIO",
        "geometry_authority": "DIO_FORMAT_CORE",
        "text_projection_authority": "DIO_FORMAT_CORE",
        "gamma_layout_authority": "REFUSE",
        "gamma_text_authority": "REFUSE",
        "gamma_role": "OPTIONAL_IMAGE_MATERIAL_ONLY",
        "automatic_selection": "APPROVED_REGISTRY_MATERIAL_ONLY",
        "human_visual_release": "NEEDS_YOU",
        "publication": "REFUSE",
        "authority_created": False,
    }
    receipt["compositor_fingerprint"] = _fingerprint(receipt)
    return receipt


__all__ = [
    "MIN_REPRESENTATIONAL_MODES",
    "PROCESS_SCENE_BUDGET",
    "REQUIRED_ROLES",
    "SiteFormatVisualCompositorError",
    "render_site_visual_assets",
]
