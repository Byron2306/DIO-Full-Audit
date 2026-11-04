#!/usr/bin/env python3
"""Create first Sonoris/Pictora key art with local Pictora/ComfyUI and receipts."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from products.pictora_organ import collect, discover, submit  # noqa: E402

PACK = ROOT / "media/product_asset_packs/dio_creative_organs_v1"
SITE_ASSET_REPO = Path("/tmp/dio-workflows-site")
CHECKPOINT = "epicrealism_naturalSinRC1VAE.safetensors"

BRIEFS = [
    {
        "id": "sonoris",
        "seed": 2026102811,
        "filename": "SONORIS_MUSICAL_MORPHOLOGY_HERO.png",
        "prompt": (
            "Premium cinematic hero artwork for Sonoris, an experimental music composition and learning organ. "
            "On a deep near-black obsidian field, a single elegant instrument constellation emerges from a luminous "
            "golden orbital geometry: fine strings bend into sound waves, a few piano keys dissolve into a warm synth "
            "oscillator, with delicate abstract silhouettes suggesting saxophone, flute and violin. The central form "
            "feels like music moving through embodied gestures, interwoven curves changing from a grounded pulse into "
            "a graceful rising phrase. Sophisticated black-and-gold DIO visual language, restrained champagne-gold "
            "highlights, precision line work, dark negative space, cinematic volumetric glow, premium editorial "
            "product artwork, clean horizontal composition, one focal subject, no people, no readable text, no letters, "
            "no logos, no watermark."
        ),
    },
    {
        "id": "pictora",
        "seed": 2026102812,
        "filename": "PICTORA_LOCAL_IMAGE_FORGE_HERO.png",
        "prompt": (
            "Premium cinematic hero artwork for Pictora, a sovereign local image creation and editing organ. "
            "A precise golden orbital frame floats in a deep black studio, holding one luminous image-plane that "
            "transforms from a sketched wireframe into a richly rendered imagined world: dramatic indigo mountain "
            "forms, an emerald botanical detail and a small amber sun, all contained inside one elegant coherent "
            "visual rather than a collage. Fine gold geometry and a controlled central glow connect the image-plane "
            "to an understated creative engine below it. Match the DIO website's black obsidian and restrained gold "
            "orbital visual system; high-end editorial technology art, precise, cinematic, generous dark negative "
            "space, clean horizontal composition, no people, no readable text, no letters, no logos, no watermark."
        ),
    },
]


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _workflow(brief: dict) -> dict:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CHECKPOINT}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": brief["prompt"], "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "text, typography, letters, logo, watermark, collage, border, extra central objects, blurry, low contrast, oversaturated, plastic texture", "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 640, "height": 360, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "seed": brief["seed"], "steps": 19, "cfg": 6.8, "sampler_name": "dpmpp_2m", "scheduler": "karras", "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0], "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": f"DIO_{brief['id'].upper()}_ORGAN_HERO"}},
    }


def main():
    snapshot = discover()
    available = snapshot.get("available_nodes", [])
    required = {"CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "KSampler", "VAEDecode", "SaveImage"}
    if not required.issubset(available):
        raise SystemExit("Local Pictora is missing required ComfyUI nodes")
    models = json.loads(__import__("urllib.request").request.urlopen(snapshot["endpoint"] + "/models/checkpoints", timeout=20).read())
    if CHECKPOINT not in models:
        raise SystemExit(f"Pinned Pictora checkpoint unavailable: {CHECKPOINT}")
    assets_dir = PACK / "assets"
    jobs_dir = PACK / "pictora_jobs"
    workflows_dir = PACK / "workflows"
    for directory in (assets_dir, jobs_dir, workflows_dir): directory.mkdir(parents=True, exist_ok=True)
    results = []
    for brief in BRIEFS:
        workflow = _workflow(brief)
        workflow_path = workflows_dir / f"{brief['id']}_hero_api.json"
        target_path = assets_dir / brief["filename"]
        job_dir = jobs_dir / brief["id"]
        workflow_text = json.dumps(workflow, indent=2, ensure_ascii=False) + "\n"
        if workflow_path.exists() and workflow_path.read_text(encoding="utf-8") != workflow_text:
            raise SystemExit(f"Existing workflow differs from current brief; refusing to replace: {workflow_path}")
        if not workflow_path.exists(): workflow_path.write_text(workflow_text, encoding="utf-8")
        if target_path.exists():
            # Preserve an already completed canonical asset on reruns.
            receipt_path = job_dir / "PICTORA_JOB_RECEIPT.json"
            result = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else {"state": "COMPLETE", "job_id": "previously_generated"}
        else:
            receipt_path = job_dir / "PICTORA_JOB_RECEIPT.json"
            if receipt_path.exists():
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                if receipt.get("workflow") != workflow: raise SystemExit(f"Existing Pictora job workflow differs for {brief['id']}")
                result = collect(receipt["job_id"], output_dir=job_dir, timeout_seconds=1800, poll_interval=2.0)
            else:
                receipt = submit(workflow, output_dir=job_dir, owner_authorized=True)
                result = collect(receipt["job_id"], output_dir=job_dir, timeout_seconds=1800, poll_interval=2.0)
        if result.get("state") not in {"COMPLETE", "COMPLETED"}:
            raise SystemExit(f"Pictora {brief['id']} generation ended in state {result.get('state')}; inspect {job_dir}")
        if not target_path.exists():
            candidates = [job_dir / row["path"] for row in result.get("artifacts", []) if Path(row["path"]).suffix.lower() == ".png"]
            if not candidates: candidates = [p for p in job_dir.rglob("*.png") if p.is_file()]
            if not candidates: raise SystemExit(f"Pictora returned no PNG for {brief['id']}; inspect {job_dir}")
            shutil.copy2(candidates[0], target_path)
        results.append({"organ": brief["id"], "path": str(target_path.relative_to(ROOT)), "sha256": _sha(target_path),
                        "bytes": target_path.stat().st_size, "workflow": str(workflow_path.relative_to(ROOT)),
                        "workflow_sha256": _sha(workflow_path), "job_receipt": str((job_dir / "PICTORA_JOB_RECEIPT.json").relative_to(ROOT)),
                        "job_id": result["job_id"], "generation_state": result["state"]})
    manifest = {
        "schema": "dio.pictora.organ_asset_pack.v1",
        "pack_id": "dio-creative-organs-" + PACK.name.replace("dio_creative_organs_", ""),
        "generator": {"organ": "Pictora", "endpoint": snapshot["endpoint"], "comfyui_version": snapshot["comfyui_version"], "checkpoint": CHECKPOINT, "remote_processing": False},
        "visual_references": {
            "repository": "https://github.com/Byron2306/DIO-Workflows",
            "checkout_commit": subprocess_check_commit(),
            "reviewed_assets": ["assets/premium/dio-hero-product-2026.webp", "assets/premium/dio-gilded-card-frame.webp"],
            "source_images_uploaded_to_generator": False,
            "direction": "obsidian black, fine gold orbital geometry, one restrained luminous focal point"
        },
        "human_visual_review": "PENDING",
        "release_authorized": False,
        "assets": results,
    }
    (PACK / "PICTORA_ORGAN_ASSET_PACK.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


def subprocess_check_commit():
    import subprocess
    try:
        return subprocess.check_output(["git", "-C", str(SITE_ASSET_REPO), "rev-parse", "HEAD"], text=True, timeout=10).strip()
    except Exception:
        return None


if __name__ == "__main__": main()
