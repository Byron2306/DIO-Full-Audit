#!/usr/bin/env python3
"""Validate a HOMS Moderate educator review against its exact packaged sources."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path, help="one grade package directory")
    parser.add_argument("--review", required=True, type=Path, help="downloaded educator review JSON")
    parser.add_argument("--output", type=Path, help="validation receipt; defaults beside the review")
    args = parser.parse_args()
    run_dir, review_path = args.run_dir.expanduser().resolve(), args.review.expanduser().resolve()
    package_path = run_dir / "CUSTOMER_PACKAGE_RECEIPT.json"
    if not package_path.is_file() or not review_path.is_file():
        parser.error("grade package receipt and educator review must both exist")
    package = json.loads(package_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    problems: list[str] = []
    if package.get("schema") != "dio.homs.moderate.customer_execution.v1":
        problems.append("unrecognized source package")
    if (package.get("independent_moderation_decision") != "NOT_ISSUED"
            or package.get("classroom_release_authorized") is not False):
        problems.append("source package has an invalid release boundary")
    for output in package.get("outputs") or []:
        output_path = run_dir / str(output.get("path") or "")
        if (not output_path.is_file() or output_path.stat().st_size != output.get("bytes")
                or sha(output_path) != output.get("sha256")):
            problems.append(f"package output failed integrity check: {output.get('path')}")
    if review.get("schema") != "dio.homs.moderate.educator_review_record.v1":
        problems.append("unrecognized review record")
    expected_sources = {
        "exam_docx_sha256": package.get("source_exam_sha256"),
        "memo_docx_sha256": package.get("source_memo_sha256"),
        "assessment_json_sha256": package.get("source_assessment_sha256"),
        "caps_source_sha256": package.get("source_caps_sha256"),
        "caps_alignment_sha256": package.get("source_caps_alignment_sha256"),
        "caps_identity_audit_sha256": None,
        "mechanical_report_sha256": None,
    }
    artifacts = {row.get("path"): row.get("sha256") for row in package.get("outputs", [])}
    expected_sources["caps_identity_audit_sha256"] = artifacts.get("sources/CAPS_DOCUMENT_IDENTITY_AUDIT.json")
    expected_sources["mechanical_report_sha256"] = artifacts.get("HOMS_MECHANICAL_PREMODERATION_REPORT.json")
    file_bindings = {
        "exam_docx_sha256": "sources/GRADE_EXAM.docx",
        "memo_docx_sha256": "sources/GRADE_MEMO.docx",
        "assessment_json_sha256": "sources/HOMS_GRADE_ASSESSMENT.json",
        "caps_source_sha256": "sources/CAPS_SOURCE.pdf",
        "caps_alignment_sha256": "sources/CAPS_QUESTION_ALIGNMENT.json",
        "caps_identity_audit_sha256": "sources/CAPS_DOCUMENT_IDENTITY_AUDIT.json",
        "mechanical_report_sha256": "HOMS_MECHANICAL_PREMODERATION_REPORT.json",
    }
    for key, rel in file_bindings.items():
        path = run_dir / rel
        if not path.is_file() or not expected_sources[key] or sha(path) != expected_sources[key]:
            problems.append(f"packaged source failed integrity check: {rel}")
    if review.get("source_hashes") != expected_sources:
        problems.append("review source hashes differ from this package")
    page_path = run_dir / "EDUCATOR_MODERATION_REVIEW.html"
    context: dict = {}
    try:
        page = page_path.read_text(encoding="utf-8")
        match = re.search(r"<script type='application/json' id='context'>(.*?)</script>", page, re.S)
        if not match:
            raise ValueError("embedded context block not found")
        context = json.loads(match.group(1))
        supplied_context_hash = context.pop("context_sha256", None)
        canonical = json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        calculated_context_hash = hashlib.sha256(canonical).hexdigest()
        if supplied_context_hash != calculated_context_hash:
            problems.append("embedded review context fingerprint does not match its contents")
        if review.get("context_sha256") != calculated_context_hash:
            problems.append("review context fingerprint differs from the embedded package context")
        if (review.get("grade") != package.get("grade")
                or review.get("subject") != package.get("subject")
                or review.get("random_seed") != package.get("random_seed")):
            problems.append("review grade, subject, or random seed differs from its source package")
        if (context.get("grade") != package.get("grade")
                or context.get("subject") != package.get("subject")
                or context.get("random_seed") != package.get("random_seed")
                or context.get("source_hashes") != expected_sources):
            problems.append("embedded review context does not match package identity or source hashes")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        problems.append(f"could not verify embedded review context: {exc}")
    reviewer = review.get("reviewer") or {}
    for key in ("name", "qualification", "independent_of_item_author", "reviewed_at"):
        if not str(reviewer.get(key) or "").strip():
            problems.append(f"reviewer field is incomplete: {key}")
    if reviewer.get("independent_of_item_author") not in {"YES", "NO", "UNKNOWN"}:
        problems.append("review independence field is invalid")
    try:
        datetime.fromisoformat(str(reviewer.get("reviewed_at", "")).replace("Z", "+00:00"))
    except ValueError:
        problems.append("review timestamp is invalid")
    if review.get("recommendation") not in {"RECOMMEND_FOR_SECOND_REVIEW", "REVISE", "UNRESOLVED"}:
        problems.append("overall recommendation is missing or invalid")
    if not str(review.get("overall_rationale") or "").strip():
        problems.append("overall rationale is required")
    question_reviews = review.get("question_reviews") or []
    try:
        assessment = json.loads((run_dir / "sources/HOMS_GRADE_ASSESSMENT.json").read_text(encoding="utf-8"))
        expected_ids = {
            str(question.get("number") or "")
            for section in assessment.get("sections") or []
            for question in section.get("questions") or []
        }
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        expected_ids = set()
        problems.append(f"could not read source question IDs: {exc}")
    context_ids = {str(row.get("question_id") or "") for row in context.get("question_rows") or []}
    if context_ids != expected_ids or len(expected_ids) != 5:
        problems.append("embedded review question IDs do not match the packaged assessment")
    if {str(row.get("question_id")) for row in question_reviews} != expected_ids or len(question_reviews) != 5:
        problems.append("review question IDs do not exactly match the packaged assessment")
    criteria = ("content_accuracy", "caps_alignment", "grade_term_fit", "memo_correctness",
                "mark_allocation", "language_accessibility")
    for row in question_reviews:
        qid = str(row.get("question_id"))
        for criterion in criteria:
            if row.get(criterion) not in {"FIT", "REVISE", "UNRESOLVED"}:
                problems.append(f"Question {qid}: {criterion} is incomplete")
        if not str(row.get("rationale") or "").strip():
            problems.append(f"Question {qid}: rationale is required")
        if row.get("mark_allocation") == "REVISE" and not str(row.get("required_revision") or "").strip():
            problems.append(f"Question {qid}: required revision is missing")
    if review.get("independent_moderation_decision") != "NOT_ISSUED" or review.get("classroom_release_authorized") is not False:
        problems.append("review record crossed its non-decisional boundary")
    result = {
        "schema": "dio.homs.moderate.educator_review_validation.v1",
        "state": "VALIDATED_FOR_SECOND_REVIEW" if not problems else "INCOMPLETE_OR_MISMATCHED",
        "issue_count": len(problems), "issues": problems,
        "source_grade_package_sha256": sha(package_path),
        "review_record_sha256": sha(review_path),
        "independent_moderation_decision": "NOT_ISSUED",
        "classroom_release_authorized": False,
    }
    output = args.output.expanduser().resolve() if args.output else review_path.with_name(review_path.stem + "_VALIDATION.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"state": result["state"], "issue_count": len(problems), "receipt": str(output),
                      "independent_moderation_decision": "NOT_ISSUED", "classroom_release_authorized": False}, indent=2))
    return 2 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
