#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "evidex_service.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jobs(run_dir: Path) -> list[dict[str, Any]]:
    job_dir = run_dir / "evidex"
    if not job_dir.exists():
        return []
    return [load_json(path) for path in sorted(job_dir.glob("*.json"))]


def first_input(job: dict[str, Any]) -> dict[str, Any]:
    return (job.get("inputs") or [{}])[0]


def find_zip(job_dir: Path) -> Path | None:
    output_dir = job_dir / "evidex_engine" / "output"
    zips = sorted(output_dir.glob("*.zip"))
    return zips[0] if zips else None


def write_text(path: Path, body: str) -> None:
    path.write_text(body.strip() + "\n", encoding="utf-8")


def build_service_docs(job: dict[str, Any], job_dir: Path, config: dict[str, Any]) -> None:
    item = first_input(job)
    service = config["service"]
    tiers = service["tiers"]
    questions = config["required_client_questions"]
    gate = config["operator_gate"]
    zip_path = find_zip(job_dir)

    tier_rows = "\n".join(
        f"- **{tier['name']}**: {service['default_currency']} {tier['price']} - {tier['description']}"
        for tier in tiers
    )
    question_rows = "\n".join(f"- [ ] {question}" for question in questions)

    write_text(
        job_dir / "SERVICE_OFFER.md",
        f"""
# {service['name']} Service Offer

Job: `{job['job_id']}`
Generated: {utc_now()}

## Positioning

{service['positioning']}

## Recommended Tiers

{tier_rows}

## Suggested First Offer

Use **Pilot Pack** for a first real client unless the client already supplied a full evidence folder and reporting template.

## Current Pack

- Request subject: {item.get('subject', '(no subject)')}
- Sender: {item.get('sender', 'unknown')}
- Attachments listed: {item.get('attachment_names', 'none listed') or 'none listed'}
- Generated ZIP: {zip_path.name if zip_path else 'not generated'}

## Scope Boundary

The pack is review-ready, not automatically final. Operator review and client confirmation are required before delivery.
""",
    )

    write_text(
        job_dir / "CLIENT_INTAKE_QUESTIONS.md",
        f"""
# Client Intake Questions

Job: `{job['job_id']}`

{question_rows}

## Minimum Required Before Final Delivery

- [ ] Organization/project name confirmed.
- [ ] Reporting period confirmed.
- [ ] Recipient/donor/auditor confirmed.
- [ ] KPI or reporting template supplied or explicitly waived.
- [ ] Sensitive data handling confirmed.
""",
    )

    write_text(
        job_dir / "PAYMENT_GATE.md",
        f"""
# Payment And Delivery Gate

Job: `{job['job_id']}`

## Gate Settings

- Payment required before final delivery: {gate['payment_required_before_final_delivery']}
- Manual payment marker: `{gate['manual_payment_status_file']}`
- Approval required before delivery: {gate['approval_required_before_delivery']}
- Automatic email sending allowed: {not gate['no_auto_email']}

## Manual Process

- [ ] Confirm selected tier and price.
- [ ] Send invoice or payment instructions.
- [ ] Wait for payment confirmation or mark as waived.
- [ ] Create `{gate['manual_payment_status_file']}` only after payment is confirmed.
- [ ] Operator approves final delivery.
- [ ] Delivery email is copied manually by the operator.
""",
    )

    write_text(
        job_dir / "PHASE2_EVIDEX_RECEIPT.json",
        json.dumps(
            {
                "job_id": job["job_id"],
                "created_at": utc_now(),
                "status": "service_layer_ready",
                "generated_zip": str(zip_path) if zip_path else None,
                "docs": [
                    str(job_dir / "SERVICE_OFFER.md"),
                    str(job_dir / "CLIENT_INTAKE_QUESTIONS.md"),
                    str(job_dir / "PAYMENT_GATE.md"),
                ],
            },
            indent=2,
        ),
    )

    if zip_path:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        write_text(
            job_dir / "ZIP_CONTENTS.txt",
            "\n".join(names),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Phase 2 service layer docs for Evidex jobs.")
    parser.add_argument("--run", default=str(ROOT / "runs" / "latest"), help="Run directory.")
    parser.add_argument("--out", default=str(ROOT / "deliverables" / "latest"), help="Deliverables directory.")
    args = parser.parse_args()

    run_dir = Path(args.run).expanduser().resolve()
    out_root = Path(args.out).expanduser().resolve()
    config = load_json(CONFIG_PATH)
    jobs = load_jobs(run_dir)
    created = []
    for job in jobs:
        job_dir = out_root / "evidex" / job["job_id"]
        job_dir.mkdir(parents=True, exist_ok=True)
        build_service_docs(job, job_dir, config)
        created.append(job_dir)
    print(f"Built Evidex service layer for {len(created)} job(s).")
    for path in created:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

