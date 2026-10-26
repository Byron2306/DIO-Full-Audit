from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from adapters.format_core.site_native_illustration import site_semantic_visual_to_composition
from adapters.format_core.visual_composer import SCHEMA as COMPOSITION_SCHEMA, content_hash, render_svg
from adapters.format_core.visual_material_registry import FILE_MATERIAL_KINDS, material_data_uri


MIXED_MEDIA_SCHEMA = "dio.format_core.site_mixed_media.v1"


class SiteMixedMediaError(RuntimeError):
    pass


def _clean(value: Any, limit: int = 320) -> str:
    return " ".join(str(value or "").split())[:limit].rstrip()


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _overlay_composition(
    spec: dict[str, Any],
    material: dict[str, Any],
    *,
    profile_id: str,
    width: int,
    height: int,
    binding: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    kind = str(material.get("material_kind") or "")
    visual_kind = str(spec.get("visual_kind") or "")
    composition_meta = dict(material.get("composition") or {})
    negative_space = str(composition_meta.get("negative_space") or "left")

    image_box = {"x": 430, "y": 0, "width": width - 430, "height": height}
    panel_box = {"x": 0, "y": 0, "width": 520, "height": height}
    if negative_space == "right":
        image_box = {"x": 0, "y": 0, "width": width - 430, "height": height}
        panel_box = {"x": width - 520, "y": 0, "width": 520, "height": height}
    elif negative_space in {"balanced", "none"} or kind == "artifact_render":
        image_box = {"x": 92, "y": 110, "width": width - 184, "height": height - 190}
        panel_box = {"x": 0, "y": 0, "width": width, "height": 116}

    title_x = panel_box["x"] + 54
    title_y = 112 if panel_box["height"] > 200 else 56
    title_width = 28 if panel_box["width"] < 700 else 52
    components: list[dict[str, Any]] = [
        {
            "id": "material-panel",
            "kind": "panel",
            **panel_box,
            "fill": "$paper",
            "stroke": "$paper",
            "stroke_width": 0,
            "radius": 0,
            "opacity": 0.96,
        },
        {
            "id": "material-kicker",
            "kind": "text",
            "x": title_x,
            "y": title_y,
            "text": visual_kind.replace("_", " ").upper(),
            "size": 13,
            "weight": "900",
            "fill": "$accent",
            "wrap_chars": title_width,
            "max_lines": 1,
        },
        {
            "id": "material-title",
            "kind": "text",
            "x": title_x,
            "y": title_y + 58,
            "text": _clean(spec.get("title") or visual_kind, 140),
            "size": 34 if panel_box["height"] > 200 else 27,
            "weight": "900",
            "fill": "$ink",
            "wrap_chars": title_width,
            "max_lines": 3 if panel_box["height"] > 200 else 2,
            "line_gap": 40,
        },
    ]
    if panel_box["height"] > 200:
        components.extend(
            [
                {
                    "id": "material-summary",
                    "kind": "text",
                    "x": title_x,
                    "y": 300,
                    "text": _clean(spec.get("summary") or spec.get("semantic_intent"), 220),
                    "size": 17,
                    "weight": "600",
                    "fill": "$muted",
                    "wrap_chars": 38,
                    "max_lines": 5,
                    "line_gap": 24,
                },
                {
                    "id": "material-authority-rule",
                    "kind": "line",
                    "x1": title_x,
                    "y1": 568,
                    "x2": title_x + 300,
                    "y2": 568,
                    "stroke": "$warning",
                    "stroke_width": 3,
                },
                {
                    "id": "material-authority",
                    "kind": "text",
                    "x": title_x,
                    "y": 606,
                    "text": "Material supports the scene. DIO meaning and release authority remain governed.",
                    "size": 13,
                    "weight": "800",
                    "fill": "$muted",
                    "wrap_chars": 42,
                    "max_lines": 3,
                    "line_gap": 18,
                },
            ]
        )
    else:
        components.append(
            {
                "id": "artifact-border",
                "kind": "rect",
                "x": image_box["x"] - 8,
                "y": image_box["y"] - 8,
                "width": image_box["width"] + 16,
                "height": image_box["height"] + 16,
                "fill": "none",
                "stroke": "$line",
                "stroke_width": 2,
                "radius": 3,
            }
        )

    composition = {
        "schema": COMPOSITION_SCHEMA,
        "composition_id": str(spec.get("visual_id") or f"SITE-MATERIAL-{visual_kind}"),
        "title": _clean(spec.get("title") or visual_kind, 120),
        "profile_id": profile_id,
        "canvas": {"width": width, "height": height, "background": "$paper"},
        "components": components,
        "binding": {
            "mixed_media_schema": MIXED_MEDIA_SCHEMA,
            "semantic_visual_hash": spec.get("semantic_visual_hash") or content_hash(spec),
            "visual_kind": visual_kind,
            "selected_material_id": material.get("material_id"),
            "selected_material_kind": kind,
            "image_box": image_box,
            "role_selects_geometry": False,
            "material_layout_authority": "REFUSE",
            **dict(binding or {}),
        },
    }
    return composition, image_box


def _inject_image(svg: str, *, data_uri: str, image_box: dict[str, Any], opacity: float = 1.0) -> str:
    if not data_uri.startswith(("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/webp;base64,")):
        raise SiteMixedMediaError("mixed-media image must be a safe embedded PNG/JPEG/WebP data URI")
    image = (
        f'<image x="{float(image_box["x"]):g}" y="{float(image_box["y"]):g}" '
        f'width="{float(image_box["width"]):g}" height="{float(image_box["height"]):g}" '
        f'preserveAspectRatio="xMidYMid slice" opacity="{float(opacity):g}" href="{_esc(data_uri)}"/>'
    )
    marker = "\n  <rect width="
    position = svg.find(marker)
    if position < 0:
        raise SiteMixedMediaError("Format Core SVG background marker was not found")
    background_end = svg.find("/>\n", position)
    if background_end < 0:
        raise SiteMixedMediaError("Format Core SVG background could not be isolated")
    insert_at = background_end + 3
    return svg[:insert_at] + "  " + image + "\n" + svg[insert_at:]


def render_site_visual_with_material(
    *,
    semantic_visual: dict[str, Any],
    material: dict[str, Any],
    resolution: dict[str, Any],
    profile_id: str,
    profiles: dict[str, Any],
    material_root: Path,
    width: int = 1280,
    height: int = 720,
    binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    material_kind = str(material.get("material_kind") or "")
    common_binding = {
        "material_resolution_hash": resolution.get("resolution_hash"),
        "material_fallback_used": resolution.get("fallback_used"),
        **dict(binding or {}),
    }

    if material_kind == "native_renderer":
        composition = site_semantic_visual_to_composition(
            semantic_visual,
            profile_id=profile_id,
            width=width,
            height=height,
            binding={
                **common_binding,
                "selected_material_id": material.get("material_id"),
                "selected_material_kind": material_kind,
                "mixed_media": False,
            },
        )
        svg = render_svg(composition, profiles)
        return {
            "svg": svg,
            "composition": composition,
            "mixed_media": False,
            "material_kind": material_kind,
            "material_id": material.get("material_id"),
        }

    if material_kind not in FILE_MATERIAL_KINDS:
        raise SiteMixedMediaError(f"Unsupported mixed-media material kind: {material_kind or '(missing)'}")

    composition, image_box = _overlay_composition(
        semantic_visual,
        material,
        profile_id=profile_id,
        width=width,
        height=height,
        binding={**common_binding, "mixed_media": True},
    )
    base_svg = render_svg(composition, profiles)
    data_uri = material_data_uri(material, root=material_root)
    svg = _inject_image(base_svg, data_uri=data_uri, image_box=image_box)
    return {
        "svg": svg,
        "composition": composition,
        "mixed_media": True,
        "material_kind": material_kind,
        "material_id": material.get("material_id"),
    }


__all__ = [
    "MIXED_MEDIA_SCHEMA",
    "SiteMixedMediaError",
    "render_site_visual_with_material",
]
