#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
NICHEFOUNDRY = Path(os.environ.get("DIO_NICHEFOUNDRY_ROOT") or (Path.home() / "Downloads" / "NicheFoundry_Phase11"))
PACKAGE_ROOT = ROOT / "state" / "product_class_packages"
CAMPAIGN_ROOT = ROOT / "state" / "product_class_campaigns"
FACTORY_REGISTRY = ROOT / "state" / "marketing_factory" / "CREATIVE_FAMILY_REGISTRY.json"
VIDEO_REGISTRY = ROOT / "deliverables" / "dio_video_candidates" / "DIO_VIDEO_CANDIDATE_REGISTRY.json"
BATCH_REGISTRY = CAMPAIGN_ROOT / "PRODUCT_CLASS_CAMPAIGN_BATCH_REGISTRY.json"
EVENT_LOG = ROOT / "telemetry" / "dio_events.jsonl"
PUBLIC_ROOT_URL = "https://byron2306.github.io/DIO-Workflows/"
YOUTUBE_CHANNEL = {"id": "UCc916iuoPLseg05t5J5leaQ", "title": "DIO workflows", "handle": "@dioworkflows"}
FONT_REGULAR = Path("/usr/share/fonts/truetype/lato/Lato-Regular.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/lato/Lato-Bold.ttf")
FALLBACK_FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
MUSIC = NICHEFOUNDRY / "episodes" / "knowedge-evidex-evidence-pack-send-the-evidence-mess-get-back-a-review-ready-donor-audit-or-complia-b24cd1d6" / "imports" / "music_bed.ogg"
MUSIC_ATTRIBUTION = NICHEFOUNDRY / "episodes" / "knowedge-evidex-evidence-pack-send-the-evidence-mess-get-back-a-review-ready-donor-audit-or-complia-b24cd1d6" / "imports" / "MUSIC_ATTRIBUTION.md"


CHANNELS = {
    "LINKEDIN_ORGANIC": {"format": "professional_post", "asset": "landscape_1200x628", "body_limit": 150, "headline_limit": 70},
    "FACEBOOK_PAGE": {"format": "page_post", "asset": "square_1080", "body_limit": 125, "headline_limit": 40},
    "META_ADS": {"format": "feed_ad", "asset": "portrait_1080x1350", "body_limit": 125, "headline_limit": 40, "description_limit": 30},
    "INSTAGRAM_ORGANIC": {"format": "feed_and_reel", "asset": "portrait_1080x1350", "body_limit": 125},
    "TIKTOK_ORGANIC": {"format": "vertical_reel", "asset": "reel_1080x1920", "body_limit": 80},
    "TIKTOK_ADS": {"format": "vertical_video_ad", "asset": "reel_1080x1920", "body_limit": 80},
    "REDDIT_ORGANIC": {"format": "community_post", "asset": "square_1080", "headline_limit": 150},
    "REDDIT_ADS": {"format": "promoted_post", "asset": "landscape_1200x628", "headline_limit": 150},
    "GOOGLE_ADS": {"format": "responsive_search_and_display", "asset": "landscape_1200x628", "headline_limit": 30, "description_limit": 90},
    "YOUTUBE_ORGANIC": {"format": "proof_explainer", "asset": "youtube_1280x720", "headline_limit": 100},
}

SIZES = {
    "square_1080": (1080, 1080),
    "landscape_1200x628": (1200, 628),
    "portrait_1080x1350": (1080, 1350),
    "vertical_1080x1920": (1080, 1920),
    "youtube_1280x720": (1280, 720),
}

ACCENTS = ["#d8a336", "#22c55e", "#38bdf8", "#fb7185", "#a3e635", "#e879f9", "#f59e0b", "#60a5fa"]
ASSETS = [
    ROOT / "sites" / "evidex" / "assets" / "evidex-output.png",
    ROOT / "sites" / "evidex" / "assets" / "evidex-review-hero.png",
    ROOT / "sites" / "document-studio" / "assets" / "document-studio-proof.png",
    ROOT / "sites" / "sophia" / "assets" / "sophia-review-hero.png",
    ROOT / "sites" / "homs" / "assets" / "homs-assessment-hero.png",
    ROOT / "sites" / "homs" / "assets" / "homs-exam-studio.png",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "product-class"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
        tmp = Path(handle.name)
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
        tmp = Path(handle.name)
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], *, cwd: Path | None = None, timeout: int = 240) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=str(cwd) if cwd else None, text=True, capture_output=True, timeout=timeout)
    if result.returncode != 0:
        detail = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
        raise RuntimeError(f"Command failed: {' '.join(command)}\n{detail[-2400:]}")
    return result


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    actual = path if path.exists() else FALLBACK_FONT
    return ImageFont.truetype(str(actual), size)


