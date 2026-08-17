#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from scripts import build_multichannel_campaign_factory as base


ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK = ROOT / "config" / "marketing_sales_playbook.json"
MATRIX = base.MATRIX
DEFAULT_OUTPUT = base.DEFAULT_OUTPUT

PRODUCT_COMMERCIAL = {
    "EVIDEX_PACK": {"family": "Evidence & Assurance", "launch_price_zar": 7900},
    "HOMS_ASSESS": {"family": "Education", "launch_price_zar": 5900},
    "HOMS_LEARNING": {"family": "Education", "launch_price_zar": 5900},
    "SOPHIA_REVIEW": {"family": "Research & Learning", "launch_price_zar": 5900},
    "VAMP_ACADEMIC": {"family": "Performance & People", "launch_price_zar": 4900},
    "DOCUMENT_STUDIO": {"family": "Documents & Rooms", "launch_price_zar": 4900},
}

CONVERSION_CHANNELS = {"META_ADS", "TIKTOK_ADS", "GOOGLE_ADS"}


def load_playbook() -> dict[str, Any]:
    return json.loads(PLAYBOOK.read_text(encoding="utf-8"))


def money(value: int) -> str:
    return f"R {value:,} ZAR"


def commercial_config(product: dict[str, Any]) -> dict[str, Any]:
    configured = PRODUCT_COMMERCIAL.get(product["id"])
    if configured:
        return configured
    return {
        "family": str(product.get("commercial_family") or "Professional Workflow"),
        "launch_price_zar": int(product.get("launch_price_zar") or 7900),
    }


def cost_of_inaction(audience: dict[str, Any]) -> str:
    pain = str(audience["pain"]).rstrip(".")
    return f"Leave it manual and the same rework, searching and deadline pressure keeps recurring: {pain.lower()}."


def commercial_strategy(product: dict[str, Any], audience: dict[str, Any], playbook: dict[str, Any] | None = None) -> dict[str, Any]:
    playbook = playbook or load_playbook()
    commercial = commercial_config(product)
    price = int(commercial["launch_price_zar"])
    objections = playbook["objections"]
    selected_objections = [
        objections["implementation"],
        objections["black_box"],
        objections["authority"],
        objections["data_scope"],
    ]
    pain = str(audience["pain"])
    outcome = str(audience["outcome"])
    name = str(product["short_name"])
    return {
        "schema": "dio.marketing.commercial_strategy.v1",
        "target_buyer": audience["name"],
        "buyer_pain": pain,
        "desired_outcome": outcome,
        "cost_of_inaction": cost_of_inaction(audience),
        "offer": {
            "name": product["offer"],
            "scope": "one bounded case",
            "launch_price_zar": price,
            "price_label": money(price),
            "expansion_rule": "Expand only after the bounded pilot produces inspectable value and the operator chooses to continue.",
        },
        "proof_angle": product["proof"],
        "promise": product["promise"],
        "hooks": [
            base.shorten(pain, 78),
            base.shorten(outcome, 78),
            base.shorten(f"{name}: one bounded proof-backed pilot from {money(price)}.", 78),
        ],
        "objections": selected_objections,
        "cta": product["cta"],
        "truth_boundaries": [
            "Controlled proof is not guaranteed ROI or customer validation.",
            "Consequential professional decisions remain human-owned.",
            "No automatic publication or ad spend is created by this strategy.",
            "No fabricated scarcity, urgency, certification or outcome claims.",
        ],
        "commercial_family": commercial["family"],
    }


def _offer_line(strategy: dict[str, Any]) -> str:
    offer = strategy["offer"]
    return f"{offer['price_label']} for {offer['scope']}."


def _objection(strategy: dict[str, Any], index: int = 0) -> dict[str, str]:
    rows = strategy["objections"]
    return rows[index % len(rows)]


