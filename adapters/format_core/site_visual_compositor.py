from __future__ import annotations

import copy
import hashlib
import json
import re
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
        {
            "id": "hook-cards",
            "kind": "cards",
            "x": 76,
            "y": 420,
            "width": 1128,
            "height": 190,
            "columns": 3,
            "items": [
                {"title": "Signal", "body": "A buyer problem expressed as a bounded professional job."},
                {"title": "Method", "body": "Evidence, reasoning and projection remain inspectable."},
                {"title": "Boundary", "body": "Release authority stays with the authorised human."},
            ],
        }
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
    return _base(scene, "service_2") + [
        {
            "id": "synthesis-flow",
            "kind": "process",
            "x": 76,
            "y": 430,
            "width": 1128,
            "steps": ["Sources", "Claims", "Evidence fit", "Synthesis", "Review"],
            "box_width": 166,
            "box_height": 68,
            "size": 15,
        }
    ]


def _service_3(scene: dict[str, Any]) -> list[dict[str, Any]]:
    return _base(scene, "service_3") + [
        {
            "id": "handoff-cards",
            "kind": "cards",
            "x": 76,
            "y": 405,
            "width": 760,
            "height": 205,
            "columns": 2,
            "items": [
                {"title": "Evidence", "body": "Traceable source material, gaps and contradictions."},
                {"title": "Decision brief", "body": "A professional artifact prepared for human judgement."},
            ],
        },
        {
            "id": "handoff-line",
            "kind": "process",
            "x": 876,
            "y": 456,
            "width": 328,
            "steps": ["DIO", "Human"],
            "box_width": 112,
            "box_height": 62,
            "size": 15,
        },
    ]


def _method(scene: dict[str, Any]) -> list[dict[str, Any]]:
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
    return _base(scene, "cta") + [
        {
            "id": "cta-flow",
            "kind": "process",
            "x": 76,
            "y": 418,
            "width": 720,
            "steps": ["Bring one job", "Build proof", "Review"],
            "box_width": 180,
            "box_height": 70,
            "size": 15,
        },
        {
            "id": "cta-card",
            "kind": "cards",
            "x": 840,
            "y": 392,
            "width": 364,
            "height": 180,
            "columns": 1,
            "items": [
                {"title": "Start bounded", "body": "One real workflow. One inspectable artifact. Human release."}
            ],
        },
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
            "layout_family": scene.get("layout_family"),
            "visual_subject": scene.get("visual_subject"),
        },
    }


def render_site_visual_assets(*, story: dict[str, Any], art: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """Render Site Studio scenes through the shared Format Core visual-composition law.

    Site Studio owns semantic story structure. Format Core owns typography, geometry,
    profile resolution, deterministic SVG bytes and composition fingerprints. External
    visual providers may contribute optional image material only; they never acquire
    text, layout, selection, publication or release authority.
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

    for index, (semantic, directed) in enumerate(zip(scenes, art_scenes), 1):
        role = str(semantic.get("role") or "")
        if role != str(directed.get("role") or ""):
            raise SiteFormatVisualCompositorError(f"scene role mismatch at index {index}: {role!r}")
        merged = {**semantic, **directed}
        composition = _composition(merged, role, story, art)
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
                "layout_family": directed.get("layout_family"),
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
                "text_authority": "DIO_FORMAT_CORE",
                "geometry_authority": "DIO_FORMAT_CORE",
                "external_visual_provider_layout_authority": "REFUSE",
            }
        )

    receipt = {
        "schema": "dio.format_core.site_visual_compositor_receipt.v1",
        "source": "homs_vector_discipline_promoted_into_format_core",
        "surface": "website",
        "story_hash": story.get("story_hash"),
        "art_direction_hash": art.get("art_direction_hash"),
        "profile_id": PROFILE_ID,
        "profile_hash": content_hash(resolved_profile),
        "scene_count": len(assets),
        "assets": assets,
        "all_scene_roles_bound": tuple(row["role"] for row in assets) == REQUIRED_ROLES,
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


__all__ = ["SiteFormatVisualCompositorError", "render_site_visual_assets"]
