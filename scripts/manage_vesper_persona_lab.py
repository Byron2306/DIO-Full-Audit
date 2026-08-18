#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.lingua.persona_lab import evaluate_persona_lab, record_outcome


def _assignment(root: Path, conversation_id: str) -> dict:
    path = root / "state" / "lingua" / "persona_lab" / "assignments" / f"{conversation_id}.json"
    if not path.is_file():
        raise SystemExit(f"No Persona Lab assignment found for {conversation_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Record and evaluate governed Vesper Persona Lab evidence.")
    parser.add_argument("--root", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)

    outcome = sub.add_parser("outcome")
    outcome.add_argument("--conversation", required=True)
    outcome.add_argument("--source", required=True)
    outcome.add_argument("--evidence-ref")
    for metric in (
        "task-completed", "issue-resolved", "qualified-intake", "pilot-requested", "paid-conversion",
        "repeat-interaction", "explicit-satisfaction", "human-escalation", "abandonment", "complaint",
        "mistaken-human-belief",
    ):
        outcome.add_argument(f"--{metric}", action="store_true")

    sub.add_parser("evaluate")
    args = parser.parse_args()
    root = args.root.resolve()

    if args.command == "evaluate":
        print(json.dumps(evaluate_persona_lab(root), indent=2, ensure_ascii=True))
        return 0

    metrics = {
        "task_completed": args.task_completed,
        "issue_resolved": args.issue_resolved,
        "qualified_intake": args.qualified_intake,
        "pilot_requested": args.pilot_requested,
        "paid_conversion": args.paid_conversion,
        "repeat_interaction": args.repeat_interaction,
        "explicit_satisfaction": args.explicit_satisfaction,
        "human_escalation": args.human_escalation,
        "abandonment": args.abandonment,
        "complaint": args.complaint,
        "mistaken_human_belief": args.mistaken_human_belief,
    }
    metrics = {key: value for key, value in metrics.items() if value}
    if not metrics:
        raise SystemExit("At least one outcome metric flag is required.")
    receipt = record_outcome(
        root=root,
        assignment=_assignment(root, args.conversation),
        metrics=metrics,
        source=args.source,
        evidence_ref=args.evidence_ref,
    )
    print(json.dumps(receipt, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
