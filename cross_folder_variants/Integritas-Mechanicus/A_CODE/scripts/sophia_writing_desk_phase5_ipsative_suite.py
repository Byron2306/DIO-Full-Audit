#!/usr/bin/env python3
"""Phase 5 ipsative improvement validation for Sophia Writing Desk."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARDA_ROOT = ROOT / "arda_os"
if str(ARDA_ROOT) not in sys.path:
    sys.path.insert(0, str(ARDA_ROOT))

from backend.services.sophia_pedagogy_orchestrator import get_sophia_pedagogy_orchestrator  # noqa: E402
from backend.services.sophia_project_store import SophiaProjectStore  # noqa: E402


def add_turn(store: SophiaProjectStore, project_id: str, text: str, findings: list[str]) -> None:
    version = store.add_draft_version(
        project_id=project_id,
        draft_text=text,
        source="ipsative_suite",
        line_start=1,
        line_end=1,
    )
    store.append_intervention_record(
        project_id=project_id,
        draft_version_id=version["version_id"],
        record={
            "task": "ask",
            "task_label": "Writing Desk feedback",
            "selected_excerpt": text,
            "findings": findings,
            "pedagogical_move": "test",
            "next_revision_move": "test",
            "pedagogical_plan": {"selected_office": "writing_coach"},
        },
    )


def run_case(store: SophiaProjectStore, case: dict) -> dict:
    project_id = case["id"]
    add_turn(store, project_id, case["prior_text"], case["prior_findings"])
    add_turn(store, project_id, case["latest_text"], case["latest_findings"])
    summary = store.summarize_project(project_id)
    improvement = summary.get("latest_intervention_improvement") or {}
    orch = get_sophia_pedagogy_orchestrator()
    plan = orch.plan(
        task="ask",
        selected_text=case["latest_text"],
        findings=case["latest_findings"],
        source_count=0,
        client_context={"pedagogical_office": "auto", "learner_level": "intermediate"},
        history_summary=summary,
    ).to_dict()
    note = str((plan.get("adaptation_trace") or {}).get("ipsative_note") or "")
    return {
        "case_id": case["id"],
        "expected": case["expect"],
        "actual": improvement.get("status"),
        "summary": summary,
        "ipsative_note": note,
        "passed": improvement.get("status") == case["expect"] and case["note_term"] in note.lower(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="evidence/sophia_writing_desk_phase5_ipsative_latest.json")
    args = parser.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="sophia-ipsative-suite-"))
    try:
        store = SophiaProjectStore(tmp)
        cases = [
            {
                "id": "improved",
                "prior_text": "AI policy is incomplete and proves a new model is needed.",
                "latest_text": "AI policy may be incomplete for encounter-level authorship, but this paper treats that as a design claim.",
                "prior_findings": [
                    "NEEDS SOURCE: field claim needs literature.",
                    "OVERCLAIM: proof language is too strong.",
                    "SCOPE LIMIT: specify evidence boundary.",
                ],
                "latest_findings": ["NEEDS SOURCE: field claim needs literature."],
                "expect": "improved",
                "note_term": "improved",
            },
            {
                "id": "stable_unresolved",
                "prior_text": "Human agency means accountable learner authorship.",
                "latest_text": "Human agency means accountable learner authorship in the encounter.",
                "prior_findings": ["OPERATIONAL DEFINITION: define agency indicators."],
                "latest_findings": ["OPERATIONAL DEFINITION: define agency indicators."],
                "expect": "stable_unresolved",
                "note_term": "unresolved",
            },
            {
                "id": "regressed_or_new_risk",
                "prior_text": "The paper proposes a bounded model.",
                "latest_text": "The paper proves a complete world-class model for all universities.",
                "prior_findings": ["REVISION READY: no high-confidence issue detected."],
                "latest_findings": [
                    "OVERCLAIM: proof language is too strong.",
                    "SCOPE LIMIT: specify evidence boundary.",
                ],
                "expect": "regressed_or_new_risk",
                "note_term": "risk",
            },
        ]
        rows = [run_case(store, case) for case in cases]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(1 for row in rows if row["passed"])
    summary = {
        "passed": passed,
        "total": len(rows),
        "pass_rate": round(passed / len(rows), 4),
    }
    artifact = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "suite": "sophia_writing_desk_phase5_ipsative",
        "summary": summary,
        "rows": rows,
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