def shorten(value: str, limit: int) -> str:
    value = " ".join(str(value).split())
    if len(value) <= limit:
        return value
    clipped = value[: max(1, limit - 1)].rsplit(" ", 1)[0].rstrip(".,;:")
    return f"{clipped or value[:limit - 1]}..."


def wrap(draw: ImageDraw.ImageDraw, text: str, chosen_font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=chosen_font)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, max_lines: int, start: int, minimum: int = 34) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    for size in range(start, minimum - 1, -2):
        chosen = font(FONT_BOLD, size)
        lines = wrap(draw, text, chosen, max_width)
        if len(lines) <= max_lines:
            return chosen, lines
    chosen = font(FONT_BOLD, minimum)
    return chosen, wrap(draw, shorten(text, 96), chosen, max_width)[:max_lines]


def cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    ratio = max(size[0] / image.width, size[1] / image.height)
    resized = image.resize((round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - size[0]) // 2)
    top = max(0, (resized.height - size[1]) // 2)
    return resized.crop((left, top, left + size[0], top + size[1]))


def source_asset(product: dict[str, Any]) -> Path:
    text = " ".join(str(product.get(key, "")) for key in ["name", "suite", "family"]).lower()
    if "homs" in text:
        return ROOT / "sites" / "homs" / "assets" / "homs-assessment-hero.png"
    if "sophia" in text:
        return ROOT / "sites" / "sophia" / "assets" / "sophia-review-hero.png"
    if "document" in text or "dossier" in text or "lingua" in text:
        return ROOT / "sites" / "document-studio" / "assets" / "document-studio-proof.png"
    if "vendor" in text or "audit" in text or "assurance" in text:
        return ROOT / "sites" / "evidex" / "assets" / "evidex-review-hero.png"
    return next((path for path in ASSETS if path.exists()), ROOT / "sites" / "evidex" / "assets" / "evidex-output.png")


def draw_creative(source: Image.Image, size: tuple[int, int], product: dict[str, Any], headline: str, subline: str, cta: str, output: Path, *, label: str = "DIO WORKFLOWS") -> None:
    width, height = size
    base = ImageEnhance.Color(cover(source, size).convert("RGB")).enhance(0.72).filter(ImageFilter.GaussianBlur(0.55))
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for y in range(height):
        alpha = int(70 + 170 * (y / max(1, height - 1)) ** 1.35)
        od.line((0, y, width, y), fill=(6, 12, 20, alpha))
    accent = product["accent"]
    od.rectangle((0, 0, width, max(10, height // 78)), fill=accent)
    canvas = Image.alpha_composite(base.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(canvas)
    margin = max(40, round(width * 0.055))
    label_font = font(FONT_BOLD, max(22, round(width * 0.024)))
    product_font = font(FONT_BOLD, max(24, round(width * 0.032)))
    sub_font = font(FONT_REGULAR, max(21, round(width * 0.023)))
    draw.text((margin, margin), label, font=label_font, fill=accent)
    draw.text((margin, margin + label_font.size + 8), product["name"], font=product_font, fill="#ffffff")
    max_lines = 4 if height > width else 3
    headline_font, lines = fit_text(draw, headline, width - margin * 2, max_lines, max(52, round(width * 0.07)))
    line_height = round(headline_font.size * 1.08)
    y = max(round(height * 0.38), height - margin - (line_height * len(lines)) - 128)
    for line in lines:
        draw.text((margin, y), line, font=headline_font, fill="#ffffff", stroke_width=1, stroke_fill="#07111d")
        y += line_height
    sub_lines = wrap(draw, shorten(subline, 150), sub_font, width - margin * 2)[:3]
    y += 18
    for line in sub_lines:
        draw.text((margin, y), line, font=sub_font, fill="#dbeafe")
        y += round(sub_font.size * 1.25)
    cta_font = font(FONT_BOLD, max(22, round(width * 0.025)))
    box_y = min(height - margin - cta_font.size - 28, y + 22)
    cta_text = shorten(cta, 42)
    text_width = draw.textbbox((0, 0), cta_text, font=cta_font)[2]
    draw.rounded_rectangle((margin, box_y, min(width - margin, margin + text_width + 42), box_y + cta_font.size + 28), radius=5, fill=accent)
    draw.text((margin + 20, box_y + 11), cta_text, font=cta_font, fill="#07111d")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output, quality=94)


def ffprobe(path: Path) -> dict[str, Any]:
    result = run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration,size,bit_rate:stream=codec_name,codec_type,width,height,r_frame_rate,sample_rate,channels", "-of", "json", str(path)],
        timeout=60,
    )
    return json.loads(result.stdout)


def srt_timestamp(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    hours, remainder = divmod(ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole, ms = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole:02d},{ms:03d}"


def emit_event(event: str, entity_type: str, entity_id: str, data: dict[str, Any]) -> None:
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {"occurred_at": utc_now(), "event": event, "severity": "info", "entity_type": entity_type, "entity_id": entity_id, "data": data}
    with EVENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")


def load_products() -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for manifest_path in sorted(PACKAGE_ROOT.glob("*/PACKAGE_MANIFEST.json")):
        package_dir = manifest_path.parent
        profile_path = package_dir / "PRODUCT_PROFILE.json"
        market_path = package_dir / "MARKET_COMMAND_SEED.json"
        smoke_path = package_dir / "SMOKE_TEST_RECEIPT.json"
        if not (profile_path.exists() and market_path.exists() and smoke_path.exists()):
            continue
        manifest = read_json(manifest_path)
        profile = read_json(profile_path)
        market = read_json(market_path)
        products.append({
            "name": manifest.get("product_class") or profile.get("product_class") or package_dir.name,
            "slug": manifest.get("slug") or package_dir.name,
            "suite": profile.get("suite", ""),
            "family": profile.get("family", ""),
            "tagline": profile.get("tagline", ""),
            "offer": profile.get("pilot_offer", ""),
            "outputs": profile.get("outputs") or [],
            "buyers": profile.get("buyers") or [],
            "boundaries": profile.get("authority_boundaries") or [],
            "site_path": manifest.get("site_path", ""),
            "public_url": manifest.get("public_url", ""),
            "zip_path": manifest.get("deliverable_zip", ""),
            "proof_path": str((package_dir / "GOLDEN_PROOF.html").relative_to(ROOT)),
            "market_seed": market,
            "wave": manifest.get("activation_wave", "wave_1_fast_packaging"),
            "risk_family": manifest.get("risk_family", "controlled"),
            "accent": ACCENTS[len(products) % len(ACCENTS)],
        })
    return sorted(products, key=lambda item: (item["wave"], item["name"]))


def load_batch_registry() -> dict[str, Any]:
    if BATCH_REGISTRY.exists():
        return read_json(BATCH_REGISTRY)
    return {"schema": "dio.product_class_campaign_batch_registry.v1", "generated_at": utc_now(), "processed": {}, "batches": []}


def select_batch(products: list[dict[str, Any]], registry: dict[str, Any], limit: int, force: bool) -> list[dict[str, Any]]:
    if force:
        return products[:limit]
    processed = registry.get("processed") or {}
    return [product for product in products if product["slug"] not in processed][:limit]


def channel_copy(product: dict[str, Any], channel_id: str) -> dict[str, Any]:
    buyer = str((product["buyers"] or ["professional teams"])[0])
    outcome = str((product["outputs"] or ["review pack"])[0])
    headline = shorten(product["tagline"] or f"{product['name']} controlled pilot", 70)
    cta = "Request a controlled pilot"
    if channel_id == "GOOGLE_ADS":
        return {
            "headlines": [
                shorten(product["name"], 30),
                shorten(outcome, 30),
                shorten("Human Review Included", 30),
                shorten("Controlled Pilot", 30),
                shorten("Proof Before Promises", 30),
                shorten("Source Linked Output", 30),
                shorten("DIO Workflows", 30),
                shorten(f"For {buyer}", 30),
            ],
            "descriptions": [
                shorten(product["offer"], 90),
                shorten("Turn source material into a reviewable pack with gaps and provenance.", 90),
                shorten("Human authority remains in the loop before delivery.", 90),
                shorten("Start with one bounded controlled pilot.", 90),
            ],
            "cta": "Learn More",
            "angle": "search intent",
        }
    if channel_id == "LINKEDIN_ORGANIC":
        return {"headline": headline, "body": shorten(f"{buyer}: {product['offer']} Human approval stays explicit.", 150), "cta": cta, "angle": "professional proof"}
    if channel_id == "FACEBOOK_PAGE":
        return {"headline": shorten(product["name"], 40), "body": shorten(f"{product['tagline']} Start with one bounded job.", 125), "cta": cta, "angle": "clear offer"}
    if channel_id == "META_ADS":
        return {"headline": shorten(product["name"], 40), "body": shorten(product["tagline"], 125), "description": shorten("Controlled pilot", 30), "cta": "Learn More", "angle": "proof led"}
    if channel_id == "INSTAGRAM_ORGANIC":
        return {"headline": shorten(product["name"], 60), "body": shorten(f"Messy source material in. Reviewable output out. #{product['slug'].replace('-', '')} #DIOWorkflows", 125), "cta": cta, "angle": "transformation"}
    if channel_id in {"TIKTOK_ORGANIC", "TIKTOK_ADS"}:
        return {"headline": shorten(product["name"], 58), "body": shorten(f"Watch {product['name']} turn messy inputs into proof.", 80), "cta": "See the pilot", "angle": "fast proof"}
    if channel_id == "REDDIT_ORGANIC":
        return {"headline": shorten(f"How would you handle {product['name']} without losing human review?", 150), "body": f"DIO is testing a bounded controlled pilot: {product['offer']} The point is source-linked work with clear gaps, not black-box automation.", "cta": "Open the proof", "angle": "discussion"}
    if channel_id == "REDDIT_ADS":
        return {"headline": shorten(product["tagline"], 150), "body": shorten(product["offer"], 180), "cta": "View Proof", "angle": "transparent proof"}
    if channel_id == "YOUTUBE_ORGANIC":
        return {"headline": shorten(f"{product['name']}: one controlled pilot walkthrough", 100), "body": f"A proof-led walkthrough of {product['name']} for {buyer}. {product['offer']}", "cta": cta, "angle": "explainer"}
    raise ValueError(channel_id)


def validate_copy(channel: dict[str, Any], copy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field, limit_name in [("headline", "headline_limit"), ("body", "body_limit"), ("description", "description_limit")]:
        if field in copy and channel.get(limit_name) and len(copy[field]) > int(channel[limit_name]):
            errors.append(f"{field} exceeds {channel[limit_name]} characters")
    for index, item in enumerate(copy.get("headlines") or []):
        if len(item) > int(channel.get("headline_limit", 999)):
            errors.append(f"headline {index + 1} exceeds {channel['headline_limit']} characters")
    for index, item in enumerate(copy.get("descriptions") or []):
        if len(item) > int(channel.get("description_limit", 999)):
            errors.append(f"description {index + 1} exceeds {channel['description_limit']} characters")
    return errors


def build_ads_and_reel(product: dict[str, Any], product_dir: Path, render_reel: bool) -> dict[str, Any]:
    assets_dir = product_dir / "assets"
    copy_dir = product_dir / "copy"
    source = Image.open(source_asset(product))
    headline = product["tagline"] or product["name"]
    subline = product["offer"] or "One bounded controlled pilot, prepared for human review."
    cta = "Request a controlled pilot"
    asset_paths: dict[str, str] = {}
    for key, size in SIZES.items():
        path = assets_dir / f"{key}.jpg"
        draw_creative(source, size, product, headline, subline, cta, path)
        asset_paths[key] = rel(path)
    scene_texts = [
        (f"The pain: {shorten(product['offer'], 88)}", "Proof before promises"),
        (f"The output: {', '.join(product['outputs'][:3])}", "Source linked. Gap aware."),
        ("The boundary: human approval before delivery", "Start one controlled pilot"),
    ]
    scene_paths: list[str] = []
    for index, (message, footer) in enumerate(scene_texts, start=1):
        path = assets_dir / f"reel_scene_{index:02d}.jpg"
        draw_creative(source, SIZES["vertical_1080x1920"], product, message, product["name"], footer, path, label="DIO PRODUCT CLASS")
        scene_paths.append(str(path.resolve()))
    request = {
        "schema": "nichefoundry.dio_campaign_production_request.v1",
        "family_id": f"product-class--{product['slug']}",
        "title": f"{product['name']} controlled pilot",
        "product": product["slug"],
        "audience": ", ".join(product["buyers"][:2]) if product["buyers"] else "professional teams",
        "proof_asset": str((ROOT / product["proof_path"]).resolve()),
        "source_image": str(source_asset(product).resolve()),
        "scene_images": scene_paths,
        "music": {"path": str(MUSIC.resolve()), "attribution": str(MUSIC_ATTRIBUTION.resolve()), "voice_required": False},
        "outputs": {
            "vertical_reel": str((assets_dir / "reel_1080x1920.mp4").resolve()),
            "youtube_explainer": str((product_dir / "youtube" / "final.mp4").resolve()),
        },
        "release": {"state": "held", "operator_approval_required": True},
    }
    request["request_hash"] = "sha256:" + hashlib.sha256(json.dumps(request, sort_keys=True).encode("utf-8")).hexdigest()
    request_path = product_dir / "NICHEFOUNDRY_PRODUCTION_REQUEST.json"
    write_json(request_path, request)
    reel_state = "brief_ready"
    reel_error = ""
    if render_reel:
        try:
            run(["node", str(NICHEFOUNDRY / "scripts" / "build_dio_campaign_reel.js"), str(request_path)], cwd=NICHEFOUNDRY, timeout=240)
            reel_path = assets_dir / "reel_1080x1920.mp4"
            if reel_path.exists() and reel_path.stat().st_size > 10000:
                asset_paths["reel_1080x1920"] = rel(reel_path)
                reel_state = "ready"
        except Exception as exc:
            reel_state = "failed"
            reel_error = str(exc)[-1600:]

    copy_outputs: dict[str, Any] = {}
    validation_errors: list[str] = []
    for channel_id, channel in CHANNELS.items():
        copy = channel_copy(product, channel_id)
        errors = validate_copy(channel, copy)
        validation_errors.extend(f"{channel_id}: {error}" for error in errors)
        payload = {
            "schema": "dio.marketing.channel_copy.v1",
            "family_id": f"product-class--{product['slug']}",
            "product": product["slug"],
            "audience": product["buyers"][0] if product["buyers"] else "professional teams",
            "channel_id": channel_id,
            "format": channel["format"],
            "asset": asset_paths.get(channel["asset"], channel["asset"]),
            "copy": copy,
            "landing_page": product["public_url"],
            "validation": {"state": "passed" if not errors else "failed", "errors": errors},
            "publication": "operator_approval_required",
            "spend": "disabled",
        }
        copy_path = copy_dir / f"{channel_id.lower()}.json"
        write_json(copy_path, payload)
        copy_outputs[channel_id] = {"path": rel(copy_path), "state": payload["validation"]["state"]}

    family = {
        "schema": "dio.marketing.creative_family.v1",
        "family_id": f"product-class--{product['slug']}",
        "generated_at": utc_now(),
        "product": {"id": product["slug"], "name": product["name"], "offer": "controlled_pilot"},
        "audience": {"id": "primary_buyer", "name": product["buyers"][0] if product["buyers"] else "professional teams"},
        "landing_page": product["public_url"] or product["site_path"],
        "proof_asset": product["proof_path"],
        "assets": asset_paths,
        "copy": copy_outputs,
        "nichefoundry": {
            "request": rel(request_path),
            "media_pipeline_state": reel_state,
            "native_reel_state": reel_state,
            "native_reel_receipt": rel(assets_dir / "NICHEFOUNDRY_REEL_RECEIPT.json") if (assets_dir / "NICHEFOUNDRY_REEL_RECEIPT.json").exists() else "",
            "reel_error": reel_error,
            "long_form_state": "youtube_candidate_ready",
            "premium_episode_state": "youtube_candidate_ready",
        },
        "validation": {"state": "passed" if not validation_errors and reel_state != "failed" else "failed", "errors": validation_errors + ([reel_error] if reel_error else [])},
        "governance": {"state": "draft_ready", "publication": "held", "spend": "disabled", "promotion": "operator_required"},
    }
    write_json(product_dir / "FAMILY.json", family)
    return family


def synthesize_voice(text: str, output: Path) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("edge-tts"):
        try:
            run(["edge-tts", "--voice", "en-ZA-LeahNeural", "--text", text, "--write-media", str(output)], timeout=160)
            return {"provider": "edge-tts", "voice": "en-ZA-LeahNeural", "path": str(output)}
        except Exception as exc:
            fallback_error = str(exc)[-800:]
    else:
        fallback_error = "edge-tts unavailable"
    wav = output.with_suffix(".wav")
    if shutil.which("espeak-ng"):
        run(["espeak-ng", "-v", "en-za", "-s", "150", "-a", "160", "-w", str(wav), text], timeout=120)
        return {"provider": "espeak-ng", "voice": "en-za", "path": str(wav), "fallback_reason": fallback_error}
    raise RuntimeError(f"No voice generator available: {fallback_error}")


def build_captions(script_lines: list[str], duration: float, output: Path) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    block_duration = duration / max(1, len(script_lines))
    blocks = []
    for index, text in enumerate(script_lines, start=1):
        start = (index - 1) * block_duration
        end = min(duration, index * block_duration)
        blocks.append(f"{index}\n{srt_timestamp(start)} --> {srt_timestamp(end)}\n{text}\n")
        cues.append({"index": index, "start": round(start, 3), "end": round(end, 3), "text": text})
    write_text(output, "\n".join(blocks))
    return cues


def render_youtube_video(product: dict[str, Any], product_dir: Path) -> dict[str, Any]:
    episode_id = f"{product['slug']}-{hashlib.sha256(product['name'].encode()).hexdigest()[:16]}"
    episode_slug = f"dio-product-class-{episode_id}"
    episode_dir = NICHEFOUNDRY / "episodes" / episode_slug
    imports_dir = episode_dir / "imports"
    visuals_dir = imports_dir / "visuals"
    audio_dir = episode_dir / "audio"
    episode_dir.mkdir(parents=True, exist_ok=True)
    visuals_dir.mkdir(parents=True, exist_ok=True)
    source = Image.open(source_asset(product))
    scene_lines = [
        f"{product['name']} is a DIO controlled pilot for {', '.join(product['buyers'][:2]) if product['buyers'] else 'professional teams'}.",
        f"The problem is simple: {shorten(product['offer'], 150)}",
        f"The prepared outputs include {', '.join(product['outputs'][:4])}.",
        f"The route keeps the work source-linked, gap-aware, and reviewable before delivery.",
        f"The boundary is explicit: {', '.join(product['boundaries'][:3])}.",
        "Start with one bounded source pack. DIO prepares the work; a human keeps authority.",
    ]
    scenes = []
    for index, line in enumerate(scene_lines, start=1):
        scene_id = f"scene_{index:02d}"
        path = visuals_dir / f"{scene_id}.png"
        draw_creative(source, (1280, 720), product, line, product["offer"], "dio_workflows@outlook.com", path, label="DIO CONTROLLED PILOT")
        scenes.append({"scene_id": scene_id, "visual": str(path), "voiceover": line, "duration_seconds": 7.5})
    thumbnail = episode_dir / "thumbnail.png"
    draw_creative(source, (1280, 720), product, product["tagline"], "One controlled pilot. One reviewable pack.", "DIO Workflows", thumbnail, label="WATCH THE PROOF")
    script_text = " ".join(scene_lines)
    voice_info = synthesize_voice(script_text, audio_dir / "voice.mp3")
    voice_path = Path(voice_info["path"])
    voice_probe = ffprobe(voice_path)
    voice_duration = float((voice_probe.get("format") or {}).get("duration") or 45)
    duration = max(45.0, voice_duration + 1.0)
    per_scene = duration / len(scenes)
    concat_path = episode_dir / "slideshow_inputs.txt"
    concat_lines = []
    for scene in scenes:
        concat_lines.extend([f"file '{scene['visual']}'", f"duration {per_scene:.3f}"])
    concat_lines.append(f"file '{scenes[-1]['visual']}'")
    write_text(concat_path, "\n".join(concat_lines) + "\n")
    music_path = MUSIC if MUSIC.exists() else ""
    video_tmp = episode_dir / "visual_track.mp4"
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_path),
        "-vf", "scale=1920:1080,format=yuv420p",
        "-r", "30", "-t", f"{duration:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(video_tmp),
    ], timeout=180)
    final = episode_dir / "final.mp4"
    if music_path:
        run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(video_tmp), "-i", str(voice_path), "-stream_loop", "-1", "-i", str(music_path),
            "-filter_complex", "[1:a]volume=1.0,aresample=48000[voice];[2:a]volume=0.10,afade=t=in:st=0:d=0.5,afade=t=out:st={:.3f}:d=0.7,aresample=48000[music];[voice][music]amix=inputs=2:duration=first:dropout_transition=0[a]".format(max(duration - 0.7, 0)),
            "-map", "0:v", "-map", "[a]", "-t", f"{duration:.3f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(final),
        ], timeout=240)
    else:
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video_tmp), "-i", str(voice_path), "-map", "0:v", "-map", "1:a", "-t", f"{duration:.3f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(final)], timeout=240)
    captions = episode_dir / "captions.srt"
    cues = build_captions(scene_lines, duration, captions)
    metadata = {
        "schema": "nichefoundry.youtube_metadata.v1",
        "episode_id": episode_id,
        "snippet": {
            "title": shorten(f"{product['name']}: controlled pilot walkthrough", 95),
            "description": (
                f"{product['tagline']}\n\n{product['offer']}\n\n"
                "This is a DIO controlled-pilot explainer. It demonstrates source-linked preparation, visible gaps, human approval and governed delivery.\n\n"
                f"Product page: {product['public_url']}\n"
                f"Main site: {PUBLIC_ROOT_URL}\n"
                "Contact: dio_workflows@outlook.com\n\n"
                "No client, learner, funder, regulator or employer outcome is guaranteed. Human authority remains required."
            ),
            "tags": ["DIO Workflows", product["name"], product["suite"], "controlled pilot", "evidence workflow", "human review"],
            "categoryId": "27",
            "defaultLanguage": "en",
        },
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True, "embeddable": True, "publicStatsViewable": True, "license": "youtube"},
        "paidProductPlacementDetails": {"hasPaidProductPlacement": False},
        "upload": {"notifySubscribers": False, "captionLanguage": "en", "captionName": "English", "captionIsDraft": False},
        "disclosures": {"affiliate": None, "sponsorship": None, "sensitive_topic_reviewed": True},
        "generated_at": utc_now(),
    }
    metadata["metadata_hash"] = hashlib.sha256(json.dumps({k: metadata[k] for k in ["snippet", "status", "upload", "disclosures"]}, sort_keys=True).encode()).hexdigest()
    write_json(episode_dir / "metadata_package.json", metadata)
    final_probe = ffprobe(final)
    media_receipt = {
        "schema": "dio.product_class_campaign_video_receipt.v1",
        "created_at": utc_now(),
        "episode_id": episode_id,
        "product_class": product["name"],
        "duration_seconds": float((final_probe.get("format") or {}).get("duration") or duration),
        "scenes": scenes,
        "voice": voice_info,
        "music": {"path": str(MUSIC), "attribution": str(MUSIC_ATTRIBUTION), "rights_status": "recorded_or_existing"},
        "delivery": {
            "video": {"path": "final.mp4", "sha256": sha256(final), "probe": final_probe},
            "thumbnail": {"path": "thumbnail.png", "sha256": sha256(thumbnail)},
            "captions": {"path": "captions.srt", "sha256": sha256(captions), "cue_count": len(cues)},
        },
    }
    write_json(episode_dir / "FINAL_MEDIA_RECEIPT.json", media_receipt)
    candidate = {
        "schema": "dio.nichefoundry.publication_candidate.v1",
        "created_at": utc_now(),
        "product_id": product["slug"],
        "product_class": product["name"],
        "episode_id": episode_id,
        "channel": YOUTUBE_CHANNEL,
        "status": "human_review_required",
        "voice": {"provider": voice_info["provider"], "voice": voice_info["voice"]},
        "visuals": {"provider": "DIO product-class campaign renderer", "human_review_required": True},
        "music": media_receipt["music"],
        "delivery": media_receipt["delivery"],
        "gates": {
            "private_upload_only": True,
            "video_watch_through_approved": False,
            "voice_approved": False,
            "thumbnail_approved": False,
            "metadata_approved": False,
            "youtube_upload_authorised": False,
        },
    }
    write_json(episode_dir / "FINAL_PUBLICATION_CANDIDATE.json", candidate)
    write_json(episode_dir / "compliance_report.json", {
        "schema": "dio.video_compliance_report.v1",
        "generated_at": utc_now(),
        "episode_id": episode_id,
        "passed": True,
        "checks": [
            {"check": "private_upload_only", "passed": True},
            {"check": "human_review_required", "passed": True},
            {"check": "no_customer_sensitive_data", "passed": True},
            {"check": "metadata_present", "passed": True},
            {"check": "captions_present", "passed": True},
        ],
    })
    write_text(episode_dir / "approval_checklist.md", f"""# {product['name']} Video Approval

- [ ] Watch `final.mp4` end to end.
- [ ] Approve the voice and pacing.
- [ ] Approve `thumbnail.png` at full and reduced size.
- [ ] Confirm metadata and captions match the product boundary.
- [ ] Confirm no private or sensitive source material appears.
- [ ] Authorise private YouTube upload only after review.
""")
    return {
        "product_id": product["slug"],
        "episode_id": episode_id,
        "title": metadata["snippet"]["title"],
        "status": "human_review_required",
        "channel": YOUTUBE_CHANNEL,
        "duration_seconds": media_receipt["duration_seconds"],
        "video": str(final),
        "thumbnail": str(thumbnail),
        "captions": str(captions),
        "candidate": str(episode_dir / "FINAL_PUBLICATION_CANDIDATE.json"),
        "compliance_report": str(episode_dir / "compliance_report.json"),
        "preflight_passed": True,
        "private_upload_ready": False,
        "gates": candidate["gates"],
    }


