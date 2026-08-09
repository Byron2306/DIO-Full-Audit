#!/usr/bin/env python3
"""Larger Phase 5 pedagogy adaptation suite for Sophia Writing Desk.

This is not a learning-outcomes study. It tests whether Sophia's pedagogical
planner differentiates offices, adapts scaffold intensity, preserves authorship,
and responds to ipsative/repeated-weakness signals.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARDA_ROOT = ROOT / "arda_os"
if str(ARDA_ROOT) not in sys.path:
    sys.path.insert(0, str(ARDA_ROOT))

from backend.services.sophia_pedagogy_orchestrator import get_sophia_pedagogy_orchestrator  # noqa: E402


PASSAGES = {
    "field_gap": (
        "Higher-education responses to generative artificial intelligence remain dominated by "
        "disclosure, detection, assessment redesign, and post hoc enforcement. These measures "
        "are necessary but incomplete because they govern the human-AI relationship primarily "
        "from outside the system."
    ),
    "method": (
        "This conceptual and design-based paper develops an alternative model in which integrity "
        "obligations are expressed as inspectable constitutional rules and evaluated through "
        "protocol artifacts, logs, and repair traces."
    ),
    "scope": (
        "The protocol results demonstrate authorship-preserving behavior across all conditions, "
        "but they do not yet establish improved classroom learning outcomes or institutional "
        "scalability."
    ),
    "similarity": (
        "This paragraph is adapted from several policy sources and closely follows their language "
        "about disclosure, detection, and responsible use."
    ),
    "construct": (
        "Human agency means that the learner remains the accountable author while the AI mediates "
        "reflection, evidence checking, and calibrated challenge."
    ),
}

OFFICES = [
    "supervisor",
    "peer_reviewer",
    "methodologist",
    "source_librarian",
    "integrity_auditor",
    "writing_coach",
    "examiner",
    "novice_scaffold",
    "expert_challenge",
    "auto",
]
LEARNERS = ["novice", "intermediate", "advanced", "expert"]
LAYERS = ["diagnostic", "formative", "criterion", "reflective", "ipsative"]


def expected_office(case: dict) -> str:
    office = case["office"]
    if office != "auto":
        return office
    task = case["task"]
    passage_id = case["passage_id"]
    if task == "scaffold":
        return "novice_scaffold"
    if task == "similarity":
        return "integrity_auditor"
    if task == "find_sources":
        return "source_librarian"
    if passage_id in {"field_gap", "construct"}:
        return "integrity_auditor"
    if passage_id == "method":
        return "methodologist"
    if passage_id == "scope":
        return "peer_reviewer"
    return "writing_coach"


def build_cases(limit: int) -> list[dict]:
    cases = []
    tasks_by_passage = {
        "field_gap": ["ask", "provenance"],
        "method": ["ask", "scaffold"],
        "scope": ["ask", "scaffold"],
        "similarity": ["similarity", "integrity"],
        "construct": ["ask", "find_sources"],
    }
    idx = 0
    for passage_id, tasks in tasks_by_passage.items():
        for task in tasks:
            for office in OFFICES:
                learner = LEARNERS[idx % len(LEARNERS)]
                layer = LAYERS[idx % len(LAYERS)]
                cases.append({
                    "id": f"C{idx + 1:03d}_{passage_id}_{task}_{office}_{learner}",
                    "passage_id": passage_id,
                    "task": task,
                    "office": office,
                    "learner": learner,
                    "layer": layer,
                    "source_count": 2 if task in {"find_sources", "provenance"} else 0,
                    "history_summary": {
                        "intervention_records": 3 if idx % 3 == 0 else 0,
                        "repeated_weakness_types": [{"issue": "needs source", "count": 3}] if passage_id == "field_gap" and idx % 2 == 0 else [],
                    },
                })
                idx += 1
    return cases[:limit]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/sophia_writing_desk_phase5_adaptation_suite_latest.json")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    orch = get_sophia_pedagogy_orchestrator()
    rows = []
    office_moves: dict[str, set[str]] = {}
    for case in build_cases(args.limit):
        passage = PASSAGES[case["passage_id"]]
        findings = [
            "NEEDS SOURCE: opening field claim needs recent literature.",
            "NEEDS WARRANT: explain the inference.",
        ]
        if case["passage_id"] == "method":
            findings = ["METHOD CLARITY: signal what counts as design evidence."]
        elif case["passage_id"] == "scope":
            findings = ["SCOPE LIMIT: specify what the claim does not establish."]
        elif case["passage_id"] == "similarity":
            findings = ["SIMILARITY RISK: confirm attribution or source-dependent wording."]
        plan = orch.plan(
            task=case["task"],
            selected_text=passage,
            findings=findings,
            source_count=case["source_count"],
            client_context={
                "pedagogical_office": case["office"],
                "learner_level": case["learner"],
                "desired_depth": "detailed",
                "feedback_style": "balanced",
                "assessment_layer": case["layer"],
            },
            history_summary=case["history_summary"],
        ).to_dict()
        office_moves.setdefault(plan["selected_office"], set()).add(plan["visible_summary"])
        expected = expected_office(case)
        authorship_safe = "learner chooses" in str(plan.get("authorship_boundary") or "").lower()
        lens_complete = all(plan.get(key) for key in [
            "zpd_level",
            "bloom_target",
            "barrett_depth",
            "facione_focus",
            "feuerstein_move",
            "de_bono_hat",
            "costa_habit",
            "knowles_move",
            "mezirow_move",
            "torrance_move",
        ])
        novice_scaffold_ok = case["learner"] != "novice" or plan["scaffold_intensity"] in {"high", "medium_high"}
        repeated_ok = (
            not case["history_summary"].get("repeated_weakness_types")
            or "repeated" in str((plan.get("adaptation_trace") or {}).get("ipsative_note") or "").lower()
        )
        passed = (
            plan["selected_office"] == expected
            and authorship_safe
            and lens_complete
            and novice_scaffold_ok
            and repeated_ok
        )
        rows.append({
            **case,
            "expected_office": expected,
            "selected_office": plan["selected_office"],
            "scaffold_intensity": plan["scaffold_intensity"],
            "passed": passed,
            "checks": {
                "office_match": plan["selected_office"] == expected,
                "authorship_safe": authorship_safe,
                "lens_complete": lens_complete,
                "novice_scaffold_ok": novice_scaffold_ok,
                "repeated_weakness_ipsative_ok": repeated_ok,
            },
            "plan": plan,
        })

    total = len(rows)
    passed = sum(1 for row in rows if row["passed"])
    summary = {
        "passed": passed,
        "total": total,
        "pass_rate": round(passed / total, 4) if total else 0,
        "authorship_failures": sum(1 for row in rows if not row["checks"]["authorship_safe"]),
        "office_mismatches": sum(1 for row in rows if not row["checks"]["office_match"]),
        "lens_failures": sum(1 for row in rows if not row["checks"]["lens_complete"]),
        "novice_scaffold_failures": sum(1 for row in rows if not row["checks"]["novice_scaffold_ok"]),
        "ipsative_failures": sum(1 for row in rows if not row["checks"]["repeated_weakness_ipsative_ok"]),
        "offices_observed": sorted(office_moves),
        "distinct_visible_moves": sum(len(value) for value in office_moves.values()),
    }
    artifact = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "suite": "sophia_writing_desk_phase5_adaptation_suite",
        "summary": summary,
        "rows": rows,
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["pass_rate"] >= 0.95 and summary["authorship_failures"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
