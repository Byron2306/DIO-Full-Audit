#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HOMS_ROOT = Path("/home/byron/Downloads/NoEdge-Multi-Hymark-main")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_jobs(run_dir: Path) -> list[dict[str, Any]]:
    job_dir = run_dir / "homs"
    if not job_dir.exists():
        return []
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(job_dir.glob("*.json"))]


def first_input(job: dict[str, Any]) -> dict[str, Any]:
    return (job.get("inputs") or [{}])[0]


def first_evidence(job: dict[str, Any]) -> dict[str, Any]:
    return (job.get("evidence") or [{}])[0]


def build_homs_request(job: dict[str, Any]) -> dict[str, Any]:
    item = first_input(job)
    evidence = first_evidence(job)
    attachment_names = str(item.get("attachment_names") or "")

    return {
        "schema": "knowedge.homs_marking_request.v1",
        "created_at": utc_now(),
        "job_id": job["job_id"],
        "homs_root": str(HOMS_ROOT),
        "source": job.get("source", {}),
        "route": job.get("route", {}),
        "intake_summary": {
            "sender": item.get("sender", "unknown"),
            "subject": item.get("subject", "(no subject)"),
            "attachments_listed": attachment_names,
            "triage_next_step": item.get("next_step", ""),
            "triage_draft_status": item.get("draft_status", ""),
            "risk": job.get("risk", "unknown"),
        },
        "required_inputs": {
            "assignment_batch_zip": {
                "required": True,
                "status": "not_verified",
                "notes": "Expected eFundi export ZIP or equivalent batch folder.",
            },
            "rubric_or_memo": {
                "required": True,
                "status": "not_verified",
                "notes": "Expected rubric, memo, essay matrix, or marking guide.",
            },
            "gradebook_csv": {
                "required": False,
                "status": "not_verified",
                "notes": "Needed for automated mark collation/update.",
            },
            "assignment_instructions": {
                "required": False,
                "status": "not_verified",
                "notes": "Can be pasted text or uploaded file.",
            },
        },
        "requested_outputs": [
            "per-student draft feedback",
            "annotated submission files where possible",
            "filled rubric documents",
            "collated marks CSV",
            "lecturer review summary",
            "return-ready ZIP",
        ],
        "approval": {
            "required": True,
            "reason": "Educator must approve final marks and feedback before release.",
        },
        "source_extract": evidence.get("text_extract", ""),
    }


def build_markdown(job: dict[str, Any], request: dict[str, Any]) -> str:
    summary = request["intake_summary"]
    return f"""
# HOMS Marking Request

Job: `{job["job_id"]}`
Created: {utc_now()}
Route confidence: {job["route"]["confidence"]}
Route reason: {job["route"]["reason"]}

## Intake

- Sender: {summary["sender"]}
- Subject: {summary["subject"]}
- Attachments listed: {summary["attachments_listed"] or "none listed"}
- Risk: {summary["risk"]}
- Triage next step: {summary["triage_next_step"] or "none"}

## Required Before Marking

- [ ] Confirm assignment batch ZIP or folder is present.
- [ ] Confirm rubric/memo/marking guide is present.
- [ ] Confirm gradebook CSV if marks must be collated.
- [ ] Confirm assignment instructions or module context.
- [ ] Confirm assessment scale and pass threshold.
- [ ] Confirm whether group submissions must be detected.

## HOMS Output Target

- Draft feedback per student.
- Annotated documents where technically possible.
- Filled rubric documents.
- Marks CSV.
- Lecturer review summary.
- Return-ready ZIP.

## Approval Rule

HOMS may prepare marking support, but educator approval is required before any final mark or feedback is released.
"""


def write_job(job: dict[str, Any], out_root: Path) -> Path:
    job_dir = (out_root / "homs" / job["job_id"]).resolve()
    job_dir.mkdir(parents=True, exist_ok=True)
    request = build_homs_request(job)
    (job_dir / "homs_marking_request.json").write_text(json.dumps(request, indent=2), encoding="utf-8")
    (job_dir / "HOMS_MARKING_REQUEST.md").write_text(build_markdown(job, request).strip() + "\n", encoding="utf-8")
    (job_dir / "HOMS_RUN_RECEIPT.json").write_text(
        json.dumps(
            {
                "job_id": job["job_id"],
                "created_at": utc_now(),
                "status": "prepared_request_only",
                "reason": "Phase 1 prepares the HOMS marking request without starting the HOMS backend or running AI marking.",
                "files": [
                    str(job_dir / "homs_marking_request.json"),
                    str(job_dir / "HOMS_MARKING_REQUEST.md"),
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return job_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare HOMS marking requests for AutoRelease jobs.")
    parser.add_argument("--run", default=str(ROOT / "runs" / "latest"), help="Run directory with routed jobs.")
    parser.add_argument("--out", default=str(ROOT / "deliverables" / "latest"), help="Deliverable output directory.")
    args = parser.parse_args()

    run_dir = Path(args.run).expanduser().resolve()
    out_root = Path(args.out).expanduser().resolve()
    jobs = load_jobs(run_dir)
    created = [write_job(job, out_root) for job in jobs]

    print(f"Prepared {len(created)} HOMS request(s).")
    for path in created:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

