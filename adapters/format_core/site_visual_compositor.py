from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from adapters.format_core.visual_composer import (
    SCHEMA,
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
    """Resolve the Format Core site law and allow only bounded brand-accent overrides."""
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


def _title(scene: dict[str, Any]) -> str:
    return _clean(scene.get("display_copy") or scene.get("screen_text") or scene.get("role"), 150)


def _subtitle(scene: dict[str, Any]) -> str:
    return _clean(scene.get("visual_subject") or scene.get("visual") or "Governed deterministic visual composition.", 220)


def _base(scene: dict[str, Any], role: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "role",
            "kind": "badge",
            "x": 76,
            "y": 58,
            "width": 210,
            "height": 38,
            "text": role.replace("_", " ").upper(),
            "size": 13,
        },
        {
            "id": "title",
            "kind": "text",
            "x": 76,
            "y": 168,
            "text": _title(scene),
            "size": 50,
            "weight": "900",
            "fill": "$ink",
            "wrap_chars": 34,
            "max_lines": 2,
            "line_gap": 56,
        },
        {
            "id": "subtitle",
            "kind": "text",
            "x": 78,
            "y": 292,
            "text": _subtitle(scene),
            "size": 18,
            "weight": "600",
            "fill": "$muted",
            "wrap_chars": 76,
            "max_lines": 2,
            "line_gap": 24,
        },
    ]


def _hook(scene: dict[str, Any]) -> list[dict[str, Any]]:
    return _base(scene, "site_hook") + [
        {"id": "hook-accent", "kind": "circle", "cx": 1090, "cy": 500, "r": 118, "fill": "$surface_alt", "stroke": "$accent", "stroke_width": 4},
        {"id": "hook-accent-text", "kind": "text", "x": 1090, "y": 492, "text": "PROBLEM", "anchor": "middle", "size": 16, "weight": "900", "fill": "$accent"},
        {"id": "hook-accent-sub", "kind": "text", "x": 1090, "y": 525, "text": "made inspectable", "anchor": "middle", "size": 15, "weight": "700", "fill": "$ink"},
        {
            "id": "hook-cards",
            "kind": "cards",
            "x": 76,
            "y": 410,
            "width": 800,
            "height": 205,
            "columns": 2,
            "items": [
                {"title": "Buyer job", "body": "A bounded professional problem, not an abstract feature list."},
                {"title": "Decision context", "body": "Evidence and consequence stay visible from the first frame."},
            ],
        },
    ]


def _service_1(scene: dict[str, Any]) -> list[dict[str, Any]]:
    return _base(scene, "service_1") + [
        {
            "id": "decision-table",
            "kind": "table",
            "x": 76,
            "y": 390,
            "width": 1128,
            "height": 220,
            "headers": ["Input", "Question", "Controlled result"],
            "rows": [
                ["Source", "What is actually known?", "Evidence-bound context"],
                ["Stakeholder", "Who owns the consequence?", "Named decision owner"],
                ["Boundary", "What remains unresolved?", "Explicit gap or escalation"],
            ],
        }
    ]


def _service_2(scene: dict[str, Any]) -> list[dict[str, Any]]:
    """Show synthesis as a constellation, not a disguised timeline."""
    return _base(scene, "service_2") + [
        {"id": "constellation-left", "kind": "panel", "x": 76, "y": 414, "width": 270, "height": 170, "fill": "$surface", "stroke": "$line"},
        {"id": "constellation-left-title", "kind": "text", "x": 104, "y": 458, "text": "SOURCE FRAGMENTS", "size": 18, "weight": "900", "fill": "$ink"},
        {"id": "constellation-left-body", "kind": "text", "x": 104, "y": 500, "text": "Claims, notes and records remain separately inspectable.", "size": 15, "weight": "600", "fill": "$muted", "wrap_chars": 30, "max_lines": 3, "line_gap": 20},
        {"id": "constellation-core", "kind": "circle", "cx": 640, "cy": 500, "r": 92, "fill": "$surface_alt", "stroke": "$accent", "stroke_width": 4},
        {"id": "constellation-core-title", "kind": "text", "x": 640, "y": 493, "text": "SYNTHESIS", "anchor": "middle", "size": 18, "weight": "900", "fill": "$accent"},
        {"id": "constellation-core-body", "kind": "text", "x": 640, "y": 526, "text": "fit + tension", "anchor": "middle", "size": 15, "weight": "700", "fill": "$ink"},
        {"id": "constellation-right", "kind": "panel", "x": 934, "y": 414, "width": 270, "height": 170, "fill": "$surface", "stroke": "$line"},
        {"id": "constellation-right-title", "kind": "text", "x": 962, "y": 458, "text": "REVIEW SIGNAL", "size": 18, "weight": "900", "fill": "$ink"},
        {"id": "constellation-right-body", "kind": "text", "x": 962, "y": 500, "text": "What fits, what conflicts and what still needs judgement.", "size": 15, "weight": "600", "fill": "$muted", "wrap_chars": 30, "max_lines": 3, "line_gap": 20},
        {"id": "constellation-line-a", "kind": "line", "x1": 346, "y1": 500, "x2": 548, "y2": 500, "stroke": "$line", "stroke_width": 2},
        {"id": "constellation-line-b", "kind": "line", "x1": 732, "y1": 500, "x2": 934, "y2": 500, "stroke": "$line", "stroke_width": 2},
    ]


