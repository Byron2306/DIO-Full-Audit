"""Local, non-destructive Pictora Image Editor product pipeline."""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from products import pictora_organ

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "dio.pictora.image_editor.job.v1"
MAX_PIXELS = 80_000_000
MAX_DIMENSION = 8192


class PictoraImageEditorError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _clamp(value: Any, low: float, high: float, default: float) -> float:
    try:
        parsed = float(value)
        return min(high, max(low, parsed)) if math.isfinite(parsed) else default
    except (TypeError, ValueError):
        return default


def discover_capabilities() -> dict[str, Any]:
    snapshot = pictora_organ.discover()
    nodes = set(snapshot.get("available_nodes") or [])
    try:
        import urllib.request
        models = json.loads(urllib.request.urlopen(snapshot["endpoint"] + "/models/upscale_models", timeout=20).read())
    except Exception:
        models = []
    return {
        "schema": "dio.pictora.image_editor.capabilities.v1",
        "state": "AVAILABLE" if snapshot.get("state") == "AVAILABLE" else snapshot.get("state"),
        "local_processing_only": True,
        "deterministic_controls": ["exposure", "contrast", "saturation", "tint", "sharpness", "median_denoise", "crop", "clone_stamp"],
        "ai_operations": {
            "upscale": {"available": "ImageUpscaleWithModel" in nodes and "RealESRGAN_x4plus.safetensors" in models, "models": models},
            "background_removal": {"available": "easy imageRemBg" in nodes, "node": "easy imageRemBg", "modes": ["RMBG-2.0", "RMBG-1.4", "Inspyrenet", "BEN2"] if "easy imageRemBg" in nodes else []},
            "generative_heal": {"available": all(name in nodes for name in ("VAEEncodeForInpaint", "CheckpointLoaderSimple", "KSampler")), "requires_mask": True},
        },
        "device_snapshot": snapshot.get("devices") or [],
        "remote_processing": False,
    }


def _apply_clone_stamp(image: Image.Image, options: dict[str, Any], base_dir: Path) -> Image.Image:
    mask_path = (base_dir / str(options.get("mask_path") or "")).resolve()
    if not mask_path.is_file():
        raise PictoraImageEditorError("clone_stamp requires an existing mask_path")
    mask_path.relative_to(base_dir.resolve())
    mask = Image.open(mask_path).convert("L").resize(image.size, Image.Resampling.LANCZOS)
    source_xy = options.get("source_xy") or []
    target_xy = options.get("target_xy") or []
    if len(source_xy) != 2 or len(target_xy) != 2:
        raise PictoraImageEditorError("clone_stamp requires source_xy and target_xy coordinate pairs")
    dx, dy = int(target_xy[0]) - int(source_xy[0]), int(target_xy[1]) - int(source_xy[1])
    patch = Image.new("RGB", image.size, (0, 0, 0))
    patch.paste(image, (dx, dy))
    alpha = mask.filter(ImageFilter.GaussianBlur(radius=_clamp(options.get("feather"), 0, 32, 6)))
    return Image.composite(patch, image, alpha)


