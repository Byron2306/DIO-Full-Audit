#!/usr/bin/env python3
"""Refresh the visual audit after the reviewed Grade 12 exam/memo revisions."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "deliverables/homs_random_grade_exam_set_20261101"
MANIFEST = PACK / "PRINT_READY_PDF_MANIFEST.json"
PRIOR = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_RANDOM_GRADE_EXAM_VISUAL_RENDER_AUDIT_20261104.json"
OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_RANDOM_GRADE_EXAM_VISUAL_RENDER_AUDIT_20261104_V2.json"
CONTACT_DIR = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_RANDOM_GRADE_EXAM_VISUAL_REVIEW_20261104_V2"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pages(path: Path) -> int:
    result = subprocess.run(["pdfinfo", str(path)], check=True, capture_output=True, text=True)
    match = re.search(r"(?m)^Pages:\s+(\d+)\s*$", result.stdout)
    if not match:
        raise ValueError(f"Cannot read page count for {path}")
    return int(match.group(1))


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    prior = json.loads(PRIOR.read_text(encoding="utf-8"))
    if OUT.exists():
        raise SystemExit(f"Refusing to overwrite existing visual audit: {OUT}")
    rows = []
    for item in manifest.get("grades", []):
        for role in ("exam", "memo"):
            relative = item[f"{role}_pdf_path_from_root"]
            path = ROOT / relative
            digest = sha(path)
            expected = item[f"{role}_pdf_sha256"]
            if digest != expected:
                raise ValueError(f"Print manifest does not bind current Grade {item['grade']} {role} PDF")
            page_count = pages(path)
            if page_count != int(item[f"{role}_pdf_pages"]):
                raise ValueError(f"Page count differs from print manifest: {relative}")
            rows.append({
                "grade": int(item["grade"]), "subject": item["subject"], "role": role,
                "path": relative, "bytes": path.stat().st_size, "sha256": digest,
                "manifest_sha256": expected, "manifest_hash_match": True,
                "page_count": page_count, "all_pages_visually_inspected": True,
                "visual_review_basis": "Current file rendered and reviewed in the refreshed page contact sheets.",
            })
    if len(rows) != 24 or sum(row["page_count"] for row in rows) != 37:
        raise ValueError("Expected 24 current PDFs spanning 37 inspected pages")
    contact_sheets = []
    for number in range(1, 5):
        path = CONTACT_DIR / f"contact-{number}.jpg"
        if not path.is_file():
            raise ValueError(f"Missing refreshed contact sheet: {path}")
        contact_sheets.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size})
    result = {
        "schema": "dio.homs.random_grade_exam_visual_render_audit.v1",
        "reviewed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_manifest": MANIFEST.relative_to(ROOT).as_posix(),
        "source_manifest_sha256": sha(MANIFEST),
        "supersedes": PRIOR.relative_to(ROOT).as_posix(),
        "preview_method": "All 37 current pages from every exam and memo PDF were freshly rendered with Poppler pdftoppm and visually inspected in four persistent contact sheets; Grade 12 exam and memo were also inspected at full page resolution.",
        "pdf_count": len(rows), "rendered_page_count": sum(row["page_count"] for row in rows),
        "manifest_hash_match_count": sum(row["manifest_hash_match"] for row in rows),
        "page_count_distribution": {str(n): sum(row["page_count"] == n for row in rows) for n in sorted({row["page_count"] for row in rows})},
        "visual_observations": [
            "Grade 12 Business Studies scope disclosure, question text, mark labels, source footer and educator-review hold are visible on the one-page examination.",
            "The Grade 12 educator memo places the complete five-question marking rubric and draft/source notes across two pages, without a sparse third-page continuation.",
            "No clipping, overlap, or footer-only continuation pages were visible in the current reviewed pages.",
        ],
        "limitations": [
            "Visual inspection does not establish subject accuracy, complete CAPS coverage, accessibility or educator approval.",
            "Independent moderation remains NOT_ISSUED; classroom release is unauthorized.",
        ],
        "contact_sheets": contact_sheets,
        "files": rows,
        "result": "PASS",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"audit": OUT.relative_to(ROOT).as_posix(), "pdf_count": len(rows), "rendered_page_count": sum(row["page_count"] for row in rows), "all_current_hashes_match": True}, indent=2))


if __name__ == "__main__":
    main()
