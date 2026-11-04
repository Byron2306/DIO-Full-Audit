"""Controllable local ComfyUI workflows for the Pictora operator studio."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import urllib.request
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from PIL import Image, ImageOps

from products import pictora_organ

ROOT = Path(__file__).resolve().parents[1]
JOB_ROOT = ROOT / "deliverables" / "pictora_image_editor" / "studio_jobs"
EXTENSION_ASSET_MANIFEST = ROOT / "config/pictora/comfyui_extension_assets_v1.json"
CHECKPOINT_TERMS_MANIFEST = ROOT / "config/pictora/checkpoint_terms_manifest_v1.json"
COMFYUI_MODELS_ROOT = Path(os.environ.get(
    "DIO_COMFYUI_MODELS_DIR",
    "/data/byron/lilith-local/runtime/ComfyUI/models",
))
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MAX_DIMENSION = 1536


class PictoraStudioError(ValueError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _checkpoint_terms() -> dict[str, dict[str, Any]]:
    fallback = {"upstream_source": None, "license": None, "terms_state": "UNVERIFIED", "commercial_use": "NOT_CLEARED"}
    try:
        document = json.loads(CHECKPOINT_TERMS_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(document, dict) or document.get("schema") != "dio.pictora.checkpoint_terms_manifest.v1":
        return {}
    result = {}
    for row in document.get("checkpoints") or []:
        if not isinstance(row, dict) or not row.get("filename"):
            continue
        state = str(row.get("terms_state") or "UNVERIFIED")
        result[str(row["filename"])] = {
            "upstream_source": row.get("upstream_source"),
            "source_version": row.get("source_version"),
            "license": row.get("license"),
            "terms_state": state,
            "commercial_use": str(row.get("commercial_use") or "NOT_CLEARED"),
            "source_file_bytes": row.get("source_file_bytes"),
            "source_file_sha256": row.get("source_file_sha256"),
            "observed_local_file_bytes": row.get("observed_local_file_bytes"),
            "observed_local_file_sha256": row.get("observed_local_file_sha256"),
            "source_metadata": row.get("source_metadata") or {},
            "usage_constraints": row.get("usage_constraints") or [],
            "workflow_guidance": row.get("workflow_guidance") or {},
        }
    return {"__fallback__": fallback, **result}


def _local_checkpoint_bytes(name: str) -> int | None:
    path = _local_checkpoint_path(name)
    try:
        return path.stat().st_size if path else None
    except OSError:
        return None


def _local_checkpoint_path(name: str) -> Path | None:
    for folder in ("checkpoints", "diffusion_models", "unet"):
        candidate = COMFYUI_MODELS_ROOT / folder / Path(name).name
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


@lru_cache(maxsize=16)
def _checkpoint_sha256(path: str, size: int, modified_ns: int) -> str:
    """Hash model weights once per unchanged file revision without reading all into RAM."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _local_checkpoint_sha256(name: str) -> str | None:
    path = _local_checkpoint_path(name)
    if path is None:
        return None
    try:
        stat = path.stat()
        return _checkpoint_sha256(str(path), stat.st_size, stat.st_mtime_ns)
    except OSError:
        return None


def _model_asset_proof(name: str, folder: str) -> dict[str, Any]:
    """Bind a reference-control weight to the exact local file used by ComfyUI."""
    path = COMFYUI_MODELS_ROOT / folder / Path(name).name
    if not path.is_file():
        return {"filename": Path(name).name, "model_directory": folder, "state": "MISSING"}
    try:
        stat = path.stat()
        return {
            "filename": path.name,
            "model_directory": folder,
            "state": "AVAILABLE",
            "local_file_bytes": stat.st_size,
            "local_file_sha256": _checkpoint_sha256(str(path), stat.st_size, stat.st_mtime_ns),
        }
    except OSError as exc:
        return {"filename": path.name, "model_directory": folder, "state": "UNREADABLE", "error": str(exc)}


def _runtime_snapshot() -> dict[str, Any]:
    try:
        with urllib.request.urlopen(pictora_organ._base_url() + "/system_stats", timeout=10) as response:
            raw = json.load(response)
    except (OSError, ValueError, json.JSONDecodeError):
        return {"state": "UNKNOWN", "devices": []}
    if not isinstance(raw, dict):
        return {"state": "UNKNOWN", "devices": []}
    system = raw.get("system") or {}
    if not isinstance(system, dict):
        system = {}
    devices = []
    for row in raw.get("devices") or []:
        if not isinstance(row, dict):
            continue
        devices.append({
            "name": str(row.get("name") or "Unknown device"),
            "type": str(row.get("type") or "unknown"),
            "vram_total_bytes": row.get("vram_total"),
            "vram_free_bytes": row.get("vram_free"),
        })
    return {
        "state": "AVAILABLE",
        "comfyui_version": system.get("comfyui_version"),
        "ram_total_bytes": system.get("ram_total"),
        "ram_free_bytes": system.get("ram_free"),
        "devices": devices,
        "snapshot_scope": "local ComfyUI runtime at capability discovery time; available memory can change during rendering",
    }


