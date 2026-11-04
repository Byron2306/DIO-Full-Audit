#!/usr/bin/env python3
"""Render a reviewable gallery of live Pictora product integrations."""
from __future__ import annotations

import hashlib
import html
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from adapters.document_studio.art_direction import build_art_direction
from adapters.document_studio.local_media_compositor import render_art_directed_scene, resolve_product_audience
from products.pictora_visual_studio import attach_html_visual

OUT = ROOT / "deliverables/pictora_image_editor/live_wiring_evidence"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def copy_preview(key: str, source_rel: str, product: str, context: str) -> dict:
    source = ROOT / source_rel
    if not source.is_file():
        return {"id": key, "state": "SOURCE_MISSING", "source": source_rel}
    folder = OUT / "product_previews" / key
    folder.mkdir(parents=True, exist_ok=False)
    target = folder / "index.html"
    shutil.copy2(source, target)
    for name in ("styles.css", "app.js"):
        sibling = source.parent / name
        if sibling.is_file():
            shutil.copy2(sibling, folder / name)
    result = attach_html_visual(target, product=product, context=context)
    receipt = Path(result["receipt"]) if result.get("receipt") else None
    return {"id": key, "state": result.get("state"), "source": source_rel, "source_sha256": sha(source), "preview": str(target.relative_to(ROOT)), "preview_sha256": sha(target), "pictora_receipt": str(receipt.relative_to(ROOT)) if receipt else None, "asset": str(Path(result["asset"]).relative_to(ROOT)) if result.get("asset") else None}