def hustle_copy_package(
    product: dict[str, Any],
    audience: dict[str, Any],
    channel_id: str,
    playbook: dict[str, Any] | None = None,
) -> dict[str, Any]:
    playbook = playbook or load_playbook()
    strategy = commercial_strategy(product, audience, playbook)
    name = product["short_name"]
    pain = strategy["buyer_pain"]
    outcome = strategy["desired_outcome"]
    price = strategy["offer"]["price_label"]
    cta = product["cta"]
    objection = _objection(strategy, 0)
    stage = playbook["funnel_by_channel"][channel_id]
    tone = playbook["tone_by_channel"][channel_id]
    common = {
        "funnel_stage": stage,
        "tone": tone,
        "objection": objection["question"],
        "objection_answer": objection["answer"],
        "offer": _offer_line(strategy),
        "proof_angle": product["proof"],
        "truth_boundary": "Human authority stays with the authorised reviewer.",
    }

    if channel_id == "LINKEDIN_ORGANIC":
        copy = {
            "headline": base.shorten(outcome, 70),
            "body": base.shorten(f"{pain} {name} turns one bounded case into review-ready work with visible proof. {cta}.", 150),
            "cta": cta,
            "angle": "authority plus proof",
        }
    elif channel_id == "FACEBOOK_PAGE":
        copy = {
            "headline": base.shorten(outcome, 40),
            "body": base.shorten(f"Still fighting this manually? {name} starts with one bounded case at {price}. Human review stays in control.", 125),
            "cta": cta,
            "angle": "pain relief plus offer",
        }
    elif channel_id == "META_ADS":
        copy = {
            "headline": base.shorten(outcome, 40),
            "body": base.shorten(f"{pain} Start one proof-backed {name} pilot at {price}. One bounded case. Human decision.", 125),
            "description": base.shorten(f"Pilot from {price}", 30),
            "cta": "Learn More",
            "angle": "direct response proof offer",
        }
    elif channel_id == "INSTAGRAM_ORGANIC":
        copy = {
            "headline": base.shorten(strategy["hooks"][0], 60),
            "body": base.shorten(f"Messy workflow → review-ready result. One bounded {name} pilot. {cta}. #DIO #{base.slug(name).replace('-', '')}", 125),
            "cta": cta,
            "angle": "visual before-after",
        }
    elif channel_id == "TIKTOK_ORGANIC":
        copy = {
            "headline": base.shorten(strategy["hooks"][0], 58),
            "body": base.shorten(f"Watch {name} turn one messy case into proof-backed review work.", 80),
            "cta": base.shorten(cta, 40),
            "angle": "scroll-stop proof",
        }
    elif channel_id == "TIKTOK_ADS":
        copy = {
            "headline": base.shorten(strategy["hooks"][0], 58),
            "body": base.shorten(f"One bounded {name} pilot. {price}. Proof-backed. Human-owned decision.", 80),
            "cta": base.shorten(cta, 40),
            "angle": "fast direct response",
        }
    elif channel_id == "REDDIT_ORGANIC":
        copy = {
            "headline": base.shorten(f"How are {audience['name'].lower()} handling this without losing the review trail?", 150),
            "body": (
                f"Recurring problem: {pain.lower()} We built a bounded {name} workflow that prepares the work, shows its proof and keeps the professional decision with the human reviewer. "
                "Curious how others are solving the same handoff without adding another black box."
            ),
            "cta": "Open the proof example",
            "angle": "credible peer discussion",
        }
    elif channel_id == "REDDIT_ADS":
        copy = {
            "headline": base.shorten(f"A proof-backed first pass for: {pain}", 150),
            "body": base.shorten(f"{product['proof']} Start with one bounded case before expanding.", 180),
            "cta": "View Proof",
            "angle": "transparent proof and low-risk entry",
        }
    elif channel_id == "GOOGLE_ADS":
        copy = {
            "headlines": [
                base.shorten(product["name"], 30),
                base.shorten(outcome, 30),
                base.shorten(f"Pilot From {price}", 30),
                base.shorten("One Bounded Case", 30),
                base.shorten("Proof-Backed Workflow", 30),
                base.shorten("Audit-Ready Receipts", 30),
                base.shorten("Keep Human Authority", 30),
                base.shorten("Review-Ready Output", 30),
                base.shorten(f"For {audience['name']}", 30),
                base.shorten("Start Small. Prove Value.", 30),
            ],
            "descriptions": [
                base.shorten(f"{product['promise']} Start one bounded pilot at {price}.", 90),
                base.shorten(f"Built for {audience['name'].lower()}. Proof and human review stay visible.", 90),
                base.shorten(f"{product['proof']} Inspect the workflow before expanding scope.", 90),
                base.shorten(f"One bounded case. {price}. No automatic authority, publication or lock-in.", 90),
            ],
            "cta": "Learn More",
            "angle": "high-intent fixed pilot",
        }
    elif channel_id == "YOUTUBE_ORGANIC":
        copy = {
            "headline": base.shorten(f"{name}: stop doing this workflow the hard way", 100),
            "body": f"For {audience['name'].lower()}: {pain} This proof-led walkthrough shows the problem, the bounded route, the evidence, the {price} pilot offer and the human authority boundary. {cta}.",
            "cta": cta,
            "angle": "problem-proof-offer explainer",
            "chapters": ["The expensive manual loop", "What DIO changes", "Proof, not promises", "The bounded pilot", "What remains human"],
        }
    else:
        raise ValueError(f"Unsupported channel: {channel_id}")

    copy.update(common)
    return copy


