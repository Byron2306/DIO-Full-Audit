#!/usr/bin/env python3
"""Generate grand ARDA wallpapers from the website source layers."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageEnhance, ImageFilter


REPO_ROOT = Path(__file__).resolve().parents[3]


def _fit_cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    src_w, src_h = image.size
    dst_w, dst_h = size
    src_ratio = src_w / src_h
    dst_ratio = dst_w / dst_h
    if src_ratio > dst_ratio:
        scale = dst_h / src_h
    else:
        scale = dst_w / src_w
    new_size = (max(1, int(src_w * scale)), max(1, int(src_h * scale)))
    resized = image.resize(new_size, Image.Resampling.LANCZOS)
    left = (resized.width - dst_w) // 2
    top = (resized.height - dst_h) // 2
    return resized.crop((left, top, left + dst_w, top + dst_h))


def _alpha_scale(image: Image.Image, factor: float) -> Image.Image:
    image = image.convert("RGBA")
    r, g, b, a = image.split()
    a = a.point(lambda px: max(0, min(255, int(px * factor))))
    return Image.merge("RGBA", (r, g, b, a))


def _make_gradient_overlay(size: tuple[int, int]) -> Image.Image:
    width, height = size
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    for y in range(height):
        t = y / max(1, height - 1)
        alpha = int(18 + (115 - 18) * t)
        color = (2, 5, 11, alpha)
        draw.line((0, y, width, y), fill=color)
    return overlay


def _make_vignette(size: tuple[int, int]) -> Image.Image:
    width, height = size
    vignette = Image.new("L", size, 0)
    draw = ImageDraw.Draw(vignette)
    draw.ellipse(
        (-int(width * 0.18), -int(height * 0.12), int(width * 1.18), int(height * 1.12)),
        fill=190,
    )
    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=min(width, height) // 8))
    rgba = Image.new("RGBA", size, (2, 5, 11, 0))
    rgba.putalpha(ImageChops.invert(vignette))
    return rgba


def _make_glow(size: tuple[int, int], center: tuple[float, float], radius: float, color: str, alpha: int) -> Image.Image:
    width, height = size
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    glow = Image.new("L", size, 0)
    draw = ImageDraw.Draw(glow)
    cx = int(width * center[0])
    cy = int(height * center[1])
    r = int(min(width, height) * radius)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=alpha)
    glow = glow.filter(ImageFilter.GaussianBlur(radius=max(12, r // 2)))
    rgba = Image.new("RGBA", size, ImageColor.getrgb(color) + (0,))
    rgba.putalpha(glow)
    return rgba


def build_wallpaper(output_path: Path, size: tuple[int, int], profile: str = "dawn") -> None:
    media = REPO_ROOT / "arda-sovereign-website/assets/media"
    brand = REPO_ROOT / "arda-sovereign-website/assets/brand"

    profile_tuning = {
        "dusk": {
            "base_brightness": 0.34,
            "base_color": 0.60,
            "canopy_alpha": 0.05,
            "veil_alpha": 0.05,
            "stars_alpha": 0.08,
            "law_seal_alpha": 0.58,
            "tree_seal_alpha": 0.26,
            "right_glow_radius": 0.12,
            "right_glow_alpha": 18,
            "left_glow_radius": 0.12,
            "left_glow_alpha": 12,
            "contrast": 0.98,
            "brightness_finish": 1.00,
            "bloom_alpha": 0,
        },
        "ember": {
            "base_brightness": 0.42,
            "base_color": 0.72,
            "canopy_alpha": 0.07,
            "veil_alpha": 0.09,
            "stars_alpha": 0.10,
            "law_seal_alpha": 0.66,
            "tree_seal_alpha": 0.34,
            "right_glow_radius": 0.13,
            "right_glow_alpha": 26,
            "left_glow_radius": 0.14,
            "left_glow_alpha": 18,
            "contrast": 1.01,
            "brightness_finish": 1.02,
            "bloom_alpha": 22,
        },
        "silver": {
            "base_brightness": 0.51,
            "base_color": 0.84,
            "canopy_alpha": 0.10,
            "veil_alpha": 0.14,
            "stars_alpha": 0.14,
            "law_seal_alpha": 0.76,
            "tree_seal_alpha": 0.42,
            "right_glow_radius": 0.15,
            "right_glow_alpha": 42,
            "left_glow_radius": 0.17,
            "left_glow_alpha": 31,
            "contrast": 1.04,
            "brightness_finish": 1.05,
            "bloom_alpha": 46,
        },
        "dawn": {
            "base_brightness": 0.58,
            "base_color": 0.92,
            "canopy_alpha": 0.12,
            "veil_alpha": 0.18,
            "stars_alpha": 0.16,
            "law_seal_alpha": 0.82,
            "tree_seal_alpha": 0.50,
            "right_glow_radius": 0.16,
            "right_glow_alpha": 54,
            "left_glow_radius": 0.18,
            "left_glow_alpha": 42,
            "contrast": 1.06,
            "brightness_finish": 1.06,
            "bloom_alpha": 62,
        },
        "crown": {
            "base_brightness": 0.56,
            "base_color": 0.90,
            "canopy_alpha": 0.11,
            "veil_alpha": 0.17,
            "stars_alpha": 0.15,
            "law_seal_alpha": 0.90,
            "tree_seal_alpha": 0.46,
            "right_glow_radius": 0.19,
            "right_glow_alpha": 82,
            "left_glow_radius": 0.16,
            "left_glow_alpha": 28,
            "contrast": 1.08,
            "brightness_finish": 1.08,
            "bloom_alpha": 74,
        },
    }
    tuning = profile_tuning[profile]

    base = _fit_cover(Image.open(media / "telperion-canopy.webp").convert("RGBA"), size)
    base = ImageEnhance.Brightness(base).enhance(tuning["base_brightness"])
    base = ImageEnhance.Color(base).enhance(tuning["base_color"])

    canopy = _fit_cover(Image.open(media / "arda-wallpaper.webp").convert("RGBA"), size)
    canopy = _alpha_scale(canopy, tuning["canopy_alpha"])

    veil = _fit_cover(Image.open(media / "silver-veil.webp").convert("RGBA"), size)
    veil = _alpha_scale(veil, tuning["veil_alpha"])

    stars = _fit_cover(Image.open(media / "witness-constellation.webp").convert("RGBA"), size)
    stars = _alpha_scale(stars, tuning["stars_alpha"])

    law_seal = Image.open(brand / "law-of-the-substrate.webp").convert("RGBA")
    law_seal = law_seal.resize((280, 280), Image.Resampling.LANCZOS)
    law_seal = _alpha_scale(law_seal, tuning["law_seal_alpha"])

    tree_seal = Image.open(brand / "arda-crowned-tree.webp").convert("RGBA")
    tree_seal = tree_seal.resize((138, 138), Image.Resampling.LANCZOS)
    tree_seal = _alpha_scale(tree_seal, tuning["tree_seal_alpha"])

    art = base.copy()
    art.alpha_composite(
        _make_glow(size, (0.76, 0.18), tuning["right_glow_radius"], "#f4fdff", tuning["right_glow_alpha"])
    )
    art.alpha_composite(
        _make_glow(size, (0.18, 0.18), tuning["left_glow_radius"], "#63e6ff", tuning["left_glow_alpha"])
    )
    art.alpha_composite(canopy)
    art.alpha_composite(veil)
    art.alpha_composite(stars)
    art.alpha_composite(_make_gradient_overlay(size))
    art.alpha_composite(_make_vignette(size))
    if tuning["bloom_alpha"]:
        bloom = Image.new("RGBA", size, (240, 246, 255, tuning["bloom_alpha"]))
        bloom.putalpha(
            _make_glow(size, (0.5, 0.22), 0.34, "#f0f6ff", tuning["bloom_alpha"]).split()[-1]
        )
        art.alpha_composite(bloom)
    if profile == "crown":
        crest_flare = Image.new("RGBA", size, (248, 252, 255, 0))
        crest_flare.putalpha(
            _make_glow(size, (0.84, 0.16), 0.22, "#f7fbff", 110).split()[-1]
        )
        art.alpha_composite(crest_flare)

    seal_x = size[0] - law_seal.width - 74
    seal_y = 56
    art.alpha_composite(law_seal, (seal_x, seal_y))

    tree_x = 68
    tree_y = 58
    art.alpha_composite(tree_seal, (tree_x, tree_y))

    art = ImageEnhance.Contrast(art).enhance(tuning["contrast"])
    art = ImageEnhance.Brightness(art).enhance(tuning["brightness_finish"])
    if output_path.suffix.lower() == ".png":
        art.save(output_path)
    else:
        art.save(output_path, quality=96)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a composite ARDA desktop wallpaper")
    parser.add_argument("--output", required=True)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--profile", choices=("dusk", "ember", "silver", "crown", "dawn"), default="dawn")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    build_wallpaper(output, (args.width, args.height), profile=args.profile)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
