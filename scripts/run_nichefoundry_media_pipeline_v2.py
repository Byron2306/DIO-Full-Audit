#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dio_secrets import load_secret_env
from scripts.build_campaign_media import CampaignMediaError, render_campaign_media


ROOT = Path(__file__).resolve().parents[1]
FOUNDRY = Path(os.environ.get("DIO_NICHEFOUNDRY_ROOT") or (Path.home() / "Downloads" / "NicheFoundry_Phase11"))
REGISTRY = ROOT / "state" / "marketing_factory" / "CREATIVE_FAMILY_REGISTRY.json"
EVENT_LOG = ROOT / "telemetry" / "dio_events.jsonl"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def resolve_repo(path_value: str) -> Path:
    path = Path(str(path_value or "")).expanduser()
    return path if path.is_absolute() else ROOT / path


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _request_path(family: dict[str, Any]) -> Path:
    value = str((family.get("nichefoundry") or {}).get("request") or "").strip()
    if not value:
        raise ValueError("Creative family has no NicheFoundry production request.")
    path = resolve_repo(value)
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _gamma_receipt(request: dict[str, Any], request_path: Path) -> Path:
    value = str((request.get("gamma") or {}).get("receipt") or "").strip()
    path = Path(value).expanduser() if value else request_path.parent / "gamma" / "GAMMA_STORY_RECEIPT.json"
    if not path.is_file():
        raise FileNotFoundError(f"Gamma story receipt is required before narrated media: {path}")
    return path


def _verify_output(path_value: str, label: str) -> Path:
    path = Path(str(path_value or "")).expanduser()
    if not str(path_value or "").strip() or not path.is_file() or path.stat().st_size < 10000:
        raise RuntimeError(f"{label} was not created as a valid MP4: {path}")
    return path


def run_family(family: dict[str, Any], *, foundry_root: Path, render_media: bool) -> dict[str, Any]:
    load_secret_env(overwrite=False)
    family_id = str(family.get("family_id") or "")
    request_path = _request_path(family)
    request = read_json(request_path)
    gamma_receipt = _gamma_receipt(request, request_path)
    receipt: dict[str, Any] = {
        "schema": "dio.nichefoundry.media_pipeline_receipt.v2",
        "family_id": family_id,
        "ran_at": utc_now(),
        "renderer": "scripts.build_campaign_media.render_campaign_media",
        "voice_provider": "piper_local",
        "music_required": True,
        "render_media_requested": render_media,
        "state": "render_ready" if not render_media else "failed",
        "outputs": {},
        "errors": [],
    }
    if render_media:
        try:
            media = render_campaign_media(request_path, gamma_receipt, nichefoundry_root=foundry_root)
            outputs = media.get("outputs") or {}
            vertical = _verify_output(str((outputs.get("vertical_reel") or {}).get("path") or ""), "Vertical reel")
            landscape = _verify_output(str((outputs.get("long_form_explainer") or {}).get("path") or ""), "Landscape explainer")
            piper_receipt = request_path.parent / "media" / "PIPER_NARRATION_RECEIPT.json"
            media_receipt = request_path.parent / "media" / "CAMPAIGN_MEDIA_RECEIPT.json"
            if not piper_receipt.is_file() or not media_receipt.is_file():
                raise RuntimeError("Narrated media returned without Piper and campaign-media receipts.")
            receipt["state"] = "ready"
            receipt["outputs"] = {
                "vertical_reel": relative(vertical),
                "long_form_explainer": relative(landscape),
                "piper_receipt": relative(piper_receipt),
                "campaign_media_receipt": relative(media_receipt),
            }
        except (CampaignMediaError, OSError, RuntimeError, ValueError) as exc:
            receipt["errors"].append(str(exc))

    family_dir = request_path.parent
    receipt_path = family_dir / "MEDIA_PIPELINE_RECEIPT.json"
    receipt["receipt"] = relative(receipt_path)
    write_json(receipt_path, receipt)

    family.setdefault("piper", {}).update({
        "required_for_media": True,
        "provider": "piper_local",
        "remote_fallback": False,
        "state": "ready" if receipt["state"] == "ready" else receipt["state"],
        "receipt": receipt["outputs"].get("piper_receipt", ""),
    })
    niche = family.setdefault("nichefoundry", {})
    niche.update({
        "media_pipeline_state": receipt["state"],
        "media_pipeline_receipt": relative(receipt_path),
        "reel_state": receipt["state"],
        "long_form_state": receipt["state"],
        "media_error": " | ".join(receipt["errors"]),
    })
    if receipt["state"] == "ready":
        family.setdefault("assets", {})["reel_1080x1920"] = receipt["outputs"]["vertical_reel"]
        family.setdefault("assets", {})["explainer_1920x1080"] = receipt["outputs"]["long_form_explainer"]
    family.setdefault("governance", {}).update({"publication": "held", "spend": "disabled"})
    write_json(family_dir / "FAMILY.json", family)
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
    del timeout
    load_secret_env(overwrite=False)
    registry = read_json(registry_path)
    families = list(registry.get("families") or [])
    selected = [
        family for family in families
        if (not family_id or str(family.get("family_id") or "") == family_id)
        and (not product_id or str((family.get("product") or {}).get("id") or "") == product_id)
    ]
    if (family_id or product_id) and not selected:
        raise ValueError("No creative families matched the requested media pipeline filter.")

    receipts = [run_family(family, foundry_root=foundry_root, render_media=render_reel) for family in selected]
    counts = {state: sum(row["state"] == state for row in receipts) for state in ("ready", "render_ready", "failed")}
    registry.setdefault("summary", {}).update({
        "media_pipeline_last_run_at": utc_now(),
        "media_pipeline_last_selected_counts": counts,
        "piper_narrations_ready": sum((family.get("piper") or {}).get("state") == "ready" for family in families),
        "native_reels_ready": sum((family.get("nichefoundry") or {}).get("reel_state") == "ready" for family in families),
        "long_form_explainers_ready": sum((family.get("nichefoundry") or {}).get("long_form_state") == "ready" for family in families),
    })
    write_json(registry_path, registry)
    run_receipt = {
        "schema": "dio.nichefoundry.media_pipeline_run.v2",
        "ran_at": utc_now(),
        "selected_count": len(selected),
        "counts": counts,
        "receipts": [row["receipt"] for row in receipts],
        "renderer": "scripts.build_campaign_media.render_campaign_media",
        "voice_provider": "piper_local",
        "music_required": True,
        "vertical_reel_required": True,
        "landscape_explainer_required": True,
        "publication": "held",
        "spend": "disabled",
    }
    write_json(ROOT / "state" / "marketing_factory" / "MEDIA_PIPELINE_RUN_RECEIPT.json", run_receipt)
    return run_receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Render full narrated NicheFoundry campaign media.")
    parser.add_argument("--family-id", default="")
    parser.add_argument("--product-id", default="")
    parser.add_argument("--no-render-reel", action="store_true")
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--nichefoundry-root", type=Path, default=FOUNDRY)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()
    result = run_media_pipeline(
        family_id=args.family_id,
        product_id=args.product_id,
        registry_path=args.registry.expanduser().resolve(),
        foundry_root=args.nichefoundry_root.expanduser().resolve(),
        render_reel=not args.no_render_reel,
        timeout=args.timeout,
    )
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0 if result["counts"].get("failed", 0) == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
