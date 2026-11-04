#!/usr/bin/env python3
"""Validate a completed HOMS Exam educator matrix against the current grade source set."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.homs_exam_customer import build_homs_exam_customer_package, validate_item_quality_review_csv


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path, help="one HOMS Exam grade package directory")
    parser.add_argument("--csv", required=True, type=Path, help="completed educator item-quality review CSV")
    parser.add_argument("--output", type=Path, help="validation receipt path; defaults beside completed CSV")
    args = parser.parse_args()
    run_dir, csv_path = args.run_dir.expanduser().resolve(), args.csv.expanduser().resolve()
    package_path = run_dir / "CUSTOMER_PACKAGE_RECEIPT.json"
    if not package_path.is_file() or not csv_path.is_file():
        parser.error("grade package receipt and review CSV must both exist")
    package = read_json(package_path)
    if (package.get("schema") != "dio.homs.exam.customer_execution.v1"
            or package.get("classroom_release_authorized") is not False
            or package.get("educator_review_required") is not True):
        parser.error("source package identity or held classroom boundary is invalid")

    with tempfile.TemporaryDirectory(prefix="homs-exam-quality-source-") as temporary:
        expected_package = build_homs_exam_customer_package(
            {"grade": int(package["grade"]), "subject": str(package["subject"])},
            Path(temporary) / "expected-source",
        )
        source_hashes = expected_package.get("educator_item_quality_review", {}).get("source_hashes") or {}
        if (expected_package.get("assessment_json_sha256") != package.get("assessment_json_sha256")
                or expected_package.get("exam_sha256") != package.get("exam_sha256")
                or expected_package.get("memo_sha256") != package.get("memo_sha256")
                or expected_package.get("caps_source_sha256") != package.get("caps_source_sha256")
                or source_hashes != (package.get("educator_item_quality_review", {}).get("source_hashes") or {})):
            parser.error("grade package is stale against the current assessment/CAPS/memo source set")
        expected_path = Path(temporary) / "expected-source/EDUCATOR_ITEM_QUALITY_REVIEW.csv"
        with expected_path.open("r", encoding="utf-8-sig", newline="") as handle:
            expected_rows = list(csv.DictReader(handle))

    validated = validate_item_quality_review_csv(csv_path, expected_rows, source_hashes=source_hashes)
    validated.update({
        "source_grade_package": str(package_path),
        "source_grade_package_sha256": sha(package_path),
        "source_customer_exam_sha256": package.get("exam_sha256"),
        "source_customer_memo_sha256": package.get("memo_sha256"),
        "independent_moderation_decision": "NOT_ISSUED",
        "classroom_release_authorized": False,
    })
    output = args.output.expanduser().resolve() if args.output else csv_path.with_name(csv_path.stem + "_VALIDATION.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(validated, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"state": validated["state"], "source_question_count": validated["source_question_count"],
                      "matched_question_count": validated["matched_question_count"],
                      "incomplete_educator_field_count": validated["incomplete_educator_field_count"],
                      "issues": len(validated["issues"]), "independent_moderation_decision": "NOT_ISSUED",
                      "classroom_release_authorized": False, "receipt": str(output)}, indent=2))
    return 2 if validated["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
