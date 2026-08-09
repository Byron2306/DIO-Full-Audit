#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELIVERABLES = ROOT / "deliverables"
RELEASE_ROOT = DELIVERABLES / "homs_fet_tight8_release_candidates"
BUNDLE_ROOT = RELEASE_ROOT / "FET_TIGHT8_FINAL_RELEASE"


@dataclass(frozen=True)
class Release:
    slug: str
    pack: Path
    assessment: Path
    memo: Path
    pdf: Path
    validation: Path
    expected_media: int


def release(path: str) -> Path:
    return ROOT / path


RELEASES = [
    Release(
        "afrikaans",
        release("deliverables/homs_afrikaans_release_candidate/hymark-exam-afrikaans_language-grade12-afrika-20260808T113620Z/1stOpp/assessment_pack.json"),
        release("deliverables/homs_afrikaans_release_candidate/hymark-exam-afrikaans_language-grade12-afrika-20260808T113620Z/AFRIKA_Assessment_1stOpp_20260808T113620Z.docx"),
        release("deliverables/homs_afrikaans_release_candidate/hymark-exam-afrikaans_language-grade12-afrika-20260808T113620Z/AFRIKA_Memo_1stOpp_20260808T113620Z.docx"),
        release("deliverables/homs_afrikaans_release_candidate/hymark-exam-afrikaans_language-grade12-afrika-20260808T113620Z/pdf_review/AFRIKA_Assessment_1stOpp_20260808T113620Z.pdf"),
        release("deliverables/homs_afrikaans_release_candidate/hymark-exam-afrikaans_language-grade12-afrika-20260808T113620Z/1stOpp/HYMARK_ASSESSMENT_VALIDATION.md"),
        0,
    ),
    Release(
        "english",
        release("deliverables/homs_fet_tight8_release_candidates/english/hymark-exam-english_language-grade12-englis-20260808T144141Z/1stOpp/assessment_pack.json"),
        release("deliverables/homs_fet_tight8_release_candidates/english/hymark-exam-english_language-grade12-englis-20260808T144141Z/ENGLIS_Assessment_1stOpp_20260808T144141Z.docx"),
        release("deliverables/homs_fet_tight8_release_candidates/english/hymark-exam-english_language-grade12-englis-20260808T144141Z/ENGLIS_Memo_1stOpp_20260808T144141Z.docx"),
        release("deliverables/homs_fet_tight8_release_candidates/english/hymark-exam-english_language-grade12-englis-20260808T144141Z/pdf_review/ENGLIS_Assessment_1stOpp_20260808T144141Z.pdf"),
        release("deliverables/homs_fet_tight8_release_candidates/english/hymark-exam-english_language-grade12-englis-20260808T144141Z/1stOpp/HYMARK_ASSESSMENT_VALIDATION.md"),
        0,
    ),
    Release(
        "history",
        release("deliverables/homs_fet_tight8_release_candidates/history/hymark-exam-history-grade12-hist12-20260808T145146Z/1stOpp/assessment_pack.json"),
        release("deliverables/homs_fet_tight8_release_candidates/history/hymark-exam-history-grade12-hist12-20260808T145146Z/1stOpp/HIST12_Assessment_1stOpp_CURATED.docx"),
        release("deliverables/homs_fet_tight8_release_candidates/history/hymark-exam-history-grade12-hist12-20260808T145146Z/1stOpp/HIST12_Memo_1stOpp_CURATED.docx"),
        release("deliverables/homs_fet_tight8_release_candidates/history/hymark-exam-history-grade12-hist12-20260808T145146Z/1stOpp/pdf_review/HIST12_Assessment_1stOpp_CURATED.pdf"),
        release("deliverables/homs_fet_tight8_release_candidates/history/hymark-exam-history-grade12-hist12-20260808T145146Z/1stOpp/HYMARK_ASSESSMENT_VALIDATION.md"),
        0,
    ),
    Release(
        "geography",
        release("deliverables/homs_fet_tight8_release_candidates/geography/geography-grade12-term3-reference/assessment_pack.json"),
        release("deliverables/homs_fet_tight8_release_candidates/geography/geography-grade12-term3-reference/GEOGRAPHY_G12_T3_ASSESSMENT.docx"),
        release("deliverables/homs_fet_tight8_release_candidates/geography/geography-grade12-term3-reference/GEOGRAPHY_G12_T3_MEMO.docx"),
        release("deliverables/homs_fet_tight8_release_candidates/geography/geography-grade12-term3-reference/pdf_review/GEOGRAPHY_G12_T3_ASSESSMENT.pdf"),
        release("deliverables/homs_fet_tight8_release_candidates/geography/geography-grade12-term3-reference/HYMARK_ASSESSMENT_VALIDATION.md"),
        2,
    ),
    Release(
        "life_sciences",
        release("deliverables/homs_fet_tight8_release_candidates/life_sciences/life-sciences-grade12-term3-reference/assessment_pack.json"),
        release("deliverables/homs_fet_tight8_release_candidates/life_sciences/life-sciences-grade12-term3-reference/LIFE_SCIENCES_G12_T3_ASSESSMENT.docx"),
        release("deliverables/homs_fet_tight8_release_candidates/life_sciences/life-sciences-grade12-term3-reference/LIFE_SCIENCES_G12_T3_MEMO.docx"),
        release("deliverables/homs_fet_tight8_release_candidates/life_sciences/life-sciences-grade12-term3-reference/pdf_review/LIFE_SCIENCES_G12_T3_ASSESSMENT.pdf"),
        release("deliverables/homs_fet_tight8_release_candidates/life_sciences/life-sciences-grade12-term3-reference/HYMARK_ASSESSMENT_VALIDATION.md"),
        3,
    ),
    Release(
        "physical_sciences",
        release("deliverables/homs_fet_tight8_release_candidates/physical_sciences/physical-sciences-grade12-term3-reference/assessment_pack.json"),
        release("deliverables/homs_fet_tight8_release_candidates/physical_sciences/physical-sciences-grade12-term3-reference/PHYSICAL_SCIENCES_G12_T3_ASSESSMENT.docx"),
        release("deliverables/homs_fet_tight8_release_candidates/physical_sciences/physical-sciences-grade12-term3-reference/PHYSICAL_SCIENCES_G12_T3_MEMO.docx"),
        release("deliverables/homs_fet_tight8_release_candidates/physical_sciences/physical-sciences-grade12-term3-reference/pdf_review/PHYSICAL_SCIENCES_G12_T3_ASSESSMENT.pdf"),
        release("deliverables/homs_fet_tight8_release_candidates/physical_sciences/physical-sciences-grade12-term3-reference/HYMARK_ASSESSMENT_VALIDATION.md"),
        3,
    ),
    Release(
        "mathematics",
        release("deliverables/homs_fet_tight8_release_candidates/mathematics/mathematics-grade12-term3-reference/assessment_pack.json"),
        release("deliverables/homs_fet_tight8_release_candidates/mathematics/mathematics-grade12-term3-reference/MATHEMATICS_G12_T3_ASSESSMENT.docx"),
        release("deliverables/homs_fet_tight8_release_candidates/mathematics/mathematics-grade12-term3-reference/MATHEMATICS_G12_T3_MEMO.docx"),
        release("deliverables/homs_fet_tight8_release_candidates/mathematics/mathematics-grade12-term3-reference/pdf_review/MATHEMATICS_G12_T3_ASSESSMENT.pdf"),
        release("deliverables/homs_fet_tight8_release_candidates/mathematics/mathematics-grade12-term3-reference/HYMARK_ASSESSMENT_VALIDATION.md"),
        3,
    ),
    Release(
        "life_orientation",
        release("deliverables/homs_fet_tight8_release_candidates/life_orientation/life-orientation-grade12-term3-reference/assessment_pack.json"),
        release("deliverables/homs_fet_tight8_release_candidates/life_orientation/life-orientation-grade12-term3-reference/LIFE_ORIENTATION_G12_T3_ASSESSMENT.docx"),
        release("deliverables/homs_fet_tight8_release_candidates/life_orientation/life-orientation-grade12-term3-reference/LIFE_ORIENTATION_G12_T3_MEMO.docx"),
        release("deliverables/homs_fet_tight8_release_candidates/life_orientation/life-orientation-grade12-term3-reference/pdf_review/LIFE_ORIENTATION_G12_T3_ASSESSMENT.pdf"),
        release("deliverables/homs_fet_tight8_release_candidates/life_orientation/life-orientation-grade12-term3-reference/HYMARK_ASSESSMENT_VALIDATION.md"),
        0,
    ),
]