def commercial_score(
    product: dict[str, Any],
    audience: dict[str, Any],
    channel_id: str,
    copy: dict[str, Any],
    playbook: dict[str, Any] | None = None,
) -> dict[str, Any]:
    playbook = playbook or load_playbook()
    strategy = commercial_strategy(product, audience, playbook)
    weights = playbook["commercial_quality"]["weights"]
    text = " ".join(
        str(value)
        for key, value in copy.items()
        if key in {"headline", "body", "description", "cta", "offer", "proof_angle", "objection_answer"}
    ).lower()
    if copy.get("headlines"):
        text += " " + " ".join(copy["headlines"]).lower()
    if copy.get("descriptions"):
        text += " " + " ".join(copy["descriptions"]).lower()
    price_label = strategy["offer"]["price_label"].lower()
    checks = {
        "buyer_specificity": bool(strategy["target_buyer"]),
        "pain_or_outcome_hook": bool(copy.get("headline") or copy.get("headlines")),
        "offer_clarity": bool(copy.get("offer")) and (channel_id not in CONVERSION_CHANNELS or price_label in text),
        "proof_specificity": bool(copy.get("proof_angle")),
        "objection_handling": bool(copy.get("objection") and copy.get("objection_answer")),
        "cta_specificity": bool(copy.get("cta")) and str(copy.get("cta")).lower() not in {"click here", "submit"},
        "truth_boundary": bool(copy.get("truth_boundary")),
    }
    score = sum(int(weights[key]) for key, passed in checks.items() if passed)
    return {
        "schema": "dio.marketing.commercial_quality.v1",
        "score": score,
        "minimum_score": int(playbook["commercial_quality"]["minimum_score"]),
        "state": "passed" if score >= int(playbook["commercial_quality"]["minimum_score"]) else "failed",
        "checks": checks,
    }


def reel_script(strategy: dict[str, Any], product: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"beat": "hook", "start_second": 0, "end_second": 2, "message": strategy["hooks"][0], "purpose": "stop the scroll"},
        {"beat": "stakes", "start_second": 2, "end_second": 6, "message": strategy["cost_of_inaction"], "purpose": "make the recurring cost visible without inventing losses"},
        {"beat": "proof", "start_second": 6, "end_second": 11, "message": product["proof"], "purpose": "replace hype with inspectable proof"},
        {"beat": "offer", "start_second": 11, "end_second": 15, "message": _offer_line(strategy), "purpose": "make the first commercial step obvious"},
        {"beat": "action", "start_second": 15, "end_second": 20, "message": product["cta"], "purpose": "ask for one concrete next action"},
    ]


def _render_hustle_reel(request_path: Path) -> tuple[str, str]:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    output = Path(request["outputs"]["vertical_reel"])
    receipt = output.parent / "NICHEFOUNDRY_REEL_RECEIPT.json"
    existing = json.loads(receipt.read_text(encoding="utf-8")) if receipt.is_file() else {}
    current = output.is_file() and output.stat().st_size > 10000 and existing.get("request_hash") == request["request_hash"]
    error = ""
    if not current:
        completed = subprocess.run(
            ["node", str(base.FOUNDRY / "scripts" / "build_dio_campaign_reel.js"), str(request_path)],
            cwd=base.FOUNDRY,
            capture_output=True,
            text=True,
            timeout=240,
        )
        if completed.returncode != 0:
            error = (completed.stderr or completed.stdout).strip()[-800:]
    state = "ready" if output.is_file() and output.stat().st_size > 10000 else ("failed" if error else "brief_ready")
    return state, error