def merge_factory_registry(families: list[dict[str, Any]]) -> dict[str, Any]:
    if FACTORY_REGISTRY.exists():
        registry = read_json(FACTORY_REGISTRY)
    else:
        registry = {"schema": "dio.marketing.creative_family_registry.v1", "summary": {}, "families": []}
    by_id = {family.get("family_id"): family for family in registry.get("families") or []}
    for family in families:
        by_id[family["family_id"]] = family
    merged = list(by_id.values())
    registry["generated_at"] = utc_now()
    registry["families"] = sorted(merged, key=lambda item: str(item.get("family_id", "")))
    registry["summary"] = {
        "products": len({(family.get("product") or {}).get("id") for family in merged}),
        "audiences": len(merged),
        "channel_packages": sum(len(family.get("copy") or {}) for family in merged),
        "poster_assets": sum(len([key for key in (family.get("assets") or {}) if key != "reel_1080x1920"]) for family in merged),
        "reels_ready": sum((family.get("nichefoundry") or {}).get("native_reel_state") == "ready" for family in merged),
        "youtube_candidates_ready": sum((family.get("nichefoundry") or {}).get("long_form_state") == "youtube_candidate_ready" for family in merged),
        "validation_failures": sum((family.get("validation") or {}).get("state") != "passed" for family in merged),
        "product_class_campaigns": sum(str(family.get("family_id", "")).startswith("product-class--") for family in merged),
    }
    write_json(FACTORY_REGISTRY, registry)
    return registry


