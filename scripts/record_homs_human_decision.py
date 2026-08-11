#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from dio_epistemic_spine import human_decision_event

def main() -> int:
    ap = argparse.ArgumentParser(description="Append a durable human HOMS decision event to a job ledger.")
    ap.add_argument("--job-dir", required=True)
    ap.add_argument("--subject-id", required=True)
    ap.add_argument("--decision", required=True, choices=["approve", "adjust", "reject", "defer"])
    ap.add_argument("--reason", required=True)
    ap.add_argument("--artifact", action="append", default=[])
    ap.add_argument("--actor", default="human_educator")
    args = ap.parse_args()
    job_dir = Path(args.job_dir).expanduser().resolve()
    if not job_dir.is_dir():
        raise SystemExit(f"job directory not found: {job_dir}")
    event = human_decision_event(
        job_id=job_dir.name,
        subject_id=args.subject_id,
        decision=args.decision,
        reason=args.reason,
        artifact_paths=[Path(item) for item in args.artifact],
        actor=args.actor,
    )
    ledger = job_dir / "HOMS_HUMAN_DECISIONS.jsonl"
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=True) + "\n")
    print(json.dumps(event, indent=2))
    print(f"ledger: {ledger}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