def apply_local_edits(source: Path, destination: Path, edits: dict[str, Any], *, mask_root: Path | None = None) -> dict[str, Any]:
    """Apply the deterministic controls in order and save a non-destructive derivative."""
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        if image.width * image.height > MAX_PIXELS:
            raise PictoraImageEditorError(f"image exceeds the {MAX_PIXELS:,}-pixel safety limit")
        alpha = image.getchannel("A") if "A" in image.getbands() else None
        image = image.convert("RGB")
    original_size = image.size
    crop = edits.get("crop")
    if isinstance(crop, (list, tuple)) and len(crop) == 4:
        left, top, right, bottom = [int(_clamp(v, 0, 1, 0) * (image.width if i % 2 == 0 else image.height)) for i, v in enumerate(crop)]
        if right <= left or bottom <= top or right - left < 16 or bottom - top < 16:
            raise PictoraImageEditorError("crop must be normalized [left, top, right, bottom] with at least 16 pixels per side")
        image = image.crop((left, top, right, bottom))
        if alpha is not None:
            alpha = alpha.crop((left, top, right, bottom))

    exposure = _clamp(edits.get("exposure_ev"), -4, 4, 0)
    if exposure:
        image = ImageEnhance.Brightness(image).enhance(2 ** exposure)
    contrast = _clamp(edits.get("contrast"), 0, 3, 1)
    if contrast != 1:
        image = ImageEnhance.Contrast(image).enhance(contrast)
    saturation = _clamp(edits.get("saturation"), 0, 3, 1)
    if saturation != 1:
        image = ImageEnhance.Color(image).enhance(saturation)
    tint = str(edits.get("tint_color") or "").strip().lstrip("#")
    tint_amount = _clamp(edits.get("tint_amount"), 0, 0.5, 0)
    if len(tint) == 6 and all(c in "0123456789abcdefABCDEF" for c in tint) and tint_amount:
        colour = tuple(int(tint[i:i + 2], 16) for i in (0, 2, 4))
        image = Image.blend(image, Image.new("RGB", image.size, colour), tint_amount)
    denoise = int(_clamp(edits.get("denoise"), 0, 1, 0))
    if denoise:
        image = image.filter(ImageFilter.MedianFilter(size=3))
    sharpness = _clamp(edits.get("sharpness"), 0, 4, 0)
    if sharpness:
        image = image.filter(ImageFilter.UnsharpMask(radius=2, percent=round(110 * sharpness), threshold=3))
    clone_stamp = edits.get("clone_stamp")
    if clone_stamp:
        image = _apply_clone_stamp(image, dict(clone_stamp), (mask_root or source.parent).resolve())

    destination.parent.mkdir(parents=True, exist_ok=True)
    if alpha is not None:
        image.putalpha(alpha)
    image.save(destination, format="PNG", optimize=True)
    return {
        "operation": "deterministic_local_photo_adjustments",
        "input_dimensions": list(original_size),
        "output_dimensions": list(image.size),
        "parameters": {"exposure_ev": exposure, "contrast": contrast, "saturation": saturation, "tint_color": tint or None, "tint_amount": tint_amount, "median_denoise": bool(denoise), "sharpness": sharpness, "crop": crop},
        "clone_stamp_applied": bool(clone_stamp),
        "lossless_output": "PNG",
    }


