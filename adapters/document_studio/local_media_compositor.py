from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = ROOT / "config" / "marketing_audience_matrix.json"
FONT_REGULAR = Path("/usr/share/fonts/truetype/lato/Lato-Regular.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/lato/Lato-Bold.ttf")


class LocalMediaCompositorError(RuntimeError):
    pass


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def _cover(image: Image.Image, size: tuple[int, int], *, scale: float = 1.0, anchor: tuple[float, float] = (0.5, 0.5)) -> Image.Image:
    width, height = size
    ratio = max(width / image.width, height / image.height) * max(1.0, scale)
    resized = image.resize((max(width, round(image.width * ratio)), max(height, round(image.height * ratio))), Image.Resampling.LANCZOS)
    excess_x = max(0, resized.width - width)
    excess_y = max(0, resized.height - height)
    left = round(excess_x * min(1.0, max(0.0, anchor[0])))
    top = round(excess_y * min(1.0, max(0.0, anchor[1])))
    return resized.crop((left, top, left + width, top + height))


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = " ".join(str(text or "").split()).split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _headline_font(draw: ImageDraw.ImageDraw, text: str, *, max_width: int, max_lines: int, start: int, minimum: int) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    for size in range(start, minimum - 1, -2):
        chosen = _font(FONT_BOLD, size)
        lines = _wrap(draw, text, chosen, max_width)
        if len(lines) <= max_lines:
            return chosen, lines
    chosen = _font(FONT_BOLD, minimum)
    return chosen, _wrap(draw, text, chosen, max_width)


