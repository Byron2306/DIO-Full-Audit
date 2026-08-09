#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BANK = ROOT / "deliverables" / "homs_core_source_bank" / "HOMS_CORE_SOURCE_BANK.json"
DEFAULT_OUT = ROOT / "deliverables" / "homs_core_source_bank_curated"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_") or "item"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def content_bbox(image: Image.Image, threshold: int) -> tuple[int, int, int, int] | None:
    gray = image.convert("L")
    mask = gray.point(lambda pixel: 255 if pixel < threshold else 0)
    return mask.getbbox()


def padded_bbox(bbox: tuple[int, int, int, int], width: int, height: int, padding: int) -> tuple[int, int, int, int]:
    left, top, right, bottom = bbox
    return (
        max(0, left - padding),
        max(0, top - padding),
        min(width, right + padding),
        min(height, bottom + padding),
    )


def crop_ratio(original: tuple[int, int], cropped: tuple[int, int]) -> float:
    original_area = max(original[0] * original[1], 1)
    cropped_area = max(cropped[0] * cropped[1], 1)
    return round(cropped_area / original_area, 4)


def curate_image(source: Path, target: Path, threshold: int, padding: int) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image = image.convert("RGB")
        original_size = image.size
        bbox = content_bbox(image, threshold)
        if not bbox:
            image.save(target)
            return {
                "curation_status": "blocked_blank_or_unreadable_source",
                "original_size": list(original_size),
                "curated_size": list(original_size),
                "content_bbox": None,
                "crop_ratio": 1.0,
                "curation_flags": ["blank_or_unreadable_source"],
            }
        crop_box = padded_bbox(bbox, image.width, image.height, padding)
        curated = image.crop(crop_box)
        curated.save(target, optimize=True)
        ratio = crop_ratio(original_size, curated.size)
        flags = ["auto_margin_trim", "page_level_source_not_object_crop", "release_blocked_auto_crop_needs_human_review"]
        if ratio > 0.92:
            flags.append("minimal_crop_detected")
        if ratio < 0.18:
            flags.append("crop_may_be_too_aggressive")
        return {
            "curation_status": "auto_margin_trimmed_needs_review",
            "original_size": list(original_size),
            "curated_size": list(curated.size),
            "content_bbox": list(crop_box),
            "crop_ratio": ratio,
            "curation_flags": flags,
        }


def norm_token(value: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "", str(value or "").lower())


def snippet_tokens(snippet: str) -> list[str]:
    return [token for token in (norm_token(part) for part in str(snippet or "").split()) if token]


