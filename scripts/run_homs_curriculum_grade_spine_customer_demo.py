#!/usr/bin/env python3
"""Run a controlled synthetic Grade 12 HOMS Curriculum spine packet."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE = ROOT / "acceptance_runs/68-product-sellability-20261027"
OUT = BASE / "HOMS_CURRICULUM_RANDOMIZED_SPINE_CUSTOMER_EXECUTION_20261103_G12_V1"
INPUT = BASE / "HOMS_CURRICULUM_RANDOMIZED_SPINE_SYNTHETIC_INPUT_20261103_G12_V1"
ALIGNMENT = ROOT / "deliverables/homs_random_grade_exam_set_20261101/CAPS_QUESTION_ALIGNMENT_ALL_GRADES_20261101.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f"output directory must be new or empty: {OUT}")
    if INPUT.exists() and any(INPUT.iterdir()):
        raise ValueError(f"input directory must be new or empty: {INPUT}")
    INPUT.mkdir(parents=True, exist_ok=True)
    alignment = json.loads(ALIGNMENT.read_text(encoding="utf-8"))
    grade = next(row for row in alignment["grades"] if row["grade"] == 12)
    question_by_id = {row["question_id"]: row for row in grade["question_mappings"]}
    plan_path = INPUT / "synthetic_grade12_business_studies_plan.csv"
    with plan_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["grade", "subject", "term", "topic", "question_id"])
        writer.writeheader()
        writer.writerow({"grade": 12, "subject": grade["subject"], "term": "Term 1",
                         "topic": question_by_id["1.1"]["caps_topic"], "question_id": "1.1"})
        writer.writerow({"grade": 12, "subject": grade["subject"], "term": "Term 1",
                         "topic": "Synthetic topic intentionally differing from the selected CAPS map",
                         "question_id": "1.2"})
    packet = {
        "owner_authorized": True,
        "randomized_exam_spine": True,
        "controlled_synthetic_demo": True,
        "grade": 12,
        "subject": grade["subject"],
        "annual_plan_path": str(plan_path),
        "case_id": "SYNTHETIC-HOMS-CURRICULUM-G12-BUSINESS-STUDIES",
    }
    packet_path = INPUT / "CUSTOMER_PACKET.json"
    packet_path.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    from products.customer_product_router import run_customer_product

    execution = run_customer_product("HOMS Curriculum", packet, OUT, render_pdf=False)
    package = json.loads((OUT / "CUSTOMER_PACKAGE_RECEIPT.json").read_text(encoding="utf-8"))
    matrix_path = OUT / "CURRICULUM_ALIGNMENT_MATRIX.csv"
    with matrix_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if (len(rows) != 2
            or rows[0]["review_state"] != "CAPS_SCOPE_CANDIDATE_MATCH_REVIEW_REQUIRED"
            or rows[1]["review_state"] != "TOPIC_DIFFERS_FROM_CAPS_SCOPE_REVIEW_REQUIRED"
            or package.get("mapped_candidate_count") != 1
            or package.get("review_required_count") != 1
            or package.get("term_fit_inferred") is not False
            or package.get("candidate_omissions_computed") is not False
            or package.get("professional_conclusion") is not False
            or package.get("external_release_authorized") is not False):
        raise ValueError("HOMS Curriculum grade-spine route exceeded its candidate-mapping boundary")
    outputs = []
    for relative in ["CUSTOMER_PACKAGE_RECEIPT.json", "CURRICULUM_SOURCE_BINDING.json",
                     "CURRICULUM_ALIGNMENT_MATRIX.csv", "CURRICULUM_REVIEW.html"]:
        artifact = OUT / relative
        outputs.append({"path": relative, "sha256": sha(artifact), "bytes": artifact.stat().st_size})
    evidence = {
        "schema": "dio.homs.curriculum.randomized_exam_spine_customer_demo.v1",
        "requested_product": "HOMS Curriculum",
        "run": OUT.relative_to(ROOT).as_posix(),
        "input_dir": INPUT.relative_to(ROOT).as_posix(),
        "input_packet_sha256": sha(packet_path),
        "plan_sha256": sha(plan_path),
        "customer_execution_sha256": sha(OUT / "CUSTOMER_EXECUTION_RECEIPT.json"),
        "package_receipt_sha256": sha(OUT / "CUSTOMER_PACKAGE_RECEIPT.json"),
        "grade": 12,
        "subject": grade["subject"],
        "randomization_seed": package["randomization_seed"],
        "candidate_match_count": package["mapped_candidate_count"],
        "review_required_count": package["review_required_count"],
        "term_fit_inferred": False,
        "candidate_omissions_computed": False,
        "professional_conclusion": False,
        "external_effects": False,
        "release_authorized": False,
        "outputs": outputs,
    }
    evidence_path = OUT / "GRADE_SPINE_EXECUTION_EVIDENCE.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
