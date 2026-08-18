#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts import build_hustle_campaign_factory as hustle
from scripts import lingua_marketing_learning as learning


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = hustle.DEFAULT_OUTPUT


def _matrix() -> dict[str, Any]:
    return json.loads(hustle.MATRIX.read_text(encoding="utf-8"))


def _lookup(matrix: dict[str, Any], product_id: str, audience_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    product = next(row for row in matrix["products"] if row["id"] == product_id)
    audience = next(row for row in product["audiences"] if row["id"] == audience_id)
    return product, audience


def _apply_channel_learning(
    *,
    channel_payload: dict[str, Any],
    product: dict[str, Any],
    audience: dict[str, Any],
    channel_id: str,
    learning_root: Path,
) -> dict[str, Any]:
    strategy = learning.apply_strategy_learning(
        dict(channel_payload.get("commercial_strategy") or {}),
        product_id=product["id"],
        audience=audience["name"],
        channel_id=channel_id,
        learning_root=learning_root,
    )
    channel_payload["commercial_strategy"] = strategy
    recommendation = dict(strategy.get("lingua_learning") or {})
    preferred_hook = str(recommendation.get("preferred_hook") or "").strip()
    copy = dict(channel_payload.get("copy") or {})
    if preferred_hook:
        if copy.get("headlines"):
            current = [str(item) for item in copy["headlines"]]
            learned = hustle.base.shorten(preferred_hook, 30)
            copy["headlines"] = [learned] + [item for item in current if item != learned]
        elif channel_id != "REDDIT_ORGANIC":
            limit = {
                "LINKEDIN_ORGANIC": 70,
                "FACEBOOK_PAGE": 40,
                "META_ADS": 40,
                "INSTAGRAM_ORGANIC": 60,
                "TIKTOK_ORGANIC": 58,
                "TIKTOK_ADS": 58,
                "REDDIT_ADS": 150,
                "YOUTUBE_ORGANIC": 100,
            }.get(channel_id, 78)
            copy["headline"] = hustle.base.shorten(preferred_hook, limit)
    copy["lingua_learning"] = recommendation
    channel_payload["copy"] = copy
    channel_payload["learning_authority"] = {
        "draft_reuse_only": True,
        "direct_learning_to_execution": False,
        "publication": False,
        "spend": False,
    }
    return channel_payload


def _apply_reel_learning(
    *,
    family: dict[str, Any],
    product: dict[str, Any],
    audience: dict[str, Any],
    output_root: Path,
    render_reels: bool,
    learning_root: Path,
) -> None:
    recommendation = learning.recommend(
        product_id=product["id"],
        audience=audience["name"],
        channel_id="TIKTOK_ORGANIC",
        learning_root=learning_root,
    )
    family.setdefault("lingua_learning", {})["reel"] = recommendation
    preferred_hook = str(recommendation.get("preferred_hook") or "").strip()
    if not preferred_hook:
        return

    directory = output_root / hustle.base.slug(product["id"]) / hustle.base.slug(audience["id"])
    assets = directory / "assets"
    source = hustle.base.Image.open(ROOT / product["source_image"])
    first_scene = assets / "01_hook.jpg"
    hustle.base.draw_poster(
        source,
        hustle.base.SIZES["vertical_1080x1920"],
        product,
        audience,
        first_scene,
        preferred_hook,
        "LINGUA-LEARNED HOOK / HELD DRAFT",
    )

    request_path = directory / "NICHEFOUNDRY_PRODUCTION_REQUEST.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    learned_strategy = learning.apply_strategy_learning(
        dict(request.get("commercial_strategy") or {}),
        product_id=product["id"],
        audience=audience["name"],
        channel_id="TIKTOK_ORGANIC",
        learning_root=learning_root,
    )
    request["commercial_strategy"] = learned_strategy
    request["script_brief"]["beats"] = hustle.reel_script(learned_strategy, product)
    request["script_brief"]["learning_authority"] = {
        "source": "LINGUA",
        "draft_reuse_only": True,
        "direct_learning_to_execution": False,
        "publication": False,
        "spend": False,
    }
    request["request_hash"] = "sha256:" + hustle.hashlib.sha256(
        json.dumps(request, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    hustle.base.write_json(request_path, request)
    if render_reels:
        state, error = hustle._render_hustle_reel(request_path)
        family["nichefoundry"]["reel_state"] = state
        family["nichefoundry"]["reel_error"] = error
        if error:
            family["validation"]["state"] = "failed"
            family["validation"].setdefault("errors", []).append(error)


def build(
    output_root: Path = DEFAULT_OUTPUT,
    *,
    render_reels: bool = True,
    limit: int = 0,
    observe_market: bool = True,
) -> dict[str, Any]:
    output_root = output_root.resolve()
    learning_root = learning.state_root_for_output(output_root) / "commercial_learning"
    observation = (
        learning.observe_market_outcomes()
        if observe_market and learning_root == learning.LEARNING_ROOT
        else {
            "schema": "dio.lingua.commercial_learning_observation.v1",
            "status": "skipped_for_isolated_build",
            "candidates": 0,
            "direct_learning_to_execution": False,
        }
    )

    # Keep the proven commercial renderer, but defer reels until LINGUA has had a
    # chance to resolve approved and negative commercial patterns for the next draft.
    registry = hustle.build(output_root, render_reels=False, limit=limit)
    matrix = _matrix()
    registered = 0
    registration_errors: list[dict[str, Any]] = []

    for family in registry.get("families") or []:
        product_id = str((family.get("product") or {}).get("id") or "")
        audience_id = str((family.get("audience") or {}).get("id") or "")
        product, audience = _lookup(matrix, product_id, audience_id)
        directory = output_root / hustle.base.slug(product_id) / hustle.base.slug(audience_id)
        for channel_id, channel_meta in (family.get("copy") or {}).items():
            payload_path = learning.resolve_path(channel_meta["path"])
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload = _apply_channel_learning(
                channel_payload=payload,
                product=product,
                audience=audience,
                channel_id=channel_id,
                learning_root=learning_root,
            )
            quality = hustle.commercial_score(product, audience, channel_id, payload["copy"])
            payload["commercial_quality"] = quality
            payload["validation"]["state"] = "passed" if quality["state"] == "passed" and not payload["validation"].get("errors") else "failed"
            hustle.base.write_json(payload_path, payload)
            family["copy"][channel_id]["commercial_score"] = quality["score"]
            family["copy"][channel_id]["lingua_reuse_state"] = payload["copy"]["lingua_learning"]["reuse_state"]
            try:
                learning.register_channel_semantics(
                    family=family,
                    channel_id=channel_id,
                    channel_payload=payload,
                    state_root=learning.state_root_for_output(output_root),
                )
                registered += 1
            except Exception as exc:
                registration_errors.append({
                    "family_id": family.get("family_id"),
                    "channel_id": channel_id,
                    "error": str(exc),
                })

        _apply_reel_learning(
            family=family,
            product=product,
            audience=audience,
            output_root=output_root,
            render_reels=render_reels,
            learning_root=learning_root,
        )
        family["governance"]["direct_learning_to_execution"] = False
        family["governance"]["learning_reuse"] = "held_drafts_only"
        hustle.base.write_json(directory / "FAMILY.json", family)

    registry["schema"] = "dio.marketing.creative_family_registry.v3"
    registry["lingua_learning"] = {
        "observation": observation,
        "semantic_objects_registered": registered,
        "registration_errors": registration_errors,
        "status": learning.status(learning_root),
        "direct_learning_to_execution": False,
        "publication": False,
        "spend": False,
    }
    registry["summary"]["lingua_semantic_objects_registered"] = registered
    registry["summary"]["lingua_registration_errors"] = len(registration_errors)
    registry["summary"]["lingua_reuse_hits"] = sum(
        meta.get("lingua_reuse_state") == "hit"
        for family in registry.get("families") or []
        for meta in (family.get("copy") or {}).values()
    )
    hustle.base.write_json(output_root / "CREATIVE_FAMILY_REGISTRY.json", registry)
    return registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Build NicheFoundry campaigns with LINGUA commercial memory and held-draft reuse.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-reels", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--no-observe-market", action="store_true")
    args = parser.parse_args()
    result = build(
        args.output,
        render_reels=not args.no_reels,
        limit=args.limit,
        observe_market=not args.no_observe_market,
    )
    print(json.dumps({
        **result["summary"],
        "lingua_learning": result["lingua_learning"]["status"],
    }, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
