#!/usr/bin/env python3
"""Capture a bounded HOMS Assess residual-point recovery demonstration."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCE_RUN = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_ASSESS_CUSTOMER_PACKET_EXECUTION_20261103_G10_V26"
INPUT = ROOT / "acceptance_runs/68-product-sellability-20261027/homs-assess-unit-feedback-gate-20261102/homs-assess/CUSTOMER_PACKET"
OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_ASSESS_TAIL_RECOVERY_20261102_V1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if not INPUT.is_dir():
        raise FileNotFoundError(f"controlled synthetic source packet is missing: {INPUT}")
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f"output directory must be new or empty: {OUT}")
    from products.customer_product_router import run_customer_product

    run_customer_product("HOMS Assess", {
        "owner_authorized": True,
        "grade": 10,
        "subject": "Physical Sciences",
        "customer_packet_dir": str(INPUT),
        "model": "granite3.2:2b",
        "temperature": 0.0,
        "controlled_synthetic_demo": True,
    }, OUT, render_pdf=False)
    package_path = OUT / "CUSTOMER_PACKAGE_RECEIPT.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    results_path = OUT / package["outputs"]["results"]
    results = json.loads(results_path.read_text(encoding="utf-8"))
    summary = []
    for row in results:
        missing_ids = sorted({
            str(point_id)
            for criterion in (row.get("criteria_scores") or {}).values()
            for point_id in (criterion.get("unreturned_point_ids") or [])
        })
        blocked = row.get("total_score") is None or row.get("score_status") in {
            "BLOCKED_INCOMPLETE_POINTWISE_RESPONSE", "BLOCKED_MARKING_QUALITY_FLAGS",
            "BLOCKED_NONREPRODUCIBLE_SCORE",
        }
        if missing_ids and not blocked:
            raise ValueError(f"{row.get('student_id')}: an incomplete point set escaped score withholding")
        summary.append({
            "student_id": row.get("student_id"),
            "repair_attempt_count": row.get("pointwise_repair_attempt_count"),
            "repair_response_complete_count": row.get("pointwise_repair_response_complete_count"),
            "unreturned_point_ids": missing_ids,
            "unresolved_quality_flag_count": len(row.get("unresolved_marking_quality_flags") or []),
            "score_status": row.get("score_status"),
            "total_score": row.get("total_score"),
            "proposed_total_score": row.get("proposed_total_score"),
        })
    if any(row.get("total_score") is not None for row in results):
        raise ValueError("synthetic HOMS Assess demonstration issued a total score")
    evidence = {
        "schema": "dio.homs.assess.tail_recovery_execution.v1",
        "product": "HOMS Assess",
        "run": OUT.relative_to(ROOT).as_posix(),
        "source_synthetic_run": SOURCE_RUN.relative_to(ROOT).as_posix(),
        "source_packet_fingerprint": package.get("source_packet_manifest_sha256"),
        "source_input_hashes": {
            path.relative_to(INPUT).as_posix(): sha(path)
            for path in sorted(INPUT.rglob("*")) if path.is_file()
        },
        "output_artifact_hashes": {
            path.relative_to(OUT).as_posix(): sha(path)
            for path in sorted(OUT.rglob("*")) if path.is_file()
        },
        "learners": summary,
        "residual_repair_policy": "At most four residual memo points receive one bounded exact-ID recovery call per point after grouped repairs.",
        "source_quote_grounding_remains_required": True,
        "educator_review_required": True,
        "classroom_release_authorized": False,
        "authority_created": False,
        "external_effects": False,
        "all_total_scores_withheld": True,
        "synthetic_acceptance_input": True,
        "claim_boundary": "This demonstrates bounded point-completeness recovery only. It does not establish score correctness, repeatability, educator approval, or classroom suitability.",
    }
    evidence_path = OUT / "TAIL_RECOVERY_EXECUTION_EVIDENCE.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"evidence": evidence_path.relative_to(ROOT).as_posix(), "learners": summary,
                      "all_total_scores_withheld": True, "educator_review_required": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
