#!/usr/bin/env python3
"""Exercise HOMS Curriculum against every randomized grade/subject spine."""
from __future__ import annotations

import csv
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE = ROOT / "acceptance_runs/68-product-sellability-20261027"
OUT = BASE / "HOMS_CURRICULUM_RANDOMIZED_SPINE_CUSTOMER_GRADE_BATCH_20261102_V8"
INPUT = BASE / "HOMS_CURRICULUM_RANDOMIZED_SPINE_SYNTHETIC_GRADE_BATCH_20261102_V8"
DELIVERABLES = ROOT / "deliverables/homs_random_grade_exam_set_20261101"
ALIGNMENT_PATH = DELIVERABLES / "CAPS_QUESTION_ALIGNMENT_ALL_GRADES_20261101.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-suffix", default="20261104_V15",
                        help="new output suffix, e.g. 20261102_V9; existing outputs are never overwritten")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Z0-9_]+", args.batch_suffix):
        raise ValueError("batch suffix may contain only uppercase letters, digits, and underscores")
    global OUT, INPUT
    OUT = BASE / f"HOMS_CURRICULUM_RANDOMIZED_SPINE_CUSTOMER_GRADE_BATCH_{args.batch_suffix}"
    INPUT = BASE / f"HOMS_CURRICULUM_RANDOMIZED_SPINE_SYNTHETIC_GRADE_BATCH_{args.batch_suffix}"
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f"output directory must be new or empty: {OUT}")
    if INPUT.exists() and any(INPUT.iterdir()):
        raise ValueError(f"input directory must be new or empty: {INPUT}")
    OUT.mkdir(parents=True, exist_ok=True)
    INPUT.mkdir(parents=True, exist_ok=True)
    alignment = json.loads(ALIGNMENT_PATH.read_text(encoding="utf-8"))
    from products.customer_product_router import run_customer_product

    rows = []
    for grade in alignment["grades"]:
        grade_number = int(grade["grade"])
        by_id = {item["question_id"]: item for item in grade["question_mappings"]}
        if set(by_id) != {f"1.{n}" for n in range(1, 6)}:
            raise ValueError(f"grade {grade_number} does not have the five audited question references")
        grade_input = INPUT / f"grade-{grade_number:02d}"
        grade_output = OUT / f"grade-{grade_number:02d}"
        grade_input.mkdir(parents=True, exist_ok=True)
        plan_path = grade_input / "synthetic_customer_plan.csv"
        with plan_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["grade", "subject", "term", "topic", "question_id"])
            writer.writeheader()
            for question_id in sorted(by_id):
                writer.writerow({"grade": grade_number, "subject": grade["subject"], "term": "Term 1",
                                 "topic": by_id[question_id]["caps_topic"], "question_id": question_id})
            writer.writerow({"grade": grade_number, "subject": grade["subject"], "term": "Term 1",
                             "topic": "Synthetic topic intentionally differing from the selected CAPS map",
                             "question_id": "1.2"})
        packet = {
            "owner_authorized": True,
            "randomized_exam_spine": True,
            "controlled_synthetic_demo": True,
            "grade": grade_number,
            "subject": grade["subject"],
            "annual_plan_path": str(plan_path),
            "case_id": f"SYNTHETIC-HOMS-CURRICULUM-GRADE-{grade_number:02d}",
        }
        packet_path = grade_input / "CUSTOMER_PACKET.json"
        packet_path.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        execution = run_customer_product("HOMS Curriculum", packet, grade_output, render_pdf=False)
        package = json.loads((grade_output / "CUSTOMER_PACKAGE_RECEIPT.json").read_text(encoding="utf-8"))
        with (grade_output / "CURRICULUM_ALIGNMENT_MATRIX.csv").open(encoding="utf-8", newline="") as handle:
            matrix = list(csv.DictReader(handle))
        if (len(matrix) != 6
                or any(row["review_state"] != "CAPS_SCOPE_CANDIDATE_MATCH_REVIEW_REQUIRED" for row in matrix[:5])
                or matrix[5]["review_state"] != "TOPIC_DIFFERS_FROM_CAPS_SCOPE_REVIEW_REQUIRED"
                or package.get("mapped_candidate_count") != 5
                or package.get("review_required_count") != 1
                or package.get("term_fit_inferred") is not False
                or package.get("candidate_omissions_computed") is not False
                or package.get("professional_conclusion") is not False
                or package.get("external_release_authorized") is not False
                or execution.get("release_authorized") is not False
                or execution.get("external_effects") is not False):
            raise ValueError(f"grade {grade_number}: route output did not preserve the mapping/review boundary")
        output_rows = []
        for name in ["CUSTOMER_PACKAGE_RECEIPT.json", "CURRICULUM_SOURCE_BINDING.json",
                     "CURRICULUM_ALIGNMENT_MATRIX.csv", "CURRICULUM_REVIEW.html"]:
            path = grade_output / name
            output_rows.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size})
        template_path = grade_output / "CURRICULUM_PLAN_ENTRY_TEMPLATE.csv"
        with template_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["grade", "subject", "term", "topic", "question_id"])
            writer.writeheader()
            for question_id in sorted(by_id):
                writer.writerow({"grade": grade_number, "subject": grade["subject"], "term": "",
                                 "topic": "", "question_id": question_id})
        output_rows.append({"path": template_path.relative_to(ROOT).as_posix(),
                            "sha256": sha(template_path), "bytes": template_path.stat().st_size})
        rows.append({
            "grade": grade_number,
            "subject": grade["subject"],
            "subject_profile": grade["random_subject_profile"],
            "randomization_seed": grade["randomization_seed"],
            "caps_source_sha256": package["caps_source_sha256"],
            "exam_sha256": package["exam_sha256"],
            "memo_sha256": package["memo_sha256"],
            "source_plan_sha256": package["customer_plan_sha256"],
            "candidate_match_count": package["mapped_candidate_count"],
            "review_required_count": package["review_required_count"],
            "term_fit_inferred": False,
            "candidate_omissions_computed": False,
            "professional_conclusion": False,
            "release_authorized": False,
            "input_packet_sha256": sha(packet_path),
            "execution_receipt_sha256": sha(grade_output / "CUSTOMER_EXECUTION_RECEIPT.json"),
            "outputs": output_rows,
        })
    if len(rows) != 12 or {row["grade"] for row in rows} != set(range(1, 13)):
        raise ValueError("HOMS Curriculum randomized spine batch must cover grades 1 through 12")
    receipt = {
        "schema": "dio.homs.curriculum.randomized_exam_spine_grade_batch.v1",
        "requested_product": "HOMS Curriculum",
        "grade_count": 12,
        "randomized_seed": 20261101,
        "assignment_coverage": "all twelve randomized grade/subject pairs from the source-bound HOMS exam batch",
        "synthetic_fixture": True,
        "candidate_mappings_per_grade": 5,
        "mismatched_topics_held_per_grade": 1,
        "term_fit_inferred": False,
        "candidate_omissions_computed": False,
        "professional_conclusion": False,
        "human_curriculum_owner_review_required": True,
        "external_effects": False,
        "release_authorized": False,
        "source_alignment_path": ALIGNMENT_PATH.relative_to(ROOT).as_posix(),
        "source_alignment_sha256": sha(ALIGNMENT_PATH),
        "grades": rows,
    }
    receipt_path = OUT / "HOMS_CURRICULUM_RANDOMIZED_SPINE_GRADE_BATCH_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    execution = {
        "schema": "dio.homs.curriculum.randomized_exam_spine_grade_batch_execution.v1",
        "requested_product": "HOMS Curriculum",
        "output_dir": OUT.relative_to(ROOT).as_posix(),
        "batch_receipt_sha256": sha(receipt_path),
        "grade_count": 12,
        "external_effects": False,
        "release_authorized": False,
    }
    execution_path = OUT / "CUSTOMER_EXECUTION_RECEIPT.json"
    execution_path.write_text(json.dumps(execution, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"receipt": receipt_path.relative_to(ROOT).as_posix(), "execution_receipt": execution_path.relative_to(ROOT).as_posix(), "grade_count": len(rows), "candidate_matches": sum(row['candidate_match_count'] for row in rows), "mismatched_rows_held": sum(row['review_required_count'] for row in rows), "release_authorized": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