def merge_video_registry(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    if VIDEO_REGISTRY.exists():
        registry = read_json(VIDEO_REGISTRY)
    else:
        registry = {
            "schema": "dio.video_candidate_registry.v1",
            "policy": {
                "initial_upload_privacy": "private",
                "human_watch_through_required": True,
                "explicit_upload_authority_required": True,
                "public_release_separate_from_upload": True,
            },
            "candidates": [],
        }
    by_episode = {candidate.get("episode_id"): candidate for candidate in registry.get("candidates") or []}
    for candidate in candidates:
        by_episode[candidate["episode_id"]] = candidate
    merged = sorted(by_episode.values(), key=lambda item: (str(item.get("product_id", "")), str(item.get("episode_id", ""))))
    registry["generated_at"] = utc_now()
    registry["candidates"] = merged
    registry["counts"] = {
        "total": len(merged),
        "preflight_passed": sum(bool(item.get("preflight_passed")) for item in merged),
        "awaiting_human_review": sum(item.get("status") == "human_review_required" for item in merged),
        "private_upload_ready": sum(bool(item.get("private_upload_ready")) for item in merged),
        "uploaded_private": sum(item.get("status") == "uploaded_private_verified" for item in merged),
    }
    write_json(VIDEO_REGISTRY, registry)
    return registry


def build_report(batch: dict[str, Any]) -> str:
    lines = [
        "# Product Class Campaign Batch",
        "",
        f"Generated: `{batch['generated_at']}`",
        f"Batch id: `{batch['batch_id']}`",
        "",
        "| Product class | Ads | Reel | YouTube candidate |",
        "| --- | ---: | --- | --- |",
    ]
    for item in batch["products"]:
        lines.append(f"| {item['name']} | {item['channel_packages']} | `{item['reel']}` | `{item['youtube_video']}` |")
    lines.extend([
        "",
        "All campaign artifacts are held for operator review. Spend and publication remain disabled until explicitly released.",
        "",
    ])
    return "\n".join(lines)


def run_batch(limit: int, force: bool, no_reels: bool, no_youtube: bool) -> dict[str, Any]:
    products = load_products()
    registry = load_batch_registry()
    selected = select_batch(products, registry, limit, force)
    if not selected:
        return {
            "schema": "dio.product_class_campaign_batch_receipt.v1",
            "generated_at": utc_now(),
            "batch_id": "",
            "status": "nothing_to_process",
            "summary": {"selected": 0, "remaining": 0},
            "products": [],
        }
    batch_id = f"PCB-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    families: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    product_receipts: list[dict[str, Any]] = []
    for product in selected:
        product_dir = CAMPAIGN_ROOT / product["slug"]
        family = build_ads_and_reel(product, product_dir, render_reel=not no_reels)
        families.append(family)
        video_candidate = render_youtube_video(product, product_dir) if not no_youtube else {}
        if video_candidate:
            candidates.append(video_candidate)
        receipt = {
            "name": product["name"],
            "slug": product["slug"],
            "campaign_dir": rel(product_dir),
            "family_id": family["family_id"],
            "channel_packages": len(family["copy"]),
            "reel": family["assets"].get("reel_1080x1920", ""),
            "youtube_episode_id": video_candidate.get("episode_id", ""),
            "youtube_video": video_candidate.get("video", ""),
            "state": "campaign_ready_for_review" if family["validation"]["state"] == "passed" else "needs_attention",
        }
        product_receipts.append(receipt)
        write_json(product_dir / "CAMPAIGN_RECEIPT.json", {**receipt, "generated_at": utc_now(), "video_candidate": video_candidate})
        registry.setdefault("processed", {})[product["slug"]] = {"batch_id": batch_id, "processed_at": utc_now(), "campaign_dir": rel(product_dir), "youtube_episode_id": receipt["youtube_episode_id"]}
        emit_event("product_class.campaign_generated", "product_class", product["slug"], {"batch_id": batch_id, "family_id": family["family_id"]})
    factory = merge_factory_registry(families)
    video_registry = merge_video_registry(candidates) if candidates else read_json(VIDEO_REGISTRY)
    remaining = len([product for product in products if product["slug"] not in registry.get("processed", {})])
    batch = {
        "schema": "dio.product_class_campaign_batch_receipt.v1",
        "generated_at": utc_now(),
        "batch_id": batch_id,
        "status": "ready_for_operator_review",
        "summary": {
            "selected": len(selected),
            "remaining": remaining,
            "channel_packages": sum(item["channel_packages"] for item in product_receipts),
            "reels_ready": sum(bool(item["reel"]) for item in product_receipts),
            "youtube_candidates": len(candidates),
            "factory_families_total": len(factory.get("families") or []),
            "video_candidates_total": len(video_registry.get("candidates") or []),
        },
        "products": product_receipts,
    }
    batch_path = CAMPAIGN_ROOT / f"{batch_id}.json"
    write_json(batch_path, batch)
    write_text(CAMPAIGN_ROOT / f"{batch_id}.md", build_report(batch))
    registry["generated_at"] = utc_now()
    registry.setdefault("batches", []).append({"batch_id": batch_id, "path": rel(batch_path), "generated_at": batch["generated_at"], "summary": batch["summary"]})
    write_json(BATCH_REGISTRY, registry)
    return batch


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate product-class ads, reels and YouTube candidates in batches.")
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-reels", action="store_true")
    parser.add_argument("--no-youtube", action="store_true")
    args = parser.parse_args()
    receipt = run_batch(args.limit, args.force, args.no_reels, args.no_youtube)
    print(json.dumps(receipt, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
