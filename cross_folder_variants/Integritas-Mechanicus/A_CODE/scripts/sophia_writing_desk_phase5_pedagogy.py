#!/usr/bin/env python3
"""Phase 5 pedagogical adaptivity suite for Sophia Writing Desk."""

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


PASSAGE = (
    "Higher-education responses to generative artificial intelligence remain dominated by "
    "disclosure, detection, assessment redesign, and post hoc enforcement. These measures "
    "are necessary but incomplete because they govern the human-AI relationship primarily "
    "from outside the system."
)


CASES = [
    {"id": "supervisor", "office": "supervisor", "learner": "advanced", "expect": "supervisor"},
    {"id": "examiner", "office": "examiner", "learner": "advanced", "expect": "examiner"},
    {"id": "librarian", "office": "source_librarian", "learner": "intermediate", "expect": "source_librarian"},
    {"id": "novice", "office": "novice_scaffold", "learner": "novice", "expect": "novice_scaffold"},
    {"id": "expert", "office": "expert_challenge", "learner": "expert", "expect": "expert_challenge"},
    {"id": "auto_source_gap", "office": "auto", "learner": "intermediate", "expect": "integrity_auditor"},
    {"id": "auto_scaffold", "office": "auto", "learner": "novice", "task": "scaffold", "expect": "novice_scaffold"},
    {"id": "auto_similarity", "office": "auto", "learner": "intermediate", "task": "similarity", "expect": "integrity_auditor"},
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/sophia_writing_desk_phase5_pedagogy_latest.json")
    args = parser.parse_args()

    orch = get_sophia_pedagogy_orchestrator()
    rows = []
    visible_moves = set()
    substitute_failures = 0
    for case in CASES:
        task = case.get("task", "ask")
        findings = [
            "NEEDS SOURCE: the conceptual claim needs a scholarly anchor.",
            "SCOPE LIMIT: avoid turning a design claim into institutional proof.",
        ]
        plan = orch.plan(
            task=task,
            selected_text=PASSAGE,
            findings=findings,
            source_count=1,
            client_context={
                "pedagogical_office": case["office"],
                "learner_level": case["learner"],
                "desired_depth": "detailed",
                "feedback_style": "balanced",
                "assessment_layer": "formative",
            },
        ).to_dict()
        visible_moves.add(plan["visible_summary"])
        no_substitution = "learner chooses" in plan["authorship_boundary"].lower()
        if not no_substitution:
            substitute_failures += 1
        rows.append({
            "case_id": case["id"],
            "expected_office": case["expect"],
            "selected_office": plan["selected_office"],
            "passed": plan["selected_office"] == case["expect"] and bool(plan["visible_summary"]) and no_substitution,
            "plan": plan,
        })

    pass_count = sum(1 for row in rows if row["passed"])
    summary = {
        "passed": pass_count,
        "total": len(rows),
        "pass_rate": round(pass_count / len(rows), 4),
        "distinct_visible_moves": len(visible_moves),
        "substitute_authorship_failures": substitute_failures,
        "meaningful_mode_differentiation": len(visible_moves) >= 5,
    }
    artifact = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "suite": "sophia_writing_desk_phase5_pedagogy",
        "summary": summary,
        "rows": rows,
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if pass_count == len(rows) and summary["meaningful_mode_differentiation"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