def bbox_words(pdf_path: Path, page: int, cache_dir: Path) -> tuple[list[dict[str, Any]], tuple[float, float] | None]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path = cache_dir / f"{slug(pdf_path.stem)}_p{page:03d}.bbox.html"
    if not out_path.exists():
        result = subprocess.run(
            ["pdftotext", "-bbox", "-f", str(page), "-l", str(page), str(pdf_path), str(out_path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0 or not out_path.exists():
            return [], None
    root = ET.parse(out_path).getroot()
    words: list[dict[str, Any]] = []
    page_size = None
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "page":
            page_size = (float(element.attrib.get("width", "0")), float(element.attrib.get("height", "0")))
        if tag != "word":
            continue
        text = "".join(element.itertext()).strip()
        token = norm_token(text)
        if not token:
            continue
        words.append(
            {
                "text": text,
                "token": token,
                "x_min": float(element.attrib.get("xMin", "0")),
                "y_min": float(element.attrib.get("yMin", "0")),
                "x_max": float(element.attrib.get("xMax", "0")),
                "y_max": float(element.attrib.get("yMax", "0")),
            }
        )
    return words, page_size


def find_anchor(words: list[dict[str, Any]], snippet: str) -> int | None:
    tokens = snippet_tokens(snippet)
    if not tokens:
        return None
    page_tokens = [word["token"] for word in words]
    for window in range(min(8, len(tokens)), 2, -1):
        needle = tokens[:window]
        for index in range(0, len(page_tokens) - window + 1):
            if page_tokens[index : index + window] == needle:
                return index
    for token in tokens[:6]:
        if token in page_tokens:
            return page_tokens.index(token)
    return None


def make_object_candidate(
    asset: dict[str, Any],
    source: Path,
    target: Path,
    threshold: int,
    padding: int,
    cache_dir: Path,
) -> dict[str, Any] | None:
    pdf_value = asset.get("pdf")
    page = int(asset.get("page") or 0)
    if not pdf_value or not page:
        return None
    pdf_path = resolve_path(str(pdf_value))
    if not pdf_path.exists():
        return None
    words, page_size = bbox_words(pdf_path, page, cache_dir)
    if not words or not page_size:
        return None
    anchor_index = find_anchor(words, str(asset.get("snippet") or ""))
    if anchor_index is None:
        return None

    with Image.open(source) as image:
        image = image.convert("RGB")
        page_width, page_height = page_size
        anchor = words[anchor_index]
        y_start_pt = max(0.0, anchor["y_min"] - 18.0)
        y_end_pt = min(page_height * 0.92, y_start_pt + (page_height * 0.55))
        y1 = max(0, int((y_start_pt / page_height) * image.height))
        y2 = min(image.height, int((y_end_pt / page_height) * image.height))
        if y2 <= y1 + 60:
            return None

        band = image.crop((0, y1, image.width, y2))
        bbox = content_bbox(band, threshold)
        if not bbox:
            return None
        left, top, right, bottom = padded_bbox(bbox, image.width, band.height, padding)
        crop_box = (left, y1 + top, right, y1 + bottom)
        object_crop = image.crop(crop_box)
        target.parent.mkdir(parents=True, exist_ok=True)
        object_crop.save(target, optimize=True)
        ratio = crop_ratio(image.size, object_crop.size)
        flags = ["snippet_anchored_object_candidate", "release_blocked_object_crop_needs_human_review"]
        if ratio > 0.82:
            flags.append("object_candidate_still_page_like")
        if ratio < 0.08:
            flags.append("object_candidate_may_be_too_aggressive")
        return {
            "object_candidate_png": str(target.relative_to(ROOT)),
            "object_candidate_status": "snippet_anchored_candidate_needs_review",
            "object_candidate_size": list(object_crop.size),
            "object_candidate_bbox": list(crop_box),
            "object_candidate_crop_ratio": ratio,
            "object_candidate_flags": flags,
        }


def curate_bank(bank: dict[str, Any], out_dir: Path, threshold: int, padding: int) -> dict[str, Any]:
    assets = []
    cache_dir = out_dir / ".bbox_cache"
    for asset in bank.get("assets") or []:
        source = resolve_path(str(asset.get("bank_png") or asset.get("png") or ""))
        target = out_dir / asset["subject_id"] / asset["source_type"] / "margin_trim" / Path(str(asset.get("bank_png") or source.name)).name
        object_target = out_dir / asset["subject_id"] / asset["source_type"] / "object_candidate" / Path(str(asset.get("bank_png") or source.name)).name
        curated = curate_image(source, target, threshold, padding)
        object_candidate = make_object_candidate(asset, source, object_target, threshold, padding, cache_dir)
        object_flags = object_candidate.get("object_candidate_flags", []) if object_candidate else []
        quality_flags = sorted(set((asset.get("quality_flags") or []) + curated["curation_flags"] + object_flags))
        preferred_png = object_candidate["object_candidate_png"] if object_candidate else str(target.relative_to(ROOT))
        release_gate = "blocked_until_human_source_review"
        assets.append(
            {
                **asset,
                "curated_png": str(target.relative_to(ROOT)),
                "object_candidate_png": object_candidate.get("object_candidate_png") if object_candidate else None,
                "preferred_png": preferred_png,
                "quality_flags": quality_flags,
                "source_quality_level": "smoke_ready_not_release_ready",
                "release_gate": release_gate,
                "curation": {**curated, **(object_candidate or {})},
            }
        )
    by_subject = Counter(asset["subject_id"] for asset in assets)
    flagged_by_subject = defaultdict(int)
    for asset in assets:
        if asset.get("quality_flags"):
            flagged_by_subject[asset["subject_id"]] += 1
    return {
        **bank,
        "schema": "knowedge.homs_core_source_bank_curated.v1",
        "created_at": utc_now(),
        "raw_bank_schema": bank.get("schema"),
        "curation_method": "Pillow threshold bbox margin trim plus pdftotext-bbox snippet-anchored object-candidate crops where possible. All results remain blocked for release until human review.",
        "asset_count": len(assets),
        "subjects": dict(sorted(by_subject.items())),
        "flagged_subjects": dict(sorted(flagged_by_subject.items())),
        "assets": assets,
    }


def write_markdown(path: Path, bank: dict[str, Any]) -> None:
    lines = [
        "# HOMS Curated Core Source Bank",
        "",
        "This is the curated derivative of the raw official-paper source bank.",
        "",
        "Important: these images are auto-generated source candidates. Where possible, the preferred image is a snippet-anchored object candidate; otherwise it falls back to a margin-trimmed page crop. All candidates remain blocked for release until human source review approves them.",
        "",
        f"- Assets: {bank['asset_count']}",
        "- Subjects: " + ", ".join(f"`{key}`={value}" for key, value in bank["subjects"].items()),
        "- Flagged subjects: " + (", ".join(f"`{key}`={value}" for key, value in bank["flagged_subjects"].items()) or "none"),
        "",
        "## Assets",
        "",
        "| Subject | Type | Paper | Page | Gate | Flags | Preferred Asset |",
        "|---|---|---|---:|---|---|---|",
    ]
    for asset in bank["assets"]:
        flags = ", ".join(f"`{flag}`" for flag in asset.get("quality_flags") or []) or "none"
        lines.append(
            f"| `{asset['subject_id']}` | `{asset['source_type']}` | {asset.get('paper') or ''} | {asset.get('page') or ''} | `{asset['release_gate']}` | {flags} | `{asset['preferred_png']}` |"
        )
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create margin-trimmed curated source-bank image candidates.")
    parser.add_argument("--bank", default=str(DEFAULT_BANK))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--threshold", type=int, default=245)
    parser.add_argument("--padding", type=int, default=28)
    args = parser.parse_args()

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    curated = curate_bank(load_json(Path(args.bank).expanduser().resolve()), out_dir, args.threshold, args.padding)
    write_json(out_dir / "HOMS_CORE_SOURCE_BANK_CURATED.json", curated)
    write_markdown(out_dir / "HOMS_CORE_SOURCE_BANK_CURATED.md", curated)
    print(json.dumps({"status": "completed", "out_dir": str(out_dir), "asset_count": curated["asset_count"], "flagged_subjects": curated["flagged_subjects"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
