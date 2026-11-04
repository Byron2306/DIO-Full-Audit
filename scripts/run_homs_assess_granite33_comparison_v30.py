#!/usr/bin/env python3
"""Run a current-route synthetic HOMS Assess comparison using local Granite 3.3."""
from __future__ import annotations

import hashlib
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SOURCE_PACKET = ROOT / "acceptance_runs/68-product-sellability-20261027/homs-assess-unit-feedback-gate-20261102/homs-assess/CUSTOMER_PACKET"
OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_ASSESS_CUSTOMER_PACKET_EXECUTION_20261102_G10_V30_GRANITE33"
BASELINE = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_ASSESS_CUSTOMER_PACKET_EXECUTION_20261107_G10_V29"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze_run(root: Path) -> dict:
    package_path = root / "CUSTOMER_PACKAGE_RECEIPT.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    results_path = root / package["outputs"]["results"]
    results = json.loads(results_path.read_text(encoding="utf-8"))
    rubric = json.loads((root / "input/rubric.json").read_text(encoding="utf-8"))
    rubric_points = {
        str(criterion.get("question") or str(criterion.get("name") or "").split(":", 1)[0]): {
            str(point.get("point_id") or ""): float(point.get("marks") or 0)
            for point in criterion.get("marking_points") or []
        }
        for criterion in rubric.get("criteria") or []
    }
    submissions = {}
    for path in sorted((root / "input/uploads").glob("*")):
        if path.suffix.casefold() in {".txt", ".md"}:
            submissions[path.stem] = " ".join(path.read_text(encoding="utf-8", errors="replace").split())
    expected_per_submission = sum(len(points) for points in rubric_points.values())
    summary = {"learners": [], "expected_point_count": expected_per_submission * len(results),
               "returned_point_count": 0, "missing_point_id_count": 0,
               "positive_point_proposal_count": 0,
               "positive_proposals_with_exact_source_quote_count": 0,
               "positive_proposals_without_exact_source_quote_count": 0,
               "score_status_counts": {}, "all_totals_blank": True,
               "model": package.get("local_provider", {}).get("selected_model"),
               "source_packet_fingerprint": package.get("customer_packet_fingerprint"),
               "package_sha256": sha(package_path), "results_sha256": sha(results_path)}
    for result in results:
        student = str(result.get("student_id") or "")
        source = submissions.get(student, "")
        returned_ids = set()
        positive = exact = 0
        for criterion_key, criterion_result in (result.get("criteria_scores") or {}).items():
            criterion_id = str(criterion_key).split(":", 1)[0].strip()
            points = criterion_result.get("point_scores") or []
            if isinstance(points, dict):
                points = [dict(value, point_id=key) if isinstance(value, dict) else {"point_id": key, "score": value} for key, value in points.items()]
            for point in points:
                point_id = str(point.get("point_id") or "")
                if point_id not in rubric_points.get(criterion_id, {}):
                    continue
                returned_ids.add((criterion_id, point_id))
                score = point.get("score")
                if score is not None and float(score) > 0:
                    positive += 1
                    quotes = point.get("quotes") or []
                    if isinstance(quotes, str):
                        quotes = [quotes]
                    if any(isinstance(q, str) and " ".join(q.split()) in source for q in quotes):
                        exact += 1
        expected_ids = {(criterion, point_id) for criterion, points in rubric_points.items() for point_id in points}
        missing = len(expected_ids - returned_ids)
        status = str(result.get("score_status") or "UNKNOWN")
        summary["returned_point_count"] += len(returned_ids)
        summary["missing_point_id_count"] += missing
        summary["positive_point_proposal_count"] += positive
        summary["positive_proposals_with_exact_source_quote_count"] += exact
        summary["positive_proposals_without_exact_source_quote_count"] += positive - exact
        summary["score_status_counts"][status] = summary["score_status_counts"].get(status, 0) + 1
        summary["all_totals_blank"] = summary["all_totals_blank"] and result.get("total_score") is None and result.get("percentage") is None
        summary["learners"].append({
            "student_id": student, "expected_point_count": expected_per_submission,
            "returned_point_count": len(returned_ids), "missing_point_id_count": missing,
            "positive_point_proposal_count": positive,
            "positive_proposals_with_exact_source_quote_count": exact,
            "positive_proposals_without_exact_source_quote_count": positive - exact,
            "score_status": status, "total_score": result.get("total_score"), "percentage": result.get("percentage"),
        })
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-existing", action="store_true", help="rebuild comparison evidence without rerunning model inference")
    parser.add_argument("--out", type=Path, default=OUT, help="new output directory for this controlled local comparison")
    args = parser.parse_args()
    output = args.out.expanduser().resolve()
    if not args.audit_existing and output.exists() and any(output.iterdir()):
        raise ValueError(f"output directory must be new or empty: {output}")
    if not args.audit_existing:
        packet = {
            "owner_authorized": True, "grade": 10, "subject": "Physical Sciences",
            "customer_packet_dir": str(SOURCE_PACKET),
            "temperature": 0.0, "controlled_synthetic_demo": True,
        }
        from products.customer_product_router import run_customer_product
        run_customer_product("HOMS Assess", packet, output, render_pdf=False)

    current = analyze_run(output)
    baseline = analyze_run(BASELINE)
    package = json.loads((output / "CUSTOMER_PACKAGE_RECEIPT.json").read_text(encoding="utf-8"))
    evidence = {
        "schema": "dio.homs.assess.granite_model_comparison.v1",
        "product": "HOMS Assess",
        "run": output.relative_to(ROOT).as_posix(),
        "controlled_synthetic_demo": True,
        "source_packet_fingerprint": current["source_packet_fingerprint"],
        "current_run": current,
        "baseline_run": {"path": BASELINE.relative_to(ROOT).as_posix(), **baseline},
        "same_source_packet": current["source_packet_fingerprint"] == baseline["source_packet_fingerprint"],
        "classroom_release_authorized": package.get("classroom_release_authorized"),
        "marks_are_final": package.get("marks_are_final"),
        "external_processing": False,
        "package_sha256": current["package_sha256"],
        "results_sha256": current["results_sha256"],
        "interpretation": "This comparison measures response completeness and exact-quote presence on a controlled synthetic packet. It is not evidence of scoring accuracy or educator acceptance.",
        "baseline_package_sha256": baseline["package_sha256"],
        "baseline_results_sha256": baseline["results_sha256"],
        "all_totals_withheld": current["all_totals_blank"] is True,
    }
    evidence_path = output / "GRANITE33_CURRENT_ROUTE_COMPARISON_EVIDENCE.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"current": current, "baseline": baseline, "same_source_packet": evidence["same_source_packet"],
                      "all_totals_withheld": evidence["all_totals_withheld"],
                      "classroom_release_authorized": evidence["classroom_release_authorized"],
                      "interpretation": evidence["interpretation"]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
