#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Record an approval decision for an AutoRelease job.")
    parser.add_argument("--job", required=True, help="Path to job JSON.")
    parser.add_argument("--state", required=True, choices=["pending", "approved", "rejected"])
    parser.add_argument("--reviewer", default="operator")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    job_path = Path(args.job).expanduser().resolve()
    job = load_json(job_path)
    approval = job.setdefault("approval", {})
    approval["required"] = True
    approval["state"] = args.state
    approval["reviewer"] = args.reviewer
    approval["reviewed_at"] = utc_now()
    if args.note:
        approval["note"] = args.note

    if args.state == "approved":
        job["status"] = "approved"
    elif args.state == "rejected":
        job["status"] = "blocked"
    elif job.get("status") == "approved":
        job["status"] = "needs_review"

    job_path.write_text(json.dumps(job, indent=2), encoding="utf-8")
    receipt_path = job_path.with_suffix(".approval.json")
    receipt = {
        "job_id": job.get("job_id"),
        "created_at": utc_now(),
        "state": args.state,
        "reviewer": args.reviewer,
        "note": args.note,
        "job_path": str(job_path),
    }
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(f"Approval receipt written to: {receipt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