BANNED = [
    "identify one important feature of the graph or diagram",
    "identify one important feature of the photo or image",
    "which one would produce the strongest assessment question",
    "as evidence in afrikaans",
    "table of contents",
    "visual placeholder",
    "insert image",
    "design law",
]


def docx_checks(path: Path, expected_media: int) -> tuple[int, list[str]]:
    errors: list[str] = []
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        media_count = len([name for name in names if name.startswith("word/media/") and not name.endswith("/")])
        if media_count < expected_media:
            errors.append(f"embedded media {media_count}, expected at least {expected_media}")
        document = archive.read("word/document.xml").decode("utf-8", errors="ignore").lower()
        if any(term in document for term in ["marking guideline", "memorandum / marking guide", "nasienriglyn"]):
            errors.append("learner paper contains marking-guide content")
        relationship_files = [name for name in names if name.startswith("word/_rels/") and name.endswith(".rels")]
        for name in relationship_files:
            rels = archive.read(name).decode("utf-8", errors="ignore")
            if "TargetMode=\"External\"" in rels and re.search(r"Type=\"[^\"]*/image\"", rels):
                errors.append("learner paper contains an externally linked image")
    return media_count, errors


def pdf_info(path: Path) -> tuple[int, bool]:
    result = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True, check=True)
    pages_match = re.search(r"^Pages:\s+(\d+)", result.stdout, re.MULTILINE)
    a4 = bool(re.search(r"^Page size:\s+595(?:\.\d+)? x 841(?:\.\d+)? pts \(A4\)", result.stdout, re.MULTILINE))
    return int(pages_match.group(1)) if pages_match else 0, a4


