"""Pictora visual candidates for governed customer-facing HTML previews.

This is a presentation layer only: generated images are decorative, provenance is
retained, source evidence is untouched, and every attached candidate stays held
for human review until the local model's commercial terms are checked.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HOMS_BANK = ROOT / "deliverables/homs_tight8_pictora_visual_source_bank_v1"
ORGANS = ROOT / "media/product_asset_packs/dio_creative_organs_site_matched_v2/assets"

SUBJECTS = {
    "afrikaans": "afrikaans_language", "english": "english_language",
    "geography": "geography", "history": "history",
    "life orientation": "life_orientation", "life sciences": "life_sciences",
    "mathematics": "mathematics", "physical sciences": "physical_sciences",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-") or "visual"


def find_candidate(*, product: str, context: str = "") -> tuple[Path, str] | None:
    """Return an existing local Pictora asset suitable for an internal preview."""
    if product == "homs_learning_studio":
        normalized = " ".join(context.casefold().split())
        subject = next((key for label, key in SUBJECTS.items() if label in normalized), None)
        if subject:
            path = HOMS_BANK / "pictora_jobs" / subject / "node-7-1.png"
            if path.is_file():
                return path, f"Pictora subject illustration: {subject.replace('_', ' ')}"
    # Site-matched organ artwork supplies an authored DIO visual language for
    # previews where product-specific generated imagery is not yet available.
    path = ORGANS / "PICTORA_ORGAN_BANNER_1920x1080.jpg"
    if path.is_file():
        return path, "Pictora image forge artwork"
    return None


def attach_html_visual(html_path: Path, *, product: str, context: str = "") -> dict[str, Any]:
    """Add a local, responsive, decorative visual to an HTML review artifact."""
    html_path = html_path.resolve()
    if not html_path.is_file():
        return {"state": "SKIPPED", "reason": "html_artifact_missing"}
    chosen = find_candidate(product=product, context=context)
    if not chosen:
        return {"state": "SKIPPED", "reason": "no_local_pictora_asset"}
    source, description = chosen
    asset_dir = html_path.parent / "pictora_visuals"
    asset_dir.mkdir(parents=True, exist_ok=True)
    target = asset_dir / f"{_slug(product)}-{_slug(context)[:48]}{source.suffix.lower()}"
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)
    relative = target.relative_to(html_path.parent).as_posix()
    visual_block = (
        "<style>.dio-pictora-visual{margin:1.5rem 0 2rem;overflow:hidden;border:1px solid #8b6b25;"
        "border-radius:14px;background:#0d1014}.dio-pictora-visual img{display:block;width:100%;"
        "max-height:360px;object-fit:cover}.dio-pictora-visual figcaption{padding:.65rem 1rem;"
        "color:#c6c9ce;font-size:.82rem}</style>"
        f"<figure class=\"dio-pictora-visual\"><img src=\"{html.escape(relative, quote=True)}\" alt=\"\">"
        f"<figcaption>{html.escape(description)} · illustrative design candidate; human review required.</figcaption></figure>"
    )
    content = html_path.read_text(encoding="utf-8")
    video_poster = False
    if product == "homs_learning_studio" and re.search(r"<video\b", content, re.I) and not re.search(r"<video\b[^>]*\bposter=", content, re.I):
        content = re.sub(
            r"<video\b",
            '<video poster="' + html.escape(relative, quote=True) + '"',
            content,
            count=1,
            flags=re.I,
        )
        video_poster = True
    if "dio-pictora-visual" not in content:
        if re.search(r"</main\s*>", content, re.I):
            content = re.sub(r"</main\s*>", visual_block + "</main>", content, count=1, flags=re.I)
        elif re.search(r"<body[^>]*>", content, re.I):
            content = re.sub(r"(<body[^>]*>)", r"\1" + visual_block, content, count=1, flags=re.I)
        else:
            content = visual_block + content
        html_path.write_text(content, encoding="utf-8")
    receipt = {
        "schema": "dio.pictora.html_visual_attachment.v1",
        "product": product,
        "artifact": str(html_path),
        "asset": relative,
        "asset_sha256": _sha(target),
        "source_asset": str(source.relative_to(ROOT)) if source.is_relative_to(ROOT) else source.name,
        "source_sha256": _sha(source),
        "video_preview_poster_attached": video_poster,
        "alt_text": "", "meaning": "decorative_only",
        "commercial_validation": "UNPROVED",
        "human_review": "REQUIRED",
        "release_authorized": False,
        "source_evidence_modified": False,
    }
    receipt_path = html_path.parent / f"{html_path.stem}_PICTORA_VISUAL_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"state": "ATTACHED_FOR_REVIEW", "receipt": str(receipt_path), "asset": str(target)}
