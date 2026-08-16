#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FOUNDRY = Path(os.environ.get("DIO_NICHEFOUNDRY_ROOT") or (Path.home() / "Downloads" / "NicheFoundry_Phase11"))
REGISTRY = ROOT / "state" / "marketing_factory" / "CREATIVE_FAMILY_REGISTRY.json"
EVENT_LOG = ROOT / "telemetry" / "dio_events.jsonl"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def resolve(path_value: str) -> Path:
    path = Path(path_value).expanduser()
    return path if path.is_absolute() else ROOT / path


def emit_event(event: str, entity_id: str, data: dict[str, Any]) -> None:
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "occurred_at": utc_now(),
        "event": event,
        "severity": "info",
        "entity_type": "creative_family",
        "entity_id": entity_id,
        "data": data,
    }
    with EVENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")


def assert_engine_ready(foundry_root: Path) -> dict[str, Any]:
    reel_engine = foundry_root / "scripts" / "build_dio_campaign_reel.js"
    checks = {
        "nichefoundry_root": str(foundry_root),
        "node": bool(shutil.which("node")),
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "ffprobe": bool(shutil.which("ffprobe")),
        "reel_engine": reel_engine.is_file(),
        "premium_assets_engine": (foundry_root / "scripts" / "build_premium_assets.js").is_file(),
        "episode_renderer": (foundry_root / "scripts" / "render_episode.js").is_file(),
        "youtube_publisher": (foundry_root / "scripts" / "upload_dio_publication_candidate.js").is_file(),
    }
    checks["ready_for_campaign_reels"] = all(checks[key] for key in ["node", "ffmpeg", "ffprobe", "reel_engine"])
    return checks


def family_request_path(family: dict[str, Any]) -> Path | None:
    nichefoundry = family.get("nichefoundry") or {}
    value = str(nichefoundry.get("request") or nichefoundry.get("request_path") or "")
    return resolve(value) if value else None


def missing_request_inputs(request: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for scene in request.get("scene_images") or []:
        if not Path(scene).expanduser().is_file():
            missing.append(f"scene image: {scene}")
    music = ((request.get("music") or {}).get("path") or "")
    if not music or not Path(music).expanduser().is_file():
        missing.append(f"music bed: {music or 'not configured'}")
    output = ((request.get("outputs") or {}).get("vertical_reel") or "")
    if not output:
        missing.append("vertical reel output path")
    return missing


def run_reel_engine(foundry_root: Path, request_path: Path, timeout: int) -> dict[str, Any]:
    completed = subprocess.run(
        ["node", str(foundry_root / "scripts" / "build_dio_campaign_reel.js"), str(request_path)],
        cwd=str(foundry_root),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "NicheFoundry reel engine failed.").strip()[-1600:])
    return json.loads(completed.stdout)


