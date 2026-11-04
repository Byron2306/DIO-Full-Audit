#!/usr/bin/env python3
"""Build hash-bound CAPS page excerpts for educator review of the HOMS exam set."""
from __future__ import annotations

import csv
import hashlib
import html
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "deliverables/homs_random_grade_exam_set_20261101"
ALIGNMENT = PACK / "CAPS_QUESTION_ALIGNMENT_ALL_GRADES_20261101.json"
CORPUS = ROOT / "corpora/caps/caps_corpus_manifest.json"
OUT = PACK / "caps_source_excerpt_reviews_20261104_v28"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def page_text(pdf: Path, page: int) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(pdf), "-"],
        check=True, capture_output=True, text=True,
    )
    value = result.stdout.strip()
    if not value:
        raise ValueError(f"CAPS PDF page {page} has no extractable text: {pdf.name}")
    return value


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f"output directory must be new or empty: {OUT}")
    alignment = json.loads(ALIGNMENT.read_text(encoding="utf-8"))
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    documents = corpus.get("documents") or []
    OUT.mkdir(parents=True, exist_ok=True)
    grade_receipts = []
    grade_html_links = []

    if alignment.get("grade_count") != 12 or alignment.get("question_mapping_count") != 60:
        raise ValueError("Expected exactly 12 grades and 60 question mappings")

    for grade_row in alignment["grades"]:
        grade = int(grade_row["grade"])
        source_hash = grade_row["caps_source_sha256"]
        document = next((row for row in documents if row.get("sha256") == source_hash), None)
        if document is None:
            raise ValueError(f"Grade {grade}: official CAPS source hash is absent from corpus manifest")
        matches = list((ROOT / "corpora/caps/pdf").rglob(Path(document["path"]).name))
        matches = [path for path in matches if sha(path.read_bytes()) == source_hash]
        if len(matches) != 1:
            raise ValueError(f"Grade {grade}: expected one local CAPS PDF matching {source_hash}, found {len(matches)}")
        pdf = matches[0]

        source_grade_dir = PACK / "grades" / f"grade-{grade:02d}-{grade_row['random_subject_profile']}"
        assessment_path = source_grade_dir / "HOMS_GRADE_ASSESSMENT.json"
        assessment_bytes = assessment_path.read_bytes()
        if sha(assessment_bytes) != grade_row["assessment_json_sha256"]:
            raise ValueError(f"Grade {grade}: assessment source hash differs from CAPS mapping")
        assessment = json.loads(assessment_bytes)
        prompt_by_id = {}
        for section in assessment.get("sections") or []:
            for question in section.get("questions") or []:
                prompt_by_id[str(question.get("question_id") or question.get("number") or "")] = str(question.get("prompt") or "")

        rows = []
        seen_question_ids: set[str] = set()
        for mapping in grade_row["question_mappings"]:
            qid = str(mapping["question_id"])
            if qid in seen_question_ids or qid not in prompt_by_id:
                raise ValueError(f"Grade {grade}: duplicate or unknown mapped question {qid}")
            seen_question_ids.add(qid)
            if prompt_by_id[qid] != mapping["prompt"]:
                raise ValueError(f"Grade {grade} question {qid}: prompt changed since CAPS alignment")
            for citation in mapping.get("caps_pages") or []:
                page = int(citation["physical_pdf_page"])
                text = page_text(pdf, page)
                text_hash = sha(text.encode("utf-8"))
                if text_hash != citation.get("page_text_sha256"):
                    raise ValueError(f"Grade {grade} question {qid} CAPS page {page}: source page-text hash mismatch")
                rows.append({
                    "grade": grade,
                    "subject": grade_row["subject"],
                    "question_id": qid,
                    "question_prompt": mapping["prompt"],
                    "caps_topic": mapping["caps_topic"],
                    "coverage_link": mapping["coverage_link"],
                    "caps_physical_pdf_page": page,
                    "caps_source_pdf": pdf.relative_to(ROOT).as_posix(),
                    "caps_source_pdf_sha256": source_hash,
                    "alignment_page_text_sha256": citation["page_text_sha256"],
                    "excerpt_text_sha256": text_hash,
                    "excerpt_text_extraction": "pdftotext -layout; trim outer whitespace; UTF-8 SHA-256",
                    "exact_page_text": text,
                    "mapping_topic_terms_found": json.dumps(citation.get("topic_terms_found") or [], ensure_ascii=False),
                    "educator_review_state": "PENDING_EDUCATOR_CONFIRMATION",
                })
        if len(seen_question_ids) != 5:
            raise ValueError(f"Grade {grade}: expected 5 unique exam questions")

        csv_path = OUT / f"GRADE_{grade:02d}_CAPS_SOURCE_EXCERPTS.csv"
        fields = list(rows[0])
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

        html_path = OUT / f"GRADE_{grade:02d}_CAPS_SOURCE_REVIEW.html"
        cards = []
        for row in rows:
            cards.append(
                "<article><h2>Question " + html.escape(row["question_id"]) + " · "
                + html.escape(row["caps_topic"]) + "</h2><p><b>Exam prompt:</b> "
                + html.escape(row["question_prompt"]) + "</p><p><b>Alignment note:</b> "
                + html.escape(row["coverage_link"]) + "</p><p><b>Official CAPS PDF page:</b> "
                + str(row["caps_physical_pdf_page"]) + " · PDF SHA-256 <code>"
                + html.escape(source_hash) + "</code> · page-text SHA-256 <code>"
                + html.escape(row["excerpt_text_sha256"]) + "</code></p><p>Alignment-map page-text hash: <code>"
                + html.escape(row["alignment_page_text_sha256"]) + "</code></p><details><summary>Show exact extracted CAPS page text</summary><pre>"
                + html.escape(row["exact_page_text"]) + "</pre></details><p class=""state"">Educator confirmation pending. This source excerpt supports review; it does not establish complete alignment, term fit or item validity.</p></article>"
            )
        html_path.write_text(
            "<!doctype html><html lang='en-ZA'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
            "<title>Grade " + str(grade) + " CAPS source review</title><style>body{font:16px/1.55 system-ui;max-width:960px;margin:2rem auto;padding:0 1rem;color:#18212b}"
            "article{border:1px solid #ccd3da;border-radius:10px;margin:1rem 0;padding:1rem}pre{white-space:pre-wrap;background:#f4f6f8;padding:1rem;max-height:36rem;overflow:auto}"
            ".state{color:#704d00;background:#fff5d8;padding:.65rem;border-radius:6px}code{overflow-wrap:anywhere}</style><body><h1>Grade "
            + str(grade) + " · " + html.escape(grade_row["subject"]) + "</h1><p>Official curriculum source excerpts paired with all five randomized exam items. Verify the original source and confirm grade and term fit before use.</p>"
            + "".join(cards) + "</body></html>\n", encoding="utf-8")

        grade_receipts.append({
            "grade": grade,
            "subject": grade_row["subject"],
            "caps_source_pdf": pdf.relative_to(ROOT).as_posix(),
            "caps_source_pdf_sha256": source_hash,
            "question_count": len(seen_question_ids),
            "question_page_excerpt_count": len(rows),
            "csv": csv_path.name,
            "csv_sha256": sha(csv_path.read_bytes()),
            "html": html_path.name,
            "html_sha256": sha(html_path.read_bytes()),
            "educator_review_state": "PENDING_EDUCATOR_CONFIRMATION",
        })
        grade_html_links.append(
            f"<li><a href='{html.escape(html_path.name)}'>Grade {grade} · {html.escape(grade_row['subject'])}</a>"
            f" · <a href='{html.escape(csv_path.name)}'>CSV excerpts</a></li>"
        )

    index = OUT / "index.html"
    index.write_text(
        "<!doctype html><html lang='en-ZA'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
        "<title>HOMS randomized exam CAPS source reviews</title><style>body{font:17px/1.55 system-ui;max-width:800px;margin:3rem auto;padding:0 1rem;color:#18212b}"
        "li{margin:.5rem 0}.note{background:#fff5d8;padding:1rem;border-radius:8px}</style><body><h1>CAPS source excerpts · Grades 1–12</h1>"
        "<p>Question-level official CAPS page text is provided beside each mapped exam item so educators can review the source without searching within the PDF.</p>"
        "<p class='note'>These excerpts and topic links are review aids, not educator approval, full CAPS coverage, term-fit confirmation or a classroom-release decision.</p><ul>"
        + "\n".join(grade_html_links) + "</ul></body></html>\n", encoding="utf-8")
    manifest = {
        "schema": "dio.homs.caps_question_source_excerpt_review.v1",
        "page_text_hash_validation": "PASS_ALL_CITATIONS_MATCH_BYTE_VERIFIED_SOURCE_PDF_EXTRACTION",
        "source_alignment": ALIGNMENT.relative_to(ROOT).as_posix(),
        "source_alignment_sha256": sha(ALIGNMENT.read_bytes()),
        "caps_corpus_manifest": CORPUS.relative_to(ROOT).as_posix(),
        "grade_count": len(grade_receipts),
        "question_count": sum(row["question_count"] for row in grade_receipts),
        "question_page_excerpt_count": sum(row["question_page_excerpt_count"] for row in grade_receipts),
        "grades": grade_receipts,
        "index": index.name,
        "index_sha256": sha(index.read_bytes()),
        "independent_educator_review": "PENDING",
        "classroom_release_authorized": False,
        "full_caps_coverage_claim": "NONE",
    }
    dump_json(OUT / "CAPS_SOURCE_EXCERPT_REVIEW_MANIFEST.json", manifest)
    print(json.dumps({"output": OUT.relative_to(ROOT).as_posix(), "grades": manifest["grade_count"],
                      "questions": manifest["question_count"], "source_page_excerpts": manifest["question_page_excerpt_count"],
                      "educator_review": manifest["independent_educator_review"], "release": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
