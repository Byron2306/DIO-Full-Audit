#!/usr/bin/env python3
"""Verify the current randomized HOMS grade 1–12 exam and memo artifact set."""
from __future__ import annotations

import hashlib
import copy
import json
import os
import re
import tempfile
import zipfile
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.build_homs_grade_exam_candidate import normalize_question_prompts

PACK = ROOT / "deliverables/homs_random_grade_exam_set_20261101"
RECEIPT = PACK / "GRADE_EXAM_SET_RECEIPT.json"
ASSIGNMENTS = PACK / "RANDOM_SUBJECT_ASSIGNMENTS.json"
MODERATION = ROOT / "deliverables/homs_random_grade_exam_set_20261101/moderation_scope_revision_20261104_v26/HOMS_MODERATION_BATCH_RECEIPT.json"
OUTPUT = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_RANDOM_GRADE_EXAM_SET_CONTENT_AUDIT_20261102.json"
INDEX = PACK / "index.html"
CROSSWALKS = PACK / "learning_crosswalks/HOMS_GRADE_LEARNING_CROSSWALK_BATCH_RECEIPT.json"
CAPS_ALIGNMENT = PACK / "CAPS_QUESTION_ALIGNMENT_ALL_GRADES_20261101.json"
PDF_MANIFEST = PACK / "PRINT_READY_PDF_MANIFEST.json"
CAPS_SOURCE_REVIEW = PACK / "caps_source_excerpt_reviews_20261104_v27"
SOURCE_BUNDLE = PACK / "HOMS_RANDOM_GRADE_EXAMS_AND_MEMOS_20261101.zip"
PRINT_BUNDLE = PACK / "HOMS_RANDOM_GRADE_EXAMS_AND_MEMOS_PRINT_READY_20261101.zip"
SUBJECT_PROFILES = {
    "Life Skills": "life_skills", "English Language": "english_language",
    "Mathematics": "mathematics", "Natural Sciences and Technology": "natural_sciences_and_technology",
    "Economic and Management Sciences": "economics_management_sciences", "Life Orientation": "life_orientation",
    "Physical Sciences": "physical_sciences", "Business Studies": "business_studies",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = ElementTree.fromstring(archive.read("word/document.xml"))
    return " ".join(node.text or "" for node in xml.iter() if node.tag.endswith("}t"))


def pdf_text(path: Path) -> str:
    import subprocess

    result = subprocess.run(["pdftotext", "-layout", str(path), "-"], check=True, capture_output=True, text=True, timeout=60)
    text = re.sub(r"([A-Za-z])-\s*\r?\n\s*([A-Za-z])", r"\1-\2", result.stdout)
    return " ".join(text.split())


def build_index(rows: list[dict], receipt: dict) -> str:
    esc = lambda value: str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    crosswalks = json.loads(CROSSWALKS.read_text(encoding="utf-8")) if CROSSWALKS.is_file() else {"grades": []}
    crosswalk_by_grade = {int(item["grade"]): item for item in crosswalks["grades"]}
    pdf_manifest = json.loads(PDF_MANIFEST.read_text(encoding="utf-8"))
    pdf_by_grade = {int(item["grade"]): item for item in pdf_manifest.get("grades", [])}
    cards = []
    for row in rows:
        exam = Path(row["exam"])
        memo = Path(row["memo"])
        slug = exam.parent.name
        grade_row = next(item for item in receipt["results"] if int(item["grade"]) == row["grade"])
        receipt_path = Path(grade_row["job_dir"]) / "HOMS_GRADE_EXAM_RECEIPT.json"
        receipt_ref = receipt_path.relative_to(PACK) if receipt_path.is_absolute() else receipt_path
        crosswalk = crosswalk_by_grade.get(row["grade"], {})
        pack_ref = PACK.relative_to(ROOT)
        map_ref = next((Path(item["path"]).relative_to(pack_ref) for item in crosswalk.get("crosswalk_files", []) if item["path"].endswith("ASSESSMENT_LINKED_TEACHING_MAP.md")), None)
        educator_ref = next((Path(item["path"]).relative_to(pack_ref) for item in crosswalk.get("crosswalk_files", []) if item["path"].endswith("EDUCATOR_ASSESSMENT_CROSSWALK.md")), None)
        planning_links = ""
        if map_ref and educator_ref:
            planning_links = f' · <a href="{esc(str(map_ref))}">Teaching map</a> · <a href="{esc(str(educator_ref))}">Educator crosswalk</a>'
        cards.append(
            f'<tr><th scope="row">Grade {row["grade"]:02d}</th><td>{esc(row["subject"])}</td>'
            f'<td>{row["total_marks"]} marks · {row["question_count"]} questions</td>'
            f'<td><a href="grades/{esc(slug)}/GRADE_EXAM.docx">Learner exam</a> · '
            f'<a href="grades/{esc(slug)}/GRADE_EXAM.pdf">Print exam PDF</a> · '
            f'<a href="grades/{esc(slug)}/GRADE_MEMO.docx">Marking memo</a> · '
            f'<a href="grades/{esc(slug)}/GRADE_MEMO.pdf">Print memo PDF</a> · '
            f'<a href="{esc(str(receipt_ref))}">CAPS and review receipt</a> · '
            f'<a href="CAPS_QUESTION_ALIGNMENT_ALL_GRADES_20261101.json">Question-level CAPS map</a>{planning_links}</td></tr>'
        )
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HOMS · randomized Grade 1–12 exam drafts</title>
<style>body{{margin:0;background:#f5f4ef;color:#172b29;font:16px/1.55 system-ui,sans-serif}}main{{max-width:1120px;margin:auto;padding:36px 22px}}h1{{font-size:clamp(2rem,5vw,3.5rem);line-height:1.08;max-width:850px}}.note{{background:#fff7e8;border-left:5px solid #a66a27;padding:14px 18px;max-width:900px}}a{{color:#075e70}}a:focus-visible{{outline:3px solid #a66a27;outline-offset:3px}}.table-wrap{{overflow:auto;background:#fff}}table{{width:100%;min-width:760px;border-collapse:collapse}}th,td{{padding:14px;text-align:left;vertical-align:top;border-bottom:1px solid #cad3ce}}thead th{{background:#163f3b;color:#fff}}small{{color:#455c55}}footer{{margin-top:22px;color:#455c55;font-size:.9rem}}</style></head>
<body><main><p><strong>HOMS · CAPS-linked draft assessment set</strong></p><h1>One exam and marking memo for every grade</h1>
<p class="note">Subjects were assigned reproducibly by the recorded random seed within each CAPS phase. These are original draft assessments with source-hashed CAPS references. Mechanical question/memo checks and HOMS Moderate checks passed. A qualified educator must verify curriculum coverage, questions, answers, fairness and mark allocation before classroom use. No classroom release is authorized.</p>
<p><a href="RANDOM_SUBJECT_REPRODUCIBILITY_AUDIT_20261102.json">Open the independent seed, subject-pool, no-replacement and CAPS-identity reconstruction audit.</a></p>
<p><a href="caps_source_excerpt_reviews_20261104_v14/index.html">Open current question-level official CAPS page-text excerpts for educator review (all 12 grades).</a></p>
<p><a href="../../acceptance_runs/68-product-sellability-20261027/HOMS_RANDOM_GRADE_EXAM_VISUAL_RENDER_AUDIT_20261104.json">Open the print-layout visual audit for all 24 PDFs and 37 rendered pages.</a></p>
<div class="table-wrap"><table><thead><tr><th>Grade</th><th>Randomized subject</th><th>Paper</th><th>Files</th></tr></thead><tbody>{''.join(cards)}</tbody></table></div>
<footer>Seed {receipt["random_seed"]} · 12 of 12 grade packs verified · 12 of 12 mechanical moderation passes · independent educator moderation remains pending.</footer></main></body></html>'''


def main() -> int:
    set_receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assignments = json.loads(ASSIGNMENTS.read_text(encoding="utf-8"))
    moderation = json.loads(MODERATION.read_text(encoding="utf-8"))
    caps_alignment = json.loads(CAPS_ALIGNMENT.read_text(encoding="utf-8"))
    if (caps_alignment.get("grade_count") != 12
            or caps_alignment.get("all_exam_question_ids_mapped_exactly_once") is not True
            or caps_alignment.get("all_cited_physical_pdf_pages_have_text") is not True
            or caps_alignment.get("all_current_caps_source_hashes_verified") is not True):
        raise ValueError("question-level CAPS alignment map is incomplete or its source checks are unverified")
    alignment_by_grade = {int(item["grade"]): item for item in caps_alignment["grades"]}
    moderation_by_grade = {int(row["grade"]): row for row in moderation["results"]}
    assignment_by_grade = {int(row["grade"]): row for row in assignments["assignments"]}
    pdf_manifest = json.loads(PDF_MANIFEST.read_text(encoding="utf-8"))
    if (pdf_manifest.get("grade_count") != 12 or pdf_manifest.get("pdf_count") != 24
            or pdf_manifest.get("source_set_receipt_sha256") != sha256(RECEIPT)):
        raise ValueError("print-ready PDF manifest is incomplete or not bound to the current grade-set receipt")
    pdf_by_grade = {int(item["grade"]): item for item in pdf_manifest.get("grades", [])}
    rows = []
    for entry in set_receipt["results"]:
        grade = int(entry["grade"])
        folder = Path(entry["job_dir"])
        if not folder.is_absolute():
            folder = ROOT / folder
        assessment_path = folder / "HOMS_GRADE_ASSESSMENT.json"
        receipt_path = folder / "HOMS_GRADE_EXAM_RECEIPT.json"
        assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        assignment = assignment_by_grade.get(grade, {})
        moderation_row = moderation_by_grade.get(grade, {})
        exam_path = ROOT / receipt["assessment"]["exam"]["path"]
        memo_path = ROOT / receipt["assessment"]["memo"]["path"]
        source_path = Path(receipt["caps_source"]["path"])
        exam_body, memo_body = docx_text(exam_path), docx_text(memo_path)
        pdf_row = pdf_by_grade.get(grade, {})
        exam_pdf = PACK / pdf_row.get("exam_pdf", "")
        memo_pdf = PACK / pdf_row.get("memo_pdf", "")
        exam_pdf_body = pdf_text(exam_pdf) if exam_pdf.is_file() else ""
        memo_pdf_body = pdf_text(memo_pdf) if memo_pdf.is_file() else ""
        questions = [(section, q) for section in assessment["sections"] for q in section["questions"]]
        display_assessment = copy.deepcopy(assessment)
        normalize_question_prompts(display_assessment)
        display_questions = [(section, q) for section in display_assessment["sections"] for q in section["questions"]]
        alignment = alignment_by_grade.get(grade, {})
        mapped = alignment.get("question_mappings", [])
        mapping_by_id = {item.get("question_id"): item for item in mapped}
        page_hashes_match = True
        page_hash_cache = {}
        for mapping in mapped:
            for citation in mapping.get("caps_pages") or []:
                page = int(citation["physical_pdf_page"])
                key = (str(source_path), page)
                if key not in page_hash_cache:
                    extracted = subprocess.run(["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(source_path), "-"], check=True, capture_output=True, text=True).stdout.strip()
                    page_hash_cache[key] = hashlib.sha256(extracted.encode("utf-8")).hexdigest()
                page_hashes_match = page_hashes_match and citation.get("page_text_sha256") == page_hash_cache[key]
        alignment_matches_assessment = (
            alignment.get("caps_source_sha256") == receipt["caps_source"]["sha256"]
            and alignment.get("assessment_json_sha256") == sha256(assessment_path)
            and len(mapped) == len(questions) == 5
            and len(mapping_by_id) == len(mapped)
            and all(mapping_by_id.get(q.get("number"), {}).get("prompt") == q.get("prompt") for _, q in questions)
            and all(mapping_by_id.get(q.get("number"), {}).get("caps_pages") for _, q in questions)
            and page_hashes_match
        )
        prompts_present = all(q["prompt"] in exam_body for _, q in display_questions)
        memo_points = [point["point"] for _, q in questions for point in q["memo"]]
        memo_points_present = all(point in memo_body for point in memo_points)
        exam_pdf_prompts_present = all(q["prompt"] in exam_pdf_body for _, q in display_questions)
        memo_pdf_points_present = all(point in memo_pdf_body for point in memo_points)
        data_table = assessment["sections"][0].get("data_table")
        table_tokens = []
        if isinstance(data_table, dict):
            table_tokens = [str(data_table.get("caption") or "")] + [str(value) for value in data_table.get("columns") or []]
            table_tokens.extend(str(value) for row in data_table.get("rows") or [] for value in row)
        embedded_table_present = (
            not data_table
            or (bool(table_tokens) and all(token and token in exam_body and token in exam_pdf_body for token in table_tokens))
        )
        question_marks = sum(int(q["marks"]) for _, q in questions)
        memo_marks = sum(int(point["marks"]) for _, q in questions for point in q["memo"])
        source_exists = source_path.is_file()
        source_hash_matches = source_exists and sha256(source_path) == receipt["caps_source"]["sha256"]
        referenced_hashes_match = (
            sha256(exam_path) == receipt["assessment"]["exam"]["sha256"]
            and sha256(memo_path) == receipt["assessment"]["memo"]["sha256"]
            and sha256(assessment_path) == receipt["assessment"]["json"]["sha256"]
        )
        if moderation_row.get("mechanical_state") is not None:
            moderation_dir = MODERATION.parent / f"grade-{grade:02d}"
            moderation_execution = moderation_dir / "CUSTOMER_EXECUTION_RECEIPT.json"
            moderation_findings = moderation_dir / "HOMS_MECHANICAL_PREMODERATION_REPORT.json"
            moderation_output_hashes = {item.get("path"): item.get("sha256") for item in moderation_row.get("outputs", [])}
            moderation_pass_and_bound = (
                moderation_row.get("mechanical_state") == "PASS"
                and moderation_row.get("grade") == grade
                and moderation_row.get("random_seed") == set_receipt["random_seed"]
                and moderation_row.get("source_exam_sha256") == sha256(exam_path)
                and moderation_row.get("source_memo_sha256") == sha256(memo_path)
                and moderation_execution.is_file()
                and sha256(moderation_execution) == moderation_row.get("execution_receipt_sha256")
                and moderation_findings.is_file()
                and sha256(moderation_findings) == moderation_output_hashes.get("HOMS_MECHANICAL_PREMODERATION_REPORT.json")
            )
        else:
            moderation_dir = ROOT / moderation_row.get("output", "")
            moderation_execution = moderation_dir / "CUSTOMER_EXECUTION_RECEIPT.json"
            moderation_findings = moderation_dir / "HOMS_MECHANICAL_PREMODERATION_REPORT.json"
            moderation_pass_and_bound = (
                moderation_row.get("state") == "PASS"
                and moderation_execution.is_file()
                and sha256(moderation_execution) == moderation_row.get("customer_execution_receipt_sha256")
                and moderation_findings.is_file()
                and sha256(moderation_findings) == moderation_row.get("moderation_findings_sha256")
            )
        checks = {
            "grade_and_subject_match_set_receipt": receipt["grade"] == grade and receipt["subject"] == entry["subject"],
            "randomization_seed_matches_set": receipt["randomization_seed"] == set_receipt["random_seed"],
            "randomized_subject_assignment_matches_manifest": assignment.get("subject_profile") == SUBJECT_PROFILES.get(entry["subject"]) and assignments["random_seed"] == set_receipt["random_seed"],
            "homs_moderate_mechanical_pass_and_receipt_hashes_match": moderation_pass_and_bound,
            "caps_source_exists_and_hash_matches": source_hash_matches,
            "exam_memo_and_json_hashes_match_receipt": referenced_hashes_match,
            "exam_docx_contains_every_question_prompt": prompts_present,
            "memo_docx_contains_every_marking_point": memo_points_present,
            "five_questions": len(questions) == 5,
            "question_and_memo_marks_reconcile": question_marks == memo_marks == assessment["total_marks"],
            "receipt_validation_flags_true": all(value is True for value in receipt.get("validation", {}).values() if isinstance(value, bool)),
            "question_level_caps_map_matches_assessment_and_source": alignment_matches_assessment,
            "caps_source_page_text_hashes_match": page_hashes_match,
            "print_pdf_manifest_binds_current_docx_and_pdf_hashes": (
                pdf_row.get("exam_docx_sha256") == sha256(exam_path)
                and pdf_row.get("memo_docx_sha256") == sha256(memo_path)
                and exam_pdf.is_file() and memo_pdf.is_file()
                and pdf_row.get("exam_pdf_sha256") == sha256(exam_pdf)
                and pdf_row.get("memo_pdf_sha256") == sha256(memo_pdf)
                and pdf_row.get("exam_pdf_text_sha256") == hashlib.sha256(exam_pdf_body.encode("utf-8")).hexdigest()
                and pdf_row.get("memo_pdf_text_sha256") == hashlib.sha256(memo_pdf_body.encode("utf-8")).hexdigest()
                and pdf_row.get("exam_pdf_pages", 0) > 0 and pdf_row.get("memo_pdf_pages", 0) > 0
            ),
            "exam_pdf_contains_every_question_prompt": exam_pdf_prompts_present,
            "memo_pdf_contains_every_marking_point": memo_pdf_points_present,
            "embedded_data_table_present_in_exam_docx_and_pdf": embedded_table_present,
        }
        rows.append({
            "grade": grade, "subject": entry["subject"], "caps_source_sha256": receipt["caps_source"]["sha256"],
            "total_marks": assessment["total_marks"], "question_count": len(questions),
            "exam": str(exam_path.relative_to(ROOT)), "memo": str(memo_path.relative_to(ROOT)),
            "exam_pdf": str(exam_pdf.relative_to(ROOT)) if exam_pdf.is_file() else "",
            "memo_pdf": str(memo_pdf.relative_to(ROOT)) if memo_pdf.is_file() else "",
            "checks": checks, "all_checks_pass": all(checks.values()),
        })

    grades = [row["grade"] for row in rows]
    complete = grades == list(range(1, 13)) and len(rows) == 12 and all(row["all_checks_pass"] for row in rows)
    crosswalks_complete = CROSSWALKS.is_file() and len(json.loads(CROSSWALKS.read_text(encoding="utf-8")).get("grades", [])) == 12
    if complete and crosswalks_complete:
        INDEX.write_text(build_index(rows, set_receipt), encoding="utf-8")
        if not SOURCE_BUNDLE.is_file():
            raise FileNotFoundError(f"Source HOMS grade-set bundle is missing: {SOURCE_BUNDLE}")
        source_additions: dict[str, Path] = {
            "README.md": PACK / "README.md",
            "index.html": INDEX,
            "RANDOM_SUBJECT_ASSIGNMENTS.json": ASSIGNMENTS,
            "RANDOM_SUBJECT_REPRODUCIBILITY_AUDIT_20261102.json": PACK / "RANDOM_SUBJECT_REPRODUCIBILITY_AUDIT_20261102.json",
            "GRADE_EXAM_SET_RECEIPT.json": RECEIPT,
            "CAPS_QUESTION_ALIGNMENT_ALL_GRADES_20261101.json": CAPS_ALIGNMENT,
            "CAPS_SOURCE_MANIFEST_VERIFIED.json": PACK / "CAPS_SOURCE_MANIFEST_VERIFIED.json",
            "CAPS_MATRIX_ANALYSIS_VERIFIED.json": PACK / "CAPS_MATRIX_ANALYSIS_VERIFIED.json",
            "GRADE07_SOURCE_TITLE_CORRECTION_20261102.json": PACK / "GRADE07_SOURCE_TITLE_CORRECTION_20261102.json",
            "PRINT_READY_PDF_MANIFEST.json": PDF_MANIFEST,
        }
        for filename in (
            "GRADE02_CONTENT_CORRECTION_20261102.json",
            "GRADE03_CONTENT_CORRECTION_20261102.json",
            "GRADE04_CONTENT_CORRECTION_20261102.json",
            "GRADE04_FRACTION_MEMO_CORRECTION_20261102.json",
            "GRADE04_CAPACITY_CONVERSION_CORRECTION_20261104.json",
            "GRADE03_GEOMETRY_SCOPE_CORRECTION_20261104.json",
            "GRADE06_PROMPT_RUBRIC_ALIGNMENT_CORRECTION_20261104.json",
            "GRADE05_CONTENT_CORRECTION_20261102.json",
            "GRADE07_CONTENT_CORRECTION_20261102.json",
            "GRADE05_CAPS_SCOPE_REFRESH_EVIDENCE_20261101.json",
            "GRADE07_CAPS_SCOPE_REFRESH_EVIDENCE_20261101.json",
            "GRADE10_CONTENT_CORRECTION_20261102.json",
            "GRADE10_DISTANCE_SPEED_REASONING_CORRECTION_20261102.json",
            "GRADE12_CAPS_SCOPE_REFRESH_EVIDENCE_20261101.json",
            "HOMS_RANDOM_GRADE_EXAM_MEMO_ARTIFACT_AUDIT_20261101.json",
            "HOMS_PRODUCT_BATCH_EVIDENCE.json",
        ):
            artifact = PACK / filename
            if artifact.is_file():
                source_additions[filename] = artifact
        if (CAPS_SOURCE_REVIEW / "CAPS_SOURCE_EXCERPT_REVIEW_MANIFEST.json").is_file():
            for artifact in CAPS_SOURCE_REVIEW.rglob("*"):
                if artifact.is_file():
                    source_additions[artifact.relative_to(PACK).as_posix()] = artifact
        for grade_row in set_receipt["results"]:
            grade_dir = Path(grade_row["job_dir"]).resolve()
            for filename in ("GRADE_EXAM.docx", "GRADE_MEMO.docx", "HOMS_GRADE_ASSESSMENT.json", "HOMS_GRADE_EXAM_RECEIPT.json"):
                artifact = grade_dir / filename
                source_additions[artifact.relative_to(PACK).as_posix()] = artifact
        for artifact in (PACK / "learning_crosswalks").rglob("*"):
            if artifact.is_file():
                source_additions[artifact.relative_to(PACK).as_posix()] = artifact
        accuracy_revision = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_GRADE12_BUSINESS_STUDIES_ACCURACY_REVISION_20261104.json"
        if accuracy_revision.is_file():
            source_additions["customer_review/HOMS_GRADE12_BUSINESS_STUDIES_ACCURACY_REVISION_20261104.json"] = accuracy_revision
        current_moderation_dir = MODERATION.parent
        for artifact in current_moderation_dir.rglob("*"):
            if artifact.is_file():
                archive_name = Path("customer_moderation") / current_moderation_dir.name / artifact.relative_to(current_moderation_dir)
                source_additions[archive_name.as_posix()] = artifact
        with tempfile.NamedTemporaryFile(prefix="homs-source-bundle-", suffix=".zip", dir=PACK, delete=False) as handle:
            source_bundle_tmp = Path(handle.name)
        try:
            with zipfile.ZipFile(source_bundle_tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as current_source:
                for archive_name, path in source_additions.items():
                    if path.is_file():
                        current_source.write(path, archive_name)
            os.replace(source_bundle_tmp, SOURCE_BUNDLE)
            os.chmod(SOURCE_BUNDLE, 0o644)
        finally:
            source_bundle_tmp.unlink(missing_ok=True)

        additions: dict[str, Path] = {
            "README.md": PACK / "README.md",
            "index.html": INDEX,
            "PRINT_READY_PDF_MANIFEST.json": PDF_MANIFEST,
        }
        for item in pdf_manifest["grades"]:
            additions[item["exam_pdf"]] = PACK / item["exam_pdf"]
            additions[item["memo_pdf"]] = PACK / item["memo_pdf"]
        with tempfile.NamedTemporaryFile(prefix="homs-print-bundle-", suffix=".zip", dir=PACK, delete=False) as handle:
            temp_bundle = Path(handle.name)
        try:
            with zipfile.ZipFile(temp_bundle, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as target_zip:
                for archive_name, path in additions.items():
                    target_zip.write(path, archive_name)
            os.replace(temp_bundle, PRINT_BUNDLE)
            os.chmod(PRINT_BUNDLE, 0o644)
        finally:
            temp_bundle.unlink(missing_ok=True)
    audit = {
        "schema": "dio.homs.random_grade_exam_content_audit.v1",
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_receipt": str(RECEIPT.relative_to(ROOT)),
        "randomized_subject_assignments": {
            "manifest": str(ASSIGNMENTS.relative_to(ROOT)), "manifest_sha256": sha256(ASSIGNMENTS),
            "selection_method": assignments.get("selection_method"),
            "seed": assignments.get("random_seed"),
        },
        "moderation": {
            "batch_receipt": str(MODERATION.relative_to(ROOT)),
            "batch_receipt_sha256": sha256(MODERATION),
            "mechanical_pass_count": moderation.get("mechanical_pass_count"),
            "independent_moderation_decision": moderation.get("independent_moderation_decision"),
        },
        "print_ready_pdfs": {
            "manifest": str(PDF_MANIFEST.relative_to(ROOT)),
            "manifest_sha256": sha256(PDF_MANIFEST),
            "pdf_count": pdf_manifest.get("pdf_count"),
            "bundle": str(PRINT_BUNDLE.relative_to(ROOT)) if PRINT_BUNDLE.is_file() else None,
            "bundle_sha256": sha256(PRINT_BUNDLE) if PRINT_BUNDLE.is_file() else None,
            "all_grade_pdfs_verified": all(
                row["checks"].get("print_pdf_manifest_binds_current_docx_and_pdf_hashes")
                and row["checks"].get("exam_pdf_contains_every_question_prompt")
                and row["checks"].get("memo_pdf_contains_every_marking_point")
                for row in rows
            ),
        },
        "grade_count": len(rows), "grades_1_through_12_present": grades == list(range(1, 13)),
        "all_grade_packs_verified": complete,
        "all_subject_assignments_unique": len({(r["grade"], r["subject"]) for r in rows}) == len(rows),
        "human_educator_review_required": True,
        "caps_alignment_claim_boundary": "This audit verifies current source-file hashes, grade/subject binding, DOCX content presence, and mark arithmetic. It does not establish full CAPS curriculum coverage or educator approval.",
        "grades": rows,
    }
    OUTPUT.write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"all_grade_packs_verified": complete, "grade_count": len(rows), "failed_grades": [r["grade"] for r in rows if not r["all_checks_pass"]], "audit": str(OUTPUT.relative_to(ROOT))}, indent=2))
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
