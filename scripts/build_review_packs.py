#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_jobs(run_dir: Path, products: set[str]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for product in products:
      product_dir = run_dir / product
      if not product_dir.exists():
          continue
      for path in sorted(product_dir.glob("*.json")):
          jobs.append(json.loads(path.read_text(encoding="utf-8")))
    return jobs


def first_input(job: dict[str, Any]) -> dict[str, Any]:
    inputs = job.get("inputs") or []
    return inputs[0] if inputs else {}


def first_evidence(job: dict[str, Any]) -> dict[str, Any]:
    evidence = job.get("evidence") or []
    return evidence[0] if evidence else {}


def write_text(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.strip() + "\n", encoding="utf-8")


def build_evidex_pack(job: dict[str, Any], out_root: Path) -> Path:
    job_dir = out_root / "evidex" / job["job_id"]
    item = first_input(job)
    evidence = first_evidence(job)

    write_text(
        job_dir / "EVIDENCE_MANIFEST.md",
        f"""
# Evidex Evidence Manifest

Job: `{job["job_id"]}`
Created: {utc_now()}
Route confidence: {job["route"]["confidence"]}
Route reason: {job["route"]["reason"]}
Risk: {job.get("risk", "unknown")}

## Intake

- Sender: {item.get("sender", "unknown")}
- Subject: {item.get("subject", "(no subject)")}
- Attachments: {item.get("attachment_names", "none listed")}

## Evidence Candidate

- Evidence ID: `{evidence.get("evidence_id", "unknown")}`
- Source type: {evidence.get("source_type", "unknown")}
- Review status: {evidence.get("review_status", "candidate")}

## Extract

{evidence.get("text_extract", "").strip() or "No text extract available."}

## Next Build Step

Map this evidence into:

- KPI / obligation.
- Proof item.
- Source file or email.
- Confidence.
- Missing evidence.
""",
    )

    write_text(
        job_dir / "CLIENT_REVIEW_CHECKLIST.md",
        f"""
# Client Review Checklist

Job: `{job["job_id"]}`

## Confirm

- [ ] The request is really an evidence/compliance/reporting pack.
- [ ] The visible attachments are enough to begin.
- [ ] The reporting period is known.
- [ ] KPI or funder requirements are available.
- [ ] Sensitive data handling is acceptable.
- [ ] Delivery format is known.

## Missing Questions

- What reporting period should this cover?
- Who is the funder/client/auditor?
- Which template or rubric governs the pack?
- Should invoices/payment proof be included?
- Should photos or raw attendance registers be summarized or attached?

## Approval

- [ ] Approved to run Evidex pack generation.
""",
    )
    return job_dir


def build_nichefoundry_pack(job: dict[str, Any], out_root: Path) -> Path:
    job_dir = out_root / "nichefoundry" / job["job_id"]
    item = first_input(job)
    evidence = first_evidence(job)

    write_text(
        job_dir / "CAMPAIGN_BRIEF.md",
        f"""
# NicheFoundry Campaign Brief

Job: `{job["job_id"]}`
Created: {utc_now()}
Route confidence: {job["route"]["confidence"]}
Route reason: {job["route"]["reason"]}
Risk: {job.get("risk", "unknown")}

## Intake

- Sender: {item.get("sender", "unknown")}
- Subject: {item.get("subject", "(no subject)")}
- Attachments: {item.get("attachment_names", "none listed")}

## Brief Extract

{evidence.get("text_extract", "").strip() or "No text extract available."}

## Campaign Hypothesis

The likely commercial task is to turn a product or service offer into a lead-generation content pack.

## Required Outputs

- Offer angle.
- Audience definition.
- Landing page outline.
- 5 short posts.
- 1 newsletter draft.
- 1 short video script.
- Call-to-action.
- Human editorial approval checklist.
""",
    )

    write_text(
        job_dir / "CONTENT_QUEUE.md",
        f"""
# Content Queue

Job: `{job["job_id"]}`

## Draft Queue

- [ ] Offer headline.
- [ ] Pain-point post.
- [ ] Proof/demo post.
- [ ] Objection-handling post.
- [ ] Founder story post.
- [ ] Lead magnet outline.
- [ ] Newsletter draft.
- [ ] Short video script.

## Approval Gate

- [ ] Claims are truthful.
- [ ] No fake metrics.
- [ ] No fabricated testimonials.
- [ ] CTA is clear.
- [ ] Tone fits the target buyer.
""",
    )
    return job_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Build human-review packs for routed AutoRelease jobs.")
    parser.add_argument("--run", default=str(ROOT / "runs" / "latest"), help="Run directory with routed jobs.")
    parser.add_argument("--out", default=str(ROOT / "deliverables" / "latest"), help="Deliverable output directory.")
    args = parser.parse_args()

    run_dir = Path(args.run).expanduser()
    out_root = Path(args.out).expanduser()
    jobs = load_jobs(run_dir, {"evidex", "nichefoundry"})

    created: list[Path] = []
    for job in jobs:
        product = job["route"]["product"]
        if product == "evidex":
            created.append(build_evidex_pack(job, out_root))
        elif product == "nichefoundry":
            created.append(build_nichefoundry_pack(job, out_root))

    print(f"Created {len(created)} review pack(s) in {out_root}")
    for path in created:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

