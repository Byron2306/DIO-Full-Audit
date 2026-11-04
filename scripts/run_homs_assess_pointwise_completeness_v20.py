#!/usr/bin/env python3
"""Run HOMS Assess V20 against the same synthetic Grade 10 packet as V17."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PACKET_DIR = ROOT / "acceptance_runs/68-product-sellability-20261027/homs-assess-unit-feedback-gate-20261102/homs-assess/CUSTOMER_PACKET"
PACKET_PATH = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_ASSESS_POINTWISE_COMPLETENESS_INPUT_20261103.json"
OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_ASSESS_CUSTOMER_PACKET_EXECUTION_20261103_G10_V20"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    packet = {
        "owner_authorized": True,
        "grade": 10,
        "subject": "Physical Sciences",
        "customer_packet_dir": str(PACKET_DIR),
        "model": "granite3.2:2b",
        "temperature": 0.0,
        "controlled_synthetic_demo": True,
    }
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f"output directory must be new or empty: {OUT}")
    PACKET_PATH.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    from products.customer_product_router import run_customer_product

    execution = run_customer_product("HOMS Assess", packet, OUT, render_pdf=False)
    package = json.loads((OUT / "CUSTOMER_PACKAGE_RECEIPT.json").read_text(encoding="utf-8"))
    results_path = OUT / package["outputs"]["results"]
    results = json.loads(results_path.read_text(encoding="utf-8"))
    rubric = json.loads((OUT / "input/rubric.json").read_text(encoding="utf-8"))
    expected_by_criterion = {
        str(criterion.get("name") or ""): {str(point.get("point_id") or "") for point in criterion.get("marking_points") or []}
        for criterion in rubric.get("criteria") or []
    }
    incomplete_rows = []
    for result in results:
        missing_count = 0
        for criterion_name, score in (result.get("criteria_scores") or {}).items():
            expected_ids = expected_by_criterion.get(criterion_name, set())
            point_rows = score.get("point_scores") or []
            returned = {str(point.get("point_id") or "") for point in point_rows if point.get("score") is not None}
            missing = expected_ids - returned
            missing_count += len(missing)
            if missing:
                if score.get("score") is not None or score.get("unreturned_point_ids") != sorted(missing):
                    raise ValueError(f"{result['student_id']} {criterion_name}: omitted memo points were scored or not recorded")
                if score.get("omitted_point_ids_defaulted_to_zero"):
                    raise ValueError("omitted memo points must never be defaulted to zero")
        if missing_count:
            if (result.get("score_status") != "BLOCKED_INCOMPLETE_POINTWISE_RESPONSE"
                    or result.get("total_score") is not None or result.get("percentage") is not None
                    or result.get("proposed_total_score") is not None):
                raise ValueError(f"{result['student_id']}: incomplete memo point set did not block all totals")
            incomplete_rows.append({"student_id": result["student_id"], "unreturned_point_count": missing_count})
    marks_path = OUT / package["outputs"]["marks_csv"]
    with marks_path.open(encoding="utf-8", newline="") as handle:
        marks = {row["student_id"]: row for row in csv.DictReader(handle)}
    for result in results:
        if result.get("score_status") == "BLOCKED_INCOMPLETE_POINTWISE_RESPONSE":
            row = marks[result["student_id"]]
            if row.get("score") or row.get("proposed_score"):
                raise ValueError("incomplete pointwise response leaked a numerical proposal into the marks CSV")
    review_path = OUT / package["outputs"]["pointwise_educator_review"]
    review_receipt_path = OUT / package["outputs"]["pointwise_review_receipt"]
    review_receipt = json.loads(review_receipt_path.read_text(encoding="utf-8"))
    if (sha(review_path) != review_receipt.get("page_sha256")
            or review_receipt.get("educator_review_required") is not True
            or review_receipt.get("classroom_release_authorized") is not False):
        raise ValueError("pointwise review surface receipt is missing or violates the held review boundary")
    zip_path = OUT / package["outputs"]["review_zip"]
    import zipfile
    with zipfile.ZipFile(zip_path) as archive:
        if "educator_review/index.html" not in archive.namelist() or "educator_review/POINTWISE_REVIEW_RECEIPT.json" not in archive.namelist():
            raise ValueError("held review ZIP does not include the pointwise educator surface and receipt")
    evidence = {
        "schema": "dio.homs.assess.pointwise_completeness_execution.v1",
        "run": OUT.relative_to(ROOT).as_posix(),
        "created_at_utc": execution.get("receipt", {}).get("created_at"),
        "source_packet_manifest_sha256": package["source_packet_manifest_sha256"],
        "model": package.get("local_provider"),
        "grade": package["grade"], "subject": package["subject"],
        "submission_count": len(results),
        "unreturned_pointwise_submissions": incomplete_rows,
        "omitted_points_defaulted_to_zero": package.get("omitted_point_ids_defaulted_to_zero"),
        "pointwise_review_path": (OUT / package["outputs"]["pointwise_educator_review"]).relative_to(ROOT).as_posix(),
        "pointwise_review_sha256": sha(review_path),
        "customer_package_sha256": sha(OUT / "CUSTOMER_PACKAGE_RECEIPT.json"),
        "customer_execution_sha256": sha(OUT / "CUSTOMER_EXECUTION_RECEIPT.json"),
        "all_incomplete_totals_withheld": True,
        "marks_csv_contains_no_incomplete_proposal": True,
        "educator_review_required": True,
        "classroom_release_authorized": False,
        "external_processing": False,
        "product_qualification": "UNPROVED",
    }
    evidence_path = OUT / "POINTWISE_COMPLETENESS_EXECUTION_EVIDENCE.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"evidence": evidence_path.relative_to(ROOT).as_posix(),
                      "submissions": len(results), "incomplete_submissions": len(incomplete_rows),
                      "omitted_points_defaulted_to_zero": package.get("omitted_point_ids_defaulted_to_zero"),
                      "pointwise_review_surface_verified": True,
                      "all_incomplete_totals_withheld": True,
                      "classroom_release_authorized": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
