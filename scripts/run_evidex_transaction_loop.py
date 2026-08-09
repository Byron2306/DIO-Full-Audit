#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EVIDEX_ROOT = Path("/home/byron/Evidex")
EVIDEX_PYTHON = EVIDEX_ROOT / ".venv" / "bin" / "python"
OUTLOOK_ROOT = Path("/home/byron/Desktop/KnowEdge_Outlook_Triage_DROP_IN_BUILD_WIX4_FIXED")
OUTLOOK_CONFIG = OUTLOOK_ROOT / "config" / "knowedge_triage.yaml"
OUTLOOK_SRC = OUTLOOK_ROOT / "src"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.strip() + "\n", encoding="utf-8")


def run(cmd: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, cwd=str(cwd), env=env, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        detail = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{detail}")
    return result


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def stage_event(events: list[dict[str, Any]], stage: str, status: str, **extra: Any) -> None:
    events.append({"stage": stage, "status": status, "at": utc_now(), **extra})


def build_reply_packet(path: Path) -> None:
    marker = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    packet = {
        "schema": "knowedge.outlook_triage_export.v1",
        "created_at": utc_now(),
        "items": [
            {
                "message_id": f"golden-evidex-reply-{marker}",
                "thread_ref": f"golden-evidex-thread-{marker}",
                "source": "controlled_outlook_reply",
                "folder": "Inbox",
                "subject": "EVIDEX Pilot Pack Request - BrightStart Community Trust",
                "sender": "M&E Coordinator <controlled.prospect@example.org>",
                "received_at": utc_now(),
                "sender_type": "external_client",
                "urgency": "high",
                "intent": "evidence_pack_request",
                "risk": "routine",
                "lane": "evidex",
                "draft_status": "draft_ready",
                "approval_required": "true",
                "safe_send_rating": "caution",
                "recommended_action": "Route to Evidex pilot pack and request approved non-sensitive evidence intake.",
                "next_step": "Qualify the lead, approve evidence intake, generate the controlled pilot pack, then gate delivery on review and payment state.",
                "attachment_names": "kpi_progress.csv; attendance_register.csv; receipts_summary.csv; field_visit_notes.txt; photo_log.txt",
                "body": (
                    "Replying to your Evidex ad. We need a donor-ready evidence pack for a community reading and food support pilot. "
                    "The evidence is scattered across KPI notes, attendance registers, receipt summaries, field visit notes, and photo logs. "
                    "We need a clean evidence table, mapped claims, provenance, narrative support, QA receipt, and delivery ZIP. "
                    "The sample is controlled and non-sensitive. Please send the intake/payment path."
                ),
            }
        ],
    }
    write_json(path, packet)


def build_uploads(upload_dir: Path) -> None:
    upload_dir.mkdir(parents=True, exist_ok=True)
    write_text(
        upload_dir / "kpi_progress.csv",
        """KPI,Target,Actual,Measurement,Notes
Youth reading workshops delivered,8,9,Workshop sessions delivered,Nine Saturday reading workshops were delivered across April to June.
Learners reached,120,137,Unique learners attending,Attendance register shows 137 unique learner names across the quarter.
Food parcels distributed,200,214,Parcels issued to households,Distribution summary records 214 parcels issued with signed register references.
Receipts reconciled,95%,98%,Eligible spend linked to receipt records,Receipt summary links 98 percent of pilot spend to receipt IDs and supplier notes.
""",
    )
    write_text(
        upload_dir / "attendance_register.csv",
        """Session Date,Workshop,Unique Learners,Register Reference
2026-04-11,Youth reading workshops delivered,18,REG-APR-01
2026-04-18,Youth reading workshops delivered,16,REG-APR-02
2026-05-02,Youth reading workshops delivered,14,REG-MAY-01
2026-05-09,Youth reading workshops delivered,17,REG-MAY-02
2026-05-23,Youth reading workshops delivered,15,REG-MAY-03
2026-06-06,Youth reading workshops delivered,19,REG-JUN-01
2026-06-13,Youth reading workshops delivered,13,REG-JUN-02
2026-06-20,Youth reading workshops delivered,12,REG-JUN-03
2026-06-27,Youth reading workshops delivered,13,REG-JUN-04
""",
    )
    write_text(
        upload_dir / "receipts_summary.csv",
        """Receipt ID,Category,Amount ZAR,KPI Link,Status
RCT-0411-01,Reading materials,1850,Youth reading workshops delivered,Verified
RCT-0502-02,Food parcels,6900,Food parcels distributed,Verified
RCT-0523-03,Transport support,1240,Learners reached,Verified
RCT-0613-04,Food parcels,7200,Food parcels distributed,Verified
RCT-0627-05,Printing and stationery,860,Receipts reconciled,Verified
""",
    )
    write_text(
        upload_dir / "field_visit_notes.txt",
        """BrightStart Community Trust field visit notes.

Project: Community Reading and Food Support Pilot.
Reporting period: 2026-04-01 to 2026-06-30.

Observed claims:
- Youth reading workshops delivered: Programme file lists nine sessions delivered in the quarter.
- Learners reached: Coordinator register indicates 137 unique learners participated.
- Food parcels distributed: Distribution notes record 214 food parcels issued to households.
- Receipts reconciled: Finance summary links 98 percent of claimed spend to source receipts.

Known caveat: Two photo consent forms are pending, so public use of learner images is excluded from this pilot pack.
""",
    )
    write_text(
        upload_dir / "photo_log.txt",
        """Photo log for non-sensitive pilot.

IMG-001: Workshop room setup, no learner faces visible. Supports Youth reading workshops delivered.
IMG-002: Reading material table, no private data visible. Supports Youth reading workshops delivered.
IMG-003: Food parcel packing table, no private data visible. Supports Food parcels distributed.
IMG-004: Delivery staging area, no household identifiers visible. Supports Food parcels distributed.
""",
    )


def build_approved_intake(path: Path, job_id: str) -> dict[str, Any]:
    intake = {
        "client": {
            "organization": "BrightStart Community Trust",
            "contact_name": "Controlled Prospect",
            "contact_email": "controlled.prospect@example.org",
        },
        "pack": {
            "purpose": "Donor evidence pack for community reading and food support pilot",
            "donor": "Ubuntu Community Fund",
            "project_name": "Community Reading and Food Support Pilot",
            "grant_id": f"GOLDEN-{job_id}",
            "reporting_period": {"start": "2026-04-01", "end": "2026-06-30"},
            "tone": "clear, conservative, donor-ready",
            "include_appendix": True,
        },
        "kpis": [
            {
                "name": "Youth reading workshops delivered",
                "target": 8,
                "actual": 9,
                "measurement": "Workshop sessions delivered",
            },
            {
                "name": "Learners reached",
                "target": 120,
                "actual": 137,
                "measurement": "Unique learners attending",
            },
            {
                "name": "Food parcels distributed",
                "target": 200,
                "actual": 214,
                "measurement": "Parcels issued to households",
            },
            {
                "name": "Receipts reconciled",
                "target": "95%",
                "actual": "98%",
                "measurement": "Eligible spend linked to receipt records",
            },
        ],
        "constraints": {
            "avoid_claims": [
                "Do not claim audited financial assurance.",
                "Do not claim public permission to use learner images.",
                "Do not imply donor approval has already been granted.",
            ],
            "known_gaps": [
                "Two photo consent forms pending; learner images excluded from public appendix.",
                "Finance officer should confirm receipt total before final donor submission.",
            ],
        },
        "billing": {
            "client_type": "ngo",
            "quantity": 1,
            "unit_price": 950,
            "currency": "ZAR",
            "service_name": "Evidex Pilot Evidence Pack",
        },
    }
    write_json(path, intake)
    return intake


def read_evidence_table(zip_path: Path, extract_dir: Path) -> list[dict[str, str]]:
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)
    table_path = extract_dir / "01_EVIDENCE_TABLE" / "evidence_table.csv"
    with table_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_mapped_claims(evidence_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    claims = []
    for row in evidence_rows:
        kpi = row.get("KPI", "")
        actual = row.get("Actual", "")
        target = row.get("Target", "")
        sources = [item.strip() for item in row.get("Sources", "").split(";") if item.strip()]
        claims.append(
            {
                "claim": f"{kpi}: actual {actual} against target {target}",
                "kpi": kpi,
                "evidence_summary": row.get("Evidence summary", ""),
                "sources": sources,
                "provenance": [
                    {
                        "source_file": source,
                        "trace": f"Matched by KPI wording in source text for '{kpi}'.",
                    }
                    for source in sources
                ],
                "operator_confidence": "high" if sources else "needs_follow_up",
            }
        )
    return claims


def build_golden_case(
    *,
    golden_dir: Path,
    intake: dict[str, Any],
    evidence_rows: list[dict[str, str]],
    mapped_claims: list[dict[str, Any]],
    zip_path: Path,
    delivery_dir: Path,
) -> None:
    golden_dir.mkdir(parents=True, exist_ok=True)
    write_json(golden_dir / "approved_intake.json", intake)
    write_json(golden_dir / "mapped_claims.json", mapped_claims)
    table_copy = golden_dir / "evidence_table.csv"
    with table_copy.open("w", encoding="utf-8", newline="") as handle:
        if evidence_rows:
            writer = csv.DictWriter(handle, fieldnames=list(evidence_rows[0].keys()))
            writer.writeheader()
            writer.writerows(evidence_rows)

    rows_md = "\n".join(
        f"| {row.get('KPI', '')} | {row.get('Actual', '')}/{row.get('Target', '')} | {row.get('Sources', '')} |"
        for row in evidence_rows
    )
    claims_md = "\n".join(
        f"- **{claim['claim']}** sourced from {', '.join(claim['sources']) or 'no source'}."
        for claim in mapped_claims
    )
    write_text(
        golden_dir / "GOLDEN_EVIDEX_CASE.md",
        f"""
# Golden Evidex Case

## 30-Second Story

Messy donor reporting evidence becomes a review-ready pack:

```text
KPI notes + attendance register + receipt summary + field notes + photo log
-> evidence table
-> mapped claims
-> provenance
-> QA report
-> delivery ZIP
```

## Evidence Table Snapshot

| KPI | Actual/Target | Provenance Sources |
|---|---:|---|
{rows_md}

## Mapped Claims

{claims_md}

## Finished Pack

```text
{zip_path}
```

Delivery folder:

```text
{delivery_dir}
```
""",
    )

    site_dir = ROOT / "sites" / "evidex" / "golden-case"
    site_dir.mkdir(parents=True, exist_ok=True)
    html_rows = "\n".join(
        f"<tr><td>{row.get('KPI', '')}</td><td>{row.get('Actual', '')}</td><td>{row.get('Target', '')}</td><td>{row.get('Sources', '')}</td></tr>"
        for row in evidence_rows
    )
    html_claims = "\n".join(
        f"<li><strong>{claim['claim']}</strong><span>{', '.join(claim['sources'])}</span></li>"
        for claim in mapped_claims
    )
    write_text(
        site_dir / "index.html",
        f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Golden Evidex Case</title>
  <style>
    body {{ margin:0; font-family:Inter,system-ui,sans-serif; background:#f8faf7; color:#071114; }}
    header, section {{ padding:48px clamp(18px,5vw,64px); }}
    header {{ min-height:70vh; display:grid; align-content:center; background:#071114; color:white; }}
    h1 {{ font-size:clamp(48px,9vw,112px); line-height:.9; margin:0; letter-spacing:0; max-width:1000px; }}
    .lead {{ font-size:clamp(20px,3vw,32px); line-height:1.18; color:#fff4d7; max-width:760px; font-weight:750; }}
    table {{ width:100%; border-collapse:collapse; background:white; border:1px solid #d7ded6; }}
    th,td {{ text-align:left; padding:14px; border-top:1px solid #e5ebe4; vertical-align:top; }}
    th {{ color:#5d6a68; }}
    ul {{ display:grid; gap:12px; padding:0; list-style:none; }}
    li {{ background:white; border-left:5px solid #6edbc0; padding:16px; }}
    li span {{ display:block; color:#5d6a68; margin-top:6px; }}
    code {{ background:#edf2ef; padding:2px 5px; border-radius:4px; }}
  </style>
</head>
<body>
  <header>
    <h1>Golden Evidex Case</h1>
    <p class="lead">Messy KPI notes, registers, receipts, field notes, and photo logs become a mapped evidence pack with provenance.</p>
  </header>
  <section>
    <h2>Evidence Table</h2>
    <table>
      <thead><tr><th>KPI</th><th>Actual</th><th>Target</th><th>Sources</th></tr></thead>
      <tbody>{html_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>Mapped Claims</h2>
    <ul>{html_claims}</ul>
  </section>
  <section>
    <h2>Finished Pack</h2>
    <p><code>{zip_path.name}</code></p>
  </section>
</body>
</html>
""",
    )


def update_telemetry(telemetry_dir: Path, row: dict[str, Any]) -> None:
    telemetry_dir.mkdir(parents=True, exist_ok=True)
    csv_path = telemetry_dir / "business_loop.csv"
    jsonl_path = telemetry_dir / "business_loop.jsonl"
    fieldnames = [
        "created_at",
        "product",
        "loop_id",
        "prospects",
        "qualified_leads",
        "intake_started",
        "intake_completed",
        "pack_started",
        "pack_approved",
        "delivery",
        "payment",
        "time_spent_manually_minutes",
        "processing_time_seconds",
        "revisions_requested",
        "revenue_per_job",
        "currency",
        "effective_hourly_return",
        "status",
        "closeout_receipt",
    ]
    exists = csv_path.exists()
    with csv_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in fieldnames})
    append_jsonl(jsonl_path, row)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one complete controlled Evidex business transaction loop.")
    parser.add_argument("--loop-id", default="evidex_golden_transaction_loop")
    parser.add_argument("--revenue", type=float, default=950.0)
    parser.add_argument("--manual-minutes", type=float, default=18.0)
    args = parser.parse_args()

    started = time.perf_counter()
    events: list[dict[str, Any]] = []
    loop_dir = ROOT / "campaigns" / "phase3" / "evidex" / "transaction_loops" / args.loop_id
    run_dir = ROOT / "runs" / args.loop_id
    deliverable_root = ROOT / "deliverables" / args.loop_id
    telemetry_dir = ROOT / "telemetry"
    golden_dir = ROOT / "campaigns" / "phase3" / "evidex" / "golden_case"
    loop_dir.mkdir(parents=True, exist_ok=True)

    ad_path = loop_dir / "AD.md"
    write_text(
        ad_path,
        """
# Evidex Controlled Ad

Your donor report probably is not missing effort. It is missing an evidence pipeline.

Reply with `EVIDEX PILOT PACK REQUEST` to test one non-sensitive pilot pack.
""",
    )
    stage_event(events, "ad", "created", path=str(ad_path))

    reply_path = loop_dir / "controlled_reply.json"
    build_reply_packet(reply_path)
    stage_event(events, "reply", "created", path=str(reply_path), prospects=1)

    outlook_out = loop_dir / "outlook_bot_output"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(OUTLOOK_SRC)
    run(
        [
            "python3",
            "-m",
            "knowedge_triage.cli",
            "triage",
            "--input-json",
            str(reply_path),
            "--out",
            str(outlook_out),
            "--config",
            str(OUTLOOK_CONFIG),
        ],
        env=env,
    )
    triage_csv = outlook_out / "triage_summary.csv"
    stage_event(events, "triage", "completed", csv=str(triage_csv))

    run(["python3", "scripts/route_intake.py", "--input", str(triage_csv), "--out", str(run_dir)])
    summary = read_json(run_dir / "run_summary.json")
    job_ref = next(item for item in summary["jobs"] if item["product"] == "evidex")
    job_path = ROOT / job_ref["path"]
    job = read_json(job_path)
    stage_event(events, "job", "created", job_id=job["job_id"], job_path=str(job_path), route=job["route"])

    approval_path = job_path.with_suffix(".approval.json")
    job["approval"]["state"] = "approved"
    job["approval"]["reviewer"] = "controlled_operator"
    job["approval"]["reviewed_at"] = utc_now()
    job["approval"]["note"] = "Controlled golden loop approved for non-sensitive evidence intake."
    job["status"] = "approved"
    write_json(job_path, job)
    write_json(
        approval_path,
        {
            "job_id": job["job_id"],
            "created_at": utc_now(),
            "state": "approved",
            "reviewer": "controlled_operator",
            "note": "Lead qualified and approved to start controlled evidence intake.",
            "job_path": str(job_path),
        },
    )
    stage_event(events, "qualified_lead", "approved", approval=str(approval_path))

    job_dir = deliverable_root / "evidex" / job["job_id"]
    engine_dir = job_dir / "evidex_engine"
    uploads_dir = engine_dir / "uploads"
    output_dir = engine_dir / "output"
    intake_path = engine_dir / "approved_intake.json"
    build_uploads(uploads_dir)
    intake = build_approved_intake(intake_path, job["job_id"])
    write_json(
        job_dir / "APPROVED_EVIDENCE_INTAKE_RECEIPT.json",
        {
            "job_id": job["job_id"],
            "created_at": utc_now(),
            "status": "approved_evidence_intake",
            "intake": str(intake_path),
            "uploads_dir": str(uploads_dir),
            "operator_boundary": "Controlled non-sensitive pilot evidence only.",
        },
    )
    stage_event(events, "approved_evidence_intake", "completed", intake=str(intake_path), uploads=str(uploads_dir))

    env = os.environ.copy()
    env["LLM_DISABLED"] = "1"
    env["SUMMARY_USE_LLM"] = "0"
    env["NARRATIVE_USE_LLM"] = "0"
    output_dir.mkdir(parents=True, exist_ok=True)
    pack_started = time.perf_counter()
    result = run(
        [
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
        ],
        cwd=EVIDEX_ROOT,
        env=env,
    )
    pack_processing_seconds = time.perf_counter() - pack_started
    zip_path = Path(result.stdout.strip().splitlines()[-1])
    write_json(
        job_dir / "EVIDEX_GENERATION_RECEIPT.json",
        {
            "job_id": job["job_id"],
            "created_at": utc_now(),
            "status": "generated",
            "returncode": result.returncode,
            "zip": str(zip_path),
            "processing_seconds": round(pack_processing_seconds, 3),
        },
    )
    stage_event(events, "evidex_generation", "completed", zip=str(zip_path), processing_seconds=round(pack_processing_seconds, 3))

    extract_dir = job_dir / "review_extract"
    evidence_rows = read_evidence_table(zip_path, extract_dir)
    mapped_claims = build_mapped_claims(evidence_rows)
    write_json(job_dir / "MAPPED_CLAIMS.json", mapped_claims)
    review = {
        "job_id": job["job_id"],
        "created_at": utc_now(),
        "status": "approved",
        "reviewer": "controlled_operator",
        "checks": {
            "evidence_table_present": bool(evidence_rows),
            "mapped_claims_present": bool(mapped_claims),
            "sources_copied": (extract_dir / "03_SOURCES").exists(),
            "quality_report_present": (extract_dir / "QUALITY_REPORT.txt").exists(),
            "delivery_email_present": (extract_dir / "DELIVERY_EMAIL.txt").exists(),
            "invoice_present": (extract_dir / "INVOICE.docx").exists(),
        },
        "revisions_requested": 0,
        "note": "Golden controlled case approved for delivery simulation.",
    }
    write_json(job_dir / "HUMAN_REVIEW_RECEIPT.json", review)
    write_text(
        job_dir / "HUMAN_REVIEW.md",
        """
# Human Review

Approved for controlled delivery simulation.

- Evidence table present.
- Mapped claims generated.
- Source provenance visible.
- Quality report present.
- Invoice and delivery email present.
- No revisions requested.
""",
    )
    stage_event(events, "human_review", "approved", review=str(job_dir / "HUMAN_REVIEW_RECEIPT.json"))

    payment_dir = job_dir / "payment"
    payment = {
        "job_id": job["job_id"],
        "created_at": utc_now(),
        "status": "paid",
        "mode": "simulated_controlled_pilot",
        "currency": "ZAR",
        "amount": args.revenue,
        "invoice_id": f"EVIDEX-SIM-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{job['job_id'][-6:]}",
        "note": "Controlled payment marker used to prove payment gate without live payment provider.",
    }
    write_json(payment_dir / "PAYMENT_STATE.json", payment)
    write_text(payment_dir / "PAID.txt", f"{payment['invoice_id']} paid ZAR {args.revenue:.2f}")
    stage_event(events, "payment_state", "paid", payment=str(payment_dir / "PAYMENT_STATE.json"))

    delivery_dir = job_dir / "delivery"
    delivery_dir.mkdir(parents=True, exist_ok=True)
    delivered_zip = delivery_dir / zip_path.name
    shutil.copy2(zip_path, delivered_zip)
    delivery_email_src = extract_dir / "DELIVERY_EMAIL.txt"
    if delivery_email_src.exists():
        shutil.copy2(delivery_email_src, delivery_dir / "DELIVERY_EMAIL.txt")
    write_text(delivery_dir / "DELIVERED_ZIP.txt", str(delivered_zip))
    write_json(
        delivery_dir / "DELIVERY_RECEIPT.json",
        {
            "job_id": job["job_id"],
            "created_at": utc_now(),
            "status": "delivered",
            "mode": "simulated_manual_delivery",
            "zip": str(delivered_zip),
            "payment_state": str(payment_dir / "PAYMENT_STATE.json"),
            "human_review": str(job_dir / "HUMAN_REVIEW_RECEIPT.json"),
        },
    )
    stage_event(events, "delivery", "completed", delivery=str(delivery_dir / "DELIVERY_RECEIPT.json"))

    build_golden_case(
        golden_dir=golden_dir,
        intake=intake,
        evidence_rows=evidence_rows,
        mapped_claims=mapped_claims,
        zip_path=zip_path,
        delivery_dir=delivery_dir,
    )
    stage_event(events, "golden_case", "created", path=str(golden_dir / "GOLDEN_EVIDEX_CASE.md"))

    total_processing_seconds = time.perf_counter() - started
    effective_hourly = args.revenue / (args.manual_minutes / 60.0) if args.manual_minutes else 0
    closeout = {
        "schema": "knowedge.evidex_transaction_loop.v1",
        "created_at": utc_now(),
        "status": "complete",
        "loop_id": args.loop_id,
        "job_id": job["job_id"],
        "gates": events,
        "artifacts": {
            "ad": str(ad_path),
            "reply": str(reply_path),
            "triage_csv": str(triage_csv),
            "job": str(job_path),
            "approved_intake": str(intake_path),
            "uploads": str(uploads_dir),
            "zip": str(zip_path),
            "human_review": str(job_dir / "HUMAN_REVIEW_RECEIPT.json"),
            "payment": str(payment_dir / "PAYMENT_STATE.json"),
            "delivery": str(delivery_dir / "DELIVERY_RECEIPT.json"),
            "golden_case": str(golden_dir / "GOLDEN_EVIDEX_CASE.md"),
            "golden_case_site": "sites/evidex/golden-case/index.html",
        },
        "business_metrics": {
            "prospects": 1,
            "qualified_leads": 1,
            "intake_started": 1,
            "intake_completed": 1,
            "pack_started": 1,
            "pack_approved": 1,
            "delivery": 1,
            "payment": 1,
            "time_spent_manually_minutes": args.manual_minutes,
            "processing_time_seconds": round(total_processing_seconds, 3),
            "pack_processing_seconds": round(pack_processing_seconds, 3),
            "revisions_requested": 0,
            "revenue_per_job": args.revenue,
            "currency": "ZAR",
            "effective_hourly_return": round(effective_hourly, 2),
        },
    }
    closeout_path = job_dir / "CLOSEOUT_RECEIPT.json"
    write_json(closeout_path, closeout)
    write_text(
        job_dir / "CLOSEOUT.md",
        f"""
# Evidex Transaction Loop Closeout

Status: complete

```text
ad -> reply -> triage -> job -> approved evidence intake -> Evidex generation -> human review -> payment state -> delivery -> closeout receipt
```

Revenue/job: ZAR {args.revenue:.2f}
Manual time estimate: {args.manual_minutes:.1f} minutes
Effective hourly return: ZAR {effective_hourly:.2f}

Golden case:

```text
{golden_dir / "GOLDEN_EVIDEX_CASE.md"}
```
""",
    )

    telemetry_row = {
        "created_at": utc_now(),
        "product": "evidex",
        "loop_id": args.loop_id,
        **closeout["business_metrics"],
        "status": "complete",
        "closeout_receipt": str(closeout_path),
    }
    update_telemetry(telemetry_dir, telemetry_row)
    write_json(loop_dir / "LOOP_INDEX.json", closeout)

    print(json.dumps({"status": "complete", "job_id": job["job_id"], "closeout": str(closeout_path), "golden_case": str(golden_dir / "GOLDEN_EVIDEX_CASE.md")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
