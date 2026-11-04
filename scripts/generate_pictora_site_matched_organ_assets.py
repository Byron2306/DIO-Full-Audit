#!/usr/bin/env python3
"""Generate Sonoris/Pictora art with a current DIO website image as local img2img anchor."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from products.pictora_organ import collect, discover, submit, upload_image  # noqa: E402

SITE = Path("/tmp/dio-workflows-site")
SOURCE = SITE / "assets/premium/dio-hero-product-2026.webp"
PACK = ROOT / "media/product_asset_packs/dio_creative_organs_site_matched_v1"
CHECKPOINT = "epicrealism_naturalSinRC1VAE.safetensors"
BRIEFS = [
    {
        "id": "sonoris", "seed": 2026102831,
        "filename": "SONORIS_ORBITAL_MUSIC_ENGINE.png",
        "prompt": (
            "Create a polished 16:9 DIO product hero image. Preserve the supplied reference's deep black obsidian "
            "background, fine concentric gold orbit rings, central luminous gold focal point, precision filigree, "
            "and cinematic negative space. Transform the central focal object into a legible, elegant musical "
            "composition engine: a curved miniature piano keyboard, analog synth oscillator, fine strings becoming "
            "a rising sound wave, and small refined saxophone and flute silhouettes, all arranged as one coherent "
            "gold instrument constellation inside the orbital architecture. Show music as motion and interaction, "
            "not as a pile of instruments. Rich black and restrained champagne gold, crisp controlled glow, premium "
            "editorial technology art, no people, no portraits, no faces, no typography, no letters, no logo, no watermark."
        ),
    },
    {
        "id": "pictora", "seed": 2026102832,
        "filename": "PICTORA_ORBITAL_IMAGE_FORGE.png",
        "prompt": (
            "Create a polished 16:9 DIO product hero image. Preserve the supplied reference's deep black obsidian "
            "background, fine concentric gold orbit rings, central luminous gold focal point, precision filigree, "
            "and cinematic negative space. Transform the central focal object into Pictora, a local image creation "
            "forge: one clear gold-edged floating canvas showing a beautifully rendered miniature imagined world, "
            "a midnight blue mountain, emerald botanical leaf, and amber sun, with the image plane resolving from "
            "fine golden generative lines. Make the canvas unmistakably an artwork held in the center of the orbital "
            "machine. Premium editorial technology art, deep black and restrained champagne gold, controlled color "
            "only inside the canvas, no people, no portraits, no faces, no typography, no letters, no logo, no watermark."
        ),
    },
]


def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""): h.update(block)
    return h.hexdigest()


def workflow(brief: dict, uploaded_name: str) -> dict:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CHECKPOINT}},
        "2": {"class_type": "LoadImage", "inputs": {"image": uploaded_name}},
        "3": {"class_type": "ImageScale", "inputs": {"image": ["2", 0], "upscale_method": "lanczos", "width": 640, "height": 360, "crop": "disabled"}},
        "4": {"class_type": "VAEEncode", "inputs": {"pixels": ["3", 0], "vae": ["1", 2]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": brief["prompt"], "clip": ["1", 1]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "person, human, face, portrait, body, hands, fashion, text, letters, logo, watermark, collage, border, blurry, muddy details, washed out black", "clip": ["1", 1]}},
        "7": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "seed": brief["seed"], "steps": 24, "cfg": 6.2, "sampler_name": "dpmpp_2m", "scheduler": "karras", "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["4", 0], "denoise": 0.55}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["1", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": f"DIO_{brief['id'].upper()}_SITE_MATCHED"}},
    }


def main():
    if not SOURCE.is_file(): raise SystemExit(f"Current DIO Workflows style reference not found: {SOURCE}")
    site_commit = subprocess.check_output(["git","-C",str(SITE),"rev-parse","HEAD"],text=True,timeout=10).strip()
    snapshot = discover()
    needed = {"CheckpointLoaderSimple","LoadImage","ImageScale","VAEEncode","CLIPTextEncode","KSampler","VAEDecode","SaveImage"}
    if not needed.issubset(snapshot.get("available_nodes", [])): raise SystemExit("Local Pictora lacks an img2img node required by this workflow")
    PACK.mkdir(parents=True,exist_ok=True)
    assets=PACK/"assets"; workflows=PACK/"workflows"; jobs=PACK/"pictora_jobs"
    for p in (assets,workflows,jobs): p.mkdir(parents=True,exist_ok=True)
    for brief in BRIEFS:
        final=assets/brief["filename"]; workfile=workflows/f"{brief['id']}_site_matched_api.json"; jobdir=jobs/brief["id"]
        if any(p.exists() for p in (final,workfile,jobdir)): raise SystemExit(f"Refusing to overwrite existing site-matched Pictora output: {brief['id']}")
        with tempfile.TemporaryDirectory(prefix="pictora-dio-style-") as temp:
            refpng=Path(temp)/"dio-hero-product-2026.png"
            with Image.open(SOURCE) as im: im.convert("RGB").save(refpng,format="PNG",optimize=True)
            source_receipt=upload_image(refpng,subfolder="dio-site-style-reference")
        uploaded=source_receipt["input"]
        image_name=(uploaded.get("subfolder","")+"/" if uploaded.get("subfolder") else "")+uploaded["name"]
        graph=workflow(brief,image_name)
        workfile.write_text(json.dumps(graph,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        receipt=submit(graph,output_dir=jobdir,owner_authorized=True,source_receipts=[{
            "source_repository":"https://github.com/Byron2306/DIO-Workflows","source_commit":site_commit,
            "source_asset":"assets/premium/dio-hero-product-2026.webp","source_sha256":sha(SOURCE),
            "uploaded_copy_sha256":source_receipt["source_sha256"],"upload_result":uploaded,
            "purpose":"local image-to-image style anchor for organ artwork","execution_location":"local_comfyui"}])
        result=collect(receipt["job_id"],output_dir=jobdir,timeout_seconds=1800,poll_interval=2)
        if result.get("state")!="COMPLETE": raise SystemExit(f"Pictora job {brief['id']} ended {result.get('state')}; inspect {jobdir}")
        pngs=[jobdir/row["path"] for row in result.get("artifacts",[]) if Path(row["path"]).suffix.lower()==".png"]
        if not pngs: raise SystemExit(f"Pictora produced no image for {brief['id']}")
        final.parent.mkdir(parents=True,exist_ok=True); final.write_bytes(pngs[0].read_bytes())
    manifest={"schema":"dio.pictora.organ_asset_pack.v1","pack_id":"dio-creative-organs-site-matched-v1",
      "generator":{"organ":"Pictora","endpoint":snapshot["endpoint"],"comfyui_version":snapshot["comfyui_version"],"checkpoint":CHECKPOINT,"mode":"image_to_image","denoise":0.55,"remote_processing":False},
      "style_source":{"repository":"https://github.com/Byron2306/DIO-Workflows","commit":site_commit,"asset":"assets/premium/dio-hero-product-2026.webp","sha256":sha(SOURCE),"uploaded_to_local_comfyui":True},
      "human_review":"PENDING","release_authorized":False,
      "assets":[{"organ":b["id"],"path":str((assets/b["filename"]).relative_to(ROOT)),"sha256":sha(assets/b["filename"]),"bytes":(assets/b["filename"]).stat().st_size,"workflow":str((workflows/f"{b['id']}_site_matched_api.json").relative_to(ROOT)),"job_receipt":str((jobs/b["id"]/"PICTORA_JOB_RECEIPT.json").relative_to(ROOT))} for b in BRIEFS]}
    (PACK/"PICTORA_SITE_MATCHED_ASSET_PACK.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(manifest,indent=2,ensure_ascii=False))


if __name__=="__main__": main()
