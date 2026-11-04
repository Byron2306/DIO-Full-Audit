"""Build a held Sonoris + Pictora review product from pinned local assets."""
from __future__ import annotations

import hashlib
import html
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "media/sonoris/releases/black_metal_where_pines_forget_v3"
IDENTITY = ROOT / "media/product_asset_packs/dio_creative_organs_site_matched_v2"
MASTER = RELEASE / "WHERE_THE_PINES_FORGET_REVIEW_MASTER_V4.mp3"
SONORIS_RECEIPT = RELEASE / "SONORIS_LOCAL_REVIEW_RECEIPT_V4.json"
MANIFEST = IDENTITY / "CREATIVE_ORGAN_IDENTITY_PACK.json"
ART = IDENTITY / "assets/SONORIS_ORGAN_BANNER_1920x1080.jpg"
OUT = RELEASE / "final_product_candidate"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(output: Path = OUT) -> dict:
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("review product output must be empty")
    source_receipt = json.loads(SONORIS_RECEIPT.read_text())
    audio_row = next((row for row in source_receipt["artifacts"] if row["path"].endswith(MASTER.name)), None)
    if not audio_row or sha(MASTER) != audio_row["sha256"]:
        raise ValueError("Sonoris review audio does not match its receipt")
    identity = json.loads(MANIFEST.read_text())
    art_row = next((row for row in identity["assets"] if row["path"].endswith(ART.name)), None)
    if not art_row or sha(ART) != art_row["sha256"]:
        raise ValueError("Pictora visual does not match its identity manifest")
    output.mkdir(parents=True, exist_ok=True)
    audio = output / "where-the-pines-forget.mp3"
    artwork = output / "sonoris-pictora-visual-preview.jpg"
    video = output / "where-the-pines-forget-review.mp4"
    shutil.copy2(MASTER, audio)
    shutil.copy2(ART, artwork)
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-loop", "1", "-i", str(artwork),
                    "-i", str(audio), "-c:v", "libx264", "-tune", "stillimage", "-crf", "24", "-pix_fmt", "yuv420p",
                    "-r", "24", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(video)], check=True)
    title = "Where the Pines Forget"
    (output / "index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{html.escape(title)} · DIO Sonoris review</title>'
        '<style>body{margin:0;background:#090b0e;color:#eee;font:16px/1.5 system-ui}main{max-width:980px;margin:auto;padding:32px}'
        'img,video{width:100%;height:auto}h1{color:#dbc083}a{color:#dbc083}small{color:#aaa}</style><main>'
        f'<h1>{html.escape(title)}</h1><p>Sonoris composition · Pictora visual identity preview</p>'
        '<img src="sonoris-pictora-visual-preview.jpg" alt="Abstract Sonoris organ artwork for review">'
        '<p><audio controls src="where-the-pines-forget.mp3"></audio></p>'
        '<video controls preload="metadata" poster="sonoris-pictora-visual-preview.jpg" src="where-the-pines-forget-review.mp4"></video>'
        '<p><small>Local review candidate. Human listening and visual review required. Commercial release held pending instrument and image rights.</small></p>'
        '<p><a href="CREATIVE_PRODUCT_RECEIPT.json">Review provenance receipt</a></p></main></html>\n', encoding="utf-8")
    receipt = {
        "schema": "dio.creative_product_candidate.v1", "title": title,
        "organs": ["sonoris", "pictora"], "state": "HELD_FOR_REVIEW",
        "source_receipts": {"sonoris": {"path": str(SONORIS_RECEIPT.relative_to(ROOT)), "sha256": sha(SONORIS_RECEIPT)},
                            "pictora": {"path": str(MANIFEST.relative_to(ROOT)), "sha256": sha(MANIFEST)}},
        "artifacts": [{"path": p.name, "sha256": sha(p), "bytes": p.stat().st_size}
                      for p in (audio, artwork, video, output / "index.html")],
        "visual_role": "organ_identity_preview_not_song_specific_cover_art",
        "human_listening_review": "REQUIRED", "human_visual_review": "REQUIRED",
        "rights_state": "UNVERIFIED_FOR_COMMERCIAL_RELEASE",
        "commercial_validation": "UNPROVED", "release_authorized": False,
    }
    (output / "CREATIVE_PRODUCT_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
