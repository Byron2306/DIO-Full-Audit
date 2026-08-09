#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EVIDEX_ROOT = Path("/home/byron/Evidex")
EVIDEX_PYTHON = EVIDEX_ROOT / ".venv" / "bin" / "python"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned[:90] or "job"


def load_evidex_jobs(run_dir: Path) -> list[dict[str, Any]]:
    job_dir = run_dir / "evidex"
    if not job_dir.exists():
        return []
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(job_dir.glob("*.json"))]


def first_input(job: dict[str, Any]) -> dict[str, Any]:
    return (job.get("inputs") or [{}])[0]


def first_evidence(job: dict[str, Any]) -> dict[str, Any]:
    return (job.get("evidence") or [{}])[0]


def infer_contact(sender: str) -> tuple[str, str]:
    match = re.search(r"([^<]+)<([^>]+)>", sender)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    email_match = re.search(r"[\w.+-]+@[\w.-]+", sender)
    if email_match:
        return sender.replace(email_match.group(0), "").strip() or "Client", email_match.group(0)
    return sender or "Client", ""


def build_intake(job: dict[str, Any]) -> dict[str, Any]:
    item = first_input(job)
    evidence = first_evidence(job)
    contact_name, contact_email = infer_contact(str(item.get("sender") or ""))
    subject = str(item.get("subject") or "Evidence pack request")
    text = str(evidence.get("text_extract") or "")

    return {
        "client": {
            "organization": "Client organization to confirm",
            "contact_name": contact_name,
            "contact_email": contact_email,
        },
        "pack": {
            "purpose": subject,
            "donor": "To be confirmed",
            "project_name": subject[:80] or "Evidence Pack",
            "grant_id": job["job_id"],
            "reporting_period": {
                "start": "To be confirmed",
                "end": "To be confirmed",
            },
            "tone": "clear, conservative, audit-ready",
            "include_appendix": True,
        },
        "kpis": [
            {
                "name": "Evidence request and source materials organized",
                "target": "Complete evidence pack",
                "actual": "Candidate evidence received",
                "measurement": "Email request, listed attachments, and source notes",
            }
        ],
        "constraints": {
            "avoid_claims": [
                "Do not claim outcomes that are not directly supported by supplied evidence.",
                "Do not treat this generated pack as final until reviewed by the operator.",
            ],
            "known_gaps": [
                "Client organization, reporting period, donor template, and KPI list may need confirmation.",
                f"Original route reason: {job['route']['reason']}",
                f"Original evidence extract: {text[:500]}",
            ],
        },
        "billing": {
            "client_type": "ngo",
            "quantity": 1,
            "currency": "ZAR",
            "service_name": "Evidex Evidence Pack",
        },
    }


def write_source_file(job: dict[str, Any], uploads_dir: Path) -> None:
    item = first_input(job)
    evidence = first_evidence(job)
    body = f"""
AutoRelease source email record
===============================

Job: {job["job_id"]}
Created: {job["created_at"]}
Route: {job["route"]["product"]}
Route confidence: {job["route"]["confidence"]}
Route reason: {job["route"]["reason"]}
Risk: {job.get("risk", "unknown")}

Sender: {item.get("sender", "unknown")}
Subject: {item.get("subject", "(no subject)")}
Attachments listed: {item.get("attachment_names", "none listed")}
Intent: {item.get("intent", "")}
Urgency: {item.get("urgency", "")}
Next step: {item.get("next_step", "")}

Evidence extract
----------------
{evidence.get("text_extract", "")}
""".strip()
    uploads_dir.mkdir(parents=True, exist_ok=True)
    (uploads_dir / "autorelease_source_email.txt").write_text(body + "\n", encoding="utf-8")


def run_evidex(job: dict[str, Any], out_root: Path) -> dict[str, Any]:
    job_dir = (out_root / "evidex" / job["job_id"]).resolve()
    engine_dir = job_dir / "evidex_engine"
    uploads_dir = engine_dir / "uploads"
    output_dir = engine_dir / "output"
    engine_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    intake = build_intake(job)
    intake_path = engine_dir / "intake.json"
    intake_path.write_text(json.dumps(intake, indent=2), encoding="utf-8")
    write_source_file(job, uploads_dir)

    env = os.environ.copy()
    env["LLM_DISABLED"] = "1"
    env["SUMMARY_USE_LLM"] = "0"
    env["NARRATIVE_USE_LLM"] = "0"

    cmd = [
        str(EVIDEX_PYTHON),
        "-m",
        "evidence_pack_engine.cli",
        "generate",
        "--intake",
        str(intake_path),
        "--uploads",
        str(uploads_dir),
        "--out",
        str(output_dir),
    ]
    result = subprocess.run(
        cmd,
        cwd=str(EVIDEX_ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    receipt = {
        "job_id": job["job_id"],
        "created_at": utc_now(),
        "command": cmd,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "intake_path": str(intake_path),
        "uploads_dir": str(uploads_dir),
        "output_dir": str(output_dir),
    }
    (job_dir / "EVIDEX_RUN_RECEIPT.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Evidex for AutoRelease Evidex jobs.")
    parser.add_argument("--run", default=str(ROOT / "runs" / "latest"), help="Run directory with routed jobs.")
    parser.add_argument("--out", default=str(ROOT / "deliverables" / "latest"), help="Deliverable output directory.")
    args = parser.parse_args()

    run_dir = Path(args.run).expanduser().resolve()
    out_root = Path(args.out).expanduser().resolve()
    jobs = load_evidex_jobs(run_dir)

    if not EVIDEX_PYTHON.exists():
        raise RuntimeError(f"Evidex Python not found: {EVIDEX_PYTHON}")

    receipts = [run_evidex(job, out_root) for job in jobs]
    print(f"Ran Evidex for {len(receipts)} job(s).")
    for receipt in receipts:
        status = "ok" if receipt["returncode"] == 0 else "failed"
        print(f"- {status}: {receipt['job_id']} -> {receipt['stdout']}")

    return 0 if all(receipt["returncode"] == 0 for receipt in receipts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
