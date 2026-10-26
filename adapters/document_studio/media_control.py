from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image


class DocumentStudioMediaError(RuntimeError):
    pass


ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = ROOT / "config/format_profiles.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_profile(style_profile: str) -> tuple[dict[str, Any], str]:
    try:
        registry = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DocumentStudioMediaError(f"invalid Format Core profile registry: {PROFILE_PATH}") from exc
    style = (registry.get("styles") or {}).get(style_profile)
    if not isinstance(style, dict):
        raise DocumentStudioMediaError(f"unknown Format Core style profile: {style_profile}")
    digest = hashlib.sha256(json.dumps(style, sort_keys=True).encode()).hexdigest()
    return style, digest


def _probe_image(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise DocumentStudioMediaError(f"media source missing: {path.name}")
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            width, height = image.size
            mode = image.mode
    except (OSError, ValueError) as exc:
        raise DocumentStudioMediaError(f"invalid media source: {path.name}") from exc
    if width < 1280 or height < 720:
        raise DocumentStudioMediaError(
            f"media source below release resolution: {path.name} is {width}x{height}"
        )
    return {
        "path": str(path),
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
        "width": width,
        "height": height,
        "mode": mode,
        "structural_image_qa": "PASS",
        "perceptual_release": "NEEDS_YOU",
    }


def build_media_control_surface(
    *,
    gamma_dir: Path,
    script_package: dict[str, Any],
    output_dir: Path,
    style_profile: str = "dio_professional",
) -> dict[str, Any]:
    """Bind editable controls without repainting completed native compositions."""
    _, profile_hash = _load_profile(style_profile)
    scenes = script_package.get("scenes") or []
    controls: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    for index, scene in enumerate(scenes, 1):
        source = gamma_dir / f"{index:02}_{scene['scene_id']}_GAMMA.png"
        probe = _probe_image(source)
        probes.append(probe)
        controls.append({
            "scene_id": scene["scene_id"],
            "source": str(source),
            "source_sha256": probe["sha256"],
            "title": str(scene.get("title") or f"Scene {index}"),
            "narration": str(scene.get("narration") or ""),
            "allowed_actions": [
                "request_native_regeneration",
                "select_native_variant",
                "approve",
                "refuse",
            ],
            "forbidden_actions": [
                "destructive_half_crop",
                "raster_text_overpaint",
                "silent_font_fallback",
                "claim_automated_perceptual_approval",
            ],
        })

    thumbnail = _probe_image(gamma_dir / "THUMBNAIL_GAMMA.png")
    output_dir.mkdir(parents=True, exist_ok=True)
    control = {
        "schema": "dio.document_studio.media_control.v2",
        "format_core_profile": style_profile,
        "format_core_profile_hash": profile_hash,
        "authority": {
            "composition_renderer": "nichefoundry.native_render_system",
            "generated_visual_provider": "gamma",
            "document_studio": "semantic_control_validation_and_human_approval",
            "release_authority": "human",
        },
        "scenes": controls,
        "thumbnail": {
            "source": thumbnail["path"],
            "source_sha256": thumbnail["sha256"],
            "perceptual_release": "NEEDS_YOU",
        },
    }
    control_path = output_dir / "EDITABLE_MEDIA_CONTROL.json"
    control_path.write_text(json.dumps(control, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    receipt = {
        "schema": "dio.document_studio.media_control_receipt.v2",
        "engine": "document_studio",
        "native_engine_invoked": False,
        "binding_state": "CONTROL_SURFACE_BOUND",
        "format_core_profile": style_profile,
        "format_core_profile_hash": profile_hash,
        "gamma_composition_preserved": "PASS",
        "non_destructive_control": "PASS",
        "silent_font_fallback": "REFUSE",
        "destructive_crop": "REFUSE",
        "raster_text_overpaint": "REFUSE",
        "structural_image_qa": "PASS",
        "automated_perceptual_release": "REFUSE",
        "human_visual_release": "NEEDS_YOU",
        "scene_count": len(probes),
        "scene_coverage": "PASS",
        "scenes": probes,
        "thumbnail": thumbnail,
        "control_manifest": str(control_path),
        "control_manifest_sha256": _sha256(control_path),
        "external_publication": "REFUSE",
    }
    receipt_path = output_dir / "DOCUMENT_STUDIO_MEDIA_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


render_media_control_surface = build_media_control_surface
