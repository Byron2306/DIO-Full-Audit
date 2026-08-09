#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.commercial_language import CommercialMessageContext, render_nichefoundry_campaign


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_LAYERS = ROOT / "config" / "product_layers.json"
MARKETING_CONFIG = ROOT / "config" / "dio_marketing_integration.json"


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


def resolve_nichefoundry_root() -> Path:
    override = os.environ.get("DIO_NICHEFOUNDRY_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    if MARKETING_CONFIG.exists():
        configured = json.loads(MARKETING_CONFIG.read_text(encoding="utf-8")).get("nichefoundry_root")
        if configured:
            return Path(configured).expanduser().resolve()
    return (Path.home() / "Downloads" / "NicheFoundry_Phase11").resolve()


def layers() -> dict[str, dict[str, Any]]:
    if not PRODUCT_LAYERS.exists():
        return {}
    payload = json.loads(PRODUCT_LAYERS.read_text(encoding="utf-8"))
    return {item["id"]: item for item in payload.get("layers") or []}


def infer_layer_id(subject: str, extract: str) -> str:
    text = f"{subject} {extract}".lower()
    if "homs" in text or "marking" in text or "lecturer" in text or "assessment" in text:
        return "homs"
    if "evidex" in text or "evidence pack" in text or "grant" in text or "donor" in text:
        return "evidex"
    if "vamp" in text or "performance" in text or "task agreement" in text:
        return "vamp"
    if "sophia" in text or "academic review" in text or "citation" in text:
        return "sophia"
    if "translation" in text or "technical edit" in text or "document studio" in text:
        return "document_studio"
    return "dio"


def layer_for_job(job: dict[str, Any]) -> dict[str, Any]:
    item = first_input(job)
    evidence = first_evidence(job)
    subject = clean_text(str(item.get("subject") or "Product campaign"))
    extract = clean_text(str(evidence.get("text_extract") or ""))
    layer_id = infer_layer_id(subject, extract)
    known = layers().get(layer_id)
    if known:
        return known
    return {
        "id": "dio",
        "name": "DIO Workflows",
        "primary_buyer": "evidence-heavy professional teams",
        "pain": "A recurring workflow begins with scattered inputs and repeated manual reconstruction.",
        "promise": "A concrete first pass prepared for professional review.",
        "proof_asset": "DIO controlled workflow evidence",
        "offer": "Controlled Pilot",
        "cta": "Send one non-sensitive workflow example to test the route.",
        "risk_boundary": "Human approval remains required for consequential decisions and release.",
    }


def message_context(job: dict[str, Any]) -> CommercialMessageContext:
    layer = layer_for_job(job)
    item = first_input(job)
    evidence = first_evidence(job)
    subject = clean_text(str(item.get("subject") or ""))
    extract = clean_text(str(evidence.get("text_extract") or ""))
    problem = clean_text(str(layer.get("pain") or ""))
    if not problem and extract:
        problem = extract[:220]
    return CommercialMessageContext(
        product_id=str(layer.get("id") or "dio"),
        product_name=str(layer.get("name") or "DIO Workflows"),
        offer=str(layer.get("offer") or "Controlled Pilot"),
        relationship_stage="public_awareness",
        channel="nichefoundry",
        audience_name=str(layer.get("primary_buyer") or "evidence-heavy professional teams"),
        buyer_role=str(layer.get("primary_buyer") or ""),
        problem=problem,
        desired_outcome=str(layer.get("promise") or ""),
        proof_summary=str(layer.get("proof_asset") or ""),
        proof_grade="technical",
        cta=str(layer.get("cta") or "Send one non-sensitive workflow example to test the route."),
        source_refs=tuple(filter(None, [str(job.get("job_id") or ""), subject])),
    )


def build_opportunity(job: dict[str, Any]) -> dict[str, Any]:
    context = message_context(job)
    campaign = render_nichefoundry_campaign(context)
    return {
        "title": f"{context.product_name}: specific pain-to-proof campaign",
        "topic": f"{context.product_name} controlled service campaign",
        "angle": campaign["core_angle"],
        "viewer_job": f"help me decide whether {context.product_name} addresses this exact workload before I spend time on a pilot",
        "source_hints": [
            "Local AutoRelease routed job",
            "Canonical DIO product layer",
            "Existing product proof artifact",
        ],
        "series_hint": "Proof-bearing professional workflow services",
        "content_role": "commercial_intent",
        "commercial_context": {
            "schema": "dio.commercial.message_context.v1",
            "product_id": context.product_id,
            "audience": context.audience_name,
            "problem": context.problem,
            "desired_outcome": context.desired_outcome,
            "proof_grade": context.proof_grade,
            "cta": context.cta,
        },
        "signals": {
            "audience_demand": 0.0,
            "content_gap": 0.0,
            "series_potential": 0.0,
            "visual_potential": 0.0,
            "monetization_alignment": 0.0,
            "evidence_availability": 1.0 if context.proof_summary else 0.0,
            "production_burden": 0.0,
            "policy_risk": 0.25,
            "freshness_risk": 0.0,
        },
        "signal_note": "Unknown market scores remain zero until measured. The generator does not invent demand or monetization confidence.",
        "operator_notes": (
            f"Generated from AutoRelease job {job['job_id']} at {utc_now()}. "
            f"Route reason: {job['route']['reason']}"
        ),
    }


def build_campaign_markdown(job: dict[str, Any], opportunity: dict[str, Any]) -> str:
    context = message_context(job)
    copy = render_nichefoundry_campaign(context)
    item = first_input(job)
    evidence = first_evidence(job)
    subject = clean_text(str(item.get("subject") or "Product campaign"))
    extract = clean_text(str(evidence.get("text_extract") or ""))

    return f"""
# Campaign Pack: {context.product_name}

Job: `{job["job_id"]}`
Created: {utc_now()}
Route confidence: {job["route"]["confidence"]}
Commercial context: `dio.commercial.message_context.v1`

## Buyer And Job

- Buyer: {context.audience_name}
- Recurring problem: {context.problem}
- Desired result: {context.desired_outcome}
- Offer: {context.offer}
- Proof grade: {context.proof_grade}

## Core Angle

{copy["core_angle"]}

## Lead Message

{copy["lead_message"]}

## Source Brief

- Sender: {item.get("sender", "unknown")}
- Subject: {subject}
- Attachments: {item.get("attachment_names", "none listed")}

## Brief Extract

{extract or "No extract available."}

## Content Pieces

### 1. Pain Post

{copy["pain_post"]}

### 2. Proof Post

{copy["proof_post"]}

### 3. Offer Post

{copy["offer_post"]}

### 4. Objection Post

{copy["objection_post"]}

### 5. CTA

{copy["cta"]}

## Short Video Script

Hook: "{copy['video_hook']}"

Scene 1: Show the exact source workload, not a generic AI graphic.

Scene 2: Show the work being organised or transformed.

Scene 3: Show the real proof artifact and one visible limitation.

Scene 4: Show the professional review or approval point.

CTA: "{copy['cta']}"

## Approval Checklist

- [ ] The first line names a real buyer problem rather than DIO architecture.
- [ ] The proof shown matches the stated proof grade.
- [ ] No fake metrics, testimonials or demand scores.
- [ ] No claim that the system replaces professional judgement.
- [ ] No automatic sending or final decisions implied.
- [ ] One concrete, low-friction CTA.
"""


def build_content_queue(job: dict[str, Any], opportunity: dict[str, Any]) -> dict[str, Any]:
    foundry = resolve_nichefoundry_root()
    return {
        "schema": "knowedge.nichefoundry_campaign_request.v2",
        "created_at": utc_now(),
        "job_id": job["job_id"],
        "nichefoundry_root": str(foundry),
        "recommended_studio": "dio_proof_led_services",
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
            "invented demand scores",
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
                "reason": "Campaign request prepared from canonical DIO product and commercial-message context; publication still requires operator approval.",
                "copy_engine": "dio.commercial.message_context.v1",
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
