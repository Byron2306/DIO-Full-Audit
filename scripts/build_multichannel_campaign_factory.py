#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from scripts.build_campaign_media import CampaignMediaError, render_campaign_media


ROOT = Path(__file__).resolve().parents[1]
FOUNDRY = Path(os.environ.get("NICHEFOUNDRY_ROOT", "/home/byron/Downloads/NicheFoundry_Phase11"))
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


def canonical_hash(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()


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
    draw.text((margin, margin + product_font.size + 8), audience["name"], font=audience_font, fill="#f8fafc")
    headline = message or audience["outcome"]
    max_lines = 4 if height > width else 3
    headline_font, lines = fit_font(draw, headline, width - margin * 2, max_lines, max(52, round(width * 0.072)))
    line_height = round(headline_font.size * 1.08)
    text_height = line_height * len(lines)
    footer_text = footer or product["cta"]
    footer_font = font(FONT_BOLD, max(22, round(width * 0.025)))
    y = max(round(height * 0.42), height - margin - footer_font.size - 30 - text_height)
    for line in lines:
        draw.text((margin, y), line, font=headline_font, fill="#ffffff", stroke_width=1, stroke_fill="#07111d")
        y += line_height
    rule_y = min(height - margin - footer_font.size - 20, y + 24)
    box_right = min(width - margin, margin + draw.textbbox((0, 0), footer_text, font=footer_font)[2] + 42)
    draw.rounded_rectangle((margin, rule_y, box_right, rule_y + footer_font.size + 26), radius=4, fill=product["accent"])
    draw.text((margin + 20, rule_y + 10), footer_text, font=footer_font, fill="#07111d")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output, quality=94)


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def build_campaign_story(product: dict[str, Any], audience: dict[str, Any]) -> dict[str, Any]:
    name = str(product["short_name"])
    scenes = [
        {
            "scene_id": "scene_01_hook",
            "role": "hook",
            "screen_text": shorten(str(audience["outcome"]), 78),
            "narration": f"{name} is built around one practical outcome: {audience['outcome']}",
            "visual": "Open on the desired finished state, then reveal the workflow that makes it reviewable.",
        },
        {
            "scene_id": "scene_02_pain",
            "role": "pain",
            "screen_text": "The messy first step",
            "narration": str(audience["pain"]),
            "visual": "Show the fragmented input state: files, inboxes, notes, forms, evidence, or drafts competing for attention.",
        },
        {
            "scene_id": "scene_03_workflow",
            "role": "workflow",
            "screen_text": "Route → verify → review",
            "narration": f"{name} turns that first step into a governed workflow. {product['promise']}",
            "visual": "Show intake becoming a visible route, proof checkpoint, human review gate, and bounded output.",
        },
        {
            "scene_id": "scene_04_proof",
            "role": "proof",
            "screen_text": "Proof before promises",
            "narration": str(product["proof"]),
            "visual": "Show the actual proof object or evidence boundary, never a fictional customer result.",
        },
        {
            "scene_id": "scene_05_boundary",
            "role": "boundary",
            "screen_text": "Human authority stays",
            "narration": "The output is prepared for human review. Creating the campaign does not certify the work, publish it, spend money, or prove market demand.",
            "visual": "Make the human approval gate explicit, with publication and spend visibly held.",
        },
        {
            "scene_id": "scene_06_cta",
            "role": "cta",
            "screen_text": shorten(str(product["cta"]), 78),
            "narration": f"If this is the workflow you need, {str(product['cta']).rstrip('.')}.",
            "visual": "End on one concrete next action and the bounded pilot offer.",
        },
    ]
    story_core = {
        "schema": "dio.marketing.campaign_story.v1",
        "family_id": f"{product['id']}--{audience['id']}",
        "title": f"{name} for {audience['name']}",
        "product": product["id"],
        "audience": audience["name"],
        "arc": [scene["role"] for scene in scenes],
        "scenes": scenes,
        "governance": {
            "publication": "held",
            "spend": "disabled",
            "operator_approval_required": True,
            "market_validation_claimed": False,
        },
    }
    return {**story_core, "story_hash": canonical_hash(story_core), "generated_at": utc_now()}


def story_markdown(story: dict[str, Any]) -> str:
    lines = [f"# {story['title']}", "", f"Story hash: `{story['story_hash']}`", "", "## Campaign story", ""]
    for index, scene in enumerate(story["scenes"], 1):
        lines.extend(
            [
                f"### {index}. {scene['screen_text']}",
                "",
                f"**Role:** {scene['role']}",
                "",
                scene["narration"],
                "",
                f"Visual direction: {scene['visual']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Release boundary",
            "",
            "This pack is generated for operator review. Publication and advertising spend remain held until separately approved.",
            "",
        ]
    )
    return "\n".join(lines)