def _hex_rgb(value: str, fallback: tuple[int, int, int] = (245, 158, 11)) -> tuple[int, int, int]:
    raw = str(value or "").strip().lstrip("#")
    if len(raw) == 6:
        try:
            return tuple(int(raw[index:index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]
        except ValueError:
            pass
    return fallback


def _grain(size: tuple[int, int], seed: str, opacity: int = 18) -> Image.Image:
    width, height = size
    rng = random.Random(int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16], 16))
    small = Image.new("L", (max(1, width // 8), max(1, height // 8)))
    small.putdata([rng.randrange(80, 176) for _ in range(small.width * small.height)])
    noise = small.resize(size, Image.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(radius=0.7))
    rgba = Image.new("RGBA", size, (255, 244, 224, 0))
    rgba.putalpha(noise.point(lambda value: round(value * opacity / 255)))
    return rgba


def _gradient_overlay(size: tuple[int, int], *, left_alpha: int, right_alpha: int, vertical: bool = False) -> Image.Image:
    width, height = size
    overlay = Image.new("RGBA", size)
    px = overlay.load()
    span = height if vertical else width
    for coordinate in range(span):
        mix = coordinate / max(1, span - 1)
        alpha = round(left_alpha + (right_alpha - left_alpha) * mix)
        if vertical:
            for x in range(width):
                px[x, coordinate] = (8, 12, 16, alpha)
        else:
            for y in range(height):
                px[coordinate, y] = (8, 12, 16, alpha)
    return overlay


def resolve_product_audience(family_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if "--" not in family_id:
        raise LocalMediaCompositorError(f"Invalid family_id for local media composition: {family_id}")
    product_id, audience_id = family_id.split("--", 1)
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    product = next((row for row in matrix.get("products") or [] if row.get("id") == product_id), None)
    if not isinstance(product, dict):
        raise LocalMediaCompositorError(f"Product not found in marketing matrix: {product_id}")
    audience = next((row for row in product.get("audiences") or [] if row.get("id") == audience_id), None)
    if not isinstance(audience, dict):
        raise LocalMediaCompositorError(f"Audience not found in marketing matrix: {audience_id}")
    return product, audience


def _brand_header(draw: ImageDraw.ImageDraw, *, product: dict[str, Any], audience: dict[str, Any], accent: tuple[int, int, int], width: int, margin: int, compact: bool = False) -> None:
    product_font = _font(FONT_BOLD, max(22, round(width * (0.021 if compact else 0.025))))
    audience_font = _font(FONT_REGULAR, max(18, round(width * (0.015 if compact else 0.018))))
    draw.text((margin, margin), str(product.get("short_name") or product.get("name") or "").upper(), font=product_font, fill=accent + (255,))
    draw.text((margin, margin + product_font.size + 8), str(audience.get("name") or ""), font=audience_font, fill=(245, 247, 250, 235))


def _draw_headline(draw: ImageDraw.ImageDraw, *, text: str, box: tuple[int, int, int, int], align: str = "left", fill: tuple[int, int, int, int] = (250, 250, 250, 255)) -> None:
    left, top, right, bottom = box
    max_width = max(100, right - left)
    max_lines = 4 if bottom - top > 500 else 3
    start = max(44, round(max_width * 0.095))
    font, lines = _headline_font(draw, text, max_width=max_width, max_lines=max_lines, start=start, minimum=max(32, round(max_width * 0.045)))
    line_h = round(font.size * 1.02)
    total = line_h * len(lines)
    y = top + max(0, (bottom - top - total) // 2)
    for line in lines:
        line_w = draw.textbbox((0, 0), line, font=font)[2]
        x = left if align == "left" else (right - line_w if align == "right" else left + max(0, (max_width - line_w) // 2))
        draw.text((x + 2, y + 3), line, font=font, fill=(0, 0, 0, 130))
        draw.text((x, y), line, font=font, fill=fill)
        y += line_h


def _role_mark(draw: ImageDraw.ImageDraw, *, role: str, accent: tuple[int, int, int], x: int, y: int, width: int) -> None:
    text = " ".join(str(role or "scene").replace("_", " ").split()).upper()
    font = _font(FONT_BOLD, max(15, round(width * 0.013)))
    text_w = draw.textbbox((0, 0), text, font=font)[2]
    draw.rounded_rectangle((x, y, x + text_w + 28, y + font.size + 18), radius=4, fill=accent + (236,))
    draw.text((x + 14, y + 8), text, font=font, fill=(10, 13, 17, 255))


def render_art_directed_scene(
    *,
    source: Image.Image,
    size: tuple[int, int],
    product: dict[str, Any],
    audience: dict[str, Any],
    scene: dict[str, Any],
    art_language: dict[str, Any],
    output: Path,
    scene_index: int,
    art_direction_hash: str,
) -> dict[str, Any]:
    width, height = size
    vertical = height > width
    layout = str(scene.get("layout_family") or "full_bleed_hook")
    display = str(scene.get("display_copy") or "").strip()
    role = str(scene.get("role") or "scene")
    accent = _hex_rgb(str(product.get("accent") or ""))
    seed = f"{art_direction_hash}:{scene.get('scene_id')}:{layout}:{scene_index}"
    anchors = [(0.28, 0.5), (0.72, 0.5), (0.5, 0.32), (0.5, 0.72), (0.35, 0.35), (0.68, 0.42)]
    anchor = anchors[(scene_index - 1) % len(anchors)]
    zoom = 1.02 + (scene_index % 4) * 0.035
    base = _cover(source.convert("RGB"), size, scale=zoom, anchor=anchor)
    saturation = 1.03 if "warm" in str(art_language).casefold() else 0.88
    base = ImageEnhance.Color(base).enhance(saturation)
    base = ImageEnhance.Contrast(base).enhance(1.04)
    canvas = base.convert("RGBA")
    margin = max(36, round(width * 0.05))

    if any(token in layout for token in ("collage", "observation")):
        blurred = base.filter(ImageFilter.GaussianBlur(radius=max(10, width // 70))).convert("RGBA")
        blurred = Image.alpha_composite(blurred, Image.new("RGBA", size, (7, 11, 15, 145)))
        canvas = blurred
        panel_w = round(width * (0.72 if vertical else 0.58))
        panel_h = round(height * (0.57 if vertical else 0.72))
        crop = _cover(source.convert("RGB"), (panel_w, panel_h), scale=1.12, anchor=(0.62, 0.42)).convert("RGBA")
        panel_x = width - panel_w - margin if scene_index % 2 else margin
        panel_y = round(height * 0.22)
        shadow = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle((panel_x + 14, panel_y + 18, panel_x + panel_w + 14, panel_y + panel_h + 18), radius=10, fill=(0, 0, 0, 115))
        canvas = Image.alpha_composite(canvas, shadow)
        canvas.alpha_composite(crop, (panel_x, panel_y))
        draw = ImageDraw.Draw(canvas)
        _brand_header(draw, product=product, audience=audience, accent=accent, width=width, margin=margin, compact=vertical)
        text_top = round(height * 0.12) if vertical else round(height * 0.38)
        text_bottom = panel_y - 18 if vertical else height - margin
        text_right = width - margin if vertical else round(width * 0.42)
        _draw_headline(draw, text=display, box=(margin, text_top, text_right, text_bottom))
        _role_mark(draw, role=role, accent=accent, x=margin, y=min(height - margin - 54, text_bottom - 58), width=width)

    elif any(token in layout for token in ("macro", "proof", "evidence", "result")):
        canvas = _cover(source.convert("RGB"), size, scale=1.34, anchor=anchor).convert("RGBA")
        canvas = Image.alpha_composite(canvas, _gradient_overlay(size, left_alpha=185, right_alpha=30, vertical=False))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 0, width, max(8, height // 90)), fill=accent + (255,))
        _brand_header(draw, product=product, audience=audience, accent=accent, width=width, margin=margin, compact=vertical)
        text_box = (margin, round(height * 0.42), round(width * (0.72 if vertical else 0.58)), round(height * 0.82))
        _draw_headline(draw, text=display, box=text_box)
        _role_mark(draw, role=role, accent=accent, x=margin, y=round(height * 0.82), width=width)
        # Evidence-mark gesture, intentionally graphic rather than a dashboard card.
        line_y = round(height * 0.40)
        draw.line((margin, line_y, min(width - margin, margin + round(width * 0.28)), line_y), fill=accent + (230,), width=max(3, width // 320))

    elif any(token in layout for token in ("portrait", "authority", "handoff")):
        matte = Image.new("RGBA", size, (15, 19, 22, 255))
        image_w = round(width * (0.58 if vertical else 0.55))
        image_h = height
        panel = _cover(source.convert("RGB"), (image_w, image_h), scale=1.08, anchor=(0.42, 0.45)).convert("RGBA")
        if scene_index % 2:
            matte.alpha_composite(panel, (0, 0))
            text_left, text_right = image_w + margin, width - margin
        else:
            matte.alpha_composite(panel, (width - image_w, 0))
            text_left, text_right = margin, width - image_w - margin
        canvas = matte
        draw = ImageDraw.Draw(canvas)
        _brand_header(draw, product=product, audience=audience, accent=accent, width=width, margin=margin, compact=vertical)
        _draw_headline(draw, text=display, box=(text_left, round(height * 0.30), text_right, round(height * 0.76)))
        _role_mark(draw, role=role, accent=accent, x=text_left, y=round(height * 0.78), width=width)

    elif any(token in layout for token in ("resolve", "release", "cta")):
        canvas = Image.alpha_composite(base.convert("RGBA"), Image.new("RGBA", size, (5, 9, 12, 182)))
        canvas = Image.alpha_composite(canvas, _grain(size, seed, opacity=20))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 0, width, max(10, height // 70)), fill=accent + (255,))
        _brand_header(draw, product=product, audience=audience, accent=accent, width=width, margin=margin, compact=vertical)
        _draw_headline(draw, text=display, box=(margin, round(height * 0.30), width - margin, round(height * 0.70)), align="center")
        _role_mark(draw, role=role, accent=accent, x=round(width * 0.5) - 80, y=round(height * 0.73), width=width)

    elif any(token in layout for token in ("process", "workflow", "method", "route", "trace")):
        canvas = Image.alpha_composite(base.convert("RGBA"), _gradient_overlay(size, left_alpha=205, right_alpha=70, vertical=False))
        draw = ImageDraw.Draw(canvas)
        _brand_header(draw, product=product, audience=audience, accent=accent, width=width, margin=margin, compact=vertical)
        _draw_headline(draw, text=display, box=(margin, round(height * 0.31), round(width * 0.76), round(height * 0.67)))
        y = round(height * 0.73)
        node_count = 3
        start_x = margin
        end_x = min(width - margin, start_x + round(width * (0.52 if vertical else 0.38)))
        draw.line((start_x, y, end_x, y), fill=(245, 247, 250, 125), width=max(2, width // 500))
        for step in range(node_count):
            x = round(start_x + (end_x - start_x) * step / max(1, node_count - 1))
            radius = max(7, width // 140)
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=accent + (245,))
        _role_mark(draw, role=role, accent=accent, x=margin, y=min(height - margin - 52, y + 28), width=width)

    else:
        # Full-bleed hook / human / contextual frame.
        canvas = Image.alpha_composite(base.convert("RGBA"), _gradient_overlay(size, left_alpha=198, right_alpha=28, vertical=False))
        canvas = Image.alpha_composite(canvas, _grain(size, seed, opacity=14))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 0, width, max(8, height // 90)), fill=accent + (255,))
        _brand_header(draw, product=product, audience=audience, accent=accent, width=width, margin=margin, compact=vertical)
        _draw_headline(draw, text=display, box=(margin, round(height * 0.34), round(width * (0.78 if vertical else 0.67)), round(height * 0.73)))
        _role_mark(draw, role=role, accent=accent, x=margin, y=round(height * 0.75), width=width)

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output, quality=94, subsampling=0)
    return {
        "schema": "dio.document_studio.local_scene_frame.v1",
        "scene_id": scene.get("scene_id"),
        "layout_family": layout,
        "display_copy": display,
        "role": role,
        "path": str(output.resolve()),
        "width": width,
        "height": height,
        "art_direction_hash": art_direction_hash,
        "source": "document_studio_local_compositor",
    }


def render_story_frames(*, story: dict[str, Any], art_direction: dict[str, Any], directory: Path) -> dict[str, Any]:
    family_id = str(story.get("family_id") or "")
    product, audience = resolve_product_audience(family_id)
    source_path = ROOT / str(product.get("source_image") or "")
    if not source_path.is_file():
        raise LocalMediaCompositorError(f"Configured source image does not exist: {source_path}")
    source = Image.open(source_path)
    surface = str(story.get("surface") or "campaign_story")
    size = (1080, 1920) if surface == "vertical_short" else (1280, 720)
    art_scenes = list(art_direction.get("scenes") or [])
    story_scenes = list(story.get("scenes") or [])
    if len(art_scenes) != len(story_scenes) or not art_scenes:
        raise LocalMediaCompositorError("Document Studio art direction must cover every story scene.")
    frames: list[dict[str, Any]] = []
    assets = directory / "assets"
    for index, (story_scene, art_scene) in enumerate(zip(story_scenes, art_scenes, strict=True), 1):
        role = str(story_scene.get("role") or f"scene_{index:02d}")
        slug = "-".join(part for part in "".join(ch.lower() if ch.isalnum() else "-" for ch in role).split("-") if part)
        output = assets / f"{surface}_{index:02d}_{slug}.jpg"
        frame_scene = {**story_scene, **art_scene, "role": role}
        frames.append(render_art_directed_scene(
            source=source,
            size=size,
            product=product,
            audience=audience,
            scene=frame_scene,
            art_language=dict(art_direction.get("art_language") or {}),
            output=output,
            scene_index=index,
            art_direction_hash=str(art_direction.get("art_direction_hash") or ""),
        ))
    receipt = {
        "schema": "dio.document_studio.local_story_composition.v1",
        "state": "ready",
        "family_id": family_id,
        "surface": surface,
        "art_direction_hash": art_direction.get("art_direction_hash"),
        "frame_count": len(frames),
        "frames": frames,
        "governance": {
            "semantic_authority_created": False,
            "release_authority_created": False,
            "human_visual_release": "NEEDS_YOU",
            "gamma_required": False,
        },
    }
    receipt_path = directory / f"DOCUMENT_STUDIO_LOCAL_COMPOSITION_{surface.upper()}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt["receipt"] = str(receipt_path.resolve())
    return receipt