def _extension_asset_snapshot(controlnets: list[str], ip_models: list[str]) -> list[dict[str, Any]]:
    try:
        manifest = json.loads(EXTENSION_ASSET_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    visible_names = {Path(str(name)).name for name in (*controlnets, *ip_models)}
    rows = []
    for asset in manifest.get("assets", []):
        path = COMFYUI_MODELS_ROOT / str(asset.get("local_model_path") or "")
        present = path.is_file()
        size = path.stat().st_size if present else 0
        expected_size = int(asset.get("bytes") or 0)
        api_visible = path.name in visible_names
        state = "VERIFIED" if present and size == expected_size and api_visible else "MISSING_OR_MISMATCHED"
        rows.append({
            **asset,
            "present": present,
            "api_visible": api_visible,
            "observed_bytes": size,
            "state": state,
        })
    return rows


def _object_info() -> dict[str, Any]:
    endpoint = pictora_organ._base_url()
    with urllib.request.urlopen(endpoint + "/object_info", timeout=30) as response:
        return json.load(response)


def queue_status() -> dict[str, int]:
    with urllib.request.urlopen(pictora_organ._base_url() + "/queue", timeout=10) as response:
        queue = json.load(response)
    return {"running": len(queue.get("queue_running") or []),
            "pending": len(queue.get("queue_pending") or [])}


def discover_studio() -> dict[str, Any]:
    info = _object_info()
    nodes = set(info)

    checkpoints = (
        (info.get("CheckpointLoaderSimple") or {})
        .get("input", {})
        .get("required", {})
        .get("ckpt_name", [[]])[0]
    )

    unets = (
        (info.get("UNETLoader") or {})
        .get("input", {})
        .get("required", {})
        .get("unet_name", [[]])[0]
    )

    clips = (
        (info.get("CLIPLoader") or {})
        .get("input", {})
        .get("required", {})
        .get("clip_name", [[]])[0]
    )

    vaes = (
        (info.get("VAELoader") or {})
        .get("input", {})
        .get("required", {})
        .get("vae_name", [[]])[0]
    )

    controlnets = (
        (info.get("ControlNetLoader") or {})
        .get("input", {})
        .get("required", {})
        .get("control_net_name", [[]])[0]
    )

    ip_models = (
        (info.get("IPAdapterModelLoader") or {})
        .get("input", {})
        .get("required", {})
        .get("ipadapter_file", [[]])[0]
    )

    faceid_loras = (
        (info.get("LoraLoaderModelOnly") or {})
        .get("input", {})
        .get("required", {})
        .get("lora_name", [[]])[0]
    )

    clip_vision_models = (
        (info.get("CLIPVisionLoader") or {})
        .get("input", {})
        .get("required", {})
        .get("clip_name", [[]])[0]
    )
    extension_assets = _extension_asset_snapshot(controlnets, ip_models)
    assets_by_id = {row["id"]: row for row in extension_assets}
    sdxl_pose_asset_ready = assets_by_id.get("sdxl_openpose_controlnet_xinsir_v1", {}).get("state") == "VERIFIED"
    sdxl_composition_asset_ready = assets_by_id.get("sdxl_ipadapter_plus_vit_h_v1", {}).get("state") == "VERIFIED"
    sdxl_face_reference_asset_ready = assets_by_id.get("sdxl_ipadapter_plus_face_vit_h_v1", {}).get("state") == "VERIFIED"

    sd15_control_family = lambda family: family.startswith("sd15_")
    pose_nodes_available = (
        {"OpenposePreprocessor", "ControlNetLoader", "ControlNetApplyAdvanced"} <= nodes
    )
    pose_models = {
        "sd15": any("openpose" in str(name).lower() and "sd15" in str(name).lower() for name in controlnets),
        "sdxl": sdxl_pose_asset_ready and any("openpose" in str(name).lower() and "sdxl" in str(name).lower() for name in controlnets),
    }
    identity_nodes_available = {
        "IPAdapterModelLoader", "LoraLoaderModelOnly", "IPAdapterFaceIDV2",
        "IPAdapterInsightFaceLoader", "CLIPVisionLoader",
    } <= nodes
    identity_families = ("sd15_anime", "sd15_inpaint", "sd15_realism", "sd15_standard")
    identity_models = {
        family: bool(identity_nodes_available and _has_faceid_plus_v2_assets(ip_models, faceid_loras, family))
        for family in identity_families
    }
    identity_available = any(identity_models.values())
    has_vit_h = any("vit-h-14" in str(name).lower() for name in clip_vision_models)
    composition_node_available = {"IPAdapterUnifiedLoader", "IPAdapterAdvanced"} <= nodes and has_vit_h
    composition_models = {
        "sd15": any("plus" in str(name).lower() and "sd15" in str(name).lower() for name in ip_models),
        "sdxl": sdxl_composition_asset_ready and any("plus" in str(name).lower() and "sdxl" in str(name).lower() for name in ip_models),
    }
    face_reference_node_available = {"IPAdapterUnifiedLoader", "IPAdapterAdvanced"} <= nodes and has_vit_h
    face_reference_models = {
        "sd15": any("plus-face" in str(name).lower() and "sd15" in str(name).lower() for name in ip_models),
        "sdxl": sdxl_face_reference_asset_ready and any("plus-face" in str(name).lower() and "sdxl" in str(name).lower() for name in ip_models),
    }

    profiles = []
    model_terms = _checkpoint_terms()

    for name in checkpoints:
        low = name.lower()

        if "krea2" in low:
            family = "krea2"
            compatible = (
                name in unets
                and "qwen3vl_4b_fp8_scaled.safetensors" in clips
                and "qwen_image_vae.safetensors" in vaes
            )

            profiles.append({
                "name": name,
                "family": family,
                "terms": model_terms.get(name, model_terms.get("__fallback__", {"upstream_source": None, "license": None, "terms_state": "UNVERIFIED", "commercial_use": "NOT_CLEARED"})),
                "compatible": compatible,
                "generate": compatible,
                "image_to_image": compatible,
                # Native Krea2 masked-edit topology is not yet proven.
                "inpaint": False,
                "reshape": False,
                "reference_controls": {"pose": False, "identity": False, "composition": False, "face_reference": False},
                "defaults": {
                    "width": 832,
                    "height": 1248,
                    "steps": 10,
                    "cfg": 1.0,
                    "sampler": "euler",
                    "scheduler": "simple",
                    "denoise_generate": 1.0,
                    "denoise_img2img": 0.60,
                    "denoise_inpaint": 0.60,
                },
            })
            continue

        if "dreamshaper" in low and "inpaint" in low:
            family = "sd15_inpaint"
            defaults = {
                "width": 512,
                "height": 512,
                "steps": 28,
                "cfg": 7.0,
                "sampler": "dpmpp_2m",
                "scheduler": "karras",
                "denoise_generate": 1.0,
                "denoise_img2img": 0.65,
                "denoise_inpaint": 0.78,
            }

        elif "pony" in low and "xl" in low:
            family = "sdxl_anime"
            defaults = {
                "width": 1024,
                "height": 1024,
                "steps": 25,
                "cfg": 6.0,
                "sampler": "euler_ancestral",
                "scheduler": "normal",
                "denoise_generate": 1.0,
                "denoise_img2img": 0.60,
                "denoise_inpaint": 0.60,
            }

        elif "xl" in low or "sdxl" in low:
            family = "sdxl_standard"
            defaults = {
                "width": 1024,
                "height": 1024,
                "steps": 30,
                "cfg": 6.0,
                "sampler": "dpmpp_2m",
                "scheduler": "karras",
                "denoise_generate": 1.0,
                "denoise_img2img": 0.60,
                "denoise_inpaint": 0.60,
            }

        elif "meina" in low:
            family = "sd15_anime"
            defaults = {
                "width": 512,
                "height": 768,
                "steps": 28,
                "cfg": 7.0,
                "sampler": "dpmpp_2m",
                "scheduler": "karras",
                "denoise_generate": 1.0,
                "denoise_img2img": 0.60,
                "denoise_inpaint": 0.60,
            }

        elif "epicrealism" in low:
            family = "sd15_realism"
            defaults = {
                "width": 640,
                "height": 896,
                "steps": 30,
                "cfg": 6.5,
                "sampler": "dpmpp_2m",
                "scheduler": "karras",
                "denoise_generate": 1.0,
                "denoise_img2img": 0.60,
                "denoise_inpaint": 0.60,
            }

        else:
            family = "sd15_standard"
            defaults = {
                "width": 512,
                "height": 768,
                "steps": 26,
                "cfg": 7.0,
                "sampler": "dpmpp_2m",
                "scheduler": "karras",
                "denoise_generate": 1.0,
                "denoise_img2img": 0.60,
                "denoise_inpaint": 0.60,
            }

        is_inpaint_family = family == "sd15_inpaint"

        profiles.append({
            "name": name,
            "family": family,
            "terms": model_terms.get(name, model_terms.get("__fallback__", {"upstream_source": None, "license": None, "terms_state": "UNVERIFIED", "commercial_use": "NOT_CLEARED"})),
            "compatible": True,
            "generate": not is_inpaint_family,
            "image_to_image": not is_inpaint_family,
            "inpaint": (
                "InpaintModelConditioning" in nodes
                and (
                    not is_inpaint_family
                    or {
                        "InpaintCropImproved",
                        "InpaintStitchImproved",
                    } <= nodes
                )
            ),
            "reshape": (
                is_inpaint_family
                and {
                    "InpaintModelConditioning",
                    "InpaintCropImproved",
                    "InpaintStitchImproved",
                } <= nodes
            ),
            "reference_controls": {
                "pose": (sd15_control_family(family) and pose_nodes_available and pose_models["sd15"])
                    or (family.startswith("sdxl_") and pose_nodes_available and pose_models["sdxl"]),
                "identity": sd15_control_family(family) and identity_models.get(family, False),
                "composition": (sd15_control_family(family) and composition_node_available and composition_models["sd15"])
                    or (family.startswith("sdxl_") and composition_node_available and composition_models["sdxl"]),
                "face_reference": (sd15_control_family(family) and face_reference_node_available and face_reference_models["sd15"])
                    or (family.startswith("sdxl_") and face_reference_node_available and face_reference_models["sdxl"]),
            },
            "defaults": defaults,
        })

    runtime = _runtime_snapshot()
    for profile in profiles:
        profile["local_file_bytes"] = _local_checkpoint_bytes(str(profile["name"]))

    return {
        "schema": "dio.pictora.studio_capabilities.v2",
        "state": "AVAILABLE",
        "checkpoints": checkpoints,
        "model_profiles": profiles,
        "runtime": runtime,
        "controlnets": controlnets,
        "ipadapter_models": ip_models,
        "faceid_loras": faceid_loras,
        "clip_vision_models": clip_vision_models,
        "extension_assets": extension_assets,
        "features": {
            "generate": {
                "available": {
                    "CheckpointLoaderSimple",
                    "KSampler",
                    "EmptyLatentImage",
                    "VAEDecode",
                    "SaveImage",
                } <= nodes
            },
            "krea2": {
                "available": {
                    "UNETLoader",
                    "CLIPLoader",
                    "VAELoader",
                    "KSampler",
                    "EmptyLatentImage",
                    "VAEDecode",
                } <= nodes
            },
            "inpaint": {
                "available": "InpaintModelConditioning" in nodes
            },
            "pose": {
                "available": pose_nodes_available and any(pose_models.values()),
                "supported_families": sorted({p["family"] for p in profiles if p["reference_controls"]["pose"]})
            },
            "identity": {
                "available": identity_available,
                "supported_families": sorted(family for family, available in identity_models.items() if available),
            },
            "composition": {
                "available": composition_node_available and any(composition_models.values()),
                "supported_families": sorted({p["family"] for p in profiles if p["reference_controls"]["composition"]})
            },
            "face_reference": {
                "available": face_reference_node_available and any(face_reference_models.values()),
                "supported_families": sorted({p["family"] for p in profiles if p["reference_controls"]["face_reference"]}),
                "identity_lock": False,
                "description": "Face-cropped appearance guidance; this adapter does not guarantee identity preservation.",
            },
        },
        "local_processing_only": True,
        "human_review_required": True,
    }

def _integer(value: Any, low: int, high: int, name: str) -> int:
    try:
        result = int(value)
    except (ValueError, TypeError) as exc:
        raise PictoraStudioError(f"{name} must be an integer") from exc
    if not low <= result <= high:
        raise PictoraStudioError(f"{name} must be between {low} and {high}")
    return result


def _number(value: Any, low: float, high: float, name: str) -> float:
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise PictoraStudioError(f"{name} must be a number") from exc
    if not low <= result <= high:
        raise PictoraStudioError(f"{name} must be between {low} and {high}")
    return result


def _validate_image(path: Path) -> None:
    if path.suffix.lower() not in IMAGE_SUFFIXES or path.stat().st_size > 20 * 1024 * 1024:
        raise PictoraStudioError("reference must be a PNG, JPG, or WebP under 20 MB")
    with Image.open(path) as image:
        image.verify()


def _comfy_name(path: Path, job_id: str) -> tuple[str, dict[str, Any]]:
    uploaded = pictora_organ.upload_image(path, subfolder=f"dio-pictora-studio/{job_id}")
    row = uploaded["input"]
    name = (str(row.get("subfolder") or "") + "/" if row.get("subfolder") else "") + str(row["name"])
    return name, {"role": path.stem, "sha256": _sha(path), "filename": path.name}


def _pose_controlnet_name(controlnets: list[str], family: str, selected: str | None = None) -> str:
    family_key = str(family).lower()
    candidates = [
        str(name) for name in controlnets
        if "openpose" in str(name).lower()
        and (
            (family_key.startswith("sd15_") and "sd15" in str(name).lower())
            or (family_key.startswith("sdxl_") and ("sdxl" in str(name).lower() or "openposexl" in str(name).lower()))
        )
    ]
    if selected:
        if selected not in candidates:
            raise PictoraStudioError(f"{selected} is not a compatible OpenPose ControlNet for {family}")
        return selected
    if not candidates:
        raise PictoraStudioError(f"no installed OpenPose ControlNet is compatible with {family}")
    return candidates[0]


def _ipadapter_plus_name(models: list[str], family: str) -> str:
    family_key = str(family).lower()
    marker = "sdxl" if family_key.startswith("sdxl_") else "sd15"
    candidates = [
        str(name) for name in models
        if "plus" in str(name).lower()
        and marker in str(name).lower()
        and "faceid" not in str(name).lower()
        and "plus-face" not in str(name).lower()
        and "plus_face" not in str(name).lower()
    ]
    if not candidates:
        raise PictoraStudioError(f"no installed IP-Adapter Plus weights are compatible with {family}")
    return candidates[0]


def _face_reference_adapter(models: list[str], family: str) -> str:
    family_key = str(family).lower()
    marker = "sdxl" if family_key.startswith("sdxl_") else "sd15"
    candidates = [
        str(name) for name in models
        if "plus-face" in str(name).lower()
        and marker in str(name).lower()
    ]
    if not candidates:
        raise PictoraStudioError(f"no installed face-reference adapter is compatible with {family}")
    return candidates[0]


def _faceid_plus_v2_assets(models: list[str], loras: list[str], family: str) -> tuple[str, str]:
    """Resolve the exact FaceID Plus V2 model/LoRA pair for the selected family."""
    family_key = str(family).lower()
    marker = "sdxl" if family_key.startswith("sdxl_") else "sd15"
    for name in sorted(str(value) for value in models):
        normalized = name.lower().replace("_", "-")
        if "faceid" not in normalized or "plusv2" not in normalized or marker not in normalized:
            continue
        lora = Path(name).stem + "_lora.safetensors"
        if lora in loras:
            return name, lora
    raise PictoraStudioError(f"no installed FaceID Plus V2 model/LoRA pair is compatible with {family}")


def _has_faceid_plus_v2_assets(models: list[str], loras: list[str], family: str) -> bool:
    try:
        _faceid_plus_v2_assets(models, loras, family)
        return True
    except PictoraStudioError:
        return False


def build_workflow(
    settings: Mapping[str, Any],
    *,
    uploaded: Mapping[str, str],
    capabilities: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile model-aware ComfyUI API workflows."""

    mode = str(settings.get("mode") or "generate")

    if mode not in {"generate", "image_to_image", "inpaint", "reshape"}:
        raise PictoraStudioError(
            "mode must be generate, image_to_image, inpaint, or reshape"
        )

    checkpoint = str(settings.get("checkpoint") or "")

    profiles = {
        row["name"]: row
        for row in capabilities.get("model_profiles") or []
    }

    if checkpoint not in profiles:
        raise PictoraStudioError(
            "selected model does not have a Pictora profile"
        )

    profile = profiles[checkpoint]
    model_terms = _checkpoint_terms().get(checkpoint, {})
    model_guidance = model_terms.get("workflow_guidance") or {}

    if not profile.get("compatible"):
        raise PictoraStudioError(
            f"{checkpoint} is not compatible with its required local model family"
        )

    defaults = profile["defaults"]
    family = profile["family"]

    unsupported_references = [
        role for role in ("pose", "identity", "composition", "face_reference")
        if role in uploaded and not profile.get("reference_controls", {}).get(role, False)
    ]
    if unsupported_references:
        roles = ", ".join(unsupported_references)
        raise PictoraStudioError(
            f"{checkpoint} ({family}) has no installed compatible control weights for: {roles}"
        )

    width = _integer(
        settings.get("width", defaults["width"]),
        256,
        MAX_DIMENSION,
        "width",
    )

    height = _integer(
        settings.get("height", defaults["height"]),
        256,
        MAX_DIMENSION,
        "height",
    )

    if width % 8 or height % 8:
        raise PictoraStudioError(
            "width and height must be multiples of eight"
        )

    steps = _integer(
        settings.get("steps", defaults["steps"]),
        1,
        80,
        "steps",
    )

    seed = _integer(
        settings.get("seed", 0),
        0,
        2**63 - 1,
        "seed",
    )

    cfg = _number(
        settings.get("cfg", defaults["cfg"]),
        0.1,
        20,
        "cfg",
    )

    sampler = str(
        settings.get("sampler")
        or defaults["sampler"]
    )

    scheduler = str(
        settings.get("scheduler")
        or defaults["scheduler"]
    )

    default_denoise = (
        defaults["denoise_generate"]
        if mode == "generate"
        else 0.82
        if mode == "reshape"
        else defaults["denoise_inpaint"]
        if mode == "inpaint"
        else defaults["denoise_img2img"]
    )

    denoise = _number(
        settings.get("denoise", default_denoise),
        0.05,
        1.0,
        "denoise",
    )

    prompt = str(
        settings.get("prompt") or ""
    ).strip()

    if not prompt or len(prompt) > 4000:
        raise PictoraStudioError(
            "a prompt of at most 4000 characters is required"
        )

    negative = str(
        settings.get("negative_prompt") or ""
    ).strip()[:2000]

    if mode != "generate" and "source" not in uploaded:
        raise PictoraStudioError(
            "image editing and inpainting require a source image"
        )

    if mode in {"inpaint", "reshape"} and "mask" not in uploaded:
        raise PictoraStudioError(
            "inpainting and reshaping require a painted white-on-black mask"
        )

    w: dict[str, Any] = {}

    # ---------------------------------------------------------
    # MODEL FAMILY LOADERS
    # ---------------------------------------------------------

    if family == "krea2":
        w["1"] = {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "qwen_image_vae.safetensors"
            },
        }

        w["2"] = {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": checkpoint,
                "weight_dtype": "default",
            },
        }

        w["3"] = {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name":
                    "qwen3vl_4b_fp8_scaled.safetensors",
                "type": "krea2",
                "device": "default",
            },
        }

        model = ["2", 0]
        vae = ["1", 0]
        clip = ["3", 0]

    else:
        w["1"] = {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": checkpoint
            },
        }

        model = ["1", 0]
        clip = ["1", 1]
        vae = ["1", 2]

        clip_skip = _integer(
            model_guidance.get("clip_skip", 1),
            1,
            12,
            "model clip skip",
        )
        if clip_skip > 1:
            w["4"] = {
                "class_type": "CLIPSetLastLayer",
                "inputs": {
                    "clip": clip,
                    "stop_at_clip_layer": -clip_skip,
                },
            }
            clip = ["4", 0]

    effective_prompt = prompt
    prompt_prefix = str(model_guidance.get("positive_prompt_prefix") or "").strip()
    if prompt_prefix and "score_9" not in prompt.lower():
        effective_prompt = f"{prompt_prefix}, {prompt}"

    w["10"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": clip,
            "text": effective_prompt,
        },
    }

    w["11"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "clip": clip,
            "text": negative,
        },
    }

    positive = ["10", 0]
    negative_ref = ["11", 0]

    # ---------------------------------------------------------
    # LATENT / SOURCE
    # ---------------------------------------------------------

    if mode == "generate":
        w["20"] = {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1,
            },
        }

        latent = ["20", 0]

    else:
        w["20"] = {
            "class_type": "LoadImage",
            "inputs": {
                "image": uploaded["source"]
            },
        }

        if mode in {"inpaint", "reshape"}:
            w["21"] = {
                "class_type": "LoadImageMask",
                "inputs": {
                    "image": uploaded["mask"],
                    "channel": "red",
                },
            }

            # Keep two masks:
            #
            # composite_mask_ref = exactly what the operator painted.
            # mask_ref           = working mask that diffusion may expand.
            #
            # The expanded mask gives the model blending room but MUST NOT
            # enlarge the final replacement boundary.
            composite_mask_ref = ["21", 0]

            mask_ref = composite_mask_ref


            # Default final boundary is the exact operator-painted mask.

            final_composite_mask_ref = composite_mask_ref


            # Feather only affects the final blend edge.

            w["21f"] = {

                "class_type": "FeatherMask",

                "inputs": {

                    "mask": composite_mask_ref,

                    "left": _integer(

                        settings.get("mask_feather", 12),

                        0, 128, "mask_feather"

                    ),

                    "top": _integer(

                        settings.get("mask_feather", 12),

                        0, 128, "mask_feather"

                    ),

                    "right": _integer(

                        settings.get("mask_feather", 12),

                        0, 128, "mask_feather"

                    ),

                    "bottom": _integer(

                        settings.get("mask_feather", 12),

                        0, 128, "mask_feather"

                    ),

                },

            }


            final_composite_mask_ref = ["21f", 0]


            if mode == "reshape":
                w["21a"] = {
                    "class_type": "GrowMask",
                    "inputs": {
                        "mask": mask_ref,
                        "expand": _integer(
                            settings.get("mask_grow", 24),
                            0,
                            256,
                            "mask_grow",
                        ),
                        "tapered_corners": True,
                    },
                }
                mask_ref = ["21a", 0]

                w["21b"] = {
                    "class_type": "DifferentialDiffusion",
                    "inputs": {
                        "model": model,
                        "strength": _number(
                            settings.get(
                                "differential_strength",
                                1.0,
                            ),
                            0.0,
                            1.0,
                            "differential_strength",
                        ),
                    },
                }
                model = ["21b", 0]

            w["22"] = {
                "class_type": "InpaintModelConditioning",
                "inputs": {
                    "positive": positive,
                    "negative": negative_ref,
                    "vae": vae,
                    "pixels": ["20", 0],
                    "mask": mask_ref,
                    "noise_mask": True,
                },
            }

            positive = ["22", 0]
            negative_ref = ["22", 1]
            latent = ["22", 2]

        else:
            w["22"] = {
                "class_type": "VAEEncode",
                "inputs": {
                    "pixels": ["20", 0],
                    "vae": vae,
                },
            }

            latent = ["22", 0]

    # ---------------------------------------------------------
    # OPTIONAL SD1.5 / SDXL CONTROLS
    #
    # Adapter families are selected from the installed compatible
    # weights. Krea2 has its own control
    # topology and must not silently receive SD1.5 adapters.
    # ---------------------------------------------------------

    if family.startswith(("sd15_", "sdxl_")):
        if "pose" in uploaded:
            controlnets = capabilities["controlnets"]
            controlnet = _pose_controlnet_name(
                controlnets,
                family,
                str(settings.get("controlnet") or "") or None,
            )

            w["30"] = {
                "class_type": "LoadImage",
                "inputs": {
                    "image": uploaded["pose"]
                },
            }

            w["31"] = {
                "class_type": "OpenposePreprocessor",
                "inputs": {
                    "image": ["30", 0],
                    "resolution": 512,
                    "detect_body": "enable",
                    "detect_face": "enable",
                    "detect_hand": "enable",
                },
            }

            w["32"] = {
                "class_type": "ControlNetLoader",
                "inputs": {
                    "control_net_name": controlnet
                },
            }

            w["33"] = {
                "class_type": "ControlNetApplyAdvanced",
                "inputs": {
                    "positive": positive,
                    "negative": negative_ref,
                    "control_net": ["32", 0],
                    "image": ["31", 0],
                    "strength": _number(
                        settings.get(
                            "pose_strength",
                            0.85,
                        ),
                        0,
                        2,
                        "pose_strength",
                    ),
                    "start_percent": 0.0,
                    "end_percent": 1.0,
                },
            }

            positive = ["33", 0]
            negative_ref = ["33", 1]

        if "composition" in uploaded:
            w["40"] = {
                "class_type": "LoadImage",
                "inputs": {
                    "image": uploaded["composition"]
                },
            }

            w["41"] = {
                "class_type": "IPAdapterUnifiedLoader",
                "inputs": {
                    "model": model,
                    "preset": "PLUS (high strength)",
                },
            }

            w["42"] = {
                "class_type": "IPAdapterAdvanced",
                "inputs": {
                    "model": ["41", 0],
                    "ipadapter": ["41", 1],
                    "image": ["40", 0],
                    "weight": _number(
                        settings.get(
                            "composition_strength",
                            0.75,
                        ),
                        0,
                        2,
                        "composition_strength",
                    ),
                    "weight_type": "composition",
                    "combine_embeds": "concat",
                    "start_at": 0.0,
                    "end_at": 1.0,
                    "embeds_scaling": "V only",
                },
            }

            model = ["42", 0]

        if "face_reference" in uploaded:
            w["44"] = {
                "class_type": "LoadImage",
                "inputs": {"image": uploaded["face_reference"]},
            }

            w["45"] = {
                "class_type": "IPAdapterUnifiedLoader",
                "inputs": {
                    "model": model,
                    "preset": "PLUS FACE (portraits)",
                },
            }

            w["46"] = {
                "class_type": "IPAdapterAdvanced",
                "inputs": {
                    "model": ["45", 0],
                    "ipadapter": ["45", 1],
                    "image": ["44", 0],
                    "weight": _number(
                        settings.get("face_reference_strength", 0.65),
                        0,
                        2,
                        "face_reference_strength",
                    ),
                    "weight_type": "linear",
                    "combine_embeds": "concat",
                    "start_at": 0.0,
                    "end_at": 1.0,
                    "embeds_scaling": "V only",
                },
            }

            model = ["46", 0]

        if "identity" in uploaded:
            adapter_name, identity_lora_name = _faceid_plus_v2_assets(
                capabilities.get("ipadapter_models") or [],
                capabilities.get("faceid_loras") or [],
                family,
            )
            identity_lora_strength = _number(
                settings.get("identity_lora_strength", 0.6),
                0,
                2,
                "identity_lora_strength",
            )
            clip_vision_name = next(
                (
                    str(name)
                    for name in capabilities.get("clip_vision_models") or []
                    if "vit-h-14" in str(name).lower()
                ),
                None,
            )
            if not clip_vision_name:
                raise PictoraStudioError("FaceID Plus V2 requires an installed CLIP Vision model")

            w["50"] = {
                "class_type": "LoadImage",
                "inputs": {
                    "image": uploaded["identity"]
                },
            }

            w["51"] = {
                "class_type": "IPAdapterModelLoader",
                "inputs": {
                    "ipadapter_file": adapter_name,
                },
            }

            w["52"] = {
                "class_type": "LoraLoaderModelOnly",
                "inputs": {
                    "model": model,
                    "lora_name": identity_lora_name,
                    "strength_model": identity_lora_strength,
                },
            }

            w["53"] = {
                "class_type": "CLIPVisionLoader",
                "inputs": {
                    "clip_name": clip_vision_name,
                },
            }

            w["54"] = {
                "class_type": "IPAdapterInsightFaceLoader",
                "inputs": {"provider": "CPU"},
            }

            w["55"] = {
                "class_type": "IPAdapterFaceIDV2",
                "inputs": {
                    "model": ["52", 0],
                    "ipadapter": ["51", 0],
                    "image": ["50", 0],
                    "clip_vision": ["53", 0],
                    "insightface": ["54", 0],
                    "weight": _number(
                        settings.get(
                            "identity_strength",
                            0.8,
                        ),
                        0,
                        2,
                        "identity_strength",
                    ),
                    "weight_faceidv2": 1.0,
                    "weight_type": "linear",
                    "combine_embeds": "concat",
                    "start_at": 0.0,
                    "end_at": 1.0,
                    "embeds_scaling": "V only",
                },
            }

            model = ["55", 0]

    elif any(
        role in uploaded
        for role in (
            "pose",
            "identity",
            "composition",
        )
    ):
        raise PictoraStudioError(
            f"{family} pose/identity/composition/face references "
            "need a model-family-matched control route and installed weights. "
            "Use source img2img or mask-based inpainting for now."
        )

    # ---------------------------------------------------------
    # PICTORA_SD15_CROP_STITCH_V1
    #
    # Dedicated SD1.5 inpainting checkpoints should solve only
    # the masked region plus surrounding context. The crop node
    # owns resizing and mask blending; the stitch node restores
    # the result into the untouched native-resolution source.
    # ---------------------------------------------------------

    use_crop_stitch = (
        family == "sd15_inpaint"
        and mode in {"inpaint", "reshape"}
    )

    if use_crop_stitch:
        if "source" not in uploaded:
            raise PictoraStudioError(
                "SD1.5 inpainting requires a source image"
            )

        if "mask" not in uploaded:
            raise PictoraStudioError(
                "SD1.5 inpainting requires a mask"
            )

        # `20` and `21` already exist in the generic local-edit
        # input path:
        #   20 = source IMAGE
        #   21 = raw MASK
        #
        # Keep those loaders, but replace the generic latent
        # preparation with the dedicated crop/stitch route.

        w["80"] = {
            "class_type": "InpaintCropImproved",
            "inputs": {
                "image": ["20", 0],

                "downscale_algorithm": "bilinear",
                "upscale_algorithm": "bicubic",

                "preresize": False,
                "preresize_mode":
                    "ensure minimum resolution",
                "preresize_min_width": 1024,
                "preresize_min_height": 1024,
                "preresize_max_width": 16384,
                "preresize_max_height": 16384,

                "mask_fill_holes": True,

                "mask_expand_pixels": _integer(
                    settings.get("mask_grow", 8),
                    0,
                    256,
                    "mask_grow",
                ),

                "mask_invert": False,

                "mask_blend_pixels": _integer(
                    settings.get("mask_blend", 16),
                    0,
                    256,
                    "mask_blend",
                ),

                "mask_hipass_filter": 0.1,

                "extend_for_outpainting": False,
                "extend_up_factor": 1.0,
                "extend_down_factor": 1.0,
                "extend_left_factor": 1.0,
                "extend_right_factor": 1.0,

                "context_from_mask_extend_factor": _number(
                    settings.get("inpaint_context", 2.0),
                    1.0,
                    8.0,
                    "inpaint_context",
                ),

                "output_resize_to_target_size": True,

                "output_target_width": _integer(
                    settings.get("inpaint_width", 512),
                    256,
                    768,
                    "inpaint_width",
                ),

                "output_target_height": _integer(
                    settings.get("inpaint_height", 512),
                    256,
                    768,
                    "inpaint_height",
                ),

                "output_padding": "32",

                # Keep crop bookkeeping off the 6 GB GPU.
                "device_mode": "cpu (compatible)",

                "mask": ["21", 0],
            },
        }

        # Improved crop outputs:
        #   output 0 = STITCHER
        #   output 1 = cropped IMAGE
        #   output 2 = cropped MASK
        w["81"] = {
            "class_type": "InpaintModelConditioning",
            "inputs": {
                "positive": positive,
                "negative": negative_ref,
                "vae": vae,
                "pixels": ["80", 1],
                "mask": ["80", 2],
                "noise_mask": True,
            },
        }

        # Replace the generic conditioning/latent immediately
        # before sampling.
        positive = ["81", 0]
        negative_ref = ["81", 1]
        latent = ["81", 2]

    # ---------------------------------------------------------
    # SAMPLER / OUTPUT
    # ---------------------------------------------------------

    w["90"] = {
        "class_type": "KSampler",
        "inputs": {
            "model": model,
            "positive": positive,
            "negative": negative_ref,
            "latent_image": latent,
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler,
            "scheduler": scheduler,
            "denoise": denoise,
        },
    }

    w["91"] = {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["90", 0],
            "vae": vae,
        },
    }

    output_image = ["91", 0]

    # Hard preservation boundary for local edits.
    #
    # Diffusion may reconsider global composition even when a
    # latent noise mask is present. For inpaint/reshape, composite
    # only the masked generated region back onto the untouched
    # prepared source. Pixels outside the mask therefore cannot
    # drift.
    if use_crop_stitch:
        w["93"] = {
            "class_type": "InpaintStitchImproved",
            "inputs": {
                "stitcher": ["80", 0],
                "inpainted_image": ["91", 0],
            },
        }

        output_image = ["93", 0]

    elif mode in {"inpaint", "reshape"}:
        # Legacy/local-edit models continue using the explicit
        # hard-preservation compositor. Dedicated inpainting
        # checkpoints bypass this path entirely.
        w["93"] = {
            "class_type": "ImageCompositeMasked",
            "inputs": {
                "destination": ["20", 0],
                "source": ["91", 0],
                "x": 0,
                "y": 0,
                "resize_source": False,
                "mask": composite_mask_ref,
            },
        }

        output_image = ["93", 0]

    w["92"] = {
        "class_type": "SaveImage",
        "inputs": {
            "images": output_image,
            "filename_prefix":
                "pictora_studio",
        },
    }

    return w

def run_studio_job(settings: Mapping[str, Any], references: Mapping[str, Path], *, owner_authorized: bool, output_root: Path = JOB_ROOT) -> dict[str, Any]:
    if owner_authorized is not True:
        raise PictoraStudioError("confirm rights or permission for the source and reference images")
    if set(references) - {"source", "mask", "pose", "identity", "composition", "face_reference"}:
        raise PictoraStudioError("unsupported reference image role")
    for path in references.values():
        _validate_image(path)
    capabilities = discover_studio()
    mode = str(settings.get("mode") or "generate")
    checkpoint = str(settings.get("checkpoint") or "")

    selected_profile = next(
        (
            row for row in capabilities.get("model_profiles", [])
            if str(row.get("name") or "") == checkpoint
        ),
        None,
    )
    if selected_profile is None:
        raise PictoraStudioError("selected model does not have a Pictora profile")
    model_terms = selected_profile.get("terms") or {}
    local_checkpoint_sha256 = _local_checkpoint_sha256(checkpoint)
    expected_checkpoint_sha256 = model_terms.get("source_file_sha256")
    observed_local_checkpoint_sha256 = model_terms.get("observed_local_file_sha256")
    pinned_checkpoint_sha256 = expected_checkpoint_sha256 or observed_local_checkpoint_sha256
    if pinned_checkpoint_sha256 and local_checkpoint_sha256 != pinned_checkpoint_sha256:
        raise PictoraStudioError(
            f"{checkpoint} does not match the pinned model file hash; "
            "review the model version before rendering"
        )

    job_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    job_dir = output_root.resolve() / job_id
    inputs = job_dir / "inputs"
    inputs.mkdir(parents=True, exist_ok=False)
    copied: dict[str, Path] = {}
    for role, path in references.items():
        dest = inputs / (role + path.suffix.lower())
        shutil.copy2(path, dest)
        copied[role] = dest

    preserve_native_source = (
        selected_profile is not None
        and selected_profile.get("family") == "sd15_inpaint"
        and mode in {"inpaint", "reshape"}
    )

    if (
        mode in {"image_to_image", "inpaint", "reshape"}
        and "source" in copied
        and not preserve_native_source
    ):
        width = _integer(
            settings.get("width", 512),
            256,
            MAX_DIMENSION,
            "width",
        )
        height = _integer(
            settings.get("height", 512),
            256,
            MAX_DIMENSION,
            "height",
        )

        with Image.open(copied["source"]) as source_image:
            source_image.convert("RGB").resize(
                (width, height),
                Image.Resampling.LANCZOS,
            ).save(inputs / "source-prepared.png")

        if "mask" in copied:
            with Image.open(copied["mask"]) as mask_image:
                mask_image.convert("L").resize(
                    (width, height),
                    Image.Resampling.NEAREST,
                ).save(inputs / "mask-prepared.png")

        original_sources = {
            role: {
                "filename": path.name,
                "sha256": _sha(path),
            }
            for role, path in copied.items()
        }

        copied["source"] = inputs / "source-prepared.png"

        if "mask" in copied:
            copied["mask"] = inputs / "mask-prepared.png"

    else:
        # Dedicated Crop-and-Stitch lanes receive the original
        # source and mask at native resolution.
        original_sources = {
            role: {
                "filename": path.name,
                "sha256": _sha(path),
            }
            for role, path in copied.items()
        }
    uploaded: dict[str, str] = {}
    source_receipts = []
    for role, path in copied.items():
        uploaded[role], receipt = _comfy_name(path, job_id)
        source_receipts.append(receipt)
    workflow = build_workflow(settings, uploaded=uploaded, capabilities=capabilities)
    family = str((selected_profile or {}).get("family") or "unknown")
    used_controls: dict[str, Any] = {}
    extension_asset_proofs: dict[str, Any] = {}
    control_weight_proofs: dict[str, Any] = {}
    clip_vision_name = next(
        (str(name) for name in capabilities.get("clip_vision_models") or [] if "vit-h-14" in str(name).lower()),
        None,
    )
    installed_assets = {
        row["id"]: row for row in capabilities.get("extension_assets", [])
        if row.get("state") == "VERIFIED"
    }
    if "pose" in copied:
        controlnet_name = workflow["32"]["inputs"]["control_net_name"]
        used_controls["pose"] = {
            "controlnet": controlnet_name,
            "preprocessor": "OpenposePreprocessor",
        }
        control_weight_proofs["pose"] = {
            "controlnet": _model_asset_proof(controlnet_name, "controlnet"),
        }
        if family.startswith("sdxl_"):
            extension_asset_proofs["pose"] = installed_assets.get("sdxl_openpose_controlnet_xinsir_v1")
    if "composition" in copied:
        composition_adapter = _ipadapter_plus_name(capabilities.get("ipadapter_models") or [], family)
        used_controls["composition"] = {
            "adapter": composition_adapter,
            "preset": "PLUS (high strength)",
            "weight_type": "composition",
        }
        control_weight_proofs["composition"] = {
            "adapter": _model_asset_proof(composition_adapter, "ipadapter"),
            "clip_vision": _model_asset_proof(clip_vision_name, "clip_vision") if clip_vision_name else {"state": "MISSING"},
        }
        if family.startswith("sdxl_"):
            extension_asset_proofs["composition"] = installed_assets.get("sdxl_ipadapter_plus_vit_h_v1")
    if "face_reference" in copied:
        face_adapter = _face_reference_adapter(capabilities.get("ipadapter_models") or [], family)
        used_controls["face_reference"] = {
            "adapter": face_adapter,
            "preset": "PLUS FACE (portraits)",
            "weight_type": "linear",
            "identity_lock": False,
        }
        control_weight_proofs["face_reference"] = {
            "adapter": _model_asset_proof(face_adapter, "ipadapter"),
            "clip_vision": _model_asset_proof(clip_vision_name, "clip_vision") if clip_vision_name else {"state": "MISSING"},
        }
        if family.startswith("sdxl_"):
            extension_asset_proofs["face_reference"] = installed_assets.get("sdxl_ipadapter_plus_face_vit_h_v1")
    if "identity" in copied:
        identity_adapter, identity_lora = _faceid_plus_v2_assets(
            capabilities.get("ipadapter_models") or [],
            capabilities.get("faceid_loras") or [],
            family,
        )
        identity_strength = _number(
            settings.get("identity_strength", 0.8), 0, 2, "identity_strength"
        )
        identity_lora_strength = _number(
            settings.get("identity_lora_strength", 0.6), 0, 2, "identity_lora_strength"
        )
        used_controls["identity"] = {
            "adapter_family": "FaceID Plus V2",
            "profile_family": family,
            "adapter_model": identity_adapter,
            "adapter_lora": identity_lora,
            "insightface_provider": "CPU",
            "strength": identity_strength,
            "faceid_v2_weight": 1.0,
            "lora_strength": identity_lora_strength,
            "identity_lock": False,
            "claim_boundary": "FaceID identity conditioning can guide resemblance but does not guarantee an exact identity match.",
        }
        control_weight_proofs["identity"] = {
            "adapter": _model_asset_proof(identity_adapter, "ipadapter"),
            "lora": _model_asset_proof(identity_lora, "loras"),
            "clip_vision": _model_asset_proof(clip_vision_name, "clip_vision") if clip_vision_name else {"state": "MISSING"},
        }
    comfy_dir = job_dir / "comfy"
    submitted = pictora_organ.submit(workflow, output_dir=comfy_dir, owner_authorized=True, source_receipts=source_receipts)
    collected = pictora_organ.collect(submitted["job_id"], output_dir=comfy_dir, timeout_seconds=900)
    if collected.get("state") != "COMPLETE":
        raise PictoraStudioError(f"ComfyUI render did not complete: {collected.get('state')}")
    outputs = [comfy_dir / str(row["path"]) for row in collected.get("artifacts") or []]
    if not outputs:
        raise PictoraStudioError("ComfyUI returned no image")
    output = outputs[-1]
    receipt = {
        "schema": "dio.pictora.studio_job.v1", "job_id": job_id, "state": "COMPLETE",
        "settings": dict(settings), "model_family": family, "reference_controls": used_controls,
        "model_provenance": {"checkpoint": checkpoint, "family": family,
                             "local_file_bytes": (selected_profile or {}).get("local_file_bytes"),
                             "local_file_sha256": local_checkpoint_sha256,
                             "pinned_source_file_sha256": expected_checkpoint_sha256,
                             "pinned_observed_local_file_sha256": observed_local_checkpoint_sha256,
                             "local_file_matches_pinned_model_hash": (local_checkpoint_sha256 == pinned_checkpoint_sha256) if pinned_checkpoint_sha256 else None,
                             "local_file_matches_pinned_source": (local_checkpoint_sha256 == expected_checkpoint_sha256) if expected_checkpoint_sha256 else None,
                             "workflow_guidance_applied": ((selected_profile or {}).get("terms") or {}).get("workflow_guidance") or {},
                             "effective_positive_prompt": workflow.get("10", {}).get("inputs", {}).get("text"),
                             "runtime_context": capabilities.get("runtime"),
                             "terms": (selected_profile or {}).get("terms", {"terms_state": "UNVERIFIED", "commercial_use": "NOT_CLEARED", "license": None, "upstream_source": None}),
                             "commercial_use_authorized": False},
        "extension_asset_proofs": extension_asset_proofs,
        "control_weight_proofs": control_weight_proofs,
        "original_inputs": original_sources, "source_receipts": source_receipts,
        "workflow_sha256": submitted["workflow_sha256"], "comfy_prompt_id": submitted["job_id"],
        "final_output": {"path": str(output.relative_to(job_dir)), "sha256": _sha(output), "bytes": output.stat().st_size},
        "human_review_required": True, "release_authorized": False, "remote_processing": False,
    }
    (job_dir / "PICTORA_STUDIO_RECEIPT.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    return receipt
