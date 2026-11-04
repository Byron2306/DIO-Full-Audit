#!/usr/bin/env python3
"""Compare a bounded Qwen3 non-thinking HOMS Assess run on the synthetic Grade 10 packet."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SOURCE_PACKET = ROOT / "acceptance_runs/68-product-sellability-20261027/homs-assess-unit-feedback-gate-20261102/homs-assess/CUSTOMER_PACKET"
OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_ASSESS_CUSTOMER_PACKET_EXECUTION_20261102_G10_V35_QWEN3_NOTHINK"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if not SOURCE_PACKET.is_dir():
        raise FileNotFoundError(f"controlled synthetic packet not found: {SOURCE_PACKET}")
    if OUT.exists() and any(OUT.iterdir()):
        raise ValueError(f"output directory must be new or empty: {OUT}")
    os.environ["HOMS_AI_NO_THINK"] = "1"
    from products.customer_product_router import run_customer_product

    run_customer_product("HOMS Assess", {
        "owner_authorized": True, "grade": 10, "subject": "Physical Sciences",
        "customer_packet_dir": str(SOURCE_PACKET), "model": "qwen3:4b",
        "temperature": 0.0, "controlled_synthetic_demo": True,
    }, OUT, render_pdf=False)
    package_path = OUT / "CUSTOMER_PACKAGE_RECEIPT.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    results_path = OUT / package["outputs"]["results"]
    results = json.loads(results_path.read_text(encoding="utf-8"))
    rubric = json.loads((OUT / "input/rubric.json").read_text(encoding="utf-8"))
    expected = {
        (str(c.get("question") or str(c.get("name") or "").split(":", 1)[0]), str(p.get("point_id") or ""))
        for c in rubric.get("criteria") or [] for p in c.get("marking_points") or []
    }
    learners = []
    for result in results:
        returned, positive, exact_positive = set(), 0, 0
        learner_file = OUT / "input/uploads" / f"{result.get('student_id')}.txt"
        answer = " ".join(learner_file.read_text(encoding="utf-8").split()) if learner_file.is_file() else ""
        for criterion_key, criterion in (result.get("criteria_scores") or {}).items():
            criterion_id = str(criterion_key).split(":", 1)[0].strip()
            for point in criterion.get("point_scores") or []:
                point_id = str(point.get("point_id") or "")
                key = (criterion_id, point_id)
                if key not in expected:
                    continue
                returned.add(key)
                if point.get("score") is not None and float(point.get("score") or 0) > 0:
                    positive += 1
                    quotes = point.get("quotes") or []
                    if isinstance(quotes, str):
                        quotes = [quotes]
                    if any(isinstance(q, str) and " ".join(q.split()) in answer for q in quotes):
                        exact_positive += 1
        flags = result.get("unresolved_marking_quality_flags") or []
        learners.append({
            "student_id": result.get("student_id"), "expected_point_count": len(expected),
            "returned_point_count": len(returned), "unreturned_point_count": len(expected - returned),
            "positive_point_proposals": positive, "positive_proposals_with_exact_source_quote": exact_positive,
            "positive_proposals_without_exact_source_quote": positive - exact_positive,
            "quality_flag_count": len(flags), "quality_flag_codes": sorted({str(f.get("code") or "") for f in flags}),
            "score_status": result.get("score_status"), "total_score": result.get("total_score"),
        })
    evidence = {
        "schema": "dio.homs.assess.qwen3_nothink_probe.v1", "product": "HOMS Assess",
        "run": OUT.relative_to(ROOT).as_posix(), "source_packet_fingerprint": package.get("customer_packet_fingerprint"),
        "source_packet_manifest_sha256": package.get("source_packet_manifest_sha256"),
        "scoring_configuration": package.get("scoring_configuration"), "learners": learners,
        "all_totals_withheld": all(row.get("total_score") is None for row in results),
        "educator_review_required": package.get("educator_review_required"),
        "classroom_release_authorized": package.get("classroom_release_authorized"),
        "external_processing": False, "synthetic_acceptance_input": True,
        "artifacts": {str(path.relative_to(OUT)): sha(path) for path in (package_path, results_path)},
        "interpretation": "A prompt-mode and response-shape probe only. Point coverage and exact quotes do not establish mark accuracy; all proposals remain subject to educator review.",
    }
    if (evidence["scoring_configuration"] or {}).get("reasoning_mode") != "QWEN3_NON_THINKING_PROMPT_SWITCH":
        raise ValueError("run did not record the requested Qwen3 non-thinking prompt mode")
    if not evidence["all_totals_withheld"] or evidence["classroom_release_authorized"] is not False:
        raise ValueError("probe violated HOMS Assess's held-score boundary")
    evidence_path = OUT / "QWEN3_NOTHINK_PROBE_EVIDENCE.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"evidence": evidence_path.relative_to(ROOT).as_posix(), "learners": learners,
                      "all_totals_withheld": evidence["all_totals_withheld"],
                      "classroom_release_authorized": False}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