def _comfy_image_operation(source: Path, destination_dir: Path, operation: str, options: dict[str, Any], *, owner_authorized: bool) -> dict[str, Any]:
    if owner_authorized is not True:
        raise PictoraImageEditorError("owner_authorized=true is required before local ComfyUI image processing")
    snapshot = pictora_organ.discover()
    nodes = set(snapshot.get("available_nodes") or [])
    job_dir = destination_dir / "comfy" / f"{operation}-{uuid.uuid4().hex[:8]}"
    job_dir.mkdir(parents=True)
    upload = pictora_organ.upload_image(source, subfolder=f"dio-pictora-editor/{job_dir.name}")
    input_row = upload["input"]
    input_name = (str(input_row.get("subfolder") or "") + "/" if input_row.get("subfolder") else "") + str(input_row["name"])
    if operation == "upscale":
        if not {"UpscaleModelLoader", "ImageUpscaleWithModel", "ImageScale"} <= nodes:
            raise PictoraImageEditorError("local ComfyUI lacks required RealESRGAN upscale nodes")
        model = str(options.get("model") or "RealESRGAN_x4plus.safetensors")
        import urllib.request
        installed = json.loads(urllib.request.urlopen(snapshot["endpoint"] + "/models/upscale_models", timeout=20).read())
        if model not in installed:
            raise PictoraImageEditorError(f"upscale model is not installed locally: {model}")
        factor = int(_clamp(options.get("factor"), 2, 4, 2))
        with Image.open(source) as im:
            width, height = im.size
        width, height = min(MAX_DIMENSION, width * factor), min(MAX_DIMENSION, height * factor)
        workflow = {
            "1": {"class_type": "LoadImage", "inputs": {"image": input_name}},
            "2": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": model}},
            "3": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["2", 0], "image": ["1", 0]}},
            "4": {"class_type": "ImageScale", "inputs": {"image": ["3", 0], "upscale_method": "lanczos", "width": width, "height": height, "crop": "disabled"}},
            "5": {"class_type": "SaveImage", "inputs": {"images": ["4", 0], "filename_prefix": "pictora_editor_upscale"}},
        }
    elif operation == "background_removal":
        if "easy imageRemBg" not in nodes:
            raise PictoraImageEditorError("local ComfyUI has no easy imageRemBg node")
        mode = str(options.get("mode") or "RMBG-1.4")
        if mode not in {"RMBG-2.0", "RMBG-1.4", "Inspyrenet", "BEN2"}:
            raise PictoraImageEditorError("unsupported local background-removal mode")
        workflow = {
            "1": {"class_type": "LoadImage", "inputs": {"image": input_name}},
            "2": {"class_type": "easy imageRemBg", "inputs": {"images": ["1", 0], "rem_mode": mode, "image_output": "Hide", "save_prefix": "pictora_editor_bg_removed", "refine_foreground": True}},
        }
        if "JoinImageWithAlpha" in nodes:
            workflow["3"] = {"class_type": "JoinImageWithAlpha", "inputs": {"image": ["2", 0], "alpha": ["2", 1]}}
            image_output = ["3", 0]
        else:
            image_output = ["2", 0]
        workflow["4"] = {"class_type": "SaveImage", "inputs": {"images": image_output, "filename_prefix": "pictora_editor_bg_removed"}}
    else:
        raise PictoraImageEditorError(f"unsupported ComfyUI operation: {operation}")
    submitted = pictora_organ.submit(workflow, output_dir=job_dir, owner_authorized=True, source_receipts=[{"source_path": str(source), "source_sha256": _sha(source), "operation": operation, "model_or_mode": options}])
    collected = pictora_organ.collect(submitted["job_id"], output_dir=job_dir, timeout_seconds=int(options.get("timeout_seconds") or 1800))
    if collected.get("state") != "COMPLETE":
        raise PictoraImageEditorError(f"local ComfyUI {operation} failed: {collected.get('state')}")
    artifacts = [job_dir / str(row["path"]) for row in collected.get("artifacts") or []]
    images = [path for path in artifacts if path.is_file() and path.suffix.casefold() in {".png", ".jpg", ".jpeg", ".webp"}]
    if not images:
        raise PictoraImageEditorError(f"local ComfyUI {operation} returned no image artifact")
    return {"operation": operation, "state": "COMPLETE", "job_id": submitted["job_id"], "receipt": str(job_dir / "PICTORA_JOB_RECEIPT.json"), "outputs": [{"path": str(path), "sha256": _sha(path), "bytes": path.stat().st_size} for path in images], "workflow_sha256": submitted["workflow_sha256"], "execution_location": "local_comfyui", "remote_processing": False, "human_review_required": True}