def main() -> int:
    BUNDLE_ROOT.mkdir(parents=True, exist_ok=True)
    rows = []
    all_errors: list[str] = []
    for item in RELEASES:
        missing = [str(path) for path in [item.pack, item.assessment, item.memo, item.pdf, item.validation] if not path.exists()]
        errors = [f"missing {path}" for path in missing]
        pack = json.loads(item.pack.read_text(encoding="utf-8")) if item.pack.exists() else {}
        question_marks = sum(int(question.get("marks") or 0) for section in pack.get("sections") or [] for question in section.get("questions") or [])
        rubric_marks = sum(int(entry.get("marks") or 0) for entry in pack.get("rubric") or [])
        total_marks = int(pack.get("total_marks") or 0)
        if question_marks != total_marks:
            errors.append(f"question marks {question_marks} != total {total_marks}")
        if rubric_marks not in {0, total_marks}:
            errors.append(f"rubric marks {rubric_marks} != 0 or total {total_marks}")
        visible = json.dumps({"title": pack.get("assessment_title"), "sections": pack.get("sections"), "evidence_cards": pack.get("evidence_cards")}, ensure_ascii=False).lower()
        errors.extend(f"banned placeholder phrase: {phrase}" for phrase in BANNED if phrase in visible)
        media_count, docx_errors = docx_checks(item.assessment, item.expected_media) if item.assessment.exists() else (0, [])
        errors.extend(docx_errors)
        pages, is_a4 = pdf_info(item.pdf) if item.pdf.exists() else (0, False)
        if not is_a4:
            errors.append("PDF is not reported as A4")
        validation_passed = item.validation.exists() and "Status: passed" in item.validation.read_text(encoding="utf-8")
        if not validation_passed:
            errors.append("validation receipt is not passed")

        subject_dir = BUNDLE_ROOT / item.slug
        subject_dir.mkdir(parents=True, exist_ok=True)
        for source, name in [
            (item.assessment, "ASSESSMENT.docx"),
            (item.memo, "MEMORANDUM.docx"),
            (item.pdf, "ASSESSMENT_REVIEW.pdf"),
            (item.pack, "assessment_pack.json"),
            (item.validation, "VALIDATION.md"),
        ]:
            if source.exists():
                shutil.copy2(source, subject_dir / name)
        source_dir = item.pack.parent / "source_material"
        if source_dir.exists():
            copied_sources = subject_dir / "source_material"
            copied_sources.mkdir(parents=True, exist_ok=True)
            for source in source_dir.iterdir():
                if source.is_file():
                    shutil.copy2(source, copied_sources / source.name)

        row = {
            "subject": pack.get("subject") or item.slug.replace("_", " ").title(),
            "slug": item.slug,
            "grade": pack.get("grade"),
            "term": 3,
            "marks": total_marks,
            "question_marks": question_marks,
            "rubric_marks": rubric_marks,
            "source_count": len(pack.get("source_assets") or []) + len(pack.get("evidence_cards") or []),
            "embedded_media": media_count,
            "pdf_pages": pages,
            "a4": is_a4,
            "status": "passed" if not errors else "failed",
            "errors": errors,
        }
        rows.append(row)
        all_errors.extend(f"{item.slug}: {error}" for error in errors)

    payload = {"schema": "knowedge.homs_fet_tight8_release_audit.v1", "status": "passed" if not all_errors else "failed", "subjects": rows, "errors": all_errors}
    (BUNDLE_ROOT / "FET_TIGHT8_RELEASE_AUDIT.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md = [
        "# HOMS FET Tight 8 Final Release",
        "",
        f"Overall status: **{payload['status'].upper()}**",
        "",
        "| Subject | Grade/Term | Marks | Sources | Embedded media | PDF pages | Status |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        md.append(f"| {row['subject']} | {row['grade']} / 3 | {row['marks']} | {row['source_count']} | {row['embedded_media']} | {row['pdf_pages']} | {row['status']} |")
    md.extend([
        "",
        "## Release Contract",
        "",
        "Each subject folder contains the learner assessment, separate memorandum, PDF review render, structured assessment pack and validation receipt. Image-bearing papers contain embedded media; text-source papers intentionally use boxed source text without decorative images.",
        "",
        "All material remains subject to qualified educator moderation and approval before classroom use.",
    ])
    (BUNDLE_ROOT / "README.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    zip_path = RELEASE_ROOT / "HOMS_FET_TIGHT8_FINAL_RELEASE.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(BUNDLE_ROOT.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(RELEASE_ROOT))
    print(json.dumps({"status": payload["status"], "bundle": str(BUNDLE_ROOT), "zip": str(zip_path), "subjects": rows}, indent=2))
    return 0 if not all_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