def render_editor_campaign() -> list[dict]:
    manifest_path = ROOT / "media/product_asset_packs/pictora_image_editor_v1/PICTORA_IMAGE_EDITOR_CAMPAIGN_POOL.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = {row["asset_id"]: ROOT / row["path"] for row in manifest.get("assets") or []}
    product, audience = resolve_product_audience("PICTORA_IMAGE_EDITOR--marketing_creative_teams")
    scenes = [
        {"scene_id": "editor_hook", "role": "hook", "screen_text": "Your photo. Your eye. Your edit.", "visual": "Photographer working deliberately with a real image."},
        {"scene_id": "retouch", "role": "workflow_demo", "screen_text": "Light. Colour. Fine detail.", "visual": "Close retouching detail and photo material."},
        {"scene_id": "finish", "role": "proof", "screen_text": "Upscale. Cut out. Keep the original.", "visual": "A finished photo and preserved original on a work surface."},
        {"scene_id": "review", "role": "human_context", "screen_text": "Every edit stays reviewable.", "visual": "A creative professional reviewing their final photo."},
    ]
    story = {"schema": "dio.pictora.editor_campaign_story.v1", "family_id": "PICTORA_IMAGE_EDITOR--marketing_creative_teams", "surface": "landscape_explainer", "title": "Pictora Image Editor", "creative_direction": {"audience_archetype": "professional_services", "visual_grammar": "tactile black and gold creative photography"}, "scenes": scenes}
    story["story_hash"] = "sha256:" + hashlib.sha256(json.dumps(story, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    art = build_art_direction(story)
    campaign_dir = OUT / "pictora_editor_ad"
    campaign_dir.mkdir(parents=True, exist_ok=False)
    rows = []
    for index, (scene, directed) in enumerate(zip(scenes, art["scenes"], strict=True), 1):
        source_id = ["editorial_workspace", "retouch_detail", "photo_finish", "creative_handoff"][index - 1]
        image_path = sources[source_id]
        image = Image.open(image_path)
        output = campaign_dir / f"pictora_editor_{index:02d}_{scene['role']}.jpg"
        row = render_art_directed_scene(source=image, size=(1280, 720), product={**product, "brand_owner": "dio"}, audience=audience, scene={**scene, **directed}, art_language=art.get("art_language") or {}, output=output, scene_index=index, art_direction_hash=str(art.get("art_direction_hash") or ""))
        rows.append({"path": str(output.relative_to(ROOT)), "sha256": sha(output), "source_asset_id": source_id, "source_path": str(image_path.relative_to(ROOT)), "source_sha256": sha(image_path), "scene_role": scene["role"], "display_copy": directed["display_copy"], "bytes": output.stat().st_size})
    receipt = {"schema": "dio.pictora.image_editor.campaign_preview.v1", "family_id": story["family_id"], "story_hash": story["story_hash"], "art_direction_hash": art["art_direction_hash"], "frames": rows, "remote_processing": False, "external_publication": False, "human_visual_review": "REQUIRED", "model_commercial_validation": "UNPROVED", "release_authorized": False}
    (campaign_dir / "PICTORA_EDITOR_CAMPAIGN_PREVIEW_RECEIPT.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return rows


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "PICTORA_LIVE_WIRING_EVIDENCE.json").exists():
        raise FileExistsError("Pictora live wiring evidence already exists; inspect it or choose a new output version.")
    previews = [
        copy_preview("homs_learning_studio", "acceptance_runs/68-product-integration-20261027/canonical-repaired/normal/homs-learning-studio/EXECUTION/SHARED_PRODUCTION_FINISH/HOMS-Learning-Studio-97d4446bdb96-format-core-review.html", "homs_learning_studio", "Geography"),
        copy_preview("accessible_publish", "acceptance_runs/68-product-integration-20261027/canonical-repaired/normal/accessible-publish/EXECUTION/ACCESSIBLE_PUBLICATION.html", "accessible_publish", "accessible publication review"),
        copy_preview("document_studio", "acceptance_runs/68-product-integration-20261027/studios-integrated/article_publication_studio/run-a/native_base/native/document_studio/CONTROLLED_PREVIEW.html", "document_studio", "document review"),
        copy_preview("correspondence_studio", "acceptance_runs/68-product-integration-20261027/studios-integrated/professional_correspondence_studio/run-a/closure/customer/PROFESSIONAL_CORRESPONDENCE_REVIEW.html", "professional_correspondence", "correspondence review"),
        copy_preview("campaign_lab", "acceptance_runs/68-product-integration-20261027/canonical-repaired/normal/campaign-lab/EXECUTION/SHARED_PRODUCTION_FINISH/Campaign-Lab-13d9065e784d-format-core-review.html", "campaign_lab", "campaign materials"),
    ]
    frames = render_editor_campaign()
    site_root = OUT / "site_studio_run/customer/FULL_GRADE_SITE"
    site_receipt = site_root / "proof/SITE_PICTORA_VISUAL_CANDIDATE.json"
    site_html = site_root / "index.html"
    if not site_html.is_file() or not site_receipt.is_file():
        raise FileNotFoundError("Run the full Site Studio proof before building the Pictora evidence index")
    manifest = {
        "schema": "dio.pictora.live_wiring_evidence.v1",
        "generated_at": "2026-10-28",
        "local_comfyui": True,
        "integrations": previews,
        "site_studio": {"preview": str(site_html.relative_to(ROOT)), "receipt": str(site_receipt.relative_to(ROOT)), "receipt_sha256": sha(site_receipt)},
        "market_command_campaign": {"preview_receipt": "deliverables/pictora_image_editor/live_wiring_evidence/market_command_campaign/DOCUMENT_STUDIO_LOCAL_COMPOSITION_LANDSCAPE_EXPLAINER.json", "state": json.loads((OUT / "market_command_campaign/DOCUMENT_STUDIO_LOCAL_COMPOSITION_LANDSCAPE_EXPLAINER.json").read_text()).get("visual_material_selection", {}).get("state"), "human_visual_release": "NEEDS_YOU"},
        "pictora_editor_campaign": {"receipt": "deliverables/pictora_image_editor/live_wiring_evidence/pictora_editor_ad/PICTORA_EDITOR_CAMPAIGN_PREVIEW_RECEIPT.json", "frame_count": len(frames), "release_authorized": False},
        "photo_edit_jobs": [
            "deliverables/pictora_image_editor/jobs/dio-brand-banner-retouch-demo-v1/PICTORA_IMAGE_EDIT_RECEIPT.json",
            "deliverables/pictora_image_editor/jobs/pictora-realesrgan-upscale-demo-v1/PICTORA_IMAGE_EDIT_RECEIPT.json",
            "deliverables/pictora_image_editor/jobs/pictora-background-removal-demo-v1/PICTORA_IMAGE_EDIT_RECEIPT.json",
        ],
        "commercial_validation": "UNPROVED",
        "external_publication": False,
    }
    manifest_path = OUT / "PICTORA_LIVE_WIRING_EVIDENCE.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    cards = []
    for row in previews:
        if row.get("preview"):
            cards.append(f"<article><p class='tag'>CONNECTED OUTPUT</p><h2>{html.escape(row['id'].replace('_',' ').title())}</h2><p>Source preview copied from retained DIO execution evidence; Pictora asset and hash receipt attached for inspection.</p><a href='{html.escape(row['preview'])}'>Open preview ↗</a></article>")
    cards.extend([
        "<article><p class='tag'>SITE STUDIO · LIVE RUN</p><h2>Full-grade Site Studio</h2><p>The current Site Studio pipeline rendered eight governed Format Core scenes and attached a held Pictora visual candidate.</p><a href='site_studio_run/customer/FULL_GRADE_SITE/index.html'>Open generated site ↗</a> · <a href='site_studio_run/customer/FULL_GRADE_SITE/proof/SITE_PICTORA_VISUAL_CANDIDATE.json'>Pictora receipt</a></article>",
        "<article><p class='tag'>MARKET COMMAND → NICHEFOUNDRY</p><h2>Campaign frame pool</h2><p>Six campaign frames consumed Pictora-generated image sources. The source/model review gate remains held.</p><a href='market_command_campaign/assets/landscape_explainer_01_question.jpg'>Open first frame ↗</a> · <a href='market_command_campaign/DOCUMENT_STUDIO_LOCAL_COMPOSITION_LANDSCAPE_EXPLAINER.json'>Composition receipt</a></article>",
        "<article><p class='tag'>PICTORA IMAGE EDITOR · CAMPAIGN PREVIEW</p><h2>Four custom image-editor frames</h2><p>Generated as separate visual concepts, composed with the Pictora product profile, and retained with source prompts and hashes.</p><a href='pictora_editor_ad/pictora_editor_01_hook.jpg'>Open ad frame ↗</a> · <a href='pictora_editor_ad/PICTORA_EDITOR_CAMPAIGN_PREVIEW_RECEIPT.json'>Frame receipt</a></article>",
        "<article><p class='tag'>LOCAL IMAGE EDITOR · WORKING PREVIEW</p><h2>Pictora Image Editor</h2><p>Adjust exposure, contrast, saturation, tint and sharpness; apply local denoise, clone-stamp retouch, background removal and RealESRGAN upscale.</p><a href='../../../sites/pictora-image-editor/index.html'>Open editor interface source ↗</a></article>",
    ])
    page = """<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Pictora · live wiring evidence</title><style>body{margin:0;background:#090b0f;color:#f4f0e4;font:16px/1.55 system-ui;}.wrap{max-width:1120px;margin:auto;padding:32px 20px 60px}header{border-bottom:1px solid #97752b;padding-bottom:24px}.eyebrow,.tag{font-size:.72rem;font-weight:850;letter-spacing:.14em;color:#dbb74d;text-transform:uppercase}h1{font-size:clamp(2.7rem,7vw,5.5rem);line-height:.95;letter-spacing:-.06em;max-width:840px;margin:18px 0}header p{color:#bfc1c1;max-width:780px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:14px;margin:26px 0}.grid article{padding:18px;border:1px solid #34353a;background:#12151a;border-radius:12px}.grid h2{margin:5px 0 10px;font-size:1.18rem}.grid p:not(.tag){color:#bfc1c1;font-size:.92rem}.grid a{color:#f2d989}.proof{display:flex;gap:18px;flex-wrap:wrap;margin:14px 0}.proof img{width:min(100%,500px);height:auto;border:1px solid #9e813e;border-radius:10px}.gate{padding:13px 16px;border-left:4px solid #d5aa42;background:#19170f;color:#e7d39f}.footer{color:#aaa;font-size:.8rem;margin-top:32px}@media(max-width:600px){.wrap{padding:20px 13px}}</style></head><body><main class='wrap'><header><p class='eyebrow'>DIO / PICTORA · REAL OUTPUTS</p><h1>Not just a wiring diagram.<br><span style='color:#d8ad48'>Actual images, pages and receipts.</span></h1><p>This folder contains local output artifacts from the Pictora integrations and image editor. Open the previews and inspect each receipt. Original proof runs were copied before visual attachment; the Site Studio item is a fresh run of the current integration.</p><p class='gate'>Local ComfyUI only. Generated image rights are not yet adjudicated; marketing, publication, educator and correspondence release remain human-held.</p></header><section class='proof'><div><p class='eyebrow'>CAMPAIGN VISUAL POOL</p><img src='pictora_campaign_contact_sheet.jpg' alt='Four Pictora-generated campaign image concepts showing a photographer workspace, retouch detail, finished imagery and creative review'></div><div><p class='eyebrow'>MARKET COMMAND FRAMES</p><img src='market_command_campaign_contact_sheet.jpg' alt='Six Pictora-generated source images composed as a DIO campaign story'></div></section><section class='grid'>""" + "".join(cards) + "</section><p class='footer'>Commercial validation: UNPROVED · External publication: REFUSED · Human visual review: REQUIRED. Manifest: <a href='PICTORA_LIVE_WIRING_EVIDENCE.json' style='color:#f2d989'>open the complete evidence manifest</a>.</p></main></body></html>"
    (OUT / "index.html").write_text(page, encoding="utf-8")
    print(json.dumps({"evidence_index": str((OUT / 'index.html').relative_to(ROOT)), "manifest": str(manifest_path.relative_to(ROOT)), "connected_preview_count": len(previews), "pictora_editor_campaign_frames": len(frames)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
