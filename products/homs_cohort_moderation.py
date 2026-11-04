"""Aggregate-only HOMS cohort item analysis for educator moderation."""
from __future__ import annotations

import math
import re
from statistics import mean, median, stdev
from typing import Any, Mapping


def analyze_cohort_scores(*, assessment: Mapping[str, Any], cohort: Mapping[str, Any], source_sha256: str, assessment_sha256: str) -> dict[str, Any]:
    """Validate a pseudonymous mark matrix and return descriptive statistics only."""
    if cohort.get("identifier_policy") != "pseudonymous_candidate_ids_only":
        raise ValueError("cohort score source must declare pseudonymous_candidate_ids_only")
    if cohort.get("source_kind") not in {"synthetic_fixture", "customer_supplied"}:
        raise ValueError("cohort score source must declare synthetic_fixture or customer_supplied")
    if not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
        raise ValueError("cohort score source hash is required")
    if cohort.get("assessment_sha256") != assessment_sha256:
        raise ValueError("cohort score source must identify the exact assessment SHA-256")
    questions = [q for section in assessment.get("sections") or [] for q in section.get("questions") or []]
    maxima = {str(q.get("number") or ""): int(q.get("marks") or 0) for q in questions}
    if not maxima or "" in maxima or len(maxima) != len(questions) or any(value <= 0 for value in maxima.values()):
        raise ValueError("assessment must have unique question numbers and positive maximum marks")

    records = cohort.get("records")
    if not isinstance(records, list) or len(records) < 2:
        raise ValueError("at least two cohort mark records are required for descriptive analysis")
    candidate_ids: set[str] = set()
    normalized: list[dict[str, float]] = []
    for index, record in enumerate(records, 1):
        if not isinstance(record, Mapping) or set(record) != {"candidate_id", "scores"}:
            raise ValueError(f"record {index} must contain only candidate_id and scores")
        candidate_id = str(record.get("candidate_id") or "")
        if (not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", candidate_id)
                or "@" in candidate_id or candidate_id in candidate_ids):
            raise ValueError(f"record {index} needs a unique opaque pseudonymous candidate_id")
        candidate_ids.add(candidate_id)
        scores = record.get("scores")
        if not isinstance(scores, Mapping) or set(scores) != set(maxima):
            raise ValueError(f"record {index} must contain one score for every assessment question")
        row: dict[str, float] = {}
        for question_id, maximum in maxima.items():
            value = scores[question_id]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"record {index} question {question_id} score must be a finite number")
            if value < 0 or value > maximum:
                raise ValueError(f"record {index} question {question_id} score is outside 0..{maximum}")
            row[question_id] = float(value)
        normalized.append(row)

    total_max = sum(maxima.values())
    totals = [sum(row.values()) for row in normalized]
    count = len(normalized)

    def correlation(left: list[float], right: list[float]) -> float | None:
        left_mean, right_mean = mean(left), mean(right)
        left_delta = [value - left_mean for value in left]
        right_delta = [value - right_mean for value in right]
        denominator = math.sqrt(sum(value * value for value in left_delta) * sum(value * value for value in right_delta))
        if denominator == 0:
            return None
        return round(sum(a * b for a, b in zip(left_delta, right_delta)) / denominator, 4)

    items = []
    for question_id, maximum in maxima.items():
        scores = [row[question_id] for row in normalized]
        rest_scores = [total - item for total, item in zip(totals, scores)]
        facility = sum(scores) / (count * maximum)
        item_rest = correlation(scores, rest_scores) if count >= 5 else None
        flags = []
        if item_rest is not None and item_rest < 0:
            flags.append("negative_item_to_rest_correlation_review")
        if item_rest is None and count >= 5:
            flags.append("item_to_rest_correlation_undefined_zero_variance")
        items.append({
            "question_id": question_id,
            "maximum_marks": maximum,
            "mean_score": round(mean(scores), 3),
            "facility_proportion": round(facility, 4),
            "item_to_rest_correlation": item_rest,
            "correlation_state": "DESCRIPTIVE_ONLY" if item_rest is not None else ("UNDEFINED" if count >= 5 else "NOT_COMPUTED_MINIMUM_FIVE_REQUIRED"),
            "review_flags": flags,
        })

    return {
        "schema": "dio.homs.cohort_item_analysis.v1",
        "cohort_id": str(cohort.get("cohort_id") or "").strip() or "UNNAMED_COHORT",
        "source_sha256": source_sha256,
        "assessment_sha256": assessment_sha256,
        "source_kind": cohort["source_kind"],
        "assessment_grade": int(assessment.get("grade") or 0),
        "assessment_subject": str(assessment.get("subject") or ""),
        "learner_level_scores_in_analysis_output": False,
        "source_payload_retained_in_held_case": True,
        "record_count": count,
        "assessment_question_count": len(maxima),
        "score_range": {"minimum_possible": 0, "maximum_possible": total_max},
        "cohort_distribution": {
            "mean": round(mean(totals), 3),
            "median": round(median(totals), 3),
            "sample_standard_deviation": round(stdev(totals), 3) if count >= 2 else None,
            "minimum_observed": round(min(totals), 3),
            "maximum_observed": round(max(totals), 3),
        },
        "item_analysis": items,
        "interpretation_boundary": "The analysis output contains aggregate statistics only; the source payload remains in the held case for provenance. No pass threshold, learner ranking, diagnosis, grading decision, curriculum adequacy or moderation approval is inferred. A qualified educator must interpret the results with the assessment, cohort context and marking policy.",
        "human_review": "REQUIRED",
        "moderation_decision": "NOT_ISSUED",
        "release_authorized": False,
    }


def render_cohort_analysis_blocks(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    distribution = report["cohort_distribution"]
    items = report["item_analysis"]
    return [
        {"type": "heading", "level": 1, "text": "Cohort score and item analysis"},
        {"type": "paragraph", "text": f"{report['record_count']} pseudonymous candidate records; aggregate statistics only. Source SHA-256: {report['source_sha256']}"},
        {"type": "table", "headers": ["Measure", "Observed"], "rows": [
            ["Mean total", f"{distribution['mean']} / {report['score_range']['maximum_possible']}"],
            ["Median total", f"{distribution['median']} / {report['score_range']['maximum_possible']}"],
            ["Sample standard deviation", distribution["sample_standard_deviation"]],
            ["Observed range", f"{distribution['minimum_observed']}–{distribution['maximum_observed']}"],
        ]},
        {"type": "table", "headers": ["Question", "Maximum", "Mean", "Facility proportion", "Item-to-rest correlation", "Review flags"], "rows": [
            [row["question_id"], row["maximum_marks"], row["mean_score"], row["facility_proportion"], row["item_to_rest_correlation"] if row["item_to_rest_correlation"] is not None else row["correlation_state"], ", ".join(row["review_flags"]) or "None generated"]
            for row in items
        ]},
        {"type": "paragraph", "text": report["interpretation_boundary"]},
    ]
