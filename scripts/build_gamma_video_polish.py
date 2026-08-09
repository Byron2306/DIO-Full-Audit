#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
NICHEFOUNDRY = Path("/home/byron/Downloads/NicheFoundry_Phase11")
WIDTH = 1920
HEIGHT = 1080

EPISODES = {
    "evidex": NICHEFOUNDRY
    / "episodes/knowedge-evidex-evidence-pack-send-the-evidence-mess-get-back-a-review-ready-donor-audit-or-complia-b24cd1d6",
    "homs": NICHEFOUNDRY
    / "episodes/knowedge-homs-marking-relief-pack-send-the-batch-rubric-memo-and-marksheet-get-structured-marking-s-aec7fc9b",
}

PRODUCTS = {
    "evidex": {
        "brand": "EVIDEX EVIDENCE PACK",
        "accent": "#16825f",
        "ink": "#14231e",
        "gamma_dir": ROOT / "campaigns/phase3/evidex/campaign_v2/gamma/raw",
        "gamma_receipt": ROOT / "campaigns/phase3/evidex/campaign_v2/gamma/GAMMA_RECEIPT.json",
        "scenes": [
            ("evidex_hero.png", "right", "Scattered evidence. One review trail.", "proof"),
            ("evidex_mapping_proof.png", "right", "The source trail stays visible.", "proof"),
            ("evidex_mapping_proof.png", "right", "Claims mapped to their evidence.", "evidence_table"),
            ("evidex_delivery_proof.png", "left", "A pack built for inspection.", "delivery"),
            ("evidex_delivery_proof.png", "left", "Human approval stays in the loop.", "boundary"),
            ("evidex_hero.png", "right", "Start with one bounded folder.", "cta"),
        ],
    },
    "homs": {
        "brand": "HOMS MARKING RELIEF",
        "accent": "#08766f",
        "ink": "#142126",
        "gamma_dir": ROOT / "campaigns/phase3/homs/campaign_v2/gamma/raw",
        "gamma_receipt": ROOT / "campaigns/phase3/homs/campaign_v2/gamma/GAMMA_RECEIPT.json",
        "scenes": [
            ("homs_hero.png", "right", "A marking batch is waiting.", "proof"),
            ("homs_marking_proof.png", "left", "Scripts, rubric and marksheet together.", "proof"),
            ("homs_marking_proof.png", "left", "Draft marks with an explicit review gate.", "marks_table"),
            ("homs_hero.png", "right", "Feedback and review files, packaged.", "delivery"),
            ("homs_hero.png", "right", "The educator remains the final authority.", "boundary"),
            ("homs_marking_proof.png", "left", "Pilot one safe, controlled batch.", "cta"),
        ],
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)


def fit_frame(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGB")
    image = ImageOps.fit(image, (WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    image = ImageEnhance.Contrast(image).enhance(1.03)
    return image


def wrap(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.FreeTypeFont, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=face) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def evidence_rows() -> list[list[str]]:
    paths = sorted(ROOT.glob("deliverables/evidex_golden_transaction_loop/**/evidence_table.csv"))
    if not paths:
        return []
    with paths[0].open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [[row["KPI"], f"{row['Actual']} / {row['Target']}", row["Sources"].split(";")[0]] for row in rows[:4]]


def marks_rows() -> list[list[str]]:
    path = ROOT / "deliverables/homs_live_batch_test/homs-live-dummy-20260807T173535Z/marks.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [[row["student_id"].replace("student_", "Submission ").title(), f"{row['score']}/{row['max_score']}", "Review required"] for row in rows]


def add_proof_sheet(canvas: Image.Image, rows: list[list[str]], title: str, accent: str, side: str) -> None:
    if not rows:
        return
    sheet_w, sheet_h = 820, 420
    sheet = Image.new("RGBA", (sheet_w, sheet_h), "#fbfbf8")
    draw = ImageDraw.Draw(sheet)
    draw.rectangle((0, 0, sheet_w, 12), fill=accent)
    draw.text((42, 38), title, font=font(34, True), fill="#152027")
    headers = ["Item", "Result", "Trace"]
    columns = [42, 455, 610]
    for x, header in zip(columns, headers):
        draw.text((x, 102), header, font=font(18, True), fill="#536068")
    y = 143
    for row in rows:
        draw.line((42, y - 12, sheet_w - 42, y - 12), fill="#d9dddc", width=2)
        draw.text((42, y), textwrap.shorten(row[0], width=34, placeholder="..."), font=font(18), fill="#1b272c")
        draw.text((455, y), row[1], font=font(18, True), fill=accent)
        draw.text((610, y), textwrap.shorten(row[2], width=20, placeholder="..."), font=font(17), fill="#38464c")
        y += 61
    shadow = Image.new("RGBA", (sheet_w + 50, sheet_h + 50), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((24, 24, sheet_w + 24, sheet_h + 24), radius=10, fill=(0, 0, 0, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    x = 70 if side == "left" else WIDTH - sheet_w - 70
    y = HEIGHT - sheet_h - 78
    canvas.alpha_composite(shadow, (x - 24, y - 24))
    canvas.alpha_composite(sheet, (x, y))


def compose_scene(product_id: str, scene_index: int, scene: dict[str, Any]) -> tuple[Image.Image, dict[str, Any]]:
    config = PRODUCTS[product_id]
    asset_name, subject_side, headline, treatment = config["scenes"][scene_index]
    source = config["gamma_dir"] / asset_name
    canvas = fit_frame(source).convert("RGBA")

    wash = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    wash_draw = ImageDraw.Draw(wash)
    text_side = "left" if subject_side == "right" else "right"
    if text_side == "left":
        wash_draw.rectangle((0, 0, 930, HEIGHT), fill=(248, 249, 246, 232))
        x = 90
    else:
        wash_draw.rectangle((990, 0, WIDTH, HEIGHT), fill=(248, 249, 246, 232))
        x = 1080
    canvas.alpha_composite(wash)

    draw = ImageDraw.Draw(canvas)
    draw.text((x, 78), config["brand"], font=font(24, True), fill=config["accent"])
    draw.rectangle((x, 126, x + 78, 134), fill=config["accent"])
    headline_face = font(62, True)
    lines = wrap(draw, headline, headline_face, 720)
    y = 192
    for line in lines:
        draw.text((x, y), line, font=headline_face, fill=config["ink"])
        y += 76
    supporting = scene.get("voiceover", "")
    body_face = font(26)
    for line in wrap(draw, supporting, body_face, 720)[:4]:
        draw.text((x, y + 22), line, font=body_face, fill="#445159")
        y += 38

    if treatment == "evidence_table":
        add_proof_sheet(canvas, evidence_rows(), "Controlled golden-case evidence map", config["accent"], text_side)
    elif treatment == "marks_table":
        add_proof_sheet(canvas, marks_rows(), "Controlled marking proof", config["accent"], text_side)
    elif treatment == "delivery":
        draw.text((x, HEIGHT - 120), "REVIEW PACK  /  RECEIPT  /  DELIVERY", font=font(20, True), fill=config["accent"])
    elif treatment == "boundary":
        draw.text((x, HEIGHT - 120), "HUMAN APPROVAL REQUIRED", font=font(20, True), fill=config["accent"])
    elif treatment == "cta":
        draw.text((x, HEIGHT - 120), "CONTROLLED PILOT", font=font(20, True), fill=config["accent"])

    return canvas.convert("RGB"), {
        "scene_id": scene["scene_id"],
        "gamma_source": str(source),
        "gamma_receipt": str(config["gamma_receipt"]),
        "treatment": treatment,
        "synthetic_context": True,
        "proof_overlay": treatment in {"evidence_table", "marks_table"},
    }


def build_product(product_id: str) -> dict[str, Any]:
    episode = EPISODES[product_id]
    script = json.loads((episode / "script_manifest.json").read_text(encoding="utf-8"))
    output_dir = episode / "imports/visuals_polished"
    output_dir.mkdir(parents=True, exist_ok=True)
    scene_receipts = []
    for index, scene in enumerate(script["scenes"]):
        image, receipt = compose_scene(product_id, index, scene)
        output = output_dir / f"{scene['card_id']}.png"
        image.save(output, "PNG", optimize=True)
        receipt["output"] = str(output)
        receipt["sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
        scene_receipts.append(receipt)
    receipt = {
        "schema": "knowedge.gamma_video_polish.v1",
        "created_at": utc_now(),
        "product_id": product_id,
        "episode": str(episode),
        "status": "visual_review_required",
        "policy": "Gamma supplies illustrative context; controlled local artifacts supply proof; no synthetic frame is represented as a client case.",
        "scenes": scene_receipts,
    }
    (episode / "GAMMA_VIDEO_POLISH_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    receipts = [build_product(product_id) for product_id in ("evidex", "homs")]
    print(json.dumps({"products": [item["product_id"] for item in receipts], "status": "visual_review_required"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
