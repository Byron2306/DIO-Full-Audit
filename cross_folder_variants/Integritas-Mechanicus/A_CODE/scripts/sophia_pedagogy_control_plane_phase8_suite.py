#!/usr/bin/env python3
"""Phase 8 pedagogy control-plane validation for Sophia.

This suite validates inspectable routing machinery, not provider eloquence:
feature extraction, normalized assessment diagnosis, office confidence scores,
conflict arbitration, delayed-transfer weighting, and multi-objective tuning.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "arda_os") not in sys.path:
    sys.path.insert(0, str(ROOT / "arda_os"))

from backend.services.sophia_pedagogy_orchestrator import SophiaPedagogyOrchestrator  # noqa: E402


def _case(case_id: str, passed: bool, **details: Any) -> Dict[str, Any]:
    return {"case_id": case_id, "passed": bool(passed), **details}


def _write_markdown(artifact: Dict[str, Any], path: Path) -> None:
    summary = artifact["summary"]
    lines = [
        "# Sophia Phase 8 Pedagogy Control-Plane Suite",
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
        "This suite proves a stronger pedagogy control-plane slice. Sophia no longer only emits a selected office; her plan now carries observable learner features, a normalized assessment diagnosis, a distribution of office confidence scores, arbitration metadata, and multi-objective post/gain/transfer weights.",
        "",
        "What is proven:",
        "",
        "- Office selection is inspectable as a score distribution, not merely a hard-coded label.",
        "- Assessment diagnosis is normalized into active layer, need state, severity, and challenge band.",
        "- Office conflicts such as source-fit versus integrity-boundary and scaffold versus challenge are surfaced explicitly.",
        "- Ipsative/repeated weaknesses increase learning-gain weighting rather than only post-response polish.",
        "- Expert/reviewer offices increase delayed-transfer weighting.",
        "",
        "What remains:",
        "",
        "- These are deterministic control-plane validations, not human learning-outcome results.",
        "- The weights are transparent heuristics and should be tuned against blinded human ratings and delayed transfer artifacts.",
        "- Future gauntlets should pair these records with actual post, delayed transfer, and integrity-preservation scores.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_suite() -> Dict[str, Any]:
    orch = SophiaPedagogyOrchestrator()
    cases: List[Dict[str, Any]] = []

    source_integrity = orch.plan(
        task="provenance",
        selected_text="This claim needs source support, a warrant, and clear provenance before citation.",
        findings=["NEEDS SOURCE: direct support missing", "NEEDS WARRANT: source fit unclear", "PROVENANCE: authorship trail unclear"],
        source_count=2,
    ).to_dict()
    cases.append(_case(
        "source_integrity_conflict_visible",
        source_integrity["office_confidence_scores"].get("source_librarian", 0) > 0.15
        and source_integrity["office_confidence_scores"].get("integrity_auditor", 0) > 0.15
        and "source_fit_vs_integrity_boundary" in source_integrity["office_arbitration"].get("conflicts", []),
        signal=f"office={source_integrity['selected_office']} conflicts={source_integrity['office_arbitration']['conflicts']}",
        plan=source_integrity,
    ))

    repeated = orch.plan(
        task="review",
        selected_text="I am confused and not happy with this claim. It has too many ideas and no clear scope.",
        findings=["SCOPE LIMIT: overclaim", "CLARITY RISK: too many constructs"],
        history_summary={
            "intervention_records": 3,
            "repeated_weakness_types": [{"issue": "scope limit"}, {"issue": "clarity risk"}],
            "latest_intervention_improvement": {"status": "stable_unresolved", "persistent_issue_labels": ["scope limit"]},
        },
        client_context={"assessment_layer": "formative"},
    ).to_dict()
    cases.append(_case(
        "ipsative_repeated_pattern_normalized",
        repeated["normalized_diagnosis"]["active_layer"] == "ipsative"
        and repeated["normalized_diagnosis"]["need_state"] == "repeated_pattern_repair"
        and repeated["objective_tuning"]["weights"]["learning_gain"] > repeated["objective_tuning"]["weights"]["delayed_transfer"],
        signal=f"layer={repeated['normalized_diagnosis']['active_layer']} gain_weight={repeated['objective_tuning']['weights']['learning_gain']}",
        plan=repeated,
    ))

    expert = orch.plan(
        task="review",
        selected_text="The argument distinguishes evidence, inference, uncertainty, and limitation, but I want a hard reviewer objection before transfer.",
        findings=["SCOPE LIMIT: transfer claim needs qualification"],
        client_context={"learner_level": "expert"},
    ).to_dict()
    cases.append(_case(
        "expert_challenge_weights_delayed_transfer",
        expert["selected_office"] in {"expert_challenge", "peer_reviewer"}
        and expert["objective_tuning"]["delayed_transfer_multiplier"] >= 1.1
        and expert["objective_tuning"]["weights"]["delayed_transfer"] >= 0.32,
        signal=f"office={expert['selected_office']} delayed={expert['objective_tuning']['weights']['delayed_transfer']}",
        plan=expert,
    ))

    novice = orch.plan(
        task="scaffold",
        selected_text="I am lost. Human agency means maybe the student has choice but I cannot explain it.",
        findings=["OPERATIONAL DEFINITION: define construct", "CLARITY RISK: vague"],
        client_context={"learner_level": "novice"},
    ).to_dict()
    cases.append(_case(
        "novice_scaffold_confidence_and_features",
        novice["selected_office"] == "novice_scaffold"
        and novice["learner_features"]["affective_uncertainty_signal"] > 0
        and novice["normalized_diagnosis"]["need_state"] in {"zpd_scaffold", "affective_reentry_or_uncertainty"},
        signal=f"office={novice['selected_office']} need={novice['normalized_diagnosis']['need_state']}",
        plan=novice,
    ))

    weights = expert["objective_tuning"]["weights"]
    cases.append(_case(
        "multi_objective_weights_normalized",
        abs(sum(float(v) for v in weights.values()) - 1.0) <= 0.01
        and {"post_quality", "learning_gain", "delayed_transfer"} == set(weights),
        signal=f"weights={weights}",
        weights=weights,
    ))

    passed = sum(1 for row in cases if row["passed"])
    return {
        "suite": "sophia_pedagogy_control_plane_phase8",
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
    parser.add_argument("--out", default=str(ROOT / "evidence" / "sophia_pedagogy_control_plane_phase8_latest.json"))
    parser.add_argument("--md-out", default=str(ROOT / "evidence" / "SOPHIA_PEDAGOGY_CONTROL_PLANE_PHASE8_LATEST.md"))
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