def upgrade_family(
    product: dict[str, Any],
    audience: dict[str, Any],
    channels: dict[str, Any],
    output_root: Path,
    render_reels: bool,
    playbook: dict[str, Any],
) -> dict[str, Any]:
    family_id = f"{product['id']}--{audience['id']}"
    directory = output_root / base.slug(product["id"]) / base.slug(audience["id"])
    assets = directory / "assets"
    copy_dir = directory / "copy"
    strategy = commercial_strategy(product, audience, playbook)
    source_path = ROOT / product["source_image"]
    source = base.Image.open(source_path)

    scene_rows = [
        ("01_hook.jpg", strategy["hooks"][0], "STOP THE LOOP"),
        ("02_stakes.jpg", strategy["cost_of_inaction"], "THE COST IS RECURRING WORK"),
        ("03_proof.jpg", product["proof"], "PROOF BEFORE PROMISES"),
        ("04_offer.jpg", _offer_line(strategy), "ONE BOUNDED PILOT"),
        ("05_action.jpg", strategy["desired_outcome"], product["cta"]),
    ]
    scene_paths: list[str] = []
    for filename, message, footer in scene_rows:
        path = assets / filename
        base.draw_poster(source, base.SIZES["vertical_1080x1920"], product, audience, path, message, footer)
        scene_paths.append(str(path.resolve()))

    copy_outputs: dict[str, Any] = {}
    validation_errors: list[str] = []
    scores: list[int] = []
    for channel_id, channel in channels.items():
        channel_copy = hustle_copy_package(product, audience, channel_id, playbook)
        errors = base.validate_copy(channel, channel_copy)
        quality = commercial_score(product, audience, channel_id, channel_copy, playbook)
        if quality["state"] != "passed":
            errors.append(f"commercial score {quality['score']} below {quality['minimum_score']}")
        validation_errors.extend(f"{channel_id}: {error}" for error in errors)
        scores.append(int(quality["score"]))
        payload = {
            "schema": "dio.marketing.channel_copy.v2",
            "family_id": family_id,
            "product": product["id"],
            "audience": audience["name"],
            "channel_id": channel_id,
            "format": channel["format"],
            "asset": str((assets / f"{channel['asset']}.jpg").resolve()) if channel["asset"] in base.SIZES else channel["asset"],
            "commercial_strategy": strategy,
            "copy": channel_copy,
            "commercial_quality": quality,
            "validation": {"state": "passed" if not errors else "failed", "errors": errors},
            "publication": "operator_approval_required",
            "spend": "disabled",
        }
        path = copy_dir / f"{channel_id.lower()}.json"
        base.write_json(path, payload)
        copy_outputs[channel_id] = {"path": base.relative(path), "state": payload["validation"]["state"], "commercial_score": quality["score"]}

    request = {
        "schema": "nichefoundry.dio_campaign_production_request.v2",
        "family_id": family_id,
        "title": f"{product['short_name']} for {audience['name']}",
        "product": product["id"],
        "audience": audience["name"],
        "proof_asset": str((ROOT / product["proof_asset"]).resolve()),
        "source_image": str(source_path.resolve()),
        "scene_images": scene_paths,
        "commercial_strategy": strategy,
        "script_brief": {
            "target_seconds": 20,
            "first_hook_deadline_seconds": 2,
            "beats": reel_script(strategy, product),
            "voice_style": "confident professional operator; urgent only where the buyer problem is genuinely urgent; never hype certainty",
            "on_screen_rule": "one idea per scene; price and bounded scope visible before the CTA",
        },
        "music": {"path": str(base.MUSIC.resolve()), "attribution": str(base.MUSIC_ATTRIBUTION.resolve()), "voice_required": False},
        "outputs": {
            "vertical_reel": str((assets / "reel_1080x1920.mp4").resolve()),
            "long_form_explainer": {
                "state": "brief_ready",
                "target_seconds": 60,
                "requires_operator_script_review": True,
                "story_arc": ["pain", "cost of inaction", "proof", "bounded offer", "objection answer", "human authority boundary", "CTA"],
            },
        },
        "release": {"state": "held", "operator_approval_required": True},
        "spend": {"state": "disabled", "operator_approval_required": True},
    }
    request["request_hash"] = "sha256:" + hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()
    request_path = directory / "NICHEFOUNDRY_PRODUCTION_REQUEST.json"
    base.write_json(request_path, request)

    reel_state, reel_error = ("brief_ready", "")
    if render_reels:
        reel_state, reel_error = _render_hustle_reel(request_path)
    if reel_error:
        validation_errors.append(reel_error)

    asset_paths = {
        key: base.relative(assets / f"{key}.jpg")
        for key in base.SIZES
        if (assets / f"{key}.jpg").is_file()
    }
    reel_path = assets / "reel_1080x1920.mp4"
    if reel_path.is_file() and reel_path.stat().st_size > 10000:
        asset_paths["reel_1080x1920"] = base.relative(reel_path)

    family = {
        "schema": "dio.marketing.creative_family.v2",
        "family_id": family_id,
        "generated_at": base.utc_now(),
        "product": {"id": product["id"], "name": product["name"], "offer": product["offer"]},
        "audience": audience,
        "commercial_strategy": strategy,
        "commercial_quality": {
            "minimum_channel_score": min(scores) if scores else 0,
            "average_channel_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "all_channels_passed": all(score >= int(playbook["commercial_quality"]["minimum_score"]) for score in scores),
        },
        "landing_page": product["landing_page"],
        "proof_asset": product["proof_asset"],
        "assets": asset_paths,
        "sales_scenes": [base.relative(Path(path)) for path in scene_paths],
        "copy": copy_outputs,
        "nichefoundry": {"request": base.relative(request_path), "reel_state": reel_state, "reel_error": reel_error, "long_form_state": "brief_ready"},
        "validation": {"state": "passed" if not validation_errors and reel_state != "failed" else "failed", "errors": validation_errors},
        "governance": {"state": "draft_ready", "publication": "held", "spend": "disabled", "promotion": "operator_required"},
    }
    base.write_json(directory / "FAMILY.json", family)
    return family