def run_family(
    family: dict[str, Any],
    foundry_root: Path,
    *,
    render_reel: bool,
    timeout: int,
) -> dict[str, Any]:
    now = utc_now()
    family_id = str(family.get("family_id") or "")
    nichefoundry = family.setdefault("nichefoundry", {})
    checks = assert_engine_ready(foundry_root)
    request_path = family_request_path(family)
    receipt: dict[str, Any] = {
        "schema": "dio.nichefoundry.media_pipeline_receipt.v1",
        "family_id": family_id,
        "ran_at": now,
        "render_reel_requested": render_reel,
        "engine_checks": checks,
        "state": "blocked",
        "missing_inputs": [],
        "outputs": {},
        "notes": [],
    }

    if not request_path or not request_path.is_file():
        receipt["missing_inputs"].append(f"production request: {request_path or 'not configured'}")
    elif not checks["ready_for_campaign_reels"]:
        receipt["missing_inputs"].append("local NicheFoundry reel engine prerequisites")
    else:
        request = load_json(request_path)
        missing = missing_request_inputs(request)
        receipt["missing_inputs"].extend(missing)
        receipt["request"] = rel(request_path)
        receipt["request_hash"] = request.get("request_hash")
        receipt["outputs"]["vertical_reel"] = rel(Path((request.get("outputs") or {}).get("vertical_reel", ""))) if (request.get("outputs") or {}).get("vertical_reel") else ""
        if not missing and render_reel:
            try:
                reel_receipt = run_reel_engine(foundry_root, request_path, timeout)
                reel_path = Path(str(reel_receipt.get("output") or ""))
                receipt["state"] = "ready"
                receipt["native_reel_receipt"] = reel_receipt
                receipt["outputs"]["vertical_reel"] = rel(reel_path)
                receipt["outputs"]["reel_receipt"] = rel(reel_path.parent / "NICHEFOUNDRY_REEL_RECEIPT.json")
            except (OSError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
                receipt["state"] = "failed"
                receipt["missing_inputs"].append(str(exc))
        elif not missing:
            output_value = (request.get("outputs") or {}).get("vertical_reel")
            if output_value:
                output_path = Path(str(output_value))
                reel_receipt_path = output_path.parent / "NICHEFOUNDRY_REEL_RECEIPT.json"
                if output_path.is_file():
                    receipt["outputs"]["vertical_reel"] = rel(output_path)
                if reel_receipt_path.is_file():
                    receipt["outputs"]["reel_receipt"] = rel(reel_receipt_path)
            receipt["state"] = "ready"
            receipt["notes"].append("Inputs are render-ready; reel render was skipped by request.")

    family_dir = request_path.parent if request_path else ROOT / "state" / "marketing_factory" / family_id.lower()
    receipt_path = family_dir / "MEDIA_PIPELINE_RECEIPT.json"
    receipt["media_pipeline_receipt"] = rel(receipt_path)
    write_json(receipt_path, receipt)

    reel_path = receipt["outputs"].get("vertical_reel") or (family.get("assets") or {}).get("reel_1080x1920")
    if reel_path:
        family.setdefault("assets", {})["reel_1080x1920"] = reel_path
    nichefoundry.update(
        {
            "request": rel(request_path) if request_path else nichefoundry.get("request", ""),
            "media_pipeline_state": receipt["state"],
            "media_pipeline_receipt": rel(receipt_path),
            "media_pipeline_at": now,
            "native_reel_state": "ready" if receipt["state"] == "ready" else receipt["state"],
            "native_reel_receipt": receipt["outputs"].get("reel_receipt", ""),
            "premium_episode_state": "needs_full_episode_promotion",
            "premium_episode_reason": "Campaign-family requests can render short reels, but Gamma assets, voice, music discovery and long-form render require a promoted NicheFoundry episode directory.",
            "long_form_state": "needs_episode_promotion",
            "engine_checks": checks,
            "missing_inputs": receipt["missing_inputs"],
        }
    )
    family.setdefault("governance", {}).update({"publication": "held", "spend": "disabled"})
    family.setdefault("validation", {})["state"] = "passed" if receipt["state"] == "ready" else "failed"
    family["validation"]["errors"] = receipt["missing_inputs"]
    write_json(family_dir / "FAMILY.json", family)
    emit_event("marketing.media_pipeline_ran", family_id, {"state": receipt["state"], "receipt": rel(receipt_path)})
    return receipt


def run_media_pipeline(
    *,
    family_id: str = "",
    product_id: str = "",
    registry_path: Path = REGISTRY,
    foundry_root: Path = FOUNDRY,
    render_reel: bool = True,
    timeout: int = 240,
) -> dict[str, Any]:
    registry = load_json(registry_path)
    families = list(registry.get("families") or [])
    selected = []
    for family in families:
        if family_id and str(family.get("family_id")) != family_id:
            continue
        if product_id and str((family.get("product") or {}).get("id")) != product_id:
            continue
        selected.append(family)
    if (family_id or product_id) and not selected:
        raise ValueError("No creative families matched the requested media pipeline filter.")

    receipts = [run_family(family, foundry_root, render_reel=render_reel, timeout=timeout) for family in selected]
    selected_counts = {
        "ready": sum(receipt["state"] == "ready" for receipt in receipts),
        "blocked": sum(receipt["state"] == "blocked" for receipt in receipts),
        "failed": sum(receipt["state"] == "failed" for receipt in receipts),
    }
    global_counts = {
        "ready": sum((family.get("nichefoundry") or {}).get("media_pipeline_state") == "ready" for family in families),
        "blocked": sum((family.get("nichefoundry") or {}).get("media_pipeline_state") == "blocked" for family in families),
        "failed": sum((family.get("nichefoundry") or {}).get("media_pipeline_state") == "failed" for family in families),
    }
    summary = registry.setdefault("summary", {})
    summary["media_pipeline_last_run_at"] = utc_now()
    summary["media_pipeline_last_selected_counts"] = selected_counts
    summary["media_pipeline_state_counts"] = global_counts
    summary["native_reels_ready"] = sum((family.get("nichefoundry") or {}).get("native_reel_state") == "ready" for family in families)
    summary["premium_episode_promotions_required"] = sum((family.get("nichefoundry") or {}).get("premium_episode_state") == "needs_full_episode_promotion" for family in families)
    write_json(registry_path, registry)

    run_receipt = {
        "schema": "dio.nichefoundry.media_pipeline_run.v1",
        "ran_at": utc_now(),
        "registry": rel(registry_path),
        "family_filter": family_id,
        "product_filter": product_id,
        "selected_count": len(selected),
        "counts": selected_counts,
        "global_counts": global_counts,
        "receipts": [str(receipt.get("media_pipeline_receipt") or "") for receipt in receipts],
    }
    write_json(ROOT / "state" / "marketing_factory" / "MEDIA_PIPELINE_RUN_RECEIPT.json", run_receipt)
    return run_receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge DIO Market Command creative families into the native NicheFoundry media engines.")
    parser.add_argument("--family-id", default="")
    parser.add_argument("--product-id", default="")
    parser.add_argument("--no-render-reel", action="store_true")
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--nichefoundry-root", type=Path, default=FOUNDRY)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()
    receipt = run_media_pipeline(
        family_id=args.family_id,
        product_id=args.product_id,
        registry_path=args.registry.expanduser().resolve(),
        foundry_root=args.nichefoundry_root.expanduser().resolve(),
        render_reel=not args.no_render_reel,
        timeout=args.timeout,
    )
    print(json.dumps(receipt, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
