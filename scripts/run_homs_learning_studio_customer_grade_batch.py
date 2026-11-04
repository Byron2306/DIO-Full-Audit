#!/usr/bin/env python3
"""Run the HOMS Learning Studio customer route for all randomized Grades 1–12."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PACK = ROOT / "deliverables/homs_random_grade_exam_set_20261101"
CROSSWALKS = PACK / "learning_crosswalks/HOMS_GRADE_LEARNING_CROSSWALK_BATCH_RECEIPT.json"
DEFAULT_OUTPUT = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_LEARNING_STUDIO_CUSTOMER_GRADE_BATCH_20261104_V30"


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

    assignments_doc = json.loads((PACK / "RANDOM_SUBJECT_ASSIGNMENTS.json").read_text(encoding="utf-8"))
    assignments = {int(row["grade"]): row for row in assignments_doc.get("assignments", [])}
    crosswalks = json.loads(CROSSWALKS.read_text(encoding="utf-8"))
    source_rows = {int(row["grade"]): row for row in crosswalks.get("grades", [])}
    if set(assignments) != set(range(1, 13)) or set(source_rows) != set(range(1, 13)):
        raise ValueError("randomized assignments and Learning Studio spines must cover Grades 1–12")

    from products.customer_product_router import run_customer_product

    results = []
    for grade in range(1, 13):
        assignment = assignments[grade]
        source_row = source_rows[grade]
        grade_out = out / f"grade-{grade:02d}"
        result = run_customer_product(
            "HOMS Learning Studio",
            {"owner_authorized": True, "grade": grade, "subject": source_row["subject"], "language": "English"},
            grade_out,
            render_pdf=False,
        )
        package_path = grade_out / "CUSTOMER_PACKAGE_RECEIPT.json"
        package = json.loads(package_path.read_text(encoding="utf-8"))
        if package.get("grade") != grade or package.get("subject") != source_row.get("subject"):
            raise ValueError(f"Grade {grade} learning package does not match its randomized subject spine")
        if source_row.get("subject_profile") and source_row["subject_profile"] != assignment.get("subject_profile"):
            raise ValueError(f"Grade {grade} learning spine does not match the randomized subject profile")
        if package.get("classroom_release_authorized") is not False or package.get("educator_approval_required") is not True:
            raise ValueError(f"Grade {grade} learning pack crossed its classroom release boundary")
        if package.get("source_exam_sha256") != source_row.get("exam_sha256") or package.get("source_memo_sha256") != source_row.get("memo_sha256"):
            raise ValueError(f"Grade {grade} learning pack is not bound to its source exam and memo")
        learning_root = grade_out / "learning_studio"
        learning_manifest = json.loads((learning_root / "HOMS_LEARNING_STUDIO_MANIFEST.json").read_text(encoding="utf-8"))
        planner = learning_manifest.get("educator_planner") or {}
        planner_path = learning_root / str(planner.get("path") or "")
        planner_validation = (learning_manifest.get("validation") or {}).get("interactive_educator_planner") or {}
        planner_output = next((row for row in package.get("outputs", []) if row.get("path") == f"learning_studio/{planner.get('path')}"), None)
        planner_text = planner_path.read_text(encoding="utf-8") if planner_path.is_file() else ""
        if (not planner_output or not planner_path.is_file()
                or planner_output.get("sha256") != sha(planner_path)
                or planner.get("sha256") != sha(planner_path)
                or planner.get("source_spine_sha256") != package.get("source_spine_sha256")
                or planner.get("question_count") != (learning_manifest.get("validation") or {}).get("question_count")
                or planner.get("planning_fields_per_question") != 7
                or planner.get("external_processing") is not False
                or planner.get("approval_recorded") is not False
                or planner.get("classroom_release_authorized") is not False
                or planner_validation.get("all_fields_initially_blank") is not True
                or planner_text.count("data-field='") != planner.get("question_count", 0) * 7
                or "localStorage" not in planner_text or "Download lesson-plan JSON" not in planner_text):
            raise ValueError(f"Grade {grade} customer pack is missing a source-bound, locally controlled educator planner")
        pdf_row = next(row for row in json.loads((PACK / "PRINT_READY_PDF_MANIFEST.json").read_text(encoding="utf-8"))["grades"] if int(row["grade"]) == grade)
        if (package.get("source_print_pdf_manifest_sha256") != sha(PACK / "PRINT_READY_PDF_MANIFEST.json")
                or package.get("exam_pdf_sha256") != pdf_row.get("exam_pdf_sha256")
                or package.get("memo_pdf_sha256") != pdf_row.get("memo_pdf_sha256")
                or package.get("exam_pdf_pages") != pdf_row.get("exam_pdf_pages")
                or package.get("memo_pdf_pages") != pdf_row.get("memo_pdf_pages")):
            raise ValueError(f"Grade {grade} Learning Studio paper/memo PDFs are not bound to the source print manifest")
        for output_row in package.get("outputs", []):
            path = grade_out / output_row["path"]
            if not path.is_file() or sha(path) != output_row.get("sha256"):
                raise ValueError(f"Grade {grade} learning output hash mismatch: {output_row.get('path')}")
        execution_path = grade_out / "CUSTOMER_EXECUTION_RECEIPT.json"
        results.append({
            "grade": grade,
            "subject": package["subject"],
            "subject_profile": assignment["subject_profile"],
            "random_seed": assignments_doc["random_seed"],
            "source_exam_sha256": package["source_exam_sha256"],
            "source_memo_sha256": package["source_memo_sha256"],
            "source_print_pdf_manifest_sha256": package["source_print_pdf_manifest_sha256"],
            "exam_pdf_sha256": package["exam_pdf_sha256"],
            "memo_pdf_sha256": package["memo_pdf_sha256"],
            "exam_pdf_pages": package["exam_pdf_pages"],
            "memo_pdf_pages": package["memo_pdf_pages"],
            "source_spine_sha256": package["source_spine_sha256"],
            "pack_status": package["pack_status"],
            "generated_guide_count": package["generated_guide_count"],
            "pdf_count": package["pdf_count"],
            "pictora_visual_state": package["pictora_visual_state"],
            "visual_count": package["visual_count"],
            "video_bundle_status": package["video_bundle_status"],
            "educator_planner_path": f"learning_studio/{planner.get('path')}",
            "educator_planner_sha256": planner["sha256"],
            "educator_planner_question_count": planner["question_count"],
            "educator_planner_fields_per_question": planner["planning_fields_per_question"],
            "execution_receipt": execution_path.relative_to(out).as_posix(),
            "execution_receipt_sha256": sha(execution_path),
            "package_receipt": package_path.relative_to(out).as_posix(),
            "package_receipt_sha256": sha(package_path),
            "outputs": package["outputs"],
        })

    receipt = {
        "schema": "dio.homs.learning_studio.customer_grade_batch.v1",
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "synthetic_acceptance_inputs_only": True,
        "grade_count": len(results),
        "random_seed": assignments_doc["random_seed"],
        "assignment_manifest_sha256": sha(PACK / "RANDOM_SUBJECT_ASSIGNMENTS.json"),
        "crosswalk_batch_sha256": sha(CROSSWALKS),
        "educator_approval_required": True,
        "classroom_release_authorized": False,
        "results": results,
    }
    receipt_path = out / "HOMS_LEARNING_STUDIO_CUSTOMER_GRADE_BATCH_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "receipt": str(receipt_path.relative_to(ROOT)),
        "grade_count": len(results),
        "all_source_exam_memo_bindings_verified": True,
        "educator_approval_required": True,
        "classroom_release_authorized": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