def _service_3(scene: dict[str, Any]) -> list[dict[str, Any]]:
    """Represent handoff as two accountable spaces rather than DIO -> Human arrows."""
    return _base(scene, "service_3") + [
        {"id": "handoff-left", "kind": "panel", "x": 76, "y": 398, "width": 500, "height": 218, "fill": "$surface", "stroke": "$accent", "stroke_width": 2.5},
        {"id": "handoff-left-kicker", "kind": "text", "x": 108, "y": 444, "text": "PREPARED EVIDENCE", "size": 16, "weight": "900", "fill": "$accent"},
        {"id": "handoff-left-body", "kind": "text", "x": 108, "y": 488, "text": "Traceable material, contradictions and a reviewable decision artifact.", "size": 18, "weight": "700", "fill": "$ink", "wrap_chars": 39, "max_lines": 3, "line_gap": 25},
        {"id": "handoff-divider", "kind": "line", "x1": 640, "y1": 398, "x2": 640, "y2": 616, "stroke": "$line", "stroke_width": 2},
        {"id": "handoff-right", "kind": "panel", "x": 704, "y": 398, "width": 500, "height": 218, "fill": "$surface_alt", "stroke": "$warning", "stroke_width": 2.5},
        {"id": "handoff-right-kicker", "kind": "text", "x": 736, "y": 444, "text": "HUMAN JUDGEMENT", "size": 16, "weight": "900", "fill": "$warning"},
        {"id": "handoff-right-body", "kind": "text", "x": 736, "y": 488, "text": "The reviewer decides what is accepted, changed, escalated or released.", "size": 18, "weight": "700", "fill": "$ink", "wrap_chars": 39, "max_lines": 3, "line_gap": 25},
    ]


def _method(scene: dict[str, Any]) -> list[dict[str, Any]]:
    """The single site scene where sequence is actually the semantic point."""
    return _base(scene, "method") + [
        {
            "id": "method-flow",
            "kind": "process",
            "x": 76,
            "y": 430,
            "width": 1128,
            "steps": ["Question", "Source", "Map", "Review", "Handoff"],
            "box_width": 166,
            "box_height": 68,
            "size": 15,
        }
    ]


def _proof(scene: dict[str, Any]) -> list[dict[str, Any]]:
    return _base(scene, "proof") + [
        {
            "id": "proof-table",
            "kind": "table",
            "x": 76,
            "y": 382,
            "width": 1128,
            "height": 235,
            "headers": ["Bound object", "State", "Meaning"],
            "rows": [
                ["Semantic law", "HASH-BOUND", "Meaning is versioned"],
                ["Projection", "HASH-BOUND", "Customer surface is traceable"],
                ["Visual profile", "HASH-BOUND", "Geometry follows Format Core"],
                ["Visual QA", "REQUIRED", "Release remains reviewable"],
            ],
        }
    ]


def _authority(scene: dict[str, Any]) -> list[dict[str, Any]]:
    return _base(scene, "human_authority") + [
        {
            "id": "authority-cards",
            "kind": "cards",
            "x": 76,
            "y": 398,
            "width": 1128,
            "height": 214,
            "columns": 3,
            "items": [
                {"title": "DIO prepares", "body": "Evidence, analysis and customer-ready material."},
                {"title": "Human reviews", "body": "Consequential judgement remains explicit."},
                {"title": "Release stays held", "body": "No visual or model output creates authority."},
            ],
        }
    ]


def _cta(scene: dict[str, Any]) -> list[dict[str, Any]]:
    """A CTA is a focal action, not another three-step journey."""
    return _base(scene, "cta") + [
        {"id": "cta-field", "kind": "panel", "x": 76, "y": 390, "width": 1128, "height": 220, "fill": "$surface_alt", "stroke": "$accent", "stroke_width": 2.5},
        {"id": "cta-kicker", "kind": "text", "x": 116, "y": 442, "text": "ONE BOUNDED NEXT STEP", "size": 16, "weight": "900", "fill": "$accent"},
        {"id": "cta-main", "kind": "text", "x": 116, "y": 504, "text": "Bring one real job.", "size": 38, "weight": "900", "fill": "$ink"},
        {"id": "cta-support", "kind": "text", "x": 116, "y": 548, "text": "Build one inspectable artifact. Review it before release.", "size": 18, "weight": "700", "fill": "$muted"},
        {"id": "cta-marker", "kind": "circle", "cx": 1080, "cy": 500, "r": 62, "fill": "$accent", "stroke": "$accent", "stroke_width": 1},
        {"id": "cta-marker-text", "kind": "text", "x": 1080, "y": 507, "text": "START", "anchor": "middle", "size": 17, "weight": "900", "fill": "$accent_ink"},
    ]


_BUILDERS = {
    "site_hook": _hook,
    "service_1": _service_1,
    "service_2": _service_2,
    "service_3": _service_3,
    "method": _method,
    "proof": _proof,
    "human_authority": _authority,
    "cta": _cta,
}

_VISUAL_FAMILIES = {
    "site_hook": "editorial_problem_field",
    "service_1": "decision_matrix",
    "service_2": "evidence_constellation",
    "service_3": "split_accountable_handoff",
    "method": "bounded_linear_process",
    "proof": "proof_matrix",
    "human_authority": "authority_triptych",
    "cta": "single_focal_action",
}


def _composition(scene: dict[str, Any], role: str, story: dict[str, Any], art: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "composition_id": f"SITE-{_clean(scene.get('scene_id') or role, 80)}",
        "title": _title(scene),
        "profile_id": PROFILE_ID,
        "canvas": {"width": WIDTH, "height": HEIGHT, "background": "$paper"},
        "components": _BUILDERS[role](scene),
        "binding": {
            "surface": "website",
            "role": role,
            "scene_id": scene.get("scene_id"),
            "story_hash": story.get("story_hash"),
            "art_direction_hash": art.get("art_direction_hash"),
            "directed_layout_family": scene.get("layout_family"),
            "visual_family": _VISUAL_FAMILIES[role],
            "visual_subject": scene.get("visual_subject"),
            "selection_law": "role_semantics_first_art_direction_secondary_no_repeated_timeline_default",
        },
    }


def render_site_visual_assets(*, story: dict[str, Any], art: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """Render Site Studio scenes through the shared Format Core visual-composition law.

    Site Studio owns semantic story structure. Format Core owns typography, geometry,
    profile resolution, deterministic SVG bytes and composition fingerprints. External
    visual providers may contribute optional image material only; they never acquire
    text, layout, selection, publication or release authority.

    Visual grammar is role-semantic, not timeline-first. A canonical eight-scene site
    may contain at most one full linear process scene unless the contract is revised.
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
    linear_process_scene_count = 0

    for index, (semantic, directed) in enumerate(zip(scenes, art_scenes), 1):
        role = str(semantic.get("role") or "")
        if role != str(directed.get("role") or ""):
            raise SiteFormatVisualCompositorError(f"scene role mismatch at index {index}: {role!r}")
        merged = {**semantic, **directed}
        composition = _composition(merged, role, story, art)
        process_components = sum(component.get("kind") == "process" for component in composition["components"])
        if process_components:
            linear_process_scene_count += 1
        svg = render_svg(composition, profiles)
        lowered = svg.casefold()
        if "<script" in lowered or "<foreignobject" in lowered:
            raise SiteFormatVisualCompositorError("Format Core emitted forbidden executable/foreign SVG content")
        path = output_dir / f"{index:02d}-{role.replace('_', '-')}.svg"
        path.write_text(svg, encoding="utf-8")
        assets.append(
            {
                "scene_id": semantic.get("scene_id"),
                "role": role,
                "directed_layout_family": directed.get("layout_family"),
                "visual_family": _VISUAL_FAMILIES[role],
                "display_copy": directed.get("display_copy"),
                "visual_subject": directed.get("visual_subject"),
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

    family_counts = dict(sorted(Counter(row["visual_family"] for row in assets).items()))
    receipt = {
        "schema": "dio.format_core.site_visual_compositor_receipt.v2",
        "source": "homs_vector_discipline_promoted_into_format_core",
        "surface": "website",
        "story_hash": story.get("story_hash"),
        "art_direction_hash": art.get("art_direction_hash"),
        "profile_id": PROFILE_ID,
        "profile_hash": content_hash(resolved_profile),
        "scene_count": len(assets),
        "assets": assets,
        "all_scene_roles_bound": tuple(row["role"] for row in assets) == REQUIRED_ROLES,
        "visual_family_counts": family_counts,
        "distinct_visual_family_count": len(family_counts),
        "linear_process_scene_count": linear_process_scene_count,
        "linear_process_scene_budget": PROCESS_SCENE_BUDGET,
        "linear_process_budget_pass": linear_process_scene_count <= PROCESS_SCENE_BUDGET,
        "timeline_default": "REFUSE",
        "selection_law": "semantic_intent_first_role_specific_visual_family",
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
    "PROCESS_SCENE_BUDGET",
    "REQUIRED_ROLES",
    "SiteFormatVisualCompositorError",
    "render_site_visual_assets",
]
