#!/usr/bin/env python3
"""Run HOMS Moderate's non-decisional customer route for Grades 1–12."""
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
DEFAULT_OUTPUT = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_MODERATE_CUSTOMER_GRADE_BATCH_20261104_V24"


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
    set_receipt = json.loads((PACK / "GRADE_EXAM_SET_RECEIPT.json").read_text(encoding="utf-8"))
    assignments = {int(row["grade"]): row for row in assignments_doc.get("assignments", [])}
    grades = {int(row["grade"]): row for row in set_receipt.get("results", [])}
    if set(assignments) != set(range(1, 13)) or set(grades) != set(range(1, 13)):
        raise ValueError("moderation source set and randomized assignments must each contain Grades 1–12")

    from products.customer_product_router import run_customer_product

    results = []
    for grade in range(1, 13):
        assignment = assignments[grade]
        grade_out = out / f"grade-{grade:02d}"
        result = run_customer_product(
            "HOMS Moderate",
            {"owner_authorized": True, "grade": grade},
            grade_out,
            render_pdf=False,
        )
        package_path = grade_out / "CUSTOMER_PACKAGE_RECEIPT.json"
        package = json.loads(package_path.read_text(encoding="utf-8"))
        if package.get("grade") != grade or package.get("subject_profile") != assignment.get("subject_profile"):
            raise ValueError(f"Grade {grade} moderation package does not match its randomized assignment")
        if package.get("random_seed") != assignments_doc.get("random_seed"):
            raise ValueError(f"Grade {grade} moderation package uses a different random seed")
        if package.get("independent_moderation_decision") != "NOT_ISSUED" or package.get("classroom_release_authorized") is not False:
            raise ValueError(f"Grade {grade} moderation route crossed its human decision/release boundary")
        if package.get("check_count") != 8 or package.get("passed_checks") != 8:
            raise ValueError(f"Grade {grade} moderation package did not pass all eight source-bound checks")
        for row in package.get("outputs", []):
            path = grade_out / row["path"]
            if not path.is_file() or sha(path) != row.get("sha256"):
                raise ValueError(f"Grade {grade} moderation output hash mismatch: {row.get('path')}")
        execution_path = grade_out / "CUSTOMER_EXECUTION_RECEIPT.json"
        results.append({
            "grade": grade,
            "subject": package["subject"],
            "subject_profile": assignment["subject_profile"],
            "random_seed": package["random_seed"],
            "mechanical_state": package["mechanical_state"],
            "check_count": package["check_count"],
            "passed_checks": package["passed_checks"],
            "source_exam_sha256": package["source_exam_sha256"],
            "source_memo_sha256": package["source_memo_sha256"],
            "source_caps_sha256": package["source_caps_sha256"],
            "source_caps_alignment_sha256": package["source_caps_alignment_sha256"],
            "execution_receipt": execution_path.relative_to(out).as_posix(),
            "execution_receipt_sha256": sha(execution_path),
            "package_receipt": package_path.relative_to(out).as_posix(),
            "package_receipt_sha256": sha(package_path),
            "outputs": package["outputs"],
        })

    receipt = {
        "schema": "dio.homs.moderate.customer_grade_batch.v1",
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "synthetic_acceptance_inputs_only": True,
        "grade_count": len(results),
        "random_seed": assignments_doc["random_seed"],
        "assignment_manifest_sha256": sha(PACK / "RANDOM_SUBJECT_ASSIGNMENTS.json"),
        "mechanical_pass_count": sum(row["mechanical_state"] == "PASS" for row in results),
        "mechanical_review_required_count": sum(row["mechanical_state"] != "PASS" for row in results),
        "independent_moderation_decision": "NOT_ISSUED",
        "classroom_release_authorized": False,
        "educator_review_required": True,
        "results": results,
    }
    receipt_path = out / "HOMS_MODERATE_CUSTOMER_GRADE_BATCH_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "receipt": str(receipt_path.relative_to(ROOT)),
        "grade_count": len(results),
        "mechanical_pass_count": receipt["mechanical_pass_count"],
        "mechanical_review_required_count": receipt["mechanical_review_required_count"],
        "independent_moderation_decision": "NOT_ISSUED",
        "classroom_release_authorized": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
