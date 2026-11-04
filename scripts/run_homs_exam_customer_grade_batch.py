#!/usr/bin/env python3
"""Run the HOMS Exam customer delivery route for all randomized Grades 1–12."""
from __future__ import annotations

import hashlib
import json
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PACK = ROOT / "deliverables/homs_random_grade_exam_set_20261101"
DEFAULT_OUTPUT = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_EXAM_CUSTOMER_GRADE_BATCH_20261104_V34"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        parser.error(f"output directory must be new or empty: {out}")
    out.mkdir(parents=True, exist_ok=True)

    assignments = json.loads((PACK / "RANDOM_SUBJECT_ASSIGNMENTS.json").read_text(encoding="utf-8"))
    expected = {int(row["grade"]): row for row in assignments.get("assignments", [])}
    if set(expected) != set(range(1, 13)):
        raise ValueError("randomized HOMS assignment manifest must contain exactly Grades 1–12")

    from products.customer_product_router import run_customer_product

    results = []
    for grade in range(1, 13):
        grade_out = out / f"grade-{grade:02d}"
        result = run_customer_product(
            "HOMS Exam",
            {"owner_authorized": True, "grade": grade},
            grade_out,
            render_pdf=False,
        )
        package_path = grade_out / "CUSTOMER_PACKAGE_RECEIPT.json"
        package = json.loads(package_path.read_text(encoding="utf-8"))
        assignment = expected[grade]
        if package.get("grade") != grade or package.get("subject_profile") != assignment.get("subject_profile"):
            raise ValueError(f"Grade {grade} delivery does not match its randomized subject assignment")
        if package.get("random_seed") != assignments.get("random_seed"):
            raise ValueError(f"Grade {grade} delivery uses a different randomization seed")
        if (package.get("caps_source_page_excerpt_hashes_match_alignment") is not True
                or package.get("caps_source_page_excerpt_count", 0) < package.get("question_count", 0)):
            raise ValueError(f"Grade {grade} delivery is missing hash-verified CAPS page excerpts")
        if package.get("classroom_release_authorized") is not False or package.get("educator_review_required") is not True:
            raise ValueError(f"Grade {grade} customer delivery crossed its educator/release boundary")
        quality = package.get("educator_item_quality_review") or {}
        if (quality.get("question_row_count") != package.get("question_count")
                or quality.get("blank_educator_decisions") is not True
                or quality.get("independent_moderation_decision") != "NOT_ISSUED"):
            raise ValueError(f"Grade {grade} educator item quality review sheet is missing or crossed its moderation boundary")
        quality_validation = json.loads((grade_out / "EDUCATOR_ITEM_QUALITY_REVIEW_VALIDATION.json").read_text(encoding="utf-8"))
        if (quality_validation.get("state") != "NEEDS_EDUCATOR_COMPLETION"
                or quality_validation.get("source_question_count") != package.get("question_count")
                or quality_validation.get("matched_question_count") != package.get("question_count")
                or quality_validation.get("classroom_release_authorized") is not False
                or quality_validation.get("independent_moderation_decision") != "NOT_ISSUED"
                or quality.get("validation_sha256") != sha(grade_out / "EDUCATOR_ITEM_QUALITY_REVIEW_VALIDATION.json")):
            raise ValueError(f"Grade {grade} blank quality review did not validate as an exact, held question set")
        with (grade_out / "EDUCATOR_ITEM_QUALITY_REVIEW.csv").open(encoding="utf-8-sig", newline="") as quality_handle:
            quality_csv_rows = list(csv.DictReader(quality_handle))
        educator_fields = ("educator_confirmed_cognitive_level", "educator_reasoning_demand", "educator_grade_term_fit",
                           "educator_caps_alignment", "educator_memo_alignment", "educator_mark_allocation_fit",
                           "educator_language_accessibility", "educator_decision", "educator_rationale", "educator_reviewer", "reviewed_at")
        if (len(quality_csv_rows) != package.get("question_count")
                or any(row.get(field, "").strip() for row in quality_csv_rows for field in educator_fields)
                or not quality.get("automated_memo_mark_balance_all_pass")):
            raise ValueError(f"Grade {grade} item review lacks complete question coverage, blank moderator fields, or balanced memo allocations")
        unclassified = sum(row.get("draft_cognitive_level_label_state") == "NEEDS_EDUCATOR_CLASSIFICATION" for row in quality_csv_rows)
        if (unclassified != quality.get("unclassified_draft_cognitive_label_count")
                or sum((quality.get("draft_cognitive_level_counts") or {}).values()) != package.get("question_count")):
            raise ValueError(f"Grade {grade} draft cognitive-label normalization does not reconcile to question rows")
        declared = {row["path"]: row["sha256"] for row in package.get("outputs", [])}
        if set(declared) != {"documents/GRADE_%02d_DRAFT_EXAM.docx" % grade,
                            "documents/GRADE_%02d_DRAFT_MARKING_MEMO.docx" % grade,
                            "documents/GRADE_%02d_DRAFT_EXAM.pdf" % grade,
                            "documents/GRADE_%02d_DRAFT_MARKING_MEMO.pdf" % grade,
                            "EDUCATOR_ITEM_QUALITY_REVIEW.csv",
                            "EDUCATOR_ITEM_QUALITY_REVIEW_GUIDE.md",
                            "EDUCATOR_ITEM_QUALITY_REVIEW.html",
                            "EDUCATOR_ITEM_QUALITY_REVIEW_VALIDATION.json",
                            "CUSTOMER_EXAM_PACKAGE.html"}:
            raise ValueError(f"Grade {grade} package has an unexpected exam/memo output set")
        for relative, digest in declared.items():
            path = grade_out / relative
            if not path.is_file() or sha(path) != digest:
                raise ValueError(f"Grade {grade} output hash mismatch: {relative}")
        execution_path = grade_out / "CUSTOMER_EXECUTION_RECEIPT.json"
        results.append({
            "grade": grade,
            "subject": package["subject"],
            "subject_profile": assignment["subject_profile"],
            "random_seed": assignments["random_seed"],
            "question_count": package["question_count"],
            "caps_question_mapping_count": package["caps_question_mapping_count"],
            "total_marks": package["total_marks"],
            "duration_minutes": package["duration_minutes"],
            "print_pdf_manifest_sha256": package["print_pdf_manifest_sha256"],
            "exam_pdf_sha256": package["exam_pdf_sha256"],
            "memo_pdf_sha256": package["memo_pdf_sha256"],
            "educator_item_quality_review": quality,
            "exam_pdf_pages": package["exam_pdf_pages"],
            "memo_pdf_pages": package["memo_pdf_pages"],
            "execution_receipt": execution_path.relative_to(out).as_posix(),
            "execution_receipt_sha256": sha(execution_path),
            "package_receipt": package_path.relative_to(out).as_posix(),
            "package_receipt_sha256": sha(package_path),
            "output_hashes": declared,
        })

    receipt = {
        "schema": "dio.homs.exam.customer_grade_batch.v1",
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "synthetic_acceptance_inputs_only": True,
        "grade_count": len(results),
        "random_seed": assignments["random_seed"],
        "assignment_manifest_sha256": sha(PACK / "RANDOM_SUBJECT_ASSIGNMENTS.json"),
        "classroom_release_authorized": False,
        "educator_review_required": True,
        "independent_moderation_decision": "NOT_ISSUED",
        "results": results,
    }
    receipt_path = out / "HOMS_EXAM_CUSTOMER_GRADE_BATCH_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"receipt": str(receipt_path.relative_to(ROOT)), "grade_count": len(results),
                      "all_grades_match_randomized_assignments": True,
                      "all_customer_routes_executed": True,
                      "classroom_release_authorized": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
