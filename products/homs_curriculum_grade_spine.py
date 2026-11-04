"""Bounded HOMS Curriculum mapping for the current randomized exam spines."""
from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import subprocess
import unicodedata
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
DELIVERABLES = ROOT / "deliverables/homs_random_grade_exam_set_20261101"
ALIGNMENT_PATH = DELIVERABLES / "CAPS_QUESTION_ALIGNMENT_ALL_GRADES_20261101.json"
IDENTITY_PATH = DELIVERABLES / "RANDOM_SUBJECT_CAPS_DOCUMENT_IDENTITY_AUDIT_20261101.json"
ASSIGNMENT_PATH = DELIVERABLES / "RANDOM_SUBJECT_ASSIGNMENTS.json"
PDF_ROOT = ROOT / "corpora/caps/pdf"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _source(path_value: Any) -> Path:
    path = Path(str(path_value or "")).expanduser().resolve()
    if not path.is_file():
        raise ValueError("annual_plan_path must identify an existing customer CSV")
    return path


def build_homs_curriculum_grade_spine_package(packet: Mapping[str, Any], output_dir: str | Path) -> dict[str, Any]:
    """Map customer plan rows to the selected grade's randomized exam/CAPS spine.

    This checks candidate topic associations only. It does not assert full CAPS
    coverage, term fit, plan truth, school compliance, or approval.
    """
    grade = int(packet.get("grade") or 0)
    subject = str(packet.get("subject") or "").strip()
    if grade not in range(1, 13) or not subject:
        raise ValueError("grade and subject must identify a randomized Grade 1-12 exam spine")
    alignment = json.loads(ALIGNMENT_PATH.read_text(encoding="utf-8"))
    identity = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
    assignments = json.loads(ASSIGNMENT_PATH.read_text(encoding="utf-8"))
    if (alignment.get("all_exam_question_ids_mapped_exactly_once") is not True
            or alignment.get("all_current_caps_source_hashes_verified") is not True
            or alignment.get("all_cited_physical_pdf_pages_have_text") is not True
            or identity.get("grade_count") != 12
            or assignments.get("random_seed") != identity.get("random_seed")):
        raise ValueError("randomized HOMS exam/CAPS spine does not pass its source-bound audit")
    grade_row = next((row for row in alignment.get("grades", []) if row.get("grade") == grade), None)
    identity_row = next((row for row in identity.get("grades", []) if row.get("grade") == grade), None)
    assignment_row = next((row for row in assignments.get("assignments", []) if row.get("grade") == grade), None)
    if not grade_row or not identity_row or not assignment_row:
        raise ValueError("grade is missing from the randomized exam, assignment, or CAPS identity manifest")
    if (_norm(subject) != _norm(grade_row.get("subject"))
            or grade_row.get("random_subject_profile") != assignment_row.get("subject_profile")
            or identity_row.get("caps_source_sha256") != grade_row.get("caps_source_sha256")
            or identity_row.get("source_identity_check") != "PASS_SUBJECT_FILENAME_AND_HASH_MATCH"):
        raise ValueError("selected subject does not match the audited randomized grade spine")
    grade_dir = DELIVERABLES / "grades" / f"grade-{grade:02d}-{grade_row['random_subject_profile']}"
    exam_path, memo_path = grade_dir / "GRADE_EXAM.docx", grade_dir / "GRADE_MEMO.docx"
    if (not exam_path.is_file() or not memo_path.is_file()
            or _sha(exam_path.read_bytes()) != grade_row.get("exam_sha256")
            or _sha(memo_path.read_bytes()) != grade_row.get("memo_sha256")):
        raise ValueError("randomized exam and memo bytes do not match the CAPS alignment manifest")
    pdf_candidates = list(PDF_ROOT.rglob(identity_row["caps_document_filename"]))
    if len(pdf_candidates) != 1:
        raise ValueError("official CAPS PDF identity must resolve to exactly one local source file")
    caps_pdf = pdf_candidates[0]
    if _sha(caps_pdf.read_bytes()) != grade_row.get("caps_source_sha256"):
        raise ValueError("official CAPS PDF hash differs from the selected grade alignment")

    plan_path = _source(packet.get("annual_plan_path"))
    plan_bytes = plan_path.read_bytes()
    try:
        decoded = plan_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("annual plan must be a UTF-8 CSV") from exc
    reader = csv.DictReader(decoded.splitlines())
    headers = {str(key or "").strip().casefold(): key for key in (reader.fieldnames or [])}
    required = {"grade", "subject", "term", "topic", "question_id"}
    if not required.issubset(headers):
        raise ValueError("grade-spine plan CSV requires grade, subject, term, topic, and question_id columns")
    plan_rows = list(reader)
    if not plan_rows:
        raise ValueError("annual plan CSV contains no rows")
    question_map = {str(row["question_id"]): row for row in grade_row.get("question_mappings", [])}
    if len(question_map) != len(grade_row.get("question_mappings", [])):
        raise ValueError("grade CAPS map contains duplicate question IDs")

    output_rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, source_row in enumerate(plan_rows, 1):
        row_grade = str(source_row.get(headers["grade"]) or "").strip()
        row_subject = str(source_row.get(headers["subject"]) or "").strip()
        term = str(source_row.get(headers["term"]) or "").strip()
        topic = str(source_row.get(headers["topic"]) or "").strip()
        question_id = str(source_row.get(headers["question_id"]) or "").strip()
        mapping = question_map.get(question_id)
        status = "CAPS_SCOPE_CANDIDATE_MATCH_REVIEW_REQUIRED"
        note = "Candidate match to one question-level CAPS mapping; curriculum-owner review remains required."
        if row_grade != str(grade) or _norm(row_subject) != _norm(subject):
            status, note = "GRADE_OR_SUBJECT_MISMATCH_REVIEW_REQUIRED", "Plan row scope differs from the selected randomized grade/subject."
        elif mapping is None:
            status, note = "QUESTION_ID_UNMAPPED_REVIEW_REQUIRED", "Question ID is not present in the selected grade's audited exam spine."
        elif _norm(topic) != _norm(mapping.get("caps_topic")):
            status, note = "TOPIC_DIFFERS_FROM_CAPS_SCOPE_REVIEW_REQUIRED", "Plan topic does not exactly match the mapped CAPS topic label."
        elif question_id in seen_ids:
            status, note = "DUPLICATE_QUESTION_MAPPING_REVIEW_REQUIRED", "More than one plan row points to the same question mapping."
        seen_ids.add(question_id)
        pages = mapping.get("caps_pages", []) if mapping else []
        page_rows = []
        for page in pages:
            page_rows.append({
                "physical_pdf_page": page.get("physical_pdf_page"),
                "page_text_sha256": page.get("page_text_sha256"),
                "topic_terms_found": page.get("topic_terms_found", []),
            })
        # The source map has topic-level citations for every selected question;
        # many map labels do not prove a term, so term fit always remains open.
        output_rows.append({
            "plan_record": f"PLAN-{index:03d}",
            "source_file": plan_path.name,
            "source_sha256": _sha(plan_bytes),
            "source_csv_row_number": index + 1,
            "source_record_sha256": _sha(json.dumps(source_row, sort_keys=True, ensure_ascii=False).encode()),
            "grade": row_grade,
            "subject": row_subject,
            "term": term,
            "question_id": question_id,
            "customer_topic": topic,
            "caps_topic": mapping.get("caps_topic", "") if mapping else "",
            "caps_pages": json.dumps(page_rows, ensure_ascii=False, sort_keys=True),
            "review_state": status,
            "term_fit": "REVIEW_REQUIRED_NOT_INFERRED",
            "note": note,
        })

    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    matrix_path = out / "CURRICULUM_ALIGNMENT_MATRIX.csv"
    with matrix_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)
    plan_sha = _sha(plan_bytes)
    alignment_sha = _sha(ALIGNMENT_PATH.read_bytes())
    source_binding = {
        "schema": "dio.homs.curriculum.randomized_exam_spine_binding.v1",
        "grade": grade,
        "subject": grade_row["subject"],
        "randomization_seed": assignments["random_seed"],
        "subject_profile": grade_row["random_subject_profile"],
        "customer_plan": {"file_name": plan_path.name, "sha256": plan_sha, "scope_attested_by_owner": packet.get("owner_authorized") is True},
        "randomized_exam": {"path": exam_path.relative_to(ROOT).as_posix(), "sha256": grade_row["exam_sha256"]},
        "randomized_memo": {"path": memo_path.relative_to(ROOT).as_posix(), "sha256": grade_row["memo_sha256"]},
        "caps_alignment_map": {"path": ALIGNMENT_PATH.relative_to(ROOT).as_posix(), "sha256": alignment_sha},
        "caps_source": {"path": caps_pdf.relative_to(ROOT).as_posix(), "sha256": grade_row["caps_source_sha256"], "url": grade_row["caps_source_url"]},
        "caps_identity_audit_sha256": _sha(IDENTITY_PATH.read_bytes()),
        "question_mapping_count": len(question_map),
        "plan_row_count": len(output_rows),
        "candidate_omissions": "NOT_COMPUTED: question-level exam mapping is not a complete CAPS inventory",
        "term_fit": "NOT_INFERRED",
        "curriculum_owner_review_required": True,
        "professional_conclusion": False,
        "release_authorized": False,
    }
    binding_path = out / "CURRICULUM_SOURCE_BINDING.json"
    binding_path.write_text(json.dumps(source_binding, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    html_rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row[key]))}</td>" for key in ("plan_record", "question_id", "term", "customer_topic", "caps_topic", "review_state", "term_fit")) + "</tr>"
        for row in output_rows
    )
    review_path = out / "CURRICULUM_REVIEW.html"
    review_path.write_text(
        "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>HOMS Curriculum · randomized grade spine review</title>"
        "<style>body{font:16px/1.5 system-ui,sans-serif;color:#192d29;margin:0;background:#f4f5ef}main{max-width:1300px;margin:auto;padding:30px}h1{line-height:1.15}p{max-width:950px}.scroll{overflow:auto;background:white}table{border-collapse:collapse;min-width:1000px;width:100%}th,td{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #ccd5cf}th{background:#153e39;color:white}a{color:#075f74}:focus-visible{outline:3px solid #a66a27;outline-offset:3px}</style><main>"
        f"<p>HOMS Curriculum · Grade {grade} · {html.escape(grade_row['subject'])} · randomized seed {assignments['random_seed']}</p>"
        "<h1>Plan rows against the selected exam’s CAPS topic map</h1>"
        "<p>This report links customer rows to one question-level mapping and its official CAPS page reference. The map is partial: no full curriculum coverage, omission, term fit, compliance, adequacy, or approval conclusion is made. A curriculum owner must review every row.</p>"
        "<div class='scroll' tabindex='0' role='region' aria-label='Scrollable curriculum mapping table'><table><thead><tr><th>Plan row</th><th>Question ID</th><th>Term</th><th>Customer topic</th><th>CAPS map topic</th><th>Review state</th><th>Term fit</th></tr></thead><tbody>"
        + html_rows + "</tbody></table></div>"
        f"<p>Plan SHA-256: <code>{plan_sha}</code><br>CAPS source SHA-256: <code>{grade_row['caps_source_sha256']}</code></p>"
        f"<p><a href='{html.escape(grade_row['caps_source_url'], quote=True)}'>Official CAPS source</a> · <a href='{html.escape(exam_path.relative_to(ROOT).as_posix(), quote=True)}'>Bound exam</a> · <a href='{html.escape(memo_path.relative_to(ROOT).as_posix(), quote=True)}'>Bound memo</a></p>"
        "<p>Owner review required; no professional conclusion, curriculum approval, or external release is issued.</p></main></html>",
        encoding="utf-8",
    )
    output_entries = []
    for path in (matrix_path, binding_path, review_path):
        output_entries.append({"path": path.name, "sha256": _sha(path.read_bytes()), "bytes": path.stat().st_size})
    receipt = {
        "schema": "dio.homs.curriculum.randomized_exam_spine_execution.v1",
        "product_name": "HOMS Curriculum",
        "grade": grade,
        "subject": grade_row["subject"],
        "randomization_seed": assignments["random_seed"],
        "case_id": str(packet.get("case_id") or f"HOMS-CURRICULUM-GRADE-{grade:02d}"),
        "customer_plan_sha256": plan_sha,
        "caps_alignment_sha256": alignment_sha,
        "caps_source_sha256": grade_row["caps_source_sha256"],
        "exam_sha256": grade_row["exam_sha256"],
        "memo_sha256": grade_row["memo_sha256"],
        "mapped_candidate_count": sum(row["review_state"] == "CAPS_SCOPE_CANDIDATE_MATCH_REVIEW_REQUIRED" for row in output_rows),
        "review_required_count": sum(row["review_state"] != "CAPS_SCOPE_CANDIDATE_MATCH_REVIEW_REQUIRED" for row in output_rows),
        "term_fit_inferred": False,
        "candidate_omissions_computed": False,
        "human_review_required": True,
        "professional_conclusion": False,
        "external_release_authorized": False,
        "outputs": output_entries,
    }
    (out / "CUSTOMER_PACKAGE_RECEIPT.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt
