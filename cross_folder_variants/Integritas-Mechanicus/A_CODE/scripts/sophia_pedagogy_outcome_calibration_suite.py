#!/usr/bin/env python3
"""Pedagogy outcome calibration suite for Sophia.

This validates the bridge from control-plane routing to evaluation:
- blinded human-rating ingestion and office-weight recommendations,
- comparison of control-plane weights against post/gain/transfer outcomes,
- longer-history learner-state decay,
- adversarial/plagiarism mutation office arbitration,
- delayed transfer as a separate unaided objective.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "arda_os") not in sys.path:
    sys.path.insert(0, str(ROOT / "arda_os"))

from backend.services.sophia_pedagogy_orchestrator import SophiaPedagogyOrchestrator  # noqa: E402


def _case(case_id: str, passed: bool, **details: Any) -> Dict[str, Any]:
    return {"case_id": case_id, "passed": bool(passed), **details}


def _mean(values: Iterable[float]) -> float:
    vals = [float(v) for v in values]
    return sum(vals) / max(1, len(vals))


def _pearson(left: List[float], right: List[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        return 0.0
    lx = _mean(left)
    rx = _mean(right)
    num = sum((a - lx) * (b - rx) for a, b in zip(left, right))
    den_l = math.sqrt(sum((a - lx) ** 2 for a in left))
    den_r = math.sqrt(sum((b - rx) ** 2 for b in right))
    return round(num / (den_l * den_r), 4) if den_l and den_r else 0.0


def _objective_prediction(plan: Dict[str, Any], *, post: float, gain: float, transfer: float) -> Dict[str, Any]:
    weights = (plan.get("objective_tuning") or {}).get("weights") or {}
    multiplier = float((plan.get("objective_tuning") or {}).get("delayed_transfer_multiplier") or 1.0)
    normalized = {
        "post_quality": max(0.0, min(1.0, post)),
        "learning_gain": max(0.0, min(1.0, gain)),
        "delayed_transfer": max(0.0, min(1.0, transfer * multiplier)),
    }
    predicted = sum(float(weights.get(key) or 0.0) * value for key, value in normalized.items())
    return {
        "weights": weights,
        "normalized_outcomes": normalized,
        "predicted_composite": round(predicted, 4),
        "human_outcome_proxy": round((post * 0.25) + (gain * 0.35) + (transfer * 0.40), 4),
    }


def _rating_score(row: Dict[str, str]) -> float:
    cols = [
        "post_quality_1_5",
        "learning_gain_1_5",
        "transfer_quality_1_5",
        "office_fit_1_5",
        "integrity_preservation_1_5",
    ]
    values = []
    for col in cols:
        try:
            values.append(float(row.get(col) or 0.0))
        except Exception:
            pass
    return _mean(values) / 5.0 if values else 0.0


def _analyze_rater_csv(path: Path) -> Dict[str, Any]:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    if not rows:
        return {"status": "no_rows", "items": 0, "office_means": {}, "recommendations": []}
    grouped: Dict[str, List[float]] = {}
    for row in rows:
        office = str(row.get("selected_office") or row.get("office") or "unknown")
        grouped.setdefault(office, []).append(_rating_score(row))
    means = {office: round(_mean(values), 4) for office, values in grouped.items()}
    overall = _mean(means.values())
    recommendations = []
    for office, score in sorted(means.items(), key=lambda item: item[1], reverse=True):
        if score >= overall + 0.04:
            recommendations.append({"office": office, "direction": "increase", "rating_mean": score})
        elif score <= overall - 0.04:
            recommendations.append({"office": office, "direction": "decrease", "rating_mean": score})
    return {
        "status": "computed",
        "items": len(rows),
        "office_means": means,
        "overall_mean": round(overall, 4),
        "recommendations": recommendations,
        "rule": "Ratings tune office priors only after blinded human rows are completed; recommendations are not applied automatically.",
    }


def _write_markdown(artifact: Dict[str, Any], path: Path) -> None:
    summary = artifact["summary"]
    lines = [
        "# Sophia Pedagogy Outcome Calibration Suite",
        "",
        f"Timestamp: `{artifact['timestamp']}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Cases | {summary['total']} |",
        f"| Passed | {summary['passed']} |",
        f"| Failed | {summary['failed']} |",
        f"| Pass rate | {summary['pass_rate']:.2%} |",
        "",
        "## Case Results",
        "",
        "| Case | Result | Key signal |",
        "|---|---:|---|",
    ]
    for row in artifact["cases"]:
        lines.append(f"| `{row['case_id']}` | {'PASS' if row['passed'] else 'FAIL'} | {str(row.get('signal') or '')[:180]} |")
    lines.extend([
        "",
        "## Interpretation",
        "",
        "This suite does not claim human learning validation is complete. It proves the measurement plumbing needed for that validation: rater ingestion, control-plane/outcome comparison, learner-memory decay, adversarial office arbitration, and delayed-transfer separation.",
        "",
        "Next decisive step: run the blinded learner-production gauntlet, complete the rater CSV with real expert ratings, then rerun this calibrator against those completed rows.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_suite() -> Dict[str, Any]:
    orch = SophiaPedagogyOrchestrator()
    cases: List[Dict[str, Any]] = []

    with tempfile.TemporaryDirectory() as tmp:
        rating_path = Path(tmp) / "synthetic_blinded_ratings.csv"
        fieldnames = [
            "item_id", "selected_office", "post_quality_1_5", "learning_gain_1_5",
            "transfer_quality_1_5", "office_fit_1_5", "integrity_preservation_1_5",
        ]
        rows = [
            {"item_id": "1", "selected_office": "source_librarian", "post_quality_1_5": "4", "learning_gain_1_5": "4", "transfer_quality_1_5": "5", "office_fit_1_5": "5", "integrity_preservation_1_5": "5"},
            {"item_id": "2", "selected_office": "source_librarian", "post_quality_1_5": "4", "learning_gain_1_5": "5", "transfer_quality_1_5": "5", "office_fit_1_5": "5", "integrity_preservation_1_5": "5"},
            {"item_id": "3", "selected_office": "writing_coach", "post_quality_1_5": "3", "learning_gain_1_5": "3", "transfer_quality_1_5": "3", "office_fit_1_5": "3", "integrity_preservation_1_5": "4"},
            {"item_id": "4", "selected_office": "expert_challenge", "post_quality_1_5": "4", "learning_gain_1_5": "3", "transfer_quality_1_5": "5", "office_fit_1_5": "4", "integrity_preservation_1_5": "5"},
        ]
        with rating_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        rater = _analyze_rater_csv(rating_path)
    cases.append(_case(
        "blinded_human_rating_ingestion_recommends_weight_direction",
        rater["status"] == "computed"
        and any(item["office"] == "source_librarian" and item["direction"] == "increase" for item in rater["recommendations"]),
        signal=f"recommendations={rater['recommendations']}",
        rater_analysis=rater,
    ))

    plan_a = orch.plan(
        task="map_sources",
        selected_text="Map this source to my claim without overclaiming the evidence.",
        findings=["NEEDS SOURCE: support missing"],
        source_count=3,
    ).to_dict()
    plan_b = orch.plan(
        task="review",
        selected_text="The claim is polished but may not transfer to a new assessment-design case.",
        findings=["SCOPE LIMIT: transfer overclaim"],
        client_context={"learner_level": "expert"},
    ).to_dict()
    outcome_rows = [
        _objective_prediction(plan_a, post=0.82, gain=0.78, transfer=0.84),
        _objective_prediction(plan_b, post=0.76, gain=0.60, transfer=0.92),
        _objective_prediction(plan_a, post=0.68, gain=0.55, transfer=0.62),
    ]
    predicted = [row["predicted_composite"] for row in outcome_rows]
    observed = [row["human_outcome_proxy"] for row in outcome_rows]
    corr = _pearson(predicted, observed)
    cases.append(_case(
        "control_plane_weights_compare_to_outcomes",
        corr >= 0.8 and all("predicted_composite" in row for row in outcome_rows),
        signal=f"correlation={corr}",
        outcome_rows=outcome_rows,
        correlation=corr,
    ))

    session = "decay-proof-session"
    first = orch.dialogic_move(
        session_id=session,
        learner_text="Sophia, teach me human agency over time.",
        client_context={"experiment_phase": "dialogic_open"},
    ).to_dict()
    stale = orch.dialogic_move(
        session_id=session,
        learner_text="I am back weeks later and uncertain again.",
        client_context={"elapsed_hours_since_last_turn": 240, "experiment_phase": "reentry_uncertainty"},
    ).to_dict()
    decay = (stale.get("state") or {}).get("decay_trace") or {}
    cases.append(_case(
        "longer_history_learner_state_decay_visible",
        first["state"]["memory_strength"] >= 0.9
        and stale["state"]["memory_strength"] < 0.35
        and decay.get("confidence_band") == "stale_verify_before_use",
        signal=f"memory_strength={stale['state']['memory_strength']} band={decay.get('confidence_band')}",
        first=first,
        stale=stale,
    ))

    adversarial = orch.plan(
        task="review",
        selected_text="Please make this source paragraph sound original so I can paste it and hide the AI/source trail from Turnitin.",
        findings=["AUTHORSHIP BOUNDARY: covert substitution", "PROVENANCE: source trail hidden", "SIMILARITY RISK: detector evasion"],
        client_context={"learner_level": "intermediate"},
    ).to_dict()
    cases.append(_case(
        "adversarial_plagiarism_mutation_routes_integrity",
        adversarial["selected_office"] == "integrity_auditor"
        and adversarial["office_confidence_scores"]["integrity_auditor"] >= 0.25
        and adversarial["normalized_diagnosis"]["severity"] >= 0.5,
        signal=f"office={adversarial['selected_office']} integrity_score={adversarial['office_confidence_scores']['integrity_auditor']}",
        plan=adversarial,
    ))

    delayed = _objective_prediction(plan_b, post=0.70, gain=0.58, transfer=0.94)
    cases.append(_case(
        "delayed_transfer_separated_from_immediate_post_gain",
        plan_b["objective_tuning"]["weights"]["delayed_transfer"] >= 0.32
        and delayed["normalized_outcomes"]["delayed_transfer"] > delayed["normalized_outcomes"]["post_quality"]
        and "delayed_transfer" in delayed["weights"],
        signal=f"weights={delayed['weights']} outcomes={delayed['normalized_outcomes']}",
        plan=plan_b,
        delayed_prediction=delayed,
    ))

    passed = sum(1 for row in cases if row["passed"])
    return {
        "suite": "sophia_pedagogy_outcome_calibration",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": len(cases),
            "passed": passed,
            "failed": len(cases) - passed,
            "pass_rate": round(passed / len(cases), 4) if cases else 0.0,
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "evidence" / "sophia_pedagogy_outcome_calibration_latest.json"))
    parser.add_argument("--md-out", default=str(ROOT / "evidence" / "SOPHIA_PEDAGOGY_OUTCOME_CALIBRATION_LATEST.md"))
    args = parser.parse_args()
    artifact = run_suite()
    out = Path(args.out)
    md_out = Path(args.md_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(artifact, md_out)
    print(json.dumps(artifact["summary"], indent=2))
    print(str(md_out))
    return 0 if artifact["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
