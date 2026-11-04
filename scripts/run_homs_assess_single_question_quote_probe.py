#!/usr/bin/env python3
"""Run one synthetic HOMS Assess question through HyMark's point-quote contract."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_homs_hymark_batch import (  # noqa: E402
    DEFAULT_HYMARK_BACKEND,
    DEFAULT_SECRET_FILE,
    configure_provider,
    load_hymark_backend,
    assessment_response_is_complete,
    merge_pointwise_repair,
    normalize_assessment,
    point_quote_grounding_flags,
    pointwise_repair_rubric,
    question_answer_block,
    retain_exact_source_quotes,
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="granite3.3:2b")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source_root = ROOT / "acceptance_runs/68-product-sellability-20261027/HOMS_ASSESS_POINT_QUOTE_REPAIR_20261102_V1/customer-route/input"
    rubric_path = source_root / "rubric.json"
    learner_path = source_root / "uploads/learner_A.txt"
    full_source_text = learner_path.read_text(encoding="utf-8")
    source_text = question_answer_block(full_source_text, "1.1") or full_source_text
    rubric_doc = json.loads(rubric_path.read_text(encoding="utf-8"))
    criterion = next(row for row in rubric_doc["criteria"] if str(row.get("question")) == "1.1")
    rubric = {**rubric_doc, "criteria": [criterion], "total_marks": sum(float(row.get("marks") or 0) for row in criterion["marking_points"])}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists():
        raise ValueError(f"output path already exists: {args.out}")

    os.environ["HOMS_AI_TIMEOUT_SECONDS"] = "180"
    os.environ["HOMS_AI_MAX_TOKENS"] = "1400"
    os.environ["HOMS_AI_TEMPERATURE"] = "0.0"
    provider = configure_provider(DEFAULT_SECRET_FILE, "ollama", args.model)
    backend = load_hymark_backend(DEFAULT_HYMARK_BACKEND)
    instructions = (
        "This is one controlled synthetic answer. Return every listed memo point ID. "
        "Each positive point must include a concise exact quote copied from the answer to question 1.1; "
        "zero points use an empty quotes list. Do not infer or invent a quote."
    )
    raw = asyncio.run(backend.assess_with_ai(source_text, rubric, instructions))
    retain_exact_source_quotes(raw, rubric, source_text)
    initial_complete = assessment_response_is_complete(raw, rubric, submission_text=source_text)
    initial_normalized = normalize_assessment(dict(raw), rubric)
    initial_points = initial_normalized["criteria_scores"][str(criterion["name"])]["point_scores"]
    initial_grounded_ids = {row["point_id"] for row in initial_points if row.get("score", 0) and row.get("quotes")}
    repair_rubric, missing_points = pointwise_repair_rubric(raw, rubric, submission_text=source_text)
    repair_attempted = bool(missing_points)
    repair_complete = False
    if repair_attempted:
        criterion_name, repair_points = next(iter(missing_points.items()))
        repair_instructions = (
            f"Bounded question 1.1 repair for criterion {criterion_name}: return each listed memo point ID exactly once. "
            "Reassess points with missing quotes and supply one concise verbatim learner span from answer 1.1 for every positive score. "
            "Use an empty quotes list for zero; use null if the answer cannot be judged. Do not invent, paraphrase, or cite a memo label."
        )
        repair_raw = asyncio.run(backend.assess_with_ai(source_text, repair_rubric, repair_instructions))
        retain_exact_source_quotes(repair_raw, repair_rubric, source_text)
        repair_complete = assessment_response_is_complete(repair_raw, repair_rubric, submission_text=source_text)
        raw = merge_pointwise_repair(
            raw, repair_raw, missing_points, rubric=repair_rubric, submission_text=source_text,
        )
        retain_exact_source_quotes(raw, rubric, source_text)
    normalized = normalize_assessment(dict(raw), rubric)
    complete = backend_assessment_complete(raw, rubric, source_text)
    flags = point_quote_grounding_flags(normalized, rubric, source_text)
    point_rows = normalized["criteria_scores"][str(criterion["name"])]["point_scores"]
    positive = [row for row in point_rows if row.get("score") is not None and float(row.get("score") or 0) > 0]
    grounded_positive = [row for row in positive if row.get("quotes")]
    repaired_grounded_ids = {row["point_id"] for row in grounded_positive} - initial_grounded_ids
    output = {
        "schema": "dio.homs.assess.single_question_point_quote_probe.v1",
        "product": "HOMS Assess",
        "synthetic_acceptance_input": True,
        "grade": int(rubric_doc.get("grade") or 10),
        "subject": rubric_doc.get("subject"),
        "question_id": str(criterion.get("question") or "1.1"),
        "model": provider["selected_model"],
        "provider": provider["selected_provider"],
        "source_answer_sha256": sha(learner_path.read_bytes()),
        "question_answer_block_sha256": sha(source_text.encode("utf-8")),
        "model_received_only_question_answer_block": True,
        "source_rubric_sha256": sha(rubric_path.read_bytes()),
        "prompt_contract_requests_per_point_quote": True,
        "strict_schema_requires_point_score_and_quotes": True,
        "initial_response_complete": initial_complete,
        "bounded_repair_attempted": repair_attempted,
        "bounded_repair_point_count": sum(len(points) for points in missing_points.values()),
        "bounded_repair_response_complete": repair_complete,
        "newly_grounded_positive_points_after_repair": len(repaired_grounded_ids),
        "returned_point_count": len(point_rows),
        "expected_point_count": len(criterion.get("marking_points") or []),
        "positive_point_count": len(positive),
        "positive_points_with_exact_question_quote": len(grounded_positive),
        "unresolved_point_quote_flags": flags,
        "response_complete_under_customer_gate": complete,
        "normalized_proposals": normalized["criteria_scores"],
        "marks_issued": False,
        "classroom_release_authorized": False,
        "educator_review_required": True,
    }
    args.out.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: output[key] for key in (
        "model", "question_id", "returned_point_count", "expected_point_count",
        "positive_point_count", "positive_points_with_exact_question_quote",
        "response_complete_under_customer_gate", "marks_issued",
    )}, indent=2))
    return 0


def backend_assessment_complete(raw: dict, rubric: dict, source_text: str) -> bool:
    """Apply the production customer gate to the single-question response."""
    from scripts.run_homs_hymark_batch import assessment_response_is_complete

    return assessment_response_is_complete(raw, rubric, submission_text=source_text)


if __name__ == "__main__":
    raise SystemExit(main())