def build(output_root: Path = DEFAULT_OUTPUT, render_reels: bool = True, limit: int = 0) -> dict[str, Any]:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    playbook = load_playbook()
    # Preserve the proven image/asset machinery, but defer reel rendering until the
    # commercial strategy and five-beat script have replaced the legacy 3-scene brief.
    base.build(output_root, render_reels=False, limit=limit)
    families: list[dict[str, Any]] = []
    for product in matrix["products"]:
        for audience in product["audiences"]:
            families.append(upgrade_family(product, audience, matrix["channels"], output_root, render_reels, playbook))
            if limit and len(families) >= limit:
                break
        if limit and len(families) >= limit:
            break
    registry = {
        "schema": "dio.marketing.creative_family_registry.v2",
        "generated_at": base.utc_now(),
        "factory_policy": matrix["factory_policy"],
        "sales_playbook": base.relative(PLAYBOOK),
        "summary": {
            "products": len({family["product"]["id"] for family in families}),
            "audiences": len(families),
            "channel_packages": sum(len(family["copy"]) for family in families),
            "poster_assets": sum(len([key for key in family["assets"] if key != "reel_1080x1920"]) for family in families),
            "reels_ready": sum(family["nichefoundry"]["reel_state"] == "ready" for family in families),
            "commercial_failures": sum(not family["commercial_quality"]["all_channels_passed"] for family in families),
            "validation_failures": sum(family["validation"]["state"] != "passed" for family in families),
        },
        "families": families,
    }
    base.write_json(output_root / "CREATIVE_FAMILY_REGISTRY.json", registry)
    return registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Build commercially sharp, proof-backed DIO campaign families without weakening governance.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-reels", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    result = build(args.output, render_reels=not args.no_reels, limit=args.limit)
    print(json.dumps(result["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
