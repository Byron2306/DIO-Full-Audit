#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NICHEFOUNDRY_ROOT = Path("/home/byron/Downloads/NicheFoundry_Phase11")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_jobs(run_dir: Path) -> list[dict[str, Any]]:
    job_dir = run_dir / "nichefoundry"
    if not job_dir.exists():
        return []
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(job_dir.glob("*.json"))]


def first_input(job: dict[str, Any]) -> dict[str, Any]:
    return (job.get("inputs") or [{}])[0]


def first_evidence(job: dict[str, Any]) -> dict[str, Any]:
    return (job.get("evidence") or [{}])[0]


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def infer_offer(subject: str, extract: str) -> str:
    text = f"{subject} {extract}".lower()
    if "homs" in text or "marking" in text or "lecturer" in text:
        return "HOMS Marking Relief Pack"
    if "evidex" in text or "evidence pack" in text or "grant" in text:
        return "Evidex Evidence Pack"
    if "vamp" in text or "performance" in text:
        return "VAMP Performance Evidence Desk"
    if "sophia" in text or "academic" in text or "research" in text:
        return "Sophia Academic Review Desk"
    return "KnowEdge Evidence Automation Suite"


def build_opportunity(job: dict[str, Any]) -> dict[str, Any]:
    item = first_input(job)
    evidence = first_evidence(job)
    subject = clean_text(str(item.get("subject") or "Product campaign"))
    extract = clean_text(str(evidence.get("text_extract") or ""))
    offer = infer_offer(subject, extract)

    return {
        "title": f"{offer}: workflow pain-to-pack campaign",
        "topic": f"{offer} productized service campaign",
        "angle": (
            "Show a concrete before/after workflow: messy evidence, email, or document batch "
            "becomes a review-ready pack with human approval preserved."
        ),
        "viewer_job": "help me understand whether this workflow can save me time without losing control",
        "source_hints": [
            "Local AutoRelease routed job",
            "KnowEdge portfolio productization report",
            "Existing product README and demo outputs",
        ],
        "series_hint": "Evidence-first AI workflows for busy professionals",
        "content_role": "commercial_intent",
        "signals": {},
        "signal_evidence": {},
        "operator_notes": (
            f"Generated from AutoRelease job {job['job_id']} at {utc_now()}. "
            f"Route reason: {job['route']['reason']} "
            "No market score is asserted by this bridge. Missing NicheFoundry signals must remain unknown "
            "or be calculated by the scorer as explicitly labelled derived heuristics."
        ),
    }


def build_campaign_markdown(job: dict[str, Any], opportunity: dict[str, Any]) -> str:
    item = first_input(job)
    evidence = first_evidence(job)
    subject = clean_text(str(item.get("subject") or "Product campaign"))
    extract = clean_text(str(evidence.get("text_extract") or ""))
    offer = infer_offer(subject, extract)

    return f"""
# Campaign Pack: {offer}

Job: `{job["job_id"]}`
Created: {utc_now()}
Route confidence: {job["route"]["confidence"]}

## Offer

{offer}

## Core Angle

Messy operational input becomes a review-ready output pack. The client keeps judgment and approval.

## Target Buyer

- Busy lecturers, teachers, academic administrators, NGO operators, consultants, or evidence-heavy professionals.
- They already have email threads, attachments, documents, rubrics, reports, and deadlines.
- They do not want another abstract AI tool. They want a done-for-you workflow result.

## Lead Message

Send the messy batch. Get back a structured review pack.

## Source Brief

- Sender: {item.get("sender", "unknown")}
- Subject: {subject}
- Attachments: {item.get("attachment_names", "none listed")}

## Brief Extract

{extract or "No extract available."}

## Content Pieces

### 1. Pain Post

You do not need another dashboard. You need the pile of emails, documents, rubrics, or evidence turned into something you can review and send.

### 2. Proof Post

The workflow creates a job packet, preserves source evidence, routes it to the right product module, generates a review pack, and keeps the human approval gate intact.

### 3. Offer Post

For a limited pilot, send one real but non-sensitive batch. We will return a review-ready pack and show exactly what the workflow can and cannot automate.

### 4. Objection Post

The system does not send emails, finalize marks, invent citations, or make HR decisions. It prepares the work so a human can decide faster.

### 5. CTA

Reply with the workflow you hate repeating: marking, evidence packs, performance reviews, inbox triage, or academic review.

## Short Video Script

Hook: "This is what happens when an inbox stops being a graveyard and starts becoming a production line."

Scene 1: Show the messy input: email, ZIP, rubric, evidence folder, or brief.

Scene 2: Show route classification and job creation.

Scene 3: Show the review pack: evidence manifest, checklist, draft, output folder.

Scene 4: Human approval stays in charge.

CTA: "Send one messy workflow. We will turn it into a review-ready pack."

## Approval Checklist

- [ ] No fake metrics.
- [ ] No fabricated testimonials.
- [ ] No claim that the system replaces professional judgment.
- [ ] No automatic sending or final decisions implied.
- [ ] CTA is concrete and low-friction.
"""


def build_content_queue(job: dict[str, Any], opportunity: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "knowedge.nichefoundry_campaign_request.v1",
        "created_at": utc_now(),
        "job_id": job["job_id"],
        "nichefoundry_root": str(NICHEFOUNDRY_ROOT),
        "recommended_studio": "practical_open_source",
        "opportunity": opportunity,
        "requested_outputs": [
            "landing_page_outline",
            "five_short_posts",
            "newsletter_draft",
            "short_video_script",
            "lead_magnet_outline",
            "editorial_approval_checklist",
        ],
        "approval_required": True,
        "do_not_generate": [
            "fake testimonials",
            "unverified revenue claims",
            "guaranteed outcomes",
            "private client data",
        ],
    }


def write_job(job: dict[str, Any], out_root: Path) -> Path:
    job_dir = (out_root / "nichefoundry" / job["job_id"]).resolve()
    job_dir.mkdir(parents=True, exist_ok=True)
    opportunity = build_opportunity(job)
    request = build_content_queue(job, opportunity)

    (job_dir / "foundry_opportunity.json").write_text(json.dumps(opportunity, indent=2), encoding="utf-8")
    (job_dir / "foundry_campaign_request.json").write_text(json.dumps(request, indent=2), encoding="utf-8")
    (job_dir / "CAMPAIGN_PACK.md").write_text(build_campaign_markdown(job, opportunity).strip() + "\n", encoding="utf-8")
    (job_dir / "NICHEFOUNDRY_RUN_RECEIPT.json").write_text(
        json.dumps(
            {
                "job_id": job["job_id"],
                "created_at": utc_now(),
                "status": "prepared_request_only",
                "reason": "Phase 1 prepares a NicheFoundry-compatible campaign request without rendering media or requiring API keys.",
                "files": [
                    str(job_dir / "foundry_opportunity.json"),
                    str(job_dir / "foundry_campaign_request.json"),
                    str(job_dir / "CAMPAIGN_PACK.md"),
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return job_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare NicheFoundry campaign requests for AutoRelease jobs.")
    parser.add_argument("--run", default=str(ROOT / "runs" / "latest"), help="Run directory with routed jobs.")
    parser.add_argument("--out", default=str(ROOT / "deliverables" / "latest"), help="Deliverable output directory.")
    args = parser.parse_args()

    run_dir = Path(args.run).expanduser().resolve()
    out_root = Path(args.out).expanduser().resolve()
    jobs = load_jobs(run_dir)
    created = [write_job(job, out_root) for job in jobs]

    print(f"Prepared {len(created)} NicheFoundry request(s).")
    for path in created:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
