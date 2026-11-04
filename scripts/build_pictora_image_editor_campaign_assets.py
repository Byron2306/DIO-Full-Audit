#!/usr/bin/env python3
"""Create a small Pictora-generated, text-free campaign image pool locally."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from products.pictora_organ import collect, discover, submit

PACK = ROOT / "media/product_asset_packs/pictora_image_editor_v1"
CHECKPOINT = "epicrealism_naturalSinRC1VAE.safetensors"
BRIEFS = [
    {"id": "editorial_workspace", "seed": 2026102901, "role": "hook", "prompt": "Premium editorial photograph for a local professional image editor: a photographer in a dark, tidy studio reviewing a vivid landscape photograph on a large color-calibrated monitor, camera and a couple of photographic prints on the desk, warm practical gold light, deep obsidian shadows, tasteful real photography, cinematic but believable, generous negative space, landscape 16:9 composition, no words, no letters, no logo, no watermark."},
    {"id": "retouch_detail", "seed": 2026102902, "role": "workflow_demo", "prompt": "Premium close editorial photograph of a printed fine-art portrait and a digital tablet with a retouching stylus beside it, subtle before and after photo pair showing careful natural skin cleanup, accurate neutral skin, tactile photographic paper, low-key black studio with restrained gold edge light, macro focus, believable material, landscape 16:9, no interface text, no words, no letters, no logo, no watermark."},
    {"id": "photo_finish", "seed": 2026102903, "role": "proof", "prompt": "High-end editorial still life of a finished vivid landscape photograph, a second original photo print, and a small translucent cutout portrait sheet arranged on a dark art director's desk, real paper and photographic texture, accurate rich color, subtle champagne gold rim light, dark premium DIO obsidian visual language, balanced landscape 16:9 composition, no interface, no words, no letters, no logo, no watermark."},
    {"id": "creative_handoff", "seed": 2026102904, "role": "human_context", "prompt": "Editorial documentary photograph of an independent designer inspecting several printed campaign photographs on a black work table, warm desk lamp, a camera lens and color swatches nearby, calm deliberate review rather than futuristic UI, natural human proportions, premium dark studio, restrained gold accents, landscape 16:9, no legible writing, no words, no letters, no logo, no watermark."},
]


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def workflow(brief: dict) -> dict:
    negative = "text, letters, typography, logo, watermark, interface, fake UI, extra fingers, fused fingers, malformed hands, distorted face, duplicate objects, collage, border, blurry, oversharpened, washed out, plastic skin"
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CHECKPOINT}},
        "2": {"class_type": "EmptyLatentImage", "inputs": {"width": 640, "height": 360, "batch_size": 1}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": brief["prompt"], "clip": ["1", 1]}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "seed": brief["seed"], "steps": 22, "cfg": 6.5, "sampler_name": "dpmpp_2m", "scheduler": "karras", "positive": ["3", 0], "negative": ["4", 0], "latent_image": ["2", 0], "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "DIO_PICTORA_EDITOR_" + brief["id"].upper()}},
    }


def main() -> int:
    snapshot = discover()
    nodes = set(snapshot.get("available_nodes") or [])
    required = {"CheckpointLoaderSimple", "EmptyLatentImage", "CLIPTextEncode", "KSampler", "VAEDecode", "SaveImage"}
    if not required <= nodes:
        raise RuntimeError("Local ComfyUI does not expose the required Pictora generation nodes")
    import urllib.request
    checkpoints = json.loads(urllib.request.urlopen(snapshot["endpoint"] + "/models/checkpoints", timeout=20).read())
    if CHECKPOINT not in checkpoints:
        raise RuntimeError(f"Pictora checkpoint is not installed locally: {CHECKPOINT}")
    assets, jobs, workflows = PACK / "assets", PACK / "pictora_jobs", PACK / "workflows"
    for directory in (assets, jobs, workflows):
        directory.mkdir(parents=True, exist_ok=True)
    records = []
    for brief in BRIEFS:
        target = assets / f"{brief['id']}.png"
        work_path = workflows / f"{brief['id']}_api.json"
        job_dir = jobs / brief["id"]
        if target.exists() or work_path.exists() or job_dir.exists():
            raise FileExistsError(f"Refusing to replace an existing Pictora campaign asset: {brief['id']}")
        graph = workflow(brief)
        work_path.write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        receipt = submit(graph, output_dir=job_dir, owner_authorized=True, source_receipts=[{"brief_id": brief["id"], "prompt_sha256": hashlib.sha256(brief["prompt"].encode()).hexdigest(), "checkpoint": CHECKPOINT, "checkpoint_terms": "UNVERIFIED", "purpose": "held campaign visual candidate for Pictora Image Editor", "execution_location": "local_comfyui"}])
        result = collect(receipt["job_id"], output_dir=job_dir, timeout_seconds=1800, poll_interval=2)
        if result.get("state") != "COMPLETE":
            raise RuntimeError(f"Pictora campaign asset {brief['id']} ended in {result.get('state')}")
        generated = [job_dir / row["path"] for row in result.get("artifacts") or [] if Path(row["path"]).suffix.casefold() == ".png"]
        if not generated:
            raise RuntimeError(f"Pictora returned no image for {brief['id']}")
        shutil.copy2(generated[0], target)
        with Image.open(target) as image:
            dimensions = list(image.size)
        records.append({"asset_id": brief["id"], "role": brief["role"], "path": str(target.relative_to(ROOT)), "sha256": sha(target), "bytes": target.stat().st_size, "dimensions": dimensions, "workflow": str(work_path.relative_to(ROOT)), "workflow_sha256": sha(work_path), "job_receipt": str((job_dir / "PICTORA_JOB_RECEIPT.json").relative_to(ROOT)), "prompt": brief["prompt"]})
    manifest = {"schema": "dio.pictora.image_editor.campaign_visual_pool.v1", "generator": {"organ": "Pictora", "comfyui_version": snapshot.get("comfyui_version"), "checkpoint": CHECKPOINT, "remote_processing": False}, "assets": records, "commercial_validation": "UNPROVED", "human_visual_review": "REQUIRED", "release_authorized": False, "campaign_diversity": "four distinct generated sources; review still required"}
    (PACK / "PICTORA_IMAGE_EDITOR_CAMPAIGN_POOL.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
