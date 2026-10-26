#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT_BOOTSTRAP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_BOOTSTRAP))

from scripts import _product_class_campaign_batch_legacy as legacy  # noqa: E402


ROOT = legacy.ROOT
VIDEO_REGISTRY = legacy.VIDEO_REGISTRY
_legacy_build_ads_and_reel = legacy.build_ads_and_reel


def _read_request_output(family: dict[str, Any]) -> tuple[Path | None, Path | None]:
    request_raw = str((family.get("nichefoundry") or {}).get("request") or "")
    if not request_raw:
        return None, None
    request_path = Path(request_raw)
    if not request_path.is_absolute():
        request_path = ROOT / request_path
    if not request_path.is_file():
        return None, None
    request = legacy.read_json(request_path)
    output_raw = str(((request.get("outputs") or {}).get("vertical_reel") or "")).strip()
    if not output_raw:
        return None, None
    reel = Path(output_raw).expanduser()
    receipt = reel.parent / "NICHEFOUNDRY_REEL_RECEIPT.json"
    return reel, receipt


def _verified(path: Path | None) -> bool:
    return path is not None and path.is_file() and path.stat().st_size > 0


def build_ads_and_reel(product: dict[str, Any], product_dir: Path, render_reel: bool) -> dict[str, Any]:
    """Run the legacy generator, then replace optimistic state labels with artifact-backed truth."""
    family = _legacy_build_ads_and_reel(product, product_dir, render_reel)
    nf = family.setdefault("nichefoundry", {})
    reel, native_receipt = _read_request_output(family)
    reel_verified = _verified(reel)
    receipt_verified = _verified(native_receipt)

    if reel_verified and receipt_verified:
        reel_state = "ready"
        family.setdefault("assets", {})["reel_1080x1920"] = legacy.rel(reel)
        nf["native_reel_receipt"] = legacy.rel(native_receipt)
    elif render_reel:
        reel_state = "failed"
        family.setdefault("assets", {}).pop("reel_1080x1920", None)
        nf["native_reel_receipt"] = ""
        errors = family.setdefault("validation", {}).setdefault("errors", [])
        marker = "Reel render was requested but no verified reel artifact + native receipt pair exists."
        if marker not in errors:
            errors.append(marker)
    else:
        reel_state = "render_ready"
        family.setdefault("assets", {}).pop("reel_1080x1920", None)
        nf["native_reel_receipt"] = ""

    nf["media_pipeline_state"] = reel_state
    nf["native_reel_state"] = reel_state
    nf["long_form_state"] = "not_generated"
    nf["premium_episode_state"] = "not_generated"
    nf["long_form_truth"] = "A YouTube candidate is recorded only after render_youtube_video returns a concrete candidate and files."

    validation = family.setdefault("validation", {})
    if reel_state == "failed":
        validation["state"] = "failed"
    elif validation.get("errors"):
        validation["state"] = "failed"
    elif reel_state == "render_ready":
        validation["state"] = "inputs_validated"
    else:
        validation["state"] = "passed"

    legacy.write_json(product_dir / "FAMILY.json", family)
    return family


def _ensure_video_registry() -> None:
    if VIDEO_REGISTRY.exists():
        return
    VIDEO_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_json(VIDEO_REGISTRY, {
        "schema": "dio.video_candidate_registry.v1",
        "generated_at": legacy.utc_now(),
        "policy": {
            "initial_upload_privacy": "private",
            "human_watch_through_required": True,
            "explicit_upload_authority_required": True,
            "public_release_separate_from_upload": True,
        },
        "counts": {
            "total": 0,
            "preflight_passed": 0,
            "awaiting_human_review": 0,
            "private_upload_ready": 0,
            "uploaded_private": 0,
        },
        "candidates": [],
    })


def run_batch(limit: int, force: bool, no_reels: bool, no_youtube: bool) -> dict[str, Any]:
    if no_youtube:
        _ensure_video_registry()
    previous = legacy.build_ads_and_reel
    legacy.build_ads_and_reel = build_ads_and_reel
    try:
        batch = legacy.run_batch(limit, force, no_reels, no_youtube)
    finally:
        legacy.build_ads_and_reel = previous

    # The legacy function creates YouTube candidates after the family object. Reconcile the
    # family registry only from concrete candidate records, never from intention.
    if batch.get("status") == "ready_for_operator_review":
        registry = legacy.read_json(legacy.FACTORY_REGISTRY)
        candidate_registry = legacy.read_json(VIDEO_REGISTRY) if VIDEO_REGISTRY.exists() else {"candidates": []}
        candidate_products = {str(item.get("product_id") or "") for item in candidate_registry.get("candidates") or []}
        for family in registry.get("families") or []:
            family_id = str(family.get("family_id") or "")
            if not family_id.startswith("product-class--"):
                continue
            product_id = str((family.get("product") or {}).get("id") or "")
            nf = family.setdefault("nichefoundry", {})
            if product_id in candidate_products:
                nf["long_form_state"] = "youtube_candidate_ready"
                nf["premium_episode_state"] = "youtube_candidate_ready"
            else:
                nf["long_form_state"] = "not_generated"
                nf["premium_episode_state"] = "not_generated"
        legacy.write_json(legacy.FACTORY_REGISTRY, registry)
    return batch


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate truth-gated product-class ads, reels and YouTube candidates in batches.")
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
