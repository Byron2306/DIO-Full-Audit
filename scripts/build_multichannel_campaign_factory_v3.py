#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from lingua.product_projection import build_projection_plan, creative_distance, project_story
from lingua.semantic_law import build_semantic_law, validate_projection
from scripts.build_campaign_media_v3 import CampaignMediaError, render_campaign_media_v3

ROOT = Path(__file__).resolve().parents[1]
FOUNDRY = Path(os.environ.get("NICHEFOUNDRY_ROOT", "/home/byron/Downloads/NicheFoundry_Phase11"))
MATRIX = ROOT / "config" / "marketing_audience_matrix.json"
DEFAULT_OUTPUT = ROOT / "state" / "marketing_factory"
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
    clean = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value))
    return "-".join(part for part in clean.split("-") if part)


def shorten(value: str, limit: int) -> str:
    clean = " ".join(str(value or "").split())
    if len(clean) <= limit:
        return clean
    clipped = clean[: max(1, limit - 1)].rsplit(" ", 1)[0]
    return (clipped or clean[: limit - 1]).rstrip(".,;:") + "…"


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def _cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    ratio = max(size[0] / image.width, size[1] / image.height)
    resized = image.resize((round(image.width * ratio), round(image.height * ratio)), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - size[0]) // 2)
    top = max(0, (resized.height - size[1]) // 2)
    return resized.crop((left, top, left + size[0], top + size[1]))


def _wrap(draw: ImageDraw.ImageDraw, text: str, chosen_font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
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


def draw_poster(
    source: Image.Image,
    size: tuple[int, int],
    product: dict[str, Any],
    audience: dict[str, Any],
    output: Path,
    *,
    message: str | None = None,
    footer: str | None = None,
    visual_grammar: str,
) -> None:
    width, height = size
    energetic = any(token in visual_grammar for token in ("bright", "energetic", "public_interest"))
    saturation = 1.08 if energetic else 0.78
    base = ImageEnhance.Color(_cover(source, size).convert("RGB")).enhance(saturation).convert("RGBA")
    overlay = Image.new("RGBA", size, (6, 12, 20, 88 if energetic else 152))
    canvas = Image.alpha_composite(base, overlay)
    draw = ImageDraw.Draw(canvas)
    accent = product["accent"]
    if "documentary" in visual_grammar:
        draw.rectangle((0, 0, max(8, width // 110), height), fill=accent)
    else:
        draw.rectangle((0, 0, width, max(8, height // 70)), fill=accent)
    margin = max(42, round(width * 0.055))
    draw.text((margin, margin), product["short_name"].upper(), font=_font(FONT_BOLD, max(24, round(width * 0.027))), fill=accent)
    draw.text((margin, margin + max(42, round(width * 0.038))), audience["name"], font=_font(FONT_REGULAR, max(22, round(width * 0.022))), fill="#f8fafc")
    headline = message or audience["outcome"]
    for size_px in range(max(52, round(width * 0.072)), 32, -2):
        headline_font = _font(FONT_BOLD, size_px)
        lines = _wrap(draw, headline, headline_font, width - margin * 2)
        if len(lines) <= (4 if height > width else 3):
            break
    y = round(height * (0.35 if energetic else 0.44))
    for line in lines:
        draw.text((margin, y), line, font=headline_font, fill="#ffffff", stroke_width=1, stroke_fill="#07111d")
        y += round(headline_font.size * 1.08)
    footer_text = footer or product["cta"]
    footer_font = _font(FONT_BOLD, max(22, round(width * 0.025)))
    box_right = min(width - margin, margin + draw.textbbox((0, 0), footer_text, font=footer_font)[2] + 42)
    rule_y = min(height - margin - footer_font.size - 26, y + 24)
    draw.rounded_rectangle((margin, rule_y, box_right, rule_y + footer_font.size + 26), radius=4, fill=accent)
    draw.text((margin + 20, rule_y + 10), footer_text, font=footer_font, fill="#07111d")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output, quality=94)


def copy_package(product: dict[str, Any], audience: dict[str, Any], channel_id: str, channel_projection: dict[str, Any]) -> dict[str, Any]:
    name = product["short_name"]
    pain = audience["pain"]
    outcome = audience["outcome"]
    cta = product["cta"]
    tone = str(channel_projection.get("tone") or "")
    if channel_id == "LINKEDIN_ORGANIC":
        return {"headline": shorten(outcome, 70), "body": shorten(f"{pain} {name} prepares {outcome.lower()} Human authority stays intact. {cta}.", 150), "cta": cta, "angle": tone}
    if channel_id == "FACEBOOK_PAGE":
        return {"headline": shorten(outcome, 40), "body": shorten(f"{pain} Then: {outcome} {cta}.", 125), "cta": cta, "angle": tone}
    if channel_id == "META_ADS":
        return {"headline": shorten(outcome, 40), "body": shorten(pain, 125), "description": shorten(cta, 30), "cta": "Learn More", "angle": tone}
    if channel_id == "INSTAGRAM_ORGANIC":
        return {"headline": shorten(outcome, 60), "body": shorten(f"{pain} Then: {outcome} #DIO #{slug(name).replace('-', '')}", 125), "cta": cta, "angle": tone}
    if channel_id in {"TIKTOK_ORGANIC", "TIKTOK_ADS"}:
        return {"headline": shorten(pain, 58), "body": shorten(f"Watch this become: {outcome}", 80), "cta": shorten(cta, 40), "angle": tone}
    if channel_id == "REDDIT_ORGANIC":
        return {"headline": shorten(f"How are {audience['name'].lower()} handling this?", 150), "body": f"{pain} We built a bounded {name} workflow around that problem. The output remains human-reviewed.", "cta": "Open the proof example", "angle": tone}
    if channel_id == "REDDIT_ADS":
        return {"headline": shorten(f"A reviewable answer to: {pain}", 150), "body": shorten(product["proof"], 180), "cta": "View Proof", "angle": tone}
    if channel_id == "GOOGLE_ADS":
        return {
            "headlines": [shorten(item, 30) for item in (product["name"], outcome, "Human-Reviewed Work", "Controlled Pilot", f"See {name} Proof", "Proof Before Promises", "Keep Human Authority", "Reviewable Output")],
            "descriptions": [shorten(product["promise"], 90), shorten(f"Built for {audience['name']}. {cta}.", 90), shorten(product["proof"], 90)],
            "cta": "Learn More",
            "angle": tone,
        }
    if channel_id == "YOUTUBE_ORGANIC":
        return {"headline": shorten(f"{name}: {outcome}", 100), "body": f"An audience-specific walkthrough for {audience['name'].lower()}. {product['proof']} {cta}.", "cta": cta, "angle": tone}
    raise ValueError(f"Unsupported channel: {channel_id}")


def validate_copy(channel: dict[str, Any], copy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field, limit_name in (("headline", "headline_limit"), ("body", "body_limit"), ("description", "description_limit")):
        if field in copy and channel.get(limit_name) and len(copy[field]) > int(channel[limit_name]):
            errors.append(f"{field} exceeds {channel[limit_name]} characters")
    for field, limit_name in (("headlines", "headline_limit"), ("descriptions", "description_limit")):
        if copy.get(field) and channel.get(limit_name):
            errors.extend(f"{field[:-1]} {index + 1} exceeds {channel[limit_name]} characters" for index, item in enumerate(copy[field]) if len(item) > int(channel[limit_name]))
    return errors


def story_markdown(story: dict[str, Any]) -> str:
    lines = [f"# {story['title']}", "", f"Story hash: `{story['story_hash']}`", f"Semantic law: `{story['semantic_law_hash']}`", f"Projection: `{story['projection_hash']}`", f"Arc family: `{story['arc_family']}`", ""]
    for index, scene in enumerate(story["scenes"], 1):
        lines.extend([f"## {index}. {scene['screen_text']}", "", f"**Role:** {scene['role']}", "", scene["narration"], "", f"Visual direction: {scene['visual']}", ""])
    lines.extend(["## Semantic boundary", "", "Creative form may change. Meaning, proof boundaries, human authority, publication hold, spend disablement and market-validation boundary may not.", ""])
    return "\n".join(lines)


def build_gamma_story_request(story: dict[str, Any], directory: Path) -> dict[str, Any]:
    blocks = [
        "\n".join([f"# {scene['screen_text']}", scene["narration"], f"Visual direction: {scene['visual']}", f"Story role: {scene['role']}"])
        for scene in story["scenes"]
    ]
    direction = story["creative_direction"]
    payload = {
        "schema": "dio.gamma.campaign_story_request.v1",
        "family_id": story["family_id"],
        "surface": story["surface"],
        "title": story["title"],
        "story_hash": story["story_hash"],
        "semantic_law_hash": story["semantic_law_hash"],
        "projection_hash": story["projection_hash"],
        "num_cards": len(story["scenes"]),
        "input_text": "\n\n---\n\n".join(blocks),
        "creative_direction": {
            "audience_archetype": direction["audience_archetype"],
            "tone": direction["tone"],
            "pacing": direction["pacing"],
            "visual_grammar": direction["visual_grammar"],
            "motion_grammar": direction["motion_grammar"],
            "surface": story["surface"],
        },
        "semantic_guardrails": story["semantic_guardrails"],
        "output_dir": str((directory / "gamma" / story["surface"]).resolve()),
        "release": {"state": "held", "visual_review_required": True, "operator_approval_required": True},
    }
    payload["request_hash"] = canonical_hash(payload)
    return payload


def _run_gamma(path: Path) -> tuple[str, str]:
    completed = subprocess.run(["node", str(ROOT / "scripts" / "run_gamma_story.js"), str(path)], cwd=ROOT, capture_output=True, text=True, timeout=540)
    if completed.returncode != 0:
        return "failed", (completed.stderr or completed.stdout or "Gamma campaign story failed").strip()[-1600:]
    return "ready", ""


def _music_tokens(value: Any) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", str(value or "").casefold()) if len(token) > 2}


def _music_catalog() -> list[dict[str, Any]]:
    root = FOUNDRY / "episodes"
    if not root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for receipt_path in sorted(root.glob("*/imports/music_choices/COMMERCIAL_MUSIC_RECEIPT.json")):
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        selected = receipt.get("selected") or {}
        episode = receipt_path.parents[2]
        audio = None
        promoted = str(selected.get("promoted_path") or "").strip()
        if promoted and (episode / promoted).is_file():
            audio = (episode / promoted).resolve()
        if audio is None:
            audio = next((candidate.resolve() for ext in ("ogg", "mp3", "wav", "m4a") if (candidate := episode / "imports" / f"music_bed.{ext}").is_file()), None)
        attribution = episode / "imports" / "MUSIC_ATTRIBUTION.md"
        rights = selected.get("rights") or {}
        if audio and attribution.is_file() and (rights.get("passed") is True or selected.get("licence_name")):
            metadata = " ".join(str(value or "") for value in (receipt.get("topic"), receipt.get("studio"), selected.get("title"), selected.get("artist"), selected.get("attribution")))
            rows.append({"path": audio, "attribution": attribution.resolve(), "receipt": receipt_path.resolve(), "metadata": metadata, "title": selected.get("title"), "artist": selected.get("artist"), "licence": selected.get("licence_name")})
    return rows


def _select_music(surface_plan: dict[str, Any], product: dict[str, Any], audience: dict[str, Any], family_id: str) -> dict[str, Any]:
    plan = dict(surface_plan["music"])
    explicit = str(os.environ.get("DIO_CAMPAIGN_MUSIC") or "").strip()
    explicit_attr = str(os.environ.get("DIO_CAMPAIGN_MUSIC_ATTRIBUTION") or "").strip()
    if explicit and explicit_attr:
        music = Path(explicit).expanduser().resolve()
        attr = Path(explicit_attr).expanduser().resolve()
        if music.is_file() and attr.is_file():
            return {**plan, "mode": "rights_recorded", "path": str(music), "attribution": str(attr), "selection_basis": "operator_environment_override"}
    wanted = _music_tokens(" ".join([plan["family"], " ".join(plan.get("keywords") or []), product["name"], audience["name"], audience["pain"], audience["outcome"]]))
    scored = []
    for row in _music_catalog():
        score = len(wanted & _music_tokens(row["metadata"]))
        tie = hashlib.sha256(f"{family_id}:{surface_plan['arc_family']}:{row['path']}".encode()).hexdigest()
        scored.append((score, tie, row))
    if scored:
        score, _tie, row = max(scored, key=lambda item: (item[0], item[1]))
        return {**plan, "mode": "rights_recorded", "path": str(row["path"]), "attribution": str(row["attribution"]), "rights_receipt": str(row["receipt"]), "title": row["title"], "artist": row["artist"], "licence": row["licence"], "selection_basis": "audience_projection_catalog_match" if score else "available_rights_catalog_tiebreak", "match_score": score}
    if plan.get("allow_silence") is True:
        return {**plan, "mode": "none", "path": "", "attribution": "", "selection_basis": "no_suitable_rights_recorded_track_available"}
    raise CampaignMediaError("LINGUA projection requires music, but no rights-recorded asset is available.")


def build_family(product: dict[str, Any], audience: dict[str, Any], channels: dict[str, Any], output_root: Path, render_reels: bool) -> dict[str, Any]:
    family_id = f"{product['id']}--{audience['id']}"
    directory = output_root / slug(product["id"]) / slug(audience["id"])
    assets = directory / "assets"
    copy_dir = directory / "copy"
    stories_dir = directory / "stories"
    source_path = ROOT / product["source_image"]
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    source = Image.open(source_path)

    law = build_semantic_law(product, audience)
    projection = build_projection_plan(law, product, audience, channels)
    projection_errors = validate_projection(law, projection)
    law_path = directory / "LINGUA_SEMANTIC_LAW.json"
    projection_path = directory / "LINGUA_PROJECTION_PLAN.json"
    write_json(law_path, law)
    write_json(projection_path, projection)

    asset_paths: dict[str, str] = {}
    for key, size in SIZES.items():
        plan = projection["surfaces"]["vertical_short"] if key in {"square_1080", "portrait_1080x1350", "vertical_1080x1920"} else projection["surfaces"]["landscape_explainer"]
        path = assets / f"{key}.jpg"
        draw_poster(source, size, product, audience, path, visual_grammar=plan["visual_grammar"])
        asset_paths[key] = relative(path)

    validation_errors = list(projection_errors)
    copy_outputs: dict[str, Any] = {}
    for channel_id, channel in channels.items():
        channel_copy = copy_package(product, audience, channel_id, projection["channel_projections"].get(channel_id) or {})
        errors = validate_copy(channel, channel_copy)
        validation_errors.extend(f"{channel_id}: {error}" for error in errors)
        payload = {"schema": "dio.marketing.channel_copy.v2", "family_id": family_id, "product": product["id"], "audience": audience["name"], "channel_id": channel_id, "format": channel["format"], "semantic_law_hash": law["semantic_law_hash"], "projection_hash": projection["projection_hash"], "channel_projection": projection["channel_projections"].get(channel_id) or {}, "asset": asset_paths.get(channel["asset"], channel["asset"]), "copy": channel_copy, "validation": {"state": "passed" if not errors else "failed", "errors": errors}, "publication": "operator_approval_required", "spend": "disabled"}
        path = copy_dir / f"{channel_id.lower()}.json"
        write_json(path, payload)
        copy_outputs[channel_id] = {"path": relative(path), "state": payload["validation"]["state"]}

    stories: dict[str, Any] = {}
    variants: dict[str, Any] = {}
    gamma_states = {"vertical_short": "request_ready", "landscape_explainer": "request_ready"}
    gamma_errors = {"vertical_short": "", "landscape_explainer": ""}
    output_specs = {
        "vertical_short": {"path": assets / "reel_1080x1920.mp4", "width": 1080, "height": 1920},
        "landscape_explainer": {"path": assets / "explainer_1920x1080.mp4", "width": 1920, "height": 1080},
    }

    for surface in ("vertical_short", "landscape_explainer"):
        story = project_story(law, projection, product, audience, surface)
        stories[surface] = story
        story_path = stories_dir / f"{surface}.json"
        write_json(story_path, story)
        md_path = stories_dir / f"{surface}.md"
        md_path.write_text(story_markdown(story), encoding="utf-8")
        plan = projection["surfaces"][surface]
        fallback_images = []
        for index, scene in enumerate(story["scenes"], 1):
            size = SIZES["vertical_1080x1920"] if surface == "vertical_short" else SIZES["youtube_1280x720"]
            image_path = assets / f"{surface}_{index:02d}_{slug(scene['role'])}.jpg"
            draw_poster(source, size, product, audience, image_path, message=scene["screen_text"], footer=scene["role"].replace("_", " ").title(), visual_grammar=plan["visual_grammar"])
            fallback_images.append(str(image_path.resolve()))
            asset_paths[f"{surface}_scene_{index:02d}"] = relative(image_path)
        gamma_request = build_gamma_story_request(story, directory)
        gamma_request_path = directory / "gamma" / surface / "GAMMA_STORY_REQUEST.json"
        write_json(gamma_request_path, gamma_request)
        gamma_receipt_path = directory / "gamma" / surface / "GAMMA_STORY_RECEIPT.json"
        variants[surface] = {
            "surface": surface,
            "story": {"path": str(story_path.resolve()), "story_hash": story["story_hash"], "scenes": story["scenes"]},
            "scene_images_fallback": fallback_images,
            "gamma": {"required": True, "request": str(gamma_request_path.resolve()), "request_hash": gamma_request["request_hash"], "receipt": str(gamma_receipt_path.resolve())},
            "voice": {"required": True, **plan["voice"]},
            "music": _select_music(plan, product, audience, family_id),
            "output": {"path": str(output_specs[surface]["path"].resolve()), "width": output_specs[surface]["width"], "height": output_specs[surface]["height"]},
        }

    request = {
        "schema": "nichefoundry.dio_campaign_production_request.v3",
        "family_id": family_id,
        "title": f"{product['short_name']} for {audience['name']}",
        "product": product["id"],
        "audience": audience["name"],
        "proof_asset": str((ROOT / product["proof_asset"]).resolve()),
        "source_image": str(source_path.resolve()),
        "semantic_law": {"path": str(law_path.resolve()), "semantic_law_hash": law["semantic_law_hash"], "source_hash": law["source_hash"]},
        "projection": {"path": str(projection_path.resolve()), "projection_hash": projection["projection_hash"], "creative_fingerprint": projection["creative_fingerprint"], "audience_archetype": projection["audience_archetype"]},
        "variants": variants,
        "release": {"state": "held", "operator_approval_required": True, "spend": "disabled", "market_validation_claimed": False, "authority_created": False},
    }
    request["request_hash"] = canonical_hash(request)
    request_path = directory / "NICHEFOUNDRY_PRODUCTION_REQUEST.json"
    write_json(request_path, request)

    media_state = "brief_ready"
    media_error = ""
    media_receipt: dict[str, Any] = {}
    if render_reels and not projection_errors:
        for surface in variants:
            gamma_states[surface], gamma_errors[surface] = _run_gamma(Path(variants[surface]["gamma"]["request"]))
        if all(state == "ready" for state in gamma_states.values()):
            try:
                media_receipt = render_campaign_media_v3(request_path, nichefoundry_root=FOUNDRY)
                media_state = str(media_receipt.get("state") or "ready")
            except (CampaignMediaError, OSError, subprocess.SubprocessError, ValueError) as exc:
                media_state = "failed"
                media_error = str(exc)[-1600:]
        else:
            media_state = "blocked_by_gamma"
    elif render_reels:
        media_state = "blocked_by_lingua_projection"
        media_error = " | ".join(projection_errors)

    if media_state == "ready":
        asset_paths["reel_1080x1920"] = relative(output_specs["vertical_short"]["path"])
        asset_paths["explainer_1920x1080"] = relative(output_specs["landscape_explainer"]["path"])

    gamma_state = "ready" if all(state == "ready" for state in gamma_states.values()) else ("request_ready" if not render_reels else "failed")
    voice_state = "ready" if media_state == "ready" else ("not_started" if not render_reels else "failed")
    voice_variants = media_receipt.get("variants") or {}
    voice_providers = sorted({str((row.get("voice") or {}).get("provider") or "") for row in voice_variants.values() if (row.get("voice") or {}).get("provider")})
    external_errors = [error for error in [*gamma_errors.values(), media_error] if error]
    failed_media = media_state in {"failed", "blocked_by_gamma", "blocked_by_lingua_projection"}

    family = {
        "schema": "dio.marketing.creative_family.v3",
        "family_id": family_id,
        "generated_at": utc_now(),
        "product": {"id": product["id"], "name": product["name"], "offer": product["offer"]},
        "audience": audience,
        "landing_page": product["landing_page"],
        "proof_asset": product["proof_asset"],
        "semantic_law": {"state": "ready" if not projection_errors else "failed", "path": relative(law_path), "semantic_law_hash": law["semantic_law_hash"], "source_hash": law["source_hash"]},
        "creative_projection": {"state": "ready" if not projection_errors else "failed", "path": relative(projection_path), "projection_hash": projection["projection_hash"], "creative_fingerprint": projection["creative_fingerprint"], "audience_archetype": projection["audience_archetype"], "errors": projection_errors},
        "story": {
            "state": "ready",
            "path": relative(stories_dir / "landscape_explainer.json"),
            "markdown": relative(stories_dir / "landscape_explainer.md"),
            "story_hash": stories["landscape_explainer"]["story_hash"],
            "scene_count": len(stories["landscape_explainer"]["scenes"]),
            "arc": stories["landscape_explainer"]["arc"],
            "variants": {surface: {"path": relative(stories_dir / f"{surface}.json"), "markdown": relative(stories_dir / f"{surface}.md"), "story_hash": stories[surface]["story_hash"], "scene_count": len(stories[surface]["scenes"]), "arc": stories[surface]["arc"], "arc_family": stories[surface]["arc_family"]} for surface in stories},
        },
        "assets": asset_paths,
        "copy": copy_outputs,
        "gamma": {"required_for_media": True, "state": gamma_state, "variants": {surface: {"state": gamma_states[surface], "request": relative(Path(variants[surface]["gamma"]["request"])), "receipt": relative(Path(variants[surface]["gamma"]["receipt"])) if Path(variants[surface]["gamma"]["receipt"]).is_file() else "", "error": gamma_errors[surface]} for surface in variants}, "error": " | ".join(error for error in gamma_errors.values() if error)},
        "voice": {"required_for_media": True, "state": voice_state, "providers": voice_providers or sorted({variants[s]["voice"]["provider"] for s in variants}), "projection_selected": True, "receipts": {surface: str((row.get("voice") or {}).get("receipt") or "") for surface, row in voice_variants.items()}},
        "piper": {"required_for_media": False, "provider": "projection_selected", "remote_fallback": False, "state": voice_state, "receipt": ""},
        "nichefoundry": {"request": relative(request_path), "reel_state": media_state, "reel_error": media_error, "long_form_state": media_state, "media_receipt": relative(directory / "media" / "CAMPAIGN_MEDIA_RECEIPT.json") if (directory / "media" / "CAMPAIGN_MEDIA_RECEIPT.json").is_file() else ""},
        "validation": {"state": "passed" if not validation_errors and not external_errors and not failed_media else "failed", "errors": validation_errors + external_errors},
        "governance": {"state": "draft_ready", "publication": "held", "spend": "disabled", "promotion": "operator_required", "market_validation_claimed": False, "authority_created": False},
    }
    write_json(directory / "FAMILY.json", family)
    return family


def build(output_root: Path = DEFAULT_OUTPUT, render_reels: bool = True, limit: int = 0) -> dict[str, Any]:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    output_root.mkdir(parents=True, exist_ok=True)
    families = []
    for product in matrix["products"]:
        for audience in product["audiences"]:
            families.append(build_family(product, audience, matrix["channels"], output_root, render_reels))
            if limit and len(families) >= limit:
                break
        if limit and len(families) >= limit:
            break
    collisions = []
    for index, left in enumerate(families):
        for right in families[index + 1:]:
            lp = left["creative_projection"]
            rp = right["creative_projection"]
            if lp["creative_fingerprint"] == rp["creative_fingerprint"] and lp["audience_archetype"] != rp["audience_archetype"]:
                collisions.append({"left": left["family_id"], "right": right["family_id"], "distance": creative_distance(lp, rp)})
    registry = {
        "schema": "dio.marketing.creative_family_registry.v3",
        "generated_at": utc_now(),
        "factory_policy": matrix["factory_policy"],
        "creative_diversity": {"state": "passed" if not collisions else "failed", "distinct_fingerprints": len({f["creative_projection"]["creative_fingerprint"] for f in families}), "cross_archetype_collisions": collisions, "law": "semantic invariance does not require representational invariance"},
        "summary": {
            "products": len({f["product"]["id"] for f in families}),
            "audiences": len(families),
            "channel_packages": sum(len(f["copy"]) for f in families),
            "stories_ready": sum(f["story"]["state"] == "ready" for f in families),
            "gamma_stories_ready": sum(f["gamma"]["state"] == "ready" for f in families),
            "voice_narrations_ready": sum(f["voice"]["state"] == "ready" for f in families),
            "piper_narrations_ready": sum(f["piper"]["state"] == "ready" for f in families),
            "reels_ready": sum(f["nichefoundry"]["reel_state"] == "ready" for f in families),
            "long_form_ready": sum(f["nichefoundry"]["long_form_state"] == "ready" for f in families),
            "validation_failures": sum(f["validation"]["state"] != "passed" for f in families),
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
            "source_lineage": {"creative_family": family_id, "semantic_law": family["semantic_law"]["path"], "creative_projection": family["creative_projection"]["path"], "campaign_story": family["story"]["path"]},
        })
    copy = copy_payload["copy"]
    hook = copy.get("headline") or (copy.get("headlines") or [family["product"]["name"]])[0]
    body = copy.get("body") or " | ".join(copy.get("descriptions") or [])
    content = store.add_content(campaign_id, {"content_id": content_id, "channel_id": channel_id, "format": copy_payload["format"], "hook": hook, "body": body, "asset_path": copy_payload["asset"], "source_language": "English", "artifact_type": "multichannel_campaign_family", "semantic_object_id": f"MARKET-{campaign_id}", "cta": copy.get("cta") or ""})
    return {"status": "draft_promoted", "campaign": campaign, "content": content, "publication": "held", "spend": "disabled"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build LINGUA-projected DIO campaign families and narrated NicheFoundry media.")
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
    print(json.dumps(build(args.output, not args.no_reels, args.limit)["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
