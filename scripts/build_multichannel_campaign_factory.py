#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FOUNDRY = Path("/home/byron/Downloads/NicheFoundry_Phase11")
MATRIX = ROOT / "config" / "marketing_audience_matrix.json"
DEFAULT_OUTPUT = ROOT / "state" / "marketing_factory"
MUSIC = FOUNDRY / "episodes" / "knowedge-evidex-evidence-pack-send-the-evidence-mess-get-back-a-review-ready-donor-audit-or-complia-b24cd1d6" / "imports" / "music_bed.ogg"
MUSIC_ATTRIBUTION = MUSIC.parent / "MUSIC_ATTRIBUTION.md"
FONT_REGULAR = Path("/usr/share/fonts/truetype/lato/Lato-Regular.ttf")
FONT_BOLD = Path("/usr/share/fonts/truetype/lato/Lato-Bold.ttf")


SIZES = {
    "square_1080": (1080, 1080),
    "landscape_1200x628": (1200, 628),
    "portrait_1080x1350": (1080, 1350),
    "vertical_1080x1920": (1080, 1920),
    "youtube_1280x720": (1280, 720),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def slug(value: str) -> str:
    clean = "".join(character.lower() if character.isalnum() else "-" for character in value)
    return "-".join(part for part in clean.split("-") if part)


def shorten(value: str, limit: int) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    clipped = value[: max(1, limit - 1)].rsplit(" ", 1)[0]
    return (clipped or value[: limit - 1]).rstrip(".,;:") + "…"


def copy_package(product: dict[str, Any], audience: dict[str, Any], channel_id: str) -> dict[str, Any]:
    name = product["short_name"]
    outcome = audience["outcome"]
    pain = audience["pain"]
    cta = product["cta"]
    hook = shorten(outcome, 68)
    if channel_id == "LINKEDIN_ORGANIC":
        body = shorten(f"{pain} {name} prepares {outcome.lower()} Human authority stays intact. {cta}.", 150)
        return {"headline": shorten(hook, 70), "body": body, "cta": cta, "angle": "professional proof"}
    if channel_id == "FACEBOOK_PAGE":
        return {"headline": shorten(hook, 40), "body": shorten(f"{pain} {name} prepares the work for human review. {cta}.", 125), "cta": cta, "angle": "relief"}
    if channel_id == "META_ADS":
        return {"headline": shorten(hook, 40), "body": shorten(f"{pain} See a controlled {name} proof workflow.", 125), "description": shorten(cta, 30), "cta": "Learn More", "angle": "pain to proof"}
    if channel_id == "INSTAGRAM_ORGANIC":
        return {"headline": shorten(hook, 60), "body": shorten(f"From scattered work to a reviewable result. {cta}. #DIO #{slug(name).replace('-', '')}", 125), "cta": cta, "angle": "visual transformation"}
    if channel_id in {"TIKTOK_ORGANIC", "TIKTOK_ADS"}:
        return {"headline": shorten(hook, 58), "body": shorten(f"Watch {name} turn the messy first step into a reviewable result.", 80), "cta": shorten(cta, 40), "angle": "fast proof"}
    if channel_id == "REDDIT_ORGANIC":
        title = shorten(f"How are {audience['name'].lower()} handling this workflow without losing human review?", 150)
        body = f"We built a bounded {name} pilot around one recurring problem: {pain.lower()} The output is prepared for human review, with proof and limitations visible. This is a workflow example, not an automated sales pitch."
        return {"headline": title, "body": body, "cta": "Open the proof example", "angle": "community discussion"}
    if channel_id == "REDDIT_ADS":
        return {"headline": shorten(f"A reviewable answer to: {pain}", 150), "body": shorten(product["proof"], 180), "cta": "View Proof", "angle": "transparent proof"}
    if channel_id == "GOOGLE_ADS":
        headlines = [
            shorten(product["name"], 30),
            shorten(outcome, 30),
            shorten("Human-Reviewed Professional Work", 30),
            shorten("Controlled Pilot Available", 30),
            shorten(f"See the {name} Proof", 30),
            shorten("Proof Before Promises", 30),
            shorten("Keep Human Authority", 30),
            shorten("Reviewable Output", 30),
            shorten(f"Built for {audience['name']}", 30),
            shorten("A Better Professional First Pass", 30),
        ]
        descriptions = [
            shorten(f"{product['promise']} Human review and clear provenance remain in the loop.", 90),
            shorten(f"Built for {audience['name'].lower()}. Start with one bounded, reviewable pilot.", 90),
            shorten(f"See how {name} turns a difficult first step into work a professional can verify.", 90),
            shorten(f"{product['proof']} Request one controlled pilot before committing further.", 90),
        ]
        return {"headlines": headlines, "descriptions": descriptions, "cta": "Learn More", "angle": "search intent"}
    if channel_id == "YOUTUBE_ORGANIC":
        return {"headline": shorten(f"{name}: from messy input to reviewable professional output", 100), "body": f"A short proof-led walkthrough for {audience['name'].lower()}. {product['proof']} {cta}.", "cta": cta, "angle": "proof explainer"}
    raise ValueError(f"Unsupported channel: {channel_id}")


def validate_copy(channel: dict[str, Any], copy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    checks = (("headline", "headline_limit"), ("body", "body_limit"), ("description", "description_limit"))
    for field, limit_name in checks:
        if field in copy and channel.get(limit_name) and len(copy[field]) > int(channel[limit_name]):
            errors.append(f"{field} exceeds {channel[limit_name]} characters")
    if copy.get("headlines"):
        errors.extend(f"headline {index + 1} exceeds {channel['headline_limit']} characters" for index, item in enumerate(copy["headlines"]) if len(item) > int(channel["headline_limit"]))
    if copy.get("descriptions"):
        errors.extend(f"description {index + 1} exceeds {channel['description_limit']} characters" for index, item in enumerate(copy["descriptions"]) if len(item) > int(channel["description_limit"]))
    return errors


def cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    ratio = max(size[0] / image.width, size[1] / image.height)
    resized = image.resize((round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - size[0]) // 2)
    top = max(0, (resized.height - size[1]) // 2)
    return resized.crop((left, top, left + size[0], top + size[1]))


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def wrapped_lines(draw: ImageDraw.ImageDraw, text: str, chosen_font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
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


def fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, max_lines: int, start: int, minimum: int = 34) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    for size in range(start, minimum - 1, -2):
        chosen = font(FONT_BOLD, size)
        lines = wrapped_lines(draw, text, chosen, max_width)
        if len(lines) <= max_lines:
            return chosen, lines
    chosen = font(FONT_BOLD, minimum)
    return chosen, wrapped_lines(draw, shorten(text, 90), chosen, max_width)[:max_lines]


def draw_poster(source: Image.Image, size: tuple[int, int], product: dict[str, Any], audience: dict[str, Any], output: Path, message: str | None = None, footer: str | None = None) -> None:
    width, height = size
    base = ImageEnhance.Color(cover(source, size).convert("RGB")).enhance(0.82).filter(ImageFilter.GaussianBlur(0.35))
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for y in range(height):
        alpha = int(40 + 178 * (y / max(1, height - 1)) ** 1.5)
        overlay_draw.line((0, y, width, y), fill=(6, 12, 20, alpha))
    overlay_draw.rectangle((0, 0, width, max(8, height // 70)), fill=product["accent"])
    canvas = Image.alpha_composite(base.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(canvas)
    margin = max(42, round(width * 0.055))
    product_font = font(FONT_BOLD, max(24, round(width * 0.027)))
    audience_font = font(FONT_REGULAR, max(22, round(width * 0.022)))
    draw.text((margin, margin), product["short_name"].upper(), font=product_font, fill=product["accent"])
    audience_label = audience["name"]
    draw.text((margin, margin + product_font.size + 8), audience_label, font=audience_font, fill="#f8fafc")
    headline = message or audience["outcome"]
    max_lines = 4 if height > width else 3
    headline_font, lines = fit_font(draw, headline, width - margin * 2, max_lines, max(52, round(width * 0.072)))
    line_height = round(headline_font.size * 1.08)
    text_height = line_height * len(lines)
    footer_text = footer or product["cta"]
    footer_font = font(FONT_BOLD, max(22, round(width * 0.025)))
    y = height - margin - footer_font.size - 30 - text_height
    y = max(round(height * 0.42), y)
    for line in lines:
        draw.text((margin, y), line, font=headline_font, fill="#ffffff", stroke_width=1, stroke_fill="#07111d")
        y += line_height
    rule_y = min(height - margin - footer_font.size - 20, y + 24)
    draw.rounded_rectangle((margin, rule_y, min(width - margin, margin + draw.textbbox((0, 0), footer_text, font=footer_font)[2] + 42), rule_y + footer_font.size + 26), radius=4, fill=product["accent"])
    draw.text((margin + 20, rule_y + 10), footer_text, font=footer_font, fill="#07111d")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output, quality=94)


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def build_family(product: dict[str, Any], audience: dict[str, Any], channels: dict[str, Any], output_root: Path, render_reels: bool) -> dict[str, Any]:
    family_id = f"{product['id']}--{audience['id']}"
    directory = output_root / slug(product["id"]) / slug(audience["id"])
    assets = directory / "assets"
    copy_dir = directory / "copy"
    source_path = ROOT / product["source_image"]
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    source = Image.open(source_path)
    asset_paths: dict[str, str] = {}
    for key, size in SIZES.items():
        path = assets / f"{key}.jpg"
        draw_poster(source, size, product, audience, path)
        asset_paths[key] = relative(path)
    scenes = [
        ("01_hook.jpg", audience["pain"], "There is a better first pass"),
        ("02_proof.jpg", product["proof"], "Proof before promises"),
        ("03_action.jpg", audience["outcome"], product["cta"]),
    ]
    scene_paths = []
    for filename, message, footer in scenes:
        path = assets / filename
        draw_poster(source, SIZES["vertical_1080x1920"], product, audience, path, message, footer)
        scene_paths.append(str(path.resolve()))

    copy_outputs: dict[str, Any] = {}
    validation_errors: list[str] = []
    for channel_id, channel in channels.items():
        channel_copy = copy_package(product, audience, channel_id)
        errors = validate_copy(channel, channel_copy)
        validation_errors.extend(f"{channel_id}: {error}" for error in errors)
        payload = {
            "schema": "dio.marketing.channel_copy.v1",
            "family_id": family_id,
            "product": product["id"],
            "audience": audience["name"],
            "channel_id": channel_id,
            "format": channel["format"],
            "asset": asset_paths.get(channel["asset"], channel["asset"]),
            "copy": channel_copy,
            "validation": {"state": "passed" if not errors else "failed", "errors": errors},
            "publication": "operator_approval_required",
            "spend": "disabled",
        }
        path = copy_dir / f"{channel_id.lower()}.json"
        write_json(path, payload)
        copy_outputs[channel_id] = {"path": relative(path), "state": payload["validation"]["state"]}

    request = {
        "schema": "nichefoundry.dio_campaign_production_request.v1",
        "family_id": family_id,
        "title": f"{product['short_name']} for {audience['name']}",
        "product": product["id"],
        "audience": audience["name"],
        "proof_asset": str((ROOT / product["proof_asset"]).resolve()),
        "source_image": str(source_path.resolve()),
        "scene_images": scene_paths,
        "music": {"path": str(MUSIC.resolve()), "attribution": str(MUSIC_ATTRIBUTION.resolve()), "voice_required": False},
        "outputs": {
            "vertical_reel": str((assets / "reel_1080x1920.mp4").resolve()),
            "long_form_explainer": {"state": "brief_ready", "target_seconds": 45, "requires_operator_script_review": True},
        },
        "release": {"state": "held", "operator_approval_required": True},
    }
    request["request_hash"] = "sha256:" + hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()
    request_path = directory / "NICHEFOUNDRY_PRODUCTION_REQUEST.json"
    write_json(request_path, request)
    reel_path = assets / "reel_1080x1920.mp4"
    reel_receipt_path = assets / "NICHEFOUNDRY_REEL_RECEIPT.json"
    existing_receipt = json.loads(reel_receipt_path.read_text(encoding="utf-8")) if reel_receipt_path.is_file() else {}
    reel_current = reel_path.is_file() and reel_path.stat().st_size > 10000 and existing_receipt.get("request_hash") == request["request_hash"]
    reel_error = ""
    if render_reels and not reel_current:
        completed = subprocess.run(
            ["node", str(FOUNDRY / "scripts" / "build_dio_campaign_reel.js"), str(request_path)],
            cwd=FOUNDRY,
            capture_output=True,
            text=True,
            timeout=240,
        )
        if completed.returncode != 0:
            reel_error = (completed.stderr or completed.stdout).strip()[-800:]
    reel_state = "ready" if reel_path.is_file() and reel_path.stat().st_size > 10000 else ("failed" if reel_error else "brief_ready")
    if reel_state == "ready":
        asset_paths["reel_1080x1920"] = relative(reel_path)

    family = {
        "schema": "dio.marketing.creative_family.v1",
        "family_id": family_id,
        "generated_at": utc_now(),
        "product": {"id": product["id"], "name": product["name"], "offer": product["offer"]},
        "audience": audience,
        "landing_page": product["landing_page"],
        "proof_asset": product["proof_asset"],
        "assets": asset_paths,
        "copy": copy_outputs,
        "nichefoundry": {"request": relative(request_path), "reel_state": reel_state, "reel_error": reel_error, "long_form_state": "brief_ready"},
        "validation": {"state": "passed" if not validation_errors and reel_state != "failed" else "failed", "errors": validation_errors + ([reel_error] if reel_error else [])},
        "governance": {"state": "draft_ready", "publication": "held", "spend": "disabled", "promotion": "operator_required"},
    }
    write_json(directory / "FAMILY.json", family)
    return family


def build(output_root: Path = DEFAULT_OUTPUT, render_reels: bool = True, limit: int = 0) -> dict[str, Any]:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    output_root.mkdir(parents=True, exist_ok=True)
    families: list[dict[str, Any]] = []
    for product in matrix["products"]:
        for audience in product["audiences"]:
            families.append(build_family(product, audience, matrix["channels"], output_root, render_reels))
            if limit and len(families) >= limit:
                break
        if limit and len(families) >= limit:
            break
    registry = {
        "schema": "dio.marketing.creative_family_registry.v1",
        "generated_at": utc_now(),
        "factory_policy": matrix["factory_policy"],
        "summary": {
            "products": len({family["product"]["id"] for family in families}),
            "audiences": len(families),
            "channel_packages": sum(len(family["copy"]) for family in families),
            "poster_assets": sum(len([key for key in family["assets"] if key != "reel_1080x1920"]) for family in families),
            "reels_ready": sum(family["nichefoundry"]["reel_state"] == "ready" for family in families),
            "validation_failures": sum(family["validation"]["state"] != "passed" for family in families),
        },
        "families": families,
    }
    write_json(output_root / "CREATIVE_FAMILY_REGISTRY.json", registry)
    return registry


def stable_market_id(prefix: str, family_id: str, channel_id: str) -> str:
    digest = hashlib.sha256(f"{family_id}:{channel_id}".encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}-{digest}"


def promote_family(family_id: str, channel_id: str) -> dict[str, Any]:
    from market_command.catalog import load_json
    from market_command.core import MarketStore

    registry = json.loads((DEFAULT_OUTPUT / "CREATIVE_FAMILY_REGISTRY.json").read_text(encoding="utf-8"))
    family = next((item for item in registry["families"] if item["family_id"] == family_id), None)
    if not family:
        raise ValueError("Creative family not found")
    if channel_id not in family["copy"]:
        raise ValueError("Channel package not found")
    copy_payload = json.loads((ROOT / family["copy"][channel_id]["path"]).read_text(encoding="utf-8"))
    campaign_id = stable_market_id("MCF", family_id, channel_id)
    content_id = stable_market_id("CNT", family_id, channel_id)
    store = MarketStore(ROOT / "state" / "market_command" / "market_command.sqlite", ROOT / "telemetry" / "dio_events.jsonl", load_json(ROOT / "config" / "market_command.json"))
    try:
        campaign = store.get_campaign(campaign_id)
    except ValueError:
        campaign = store.create_campaign({
            "campaign_id": campaign_id,
            "product_line_id": family["product"]["id"],
            "offer_id": family["product"]["offer"],
            "name": f"{family['product']['name']} | {family['audience']['name']}",
            "audience": family["audience"]["name"],
            "channel_id": channel_id,
            "objective": "Validate a proof-led audience and offer hypothesis with attributable enquiries.",
            "landing_page": family["landing_page"],
            "proof_asset": family["proof_asset"],
            "creative_brief": family["nichefoundry"]["request"],
            "budget_cap_minor": 0,
            "source_lineage": {"creative_family": family_id, "factory_registry": relative(DEFAULT_OUTPUT / "CREATIVE_FAMILY_REGISTRY.json")},
        })
    copy = copy_payload["copy"]
    hook = copy.get("headline") or (copy.get("headlines") or [family["product"]["name"]])[0]
    body = copy.get("body") or " | ".join(copy.get("descriptions") or [])
    content = store.add_content(campaign_id, {
        "content_id": content_id,
        "channel_id": channel_id,
        "format": copy_payload["format"],
        "hook": hook,
        "body": body,
        "asset_path": copy_payload["asset"],
        "source_language": "English",
        "artifact_type": "multichannel_campaign_family",
        "semantic_object_id": f"MARKET-{campaign_id}",
        "cta": copy.get("cta") or "",
    })
    return {"status": "draft_promoted", "campaign": campaign, "content": content, "publication": "held", "spend": "disabled"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build proof-led DIO campaign families for every configured audience and channel.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-reels", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--promote-family")
    parser.add_argument("--channel")
    args = parser.parse_args()
    if args.promote_family:
        if not args.channel:
            parser.error("--channel is required with --promote-family")
        print(json.dumps(promote_family(args.promote_family, args.channel), indent=2))
        return 0
    result = build(args.output, not args.no_reels, args.limit)
    print(json.dumps(result["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
