from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from adapters.format_core.semantic_visual import SEMANTIC_VISUAL_SCHEMA
from adapters.format_core.site_native_illustration import (
    SITE_ILLUSTRATION_RENDERER_VERSION,
    site_semantic_visual_to_composition,
)
from adapters.format_core.site_semantic_visual import compile_site_semantic_visual
from adapters.format_core.visual_composer import (
    content_hash,
    load_visual_profiles,
    render_svg,
    resolve_profile,
    text_hash,
)


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
    mapping = {
        "accent": "accent",
        "accent_2": "warning",
        "muted": "muted",
        "line": "line",
    }
    for source_key, target_key in mapping.items():
        colour = _safe_colour(directed.get(source_key))
        if colour:
            palette[target_key] = colour
    return profiles


def render_site_visual_assets(*, story: dict[str, Any], art: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """Compile website semantics into content-native Format Core illustrations.

    Site Studio owns semantic story structure. Format Core first compiles every
    scene into ``dio.format_core.semantic_visual.v1``. Site-native semantic
    kinds are then rendered as recognisable professional objects and situations
    rather than generic diagram topology.

    A scene role is preserved as provenance and is explicitly forbidden from
    selecting geometry. External providers may contribute optional image
    material but never acquire semantic, geometry, text, selection, release or
    publication authority.
    """
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

    output_dir.mkdir(parents=True, exist_ok=True)
    profiles = _site_profiles(art)
    resolved_profile = resolve_profile(PROFILE_ID, profiles)
    assets: list[dict[str, Any]] = []
    semantic_visuals: list[dict[str, Any]] = []
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

        composition = site_semantic_visual_to_composition(
            spec,
            profile_id=PROFILE_ID,
            width=WIDTH,
            height=HEIGHT,
            binding={
                "surface": "website",
                "role": role,
                "scene_id": semantic.get("scene_id"),
                "story_hash": story.get("story_hash"),
                "art_direction_hash": art.get("art_direction_hash"),
                "directed_layout_family": directed.get("layout_family"),
                "selection_law": "semantic_visual_kind_to_object_native_illustration_role_is_provenance_only",
            },
        )
        process_components = sum(component.get("kind") == "process" for component in composition["components"])
        if process_components:
            linear_process_scene_count += 1

        svg = render_svg(composition, profiles)
        lowered = svg.casefold()
        if "<script" in lowered or "<foreignobject" in lowered:
            raise SiteFormatVisualCompositorError("Format Core emitted forbidden executable/foreign SVG content")

        path = output_dir / f"{index:02d}-{role.replace('_', '-')}.svg"
        path.write_text(svg, encoding="utf-8")
        semantic_visuals.append(spec)
        representational_mode = str((composition.get("binding") or {}).get("representational_mode") or "")
        if not representational_mode:
            raise SiteFormatVisualCompositorError(f"Site illustration omitted representational mode at index {index}")
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
            f"Site illustration renderer collapsed the page into too few representational modes: {len(mode_counts)}<{MIN_REPRESENTATIONAL_MODES}"
        )
    if any(row["semantic_visual_role_selects_geometry"] is not False for row in assets):
        raise SiteFormatVisualCompositorError("role-selected geometry leaked into Site visual assets")

    receipt = {
        "schema": "dio.format_core.site_visual_compositor_receipt.v4",
        "source": "homs_object_native_semantic_visual_discipline_promoted_into_format_core",
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
        "selection_law": "semantic_intent_to_visual_kind_to_object_native_renderer_to_svg",
        "format_core_visual_composition": "PASS",
        "site_semantic_authority": "DIO_SITE_STUDIO",
        "geometry_authority": "DIO_FORMAT_CORE",
        "text_projection_authority": "DIO_FORMAT_CORE",
        "gamma_layout_authority": "REFUSE",
        "gamma_text_authority": "REFUSE",
        "gamma_role": "OPTIONAL_IMAGE_MATERIAL_ONLY",
        "automatic_selection": "REFUSE",
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
