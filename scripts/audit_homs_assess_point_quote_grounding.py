#!/usr/bin/env python3
"""Re-evaluate stored HOMS Assess proposals for exact question-scoped point quotes."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
JOB = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_ASSESS_CUSTOMER_PACKET_EXECUTION_20261103_G10_V23"
OUT = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_ASSESS_POINT_QUOTE_GROUNDING_AUDIT_20261102.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    from scripts.run_homs_hymark_batch import point_quote_grounding_flags

    package = json.loads((JOB / "CUSTOMER_PACKAGE_RECEIPT.json").read_text(encoding="utf-8"))
    results_path = JOB / package["outputs"]["results"]
    results = json.loads(results_path.read_text(encoding="utf-8"))
    rubric_path = JOB / "input/rubric.json"
    rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
    submissions = {p.stem: p for p in (JOB / "input/uploads").glob("learner_*.txt")}
    flags = []
    positive_point_count = 0
    for row in results:
        source = submissions.get(str(row.get("student_id") or ""))
        if source is None:
            raise ValueError("stored HOMS Assess result has no matching source submission")
        positive_point_count += sum(
            1 for criterion in (row.get("criteria_scores") or {}).values()
            for point in criterion.get("point_scores") or []
            if point.get("score") is not None and float(point.get("score") or 0) > 0
        )
        for flag in point_quote_grounding_flags(row, rubric, source.read_text(encoding="utf-8")):
            flags.append({"student_id": row["student_id"], **flag})
    if not positive_point_count or len(flags) != positive_point_count:
        raise ValueError("stored route did not reproduce a point-specific citation gap for every positive proposal")
    if any(row.get("total_score") is not None or row.get("score_issued") is True for row in results):
        raise ValueError("stored route unexpectedly contains an issued score; preserve review boundary before auditing")
    evidence = {
        "schema": "dio.homs.assess.point_quote_grounding_audit.v1",
        "product": "HOMS Assess",
        "source_execution": JOB.relative_to(ROOT).as_posix(),
        "source_customer_package_sha256": sha(JOB / "CUSTOMER_PACKAGE_RECEIPT.json"),
        "source_results_sha256": sha(results_path),
        "source_rubric_sha256": sha(rubric_path),
        "submission_sha256": {key: sha(path) for key, path in sorted(submissions.items())},
        "learner_count": len(results),
        "positive_point_proposal_count": positive_point_count,
        "positive_point_proposal_without_question_scoped_quote_count": len(flags),
        "flagged_points": flags,
        "prior_route_scores_issued": False,
        "score_mutation_performed": False,
        "evaluation_scope": "Retrospective deterministic audit of stored synthetic proposals. No provider rerun, score inference, mark change, educator decision, or classroom release.",
        "claim_boundary": "An exact question-scoped quote is a traceability aid, not proof that a proposed mark is correct. Educators must judge the answer against the source memo.",
    }
    OUT.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": OUT.relative_to(ROOT).as_posix(), "positive_proposals": positive_point_count,
                      "missing_question_scoped_quotes": len(flags), "scores_issued": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