def run_edit(source_path: str | Path, output_root: str | Path, *, edits: dict[str, Any] | None = None, ai_operations: list[dict[str, Any]] | None = None, owner_authorized: bool, job_id: str | None = None) -> dict[str, Any]:
    """Create an immutable, receipt-backed image-edit job under output_root."""
    if owner_authorized is not True:
        raise PictoraImageEditorError("owner_authorized=true is required to process source imagery")
    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    job_id = job_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    output = (Path(output_root).expanduser().resolve() / job_id)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing Pictora job: {output}")
    output.mkdir(parents=True)
    inputs = output / "input"
    result_dir = output / "results"
    inputs.mkdir(); result_dir.mkdir()
    copied_source = inputs / ("source" + (source.suffix.lower() if source.suffix else ".image"))
    shutil.copy2(source, copied_source)
    edits = dict(edits or {})
    if isinstance(edits.get("clone_stamp"), dict):
        clone_options = dict(edits["clone_stamp"])
        raw_mask = Path(str(clone_options.get("mask_path") or ""))
        mask_source = (source.parent / raw_mask).resolve()
        if not mask_source.is_file():
            raise PictoraImageEditorError("clone stamp mask file is missing")
        mask_target = inputs / "clone-mask.png"
        shutil.copy2(mask_source, mask_target)
        clone_options["mask_path"] = mask_target.name
        edits["clone_stamp"] = clone_options
    original = Image.open(copied_source)
    original.verify()
    source_dims = Image.open(copied_source).size
    if source_dims[0] * source_dims[1] > MAX_PIXELS:
        raise PictoraImageEditorError(f"image exceeds the {MAX_PIXELS:,}-pixel safety limit")

    local_path = result_dir / "01-local-edits.png"
    local_receipt = apply_local_edits(copied_source, local_path, edits, mask_root=inputs)
    operations: list[dict[str, Any]] = [local_receipt]
    current = local_path
    ordered_ai_operations = list(ai_operations or [])
    # Removing the background last preserves its alpha when the customer asks
    # for both a larger image and a transparent cutout.
    ordered_ai_operations.sort(key=lambda row: 1 if row.get("operation") == "background_removal" else 0)
    for index, requested in enumerate(ordered_ai_operations, 1):
        operation = str(requested.get("operation") or "")
        prior_alpha = None
        if operation == "upscale":
            with Image.open(current) as current_image:
                if "A" in current_image.getbands():
                    prior_alpha = current_image.getchannel("A")
        row = _comfy_image_operation(current, output, operation, dict(requested.get("options") or {}), owner_authorized=owner_authorized)
        selected = Path(row["outputs"][-1]["path"])
        if prior_alpha is not None:
            with Image.open(selected) as upscale_image:
                rgba = upscale_image.convert("RGBA")
                rgba.putalpha(prior_alpha.resize(rgba.size, Image.Resampling.LANCZOS))
                alpha_preserved = selected.with_name(selected.stem + "-alpha-preserved.png")
                rgba.save(alpha_preserved, format="PNG", optimize=True)
            selected = alpha_preserved
            row["alpha_preserved"] = True
        if index < len(ordered_ai_operations):
            chained = result_dir / f"{index + 1:02d}-{operation}.png"
            shutil.copy2(selected, chained)
            current = chained
        else:
            final = result_dir / f"{index + 1:02d}-{operation}{selected.suffix.lower()}"
            shutil.copy2(selected, final)
            current = final
        row["editor_result"] = str(current.relative_to(output))
        operations.append(row)
    if current == local_path:
        final = result_dir / "FINAL_EDIT.png"
        shutil.copy2(local_path, final)
        current = final
    manifest = {
        "schema": SCHEMA,
        "job_id": job_id,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": {"path": str(source), "filename": source.name, "sha256": _sha(source), "dimensions": list(source_dims), "exif_oriented": True},
        "preservation": {"original_copy": str(copied_source.relative_to(output)), "original_unchanged": True, "all_edits_non_destructive": True},
        "operations": operations,
        "final_output": {"path": str(current.relative_to(output)), "sha256": _sha(current), "bytes": current.stat().st_size, "dimensions": list(Image.open(current).size)},
        "execution": {"local_only": True, "remote_processing": False},
        "commercial_validation": "UNPROVED",
        "human_visual_review": "REQUIRED",
        "release_authorized": False,
    }
    manifest_path = output / "PICTORA_IMAGE_EDIT_RECEIPT.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"job_dir": str(output), "final_output": str(current), "receipt": str(manifest_path), "job_id": job_id, "manifest": manifest}