def build_gamma_story_request(story: dict[str, Any], directory: Path) -> dict[str, Any]:
    card_blocks = []
    for scene in story["scenes"]:
        card_blocks.append(
            "\n".join(
                [
                    f"# {scene['screen_text']}",
                    scene["narration"],
                    f"Visual direction: {scene['visual']}",
                    f"Story role: {scene['role']}",
                ]
            )
        )
    payload = {
        "schema": "dio.gamma.campaign_story_request.v1",
        "family_id": story["family_id"],
        "title": story["title"],
        "story_hash": story["story_hash"],
        "num_cards": len(story["scenes"]),
        "input_text": "\n\n---\n\n".join(card_blocks),
        "output_dir": str((directory / "gamma").resolve()),
        "release": {
            "state": "held",
            "visual_review_required": True,
            "operator_approval_required": True,
        },
    }
    payload["request_hash"] = canonical_hash(payload)
    return payload


def _run_gamma(request_path: Path) -> tuple[str, str]:
    completed = subprocess.run(
        ["node", str(ROOT / "scripts" / "run_gamma_story.js"), str(request_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=540,
    )
    if completed.returncode != 0:
        return "failed", (completed.stderr or completed.stdout or "Gamma campaign story failed").strip()[-1600:]
    return "ready", ""


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

    story = build_campaign_story(product, audience)
    story_path = directory / "CAMPAIGN_STORY.json"
    story_md_path = directory / "CAMPAIGN_STORY.md"
    write_json(story_path, story)
    story_md_path.write_text(story_markdown(story), encoding="utf-8")

    scene_paths: list[str] = []
    for index, scene in enumerate(story["scenes"], 1):
        path = assets / f"story_{index:02d}_{scene['role']}.jpg"
        draw_poster(source, SIZES["vertical_1080x1920"], product, audience, path, scene["screen_text"], scene["role"].replace("_", " ").title())
        scene_paths.append(str(path.resolve()))
        asset_paths[f"story_scene_{index:02d}"] = relative(path)

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

    gamma_request = build_gamma_story_request(story, directory)
    gamma_request_path = directory / "GAMMA_STORY_REQUEST.json"
    write_json(gamma_request_path, gamma_request)
    gamma_receipt_path = directory / "gamma" / "GAMMA_STORY_RECEIPT.json"

    reel_path = assets / "reel_1080x1920.mp4"
    explainer_path = assets / "explainer_1920x1080.mp4"
    request = {
        "schema": "nichefoundry.dio_campaign_production_request.v2",
        "family_id": family_id,
        "title": story["title"],
        "product": product["id"],
        "audience": audience["name"],
        "proof_asset": str((ROOT / product["proof_asset"]).resolve()),
        "source_image": str(source_path.resolve()),
        "story": {
            "path": str(story_path.resolve()),
            "story_hash": story["story_hash"],
            "scenes": story["scenes"],
        },
        "scene_images": scene_paths,
        "gamma": {
            "required": True,
            "request": str(gamma_request_path.resolve()),
            "receipt": str(gamma_receipt_path.resolve()),
        },
        "gamma_request_hash": gamma_request["request_hash"],
        "voice": {
            "required": True,
            "provider": "piper_local",
            "fallback_provider": None,
            "remote_tts_allowed": False,
        },
        "music": {
            "path": str(MUSIC.resolve()),
            "attribution": str(MUSIC_ATTRIBUTION.resolve()),
            "voice_required": True,
        },
        "outputs": {
            "vertical_reel": str(reel_path.resolve()),
            "long_form_explainer": str(explainer_path.resolve()),
        },
        "release": {"state": "held", "operator_approval_required": True},
    }
    request["request_hash"] = canonical_hash(request)
    request_path = directory / "NICHEFOUNDRY_PRODUCTION_REQUEST.json"
    write_json(request_path, request)

    gamma_state = "request_ready"
    gamma_error = ""
    media_state = "brief_ready"
    media_error = ""
    piper_state = "required_local"
    media_receipt: dict[str, Any] = {}

    if render_reels:
        gamma_state, gamma_error = _run_gamma(gamma_request_path)
        if gamma_state == "ready":
            try:
                media_receipt = render_campaign_media(request_path, gamma_receipt_path, nichefoundry_root=FOUNDRY)
                media_state = str(media_receipt.get("state") or "ready")
                piper_state = "ready" if media_state == "ready" else "failed"
            except (CampaignMediaError, OSError, subprocess.SubprocessError, ValueError) as exc:
                media_state = "failed"
                piper_state = "failed"
                media_error = str(exc)[-1600:]
        else:
            media_state = "blocked_by_gamma"
            piper_state = "not_started"

    if media_state == "ready":
        asset_paths["reel_1080x1920"] = relative(reel_path)
        asset_paths["explainer_1920x1080"] = relative(explainer_path)

    external_errors = [error for error in (gamma_error, media_error) if error]
    family = {
        "schema": "dio.marketing.creative_family.v2",
        "family_id": family_id,
        "generated_at": utc_now(),
        "product": {"id": product["id"], "name": product["name"], "offer": product["offer"]},
        "audience": audience,
        "landing_page": product["landing_page"],
        "proof_asset": product["proof_asset"],
        "story": {
            "state": "ready",
            "path": relative(story_path),
            "markdown": relative(story_md_path),
            "story_hash": story["story_hash"],
            "scene_count": len(story["scenes"]),
            "arc": story["arc"],
        },
        "assets": asset_paths,
        "copy": copy_outputs,
        "gamma": {
            "required_for_media": True,
            "state": gamma_state,
            "request": relative(gamma_request_path),
            "receipt": relative(gamma_receipt_path) if gamma_receipt_path.is_file() else "",
            "error": gamma_error,
        },
        "piper": {
            "required_for_media": True,
            "provider": "piper_local",
            "remote_fallback": False,
            "state": piper_state,
            "receipt": relative(directory / "media" / "PIPER_NARRATION_RECEIPT.json") if (directory / "media" / "PIPER_NARRATION_RECEIPT.json").is_file() else "",
        },
        "nichefoundry": {
            "request": relative(request_path),
            "reel_state": media_state,
            "reel_error": media_error,
            "long_form_state": media_state,
            "media_receipt": relative(directory / "media" / "CAMPAIGN_MEDIA_RECEIPT.json") if (directory / "media" / "CAMPAIGN_MEDIA_RECEIPT.json").is_file() else "",
        },
        "validation": {
            "state": "passed" if not validation_errors and not external_errors and media_state != "failed" and media_state != "blocked_by_gamma" else "failed",
            "errors": validation_errors + external_errors,
        },
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
        "schema": "dio.marketing.creative_family_registry.v2",
        "generated_at": utc_now(),
        "factory_policy": matrix["factory_policy"],
        "summary": {
            "products": len({family["product"]["id"] for family in families}),
            "audiences": len(families),
            "channel_packages": sum(len(family["copy"]) for family in families),
            "poster_assets": sum(len([key for key in family["assets"] if key not in {"reel_1080x1920", "explainer_1920x1080"}]) for family in families),
            "stories_ready": sum(family["story"]["state"] == "ready" for family in families),
            "gamma_stories_ready": sum(family["gamma"]["state"] == "ready" for family in families),
            "piper_narrations_ready": sum(family["piper"]["state"] == "ready" for family in families),
            "reels_ready": sum(family["nichefoundry"]["reel_state"] == "ready" for family in families),
            "long_form_ready": sum(family["nichefoundry"]["long_form_state"] == "ready" for family in families),
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
    store = MarketStore(
        ROOT / "state" / "market_command" / "market_command.sqlite",
        ROOT / "telemetry" / "dio_events.jsonl",
        load_json(ROOT / "config" / "market_command.json"),
    )
    try:
        campaign = store.get_campaign(campaign_id)
    except ValueError:
        campaign = store.create_campaign(
            {
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
                "source_lineage": {
                    "creative_family": family_id,
                    "factory_registry": relative(DEFAULT_OUTPUT / "CREATIVE_FAMILY_REGISTRY.json"),
                    "campaign_story": family["story"]["path"],
                    "gamma_receipt": family["gamma"].get("receipt") or None,
                    "piper_receipt": family["piper"].get("receipt") or None,
                },
            }
        )
    copy = copy_payload["copy"]
    hook = copy.get("headline") or (copy.get("headlines") or [family["product"]["name"]])[0]
    body = copy.get("body") or " | ".join(copy.get("descriptions") or [])
    content = store.add_content(
        campaign_id,
        {
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
        },
    )
    return {"status": "draft_promoted", "campaign": campaign, "content": content, "publication": "held", "spend": "disabled"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build proof-led DIO campaign families, Gamma stories, and local-Piper narrated media.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-reels", action="store_true", help="Build story/copy/Gamma requests without invoking Gamma or Piper media rendering.")
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
