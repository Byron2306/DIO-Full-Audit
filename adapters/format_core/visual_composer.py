from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = ROOT / "config" / "visual_profiles.json"
SCHEMA = "dio.visual_composition.v1"
RECEIPT_SCHEMA = "dio.format_core.visual_composition_receipt.v1"
SUPPORTED_COMPONENTS = {
    "rect",
    "line",
    "circle",
    "path",
    "text",
    "badge",
    "panel",
    "cards",
    "process",
    "table",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def content_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def text_hash(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "visual"


def _wrap(value: str, width: int, max_lines: int) -> list[str]:
    words = re.sub(r"\s+", " ", str(value or "")).strip().split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and len(candidate) > width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(" ".join(current))
    return lines


def load_visual_profiles(path: Path | None = None) -> dict[str, Any]:
    target = path or PROFILE_PATH
    return json.loads(target.read_text(encoding="utf-8"))


def resolve_profile(profile_id: str, profiles: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = profiles or load_visual_profiles()
    profile = (payload.get("profiles") or {}).get(profile_id)
    if not profile:
        raise ValueError(f"Unknown visual profile: {profile_id}")
    return json.loads(json.dumps(profile))


def validate_composition(composition: dict[str, Any], profiles: dict[str, Any] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if composition.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    for key in ("composition_id", "title", "profile_id"):
        if not str(composition.get(key) or "").strip():
            errors.append(f"{key} is required")

    canvas = composition.get("canvas") or {}
    width = int(canvas.get("width") or 0)
    height = int(canvas.get("height") or 0)
    if width < 320 or width > 7680:
        errors.append("canvas.width must be between 320 and 7680")
    if height < 240 or height > 4320:
        errors.append("canvas.height must be between 240 and 4320")

    try:
        resolve_profile(str(composition.get("profile_id") or ""), profiles)
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    components = composition.get("components") or []
    if not components:
        errors.append("at least one component is required")

    seen: set[str] = set()
    for index, component in enumerate(components, start=1):
        component_id = str(component.get("id") or "")
        kind = str(component.get("kind") or "")
        if not component_id:
            errors.append(f"component {index} requires id")
        elif component_id in seen:
            errors.append(f"duplicate component id: {component_id}")
        seen.add(component_id)
        if kind not in SUPPORTED_COMPONENTS:
            errors.append(f"{component_id or index} has unsupported kind {kind or '(missing)'}")
        for axis in ("x", "y"):
            if axis in component and not isinstance(component[axis], (int, float)):
                errors.append(f"{component_id or index}.{axis} must be numeric")
        if kind in {"rect", "panel", "cards", "table"}:
            for dim in ("width", "height"):
                if dim in component and float(component[dim]) < 0:
                    errors.append(f"{component_id or index}.{dim} cannot be negative")
        if kind == "text" and not str(component.get("text") or "").strip():
            errors.append(f"{component_id or index} requires text")
        if kind == "table":
            headers = component.get("headers") or []
            rows = component.get("rows") or []
            if not headers or not rows:
                errors.append(f"{component_id or index} requires headers and rows")
            if headers and any(len(row) != len(headers) for row in rows):
                errors.append(f"{component_id or index} row width does not match headers")
        if kind == "process" and len(component.get("steps") or []) < 2:
            errors.append(f"{component_id or index} requires at least two steps")
        if kind == "cards" and not component.get("items"):
            errors.append(f"{component_id or index} requires items")

    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "component_count": len(components),
    }


def _color(value: str | None, profile: dict[str, Any], fallback: str) -> str:
    if not value:
        value = fallback
    palette = profile.get("palette") or {}
    if str(value).startswith("$"):
        token = str(value)[1:]
        return str(palette.get(token) or fallback)
    return str(value)


def _font(profile: dict[str, Any]) -> str:
    return str((profile.get("typography") or {}).get("font_family") or "Arial, sans-serif")


def _text_svg(component: dict[str, Any], profile: dict[str, Any]) -> str:
    typography = profile.get("typography") or {}
    x = float(component.get("x") or 0)
    y = float(component.get("y") or 0)
    size = int(component.get("size") or typography.get("body_size") or 20)
    weight = str(component.get("weight") or "500")
    fill = _color(component.get("fill"), profile, "$ink")
    anchor = str(component.get("anchor") or "start")
    width_chars = int(component.get("wrap_chars") or 0)
    max_lines = int(component.get("max_lines") or 1)
    line_gap = int(component.get("line_gap") or round(size * 1.25))
    text = str(component.get("text") or "")
    lines = _wrap(text, width_chars, max_lines) if width_chars else [text]
    spans = []
    for index, line in enumerate(lines):
        dy = 0 if index == 0 else line_gap
        spans.append(f'<tspan x="{x:g}" dy="{dy:g}">{_esc(line)}</tspan>')
    return (
        f'<text x="{x:g}" y="{y:g}" text-anchor="{_esc(anchor)}" '
        f'font-family="{_esc(_font(profile))}" font-size="{size}" font-weight="{_esc(weight)}" '
        f'fill="{_esc(fill)}">{"".join(spans)}</text>'
    )


def _panel_svg(component: dict[str, Any], profile: dict[str, Any]) -> str:
    x = float(component.get("x") or 0)
    y = float(component.get("y") or 0)
    width = float(component.get("width") or 0)
    height = float(component.get("height") or 0)
    radius = float(component.get("radius") or (profile.get("geometry") or {}).get("radius") or 0)
    fill = _color(component.get("fill"), profile, "$surface")
    stroke = _color(component.get("stroke"), profile, "$line")
    stroke_width = float(component.get("stroke_width") or 1.5)
    opacity = float(component.get("opacity") if component.get("opacity") is not None else 1.0)
    return (
        f'<rect x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" rx="{radius:g}" '
        f'fill="{_esc(fill)}" stroke="{_esc(stroke)}" stroke-width="{stroke_width:g}" opacity="{opacity:g}"/>'
    )


def _badge_svg(component: dict[str, Any], profile: dict[str, Any]) -> str:
    x = float(component.get("x") or 0)
    y = float(component.get("y") or 0)
    width = float(component.get("width") or 180)
    height = float(component.get("height") or 38)
    radius = float(component.get("radius") or height / 2)
    fill = _color(component.get("fill"), profile, "$accent")
    ink = _color(component.get("text_fill"), profile, "$accent_ink")
    text = str(component.get("text") or "")
    size = int(component.get("size") or 14)
    return "\n".join([
        f'<rect x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" rx="{radius:g}" fill="{_esc(fill)}"/>',
        f'<text x="{x + width / 2:g}" y="{y + height / 2 + size * 0.34:g}" text-anchor="middle" font-family="{_esc(_font(profile))}" font-size="{size}" font-weight="800" fill="{_esc(ink)}">{_esc(text)}</text>',
    ])


def _cards_svg(component: dict[str, Any], profile: dict[str, Any]) -> str:
    items = list(component.get("items") or [])
    x = float(component.get("x") or 0)
    y = float(component.get("y") or 0)
    width = float(component.get("width") or 0)
    height = float(component.get("height") or 0)
    columns = max(1, int(component.get("columns") or min(3, len(items) or 1)))
    gap = float(component.get("gap") or 18)
    rows = max(1, (len(items) + columns - 1) // columns)
    card_w = (width - gap * (columns - 1)) / columns
    card_h = (height - gap * (rows - 1)) / rows
    parts: list[str] = []
    for index, item in enumerate(items):
        row = index // columns
        col = index % columns
        cx = x + col * (card_w + gap)
        cy = y + row * (card_h + gap)
        card = {
            "x": cx,
            "y": cy,
            "width": card_w,
            "height": card_h,
            "fill": item.get("fill") or component.get("fill") or "$surface",
            "stroke": item.get("stroke") or component.get("stroke") or "$line",
            "radius": item.get("radius") or component.get("radius"),
        }
        parts.append(_panel_svg(card, profile))
        accent = _color(item.get("accent"), profile, "$accent")
        parts.append(f'<rect x="{cx:g}" y="{cy:g}" width="6" height="{card_h:g}" rx="3" fill="{_esc(accent)}"/>')
        title = str(item.get("title") or "")
        body = str(item.get("body") or "")
        if title:
            parts.append(_text_svg({
                "x": cx + 22,
                "y": cy + 34,
                "text": title,
                "size": item.get("title_size") or 20,
                "weight": "800",
                "fill": item.get("title_fill") or "$ink",
                "wrap_chars": item.get("title_wrap_chars") or 28,
                "max_lines": 2,
                "line_gap": 24,
            }, profile))
        if body:
            parts.append(_text_svg({
                "x": cx + 22,
                "y": cy + 82,
                "text": body,
                "size": item.get("body_size") or 15,
                "weight": "500",
                "fill": item.get("body_fill") or "$muted",
                "wrap_chars": item.get("body_wrap_chars") or 38,
                "max_lines": item.get("body_max_lines") or 4,
                "line_gap": 20,
            }, profile))
    return "\n".join(parts)


def _process_svg(component: dict[str, Any], profile: dict[str, Any]) -> str:
    steps = [str(step) for step in component.get("steps") or []]
    x = float(component.get("x") or 0)
    y = float(component.get("y") or 0)
    width = float(component.get("width") or 0)
    box_w = float(component.get("box_width") or 150)
    box_h = float(component.get("box_height") or 62)
    gap = (width - box_w * len(steps)) / max(1, len(steps) - 1) if len(steps) > 1 else 0
    stroke = _color(component.get("stroke"), profile, "$ink")
    fill = _color(component.get("fill"), profile, "$surface")
    text_fill = _color(component.get("text_fill"), profile, "$ink")
    parts = [
        '<defs><marker id="dio-visual-arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="%s"/></marker></defs>' % _esc(stroke)
    ]
    for index, step in enumerate(steps):
        sx = x + index * (box_w + gap)
        parts.append(f'<rect x="{sx:g}" y="{y:g}" width="{box_w:g}" height="{box_h:g}" rx="10" fill="{_esc(fill)}" stroke="{_esc(stroke)}" stroke-width="2"/>')
        parts.append(_text_svg({
            "x": sx + box_w / 2,
            "y": y + box_h / 2 + 6,
            "text": step,
            "size": component.get("size") or 16,
            "weight": "800",
            "fill": text_fill,
            "anchor": "middle",
            "wrap_chars": component.get("wrap_chars") or 18,
            "max_lines": 2,
            "line_gap": 18,
        }, profile))
        if index < len(steps) - 1:
            x1 = sx + box_w + 8
            x2 = x + (index + 1) * (box_w + gap) - 10
            yy = y + box_h / 2
            parts.append(f'<path d="M{x1:g} {yy:g} L{x2:g} {yy:g}" stroke="{_esc(stroke)}" stroke-width="3" marker-end="url(#dio-visual-arrow)"/>')
    return "\n".join(parts)


def _table_svg(component: dict[str, Any], profile: dict[str, Any]) -> str:
    headers = [str(value) for value in component.get("headers") or []]
    rows = [[str(value) for value in row] for row in component.get("rows") or []]
    x = float(component.get("x") or 0)
    y = float(component.get("y") or 0)
    width = float(component.get("width") or 0)
    height = float(component.get("height") or 0)
    columns = len(headers)
    row_count = len(rows) + 1
    col_w = width / max(1, columns)
    row_h = height / max(1, row_count)
    line = _color(component.get("stroke"), profile, "$line")
    header_fill = _color(component.get("header_fill"), profile, "$surface_alt")
    cell_fill = _color(component.get("fill"), profile, "$surface")
    ink = _color(component.get("text_fill"), profile, "$ink")
    muted = _color(component.get("muted_fill"), profile, "$muted")
    parts: list[str] = []
    for col, header in enumerate(headers):
        cx = x + col * col_w
        parts.append(f'<rect x="{cx:g}" y="{y:g}" width="{col_w:g}" height="{row_h:g}" fill="{_esc(header_fill)}" stroke="{_esc(line)}"/>')
        parts.append(_text_svg({"x": cx + 12, "y": y + row_h / 2 + 5, "text": header, "size": 14, "weight": "800", "fill": ink, "wrap_chars": 22, "max_lines": 2}, profile))
    for row_index, row in enumerate(rows, start=1):
        cy = y + row_index * row_h
        for col, value in enumerate(row):
            cx = x + col * col_w
            parts.append(f'<rect x="{cx:g}" y="{cy:g}" width="{col_w:g}" height="{row_h:g}" fill="{_esc(cell_fill)}" stroke="{_esc(line)}"/>')
            parts.append(_text_svg({"x": cx + 12, "y": cy + row_h / 2 + 5, "text": value, "size": 13, "weight": "500", "fill": muted, "wrap_chars": 24, "max_lines": 2}, profile))
    return "\n".join(parts)


def _primitive_svg(component: dict[str, Any], profile: dict[str, Any]) -> str:
    kind = str(component["kind"])
    if kind == "text":
        return _text_svg(component, profile)
    if kind == "badge":
        return _badge_svg(component, profile)
    if kind == "panel":
        return _panel_svg(component, profile)
    if kind == "cards":
        return _cards_svg(component, profile)
    if kind == "process":
        return _process_svg(component, profile)
    if kind == "table":
        return _table_svg(component, profile)
    if kind == "rect":
        return _panel_svg(component, profile)
    if kind == "line":
        stroke = _color(component.get("stroke"), profile, "$line")
        return f'<line x1="{float(component.get("x1") or 0):g}" y1="{float(component.get("y1") or 0):g}" x2="{float(component.get("x2") or 0):g}" y2="{float(component.get("y2") or 0):g}" stroke="{_esc(stroke)}" stroke-width="{float(component.get("stroke_width") or 2):g}"/>'
    if kind == "circle":
        fill = _color(component.get("fill"), profile, "$surface")
        stroke = _color(component.get("stroke"), profile, "$line")
        return f'<circle cx="{float(component.get("cx") or 0):g}" cy="{float(component.get("cy") or 0):g}" r="{float(component.get("r") or 0):g}" fill="{_esc(fill)}" stroke="{_esc(stroke)}" stroke-width="{float(component.get("stroke_width") or 1.5):g}"/>'
    if kind == "path":
        fill = _color(component.get("fill"), profile, "none")
        stroke = _color(component.get("stroke"), profile, "$ink")
        return f'<path d="{_esc(component.get("d") or "")}" fill="{_esc(fill)}" stroke="{_esc(stroke)}" stroke-width="{float(component.get("stroke_width") or 2):g}"/>'
    raise ValueError(f"Unsupported component kind: {kind}")


def render_svg(composition: dict[str, Any], profiles: dict[str, Any] | None = None) -> str:
    validation = validate_composition(composition, profiles)
    if not validation["passed"]:
        raise ValueError("Invalid visual composition: " + "; ".join(validation["errors"]))

    profile = resolve_profile(str(composition["profile_id"]), profiles)
    canvas = composition["canvas"]
    width = int(canvas["width"])
    height = int(canvas["height"])
    background = _color(canvas.get("background"), profile, "$paper")
    components = "\n  ".join(_primitive_svg(component, profile) for component in composition["components"])
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
        f'  <rect width="{width}" height="{height}" fill="{_esc(background)}"/>\n'
        f'  {components}\n'
        '</svg>\n'
    )


def render_png(svg_path: Path, png_path: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(svg_path), "-frames:v", "1", "-pix_fmt", "rgb24", str(png_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.returncode == 0 and png_path.exists()


def write_visual_bundle(
    composition: dict[str, Any],
    out_dir: Path,
    *,
    basename: str | None = None,
    profiles: dict[str, Any] | None = None,
    rasterize: bool = True,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    validation = validate_composition(composition, profiles)
    if not validation["passed"]:
        raise ValueError("Invalid visual composition: " + "; ".join(validation["errors"]))
    profile = resolve_profile(str(composition["profile_id"]), profiles)
    svg = render_svg(composition, profiles)
    stem = basename or _slug(str(composition.get("composition_id") or composition.get("title") or "visual"))
    svg_path = out_dir / f"{stem}.svg"
    png_path = out_dir / f"{stem}.png"
    receipt_path = out_dir / f"{stem}.receipt.json"
    svg_path.write_text(svg, encoding="utf-8")
    png_rendered = render_png(svg_path, png_path) if rasterize else False

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "state": "PASS",
        "composition_id": composition["composition_id"],
        "composition_hash": content_hash(composition),
        "profile_id": composition["profile_id"],
        "profile_hash": content_hash(profile),
        "svg": str(svg_path),
        "svg_hash": text_hash(svg),
        "png": str(png_path) if png_rendered else None,
        "png_rendered": png_rendered,
        "component_count": validation["component_count"],
        "authority_created": False,
        "automatic_publication": "REFUSE",
    }
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    receipt["receipt"] = str(receipt_path)
    return receipt
