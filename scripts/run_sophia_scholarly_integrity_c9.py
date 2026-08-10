#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.sophia.product_integrity import (  # noqa: E402
    compare_revision_packs,
    enrich_review_pack,
    markdown_revision_report,
    rebuild_archive,
    write_json,
    write_text,
)
from adapters.sophia.review_pipeline import run_review  # noqa: E402
import scripts.manage_sophia_commercial as commercial  # noqa: E402


DEFAULT_JOB_ROOT = commercial.DEFAULT_JOB_ROOT
DEFAULT_EVENT_LOG = commercial.DEFAULT_EVENT_LOG
DEFAULT_SERVICE_CONFIG = commercial.DEFAULT_SERVICE_CONFIG
DEFAULT_SOPHIA_ROOT = commercial.DEFAULT_SOPHIA_ROOT
DEFAULT_REVIEW_ROOT = commercial.DEFAULT_REVIEW_ROOT


def _load_service(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_initial(
    *,
    job_root: Path,
    job_id: str,
    event_log: Path,
    base_url: str,
    sophia_root: Path,
    review_root: Path,
) -> dict[str, Any]:
    job = commercial.run_job(job_root, job_id, event_log, base_url, sophia_root, review_root)
    output_dir = Path(job["review"]["output_dir"])
    manuscript_path = Path(job["source"]["document_path"])
    enrichment = enrich_review_pack(
        job_id=job_id,
        output_dir=output_dir,
        manuscript_path=manuscript_path,
        sophia_root=sophia_root,
    )
    path, job = commercial.load_job(job_root, job_id)
    job["review"]["c9_integrity"] = enrichment
    job["review"]["scholarly_risk_state"] = enrichment["risk_state"]
    job["review"]["open_scholarly_risks"] = enrichment["open_risk_count"]
    job["review"]["verification_queue_count"] = enrichment["verification_queue_count"]
    job["review"]["integrity_record_hash"] = enrichment["speculum_integrity_record_hash"]
    job.setdefault("revision_rounds", [])
    commercial.save_job(path, job)
    commercial.emit_event(
        event_log,
        "sophia.c9_integrity_pack_ready",
        "action",
        "sophia_job",
        job_id,
        {
            "risk_state": enrichment["risk_state"],
            "open_risks": enrichment["open_risk_count"],
            "verification_queue": enrichment["verification_queue_count"],
            "integrity_record_hash": enrichment["speculum_integrity_record_hash"],
        },
        job_id,
    )
    return job


def run_revision(
    *,
    job_root: Path,
    job_id: str,
    revised_document: Path,
    event_log: Path,
    service_config: Path,
    base_url: str,
    sophia_root: Path,
    review_root: Path,
) -> dict[str, Any]:
    path, job = commercial.load_job(job_root, job_id)
    if not revised_document.is_file():
        raise FileNotFoundError(revised_document)
    if not all(bool(value) for value in job.get("consents", {}).values()):
        raise ValueError("The original manuscript and remote-processing consents must still be valid.")
    if job.get("review", {}).get("state") != "ready_for_human_review":
        raise ValueError("The initial Sophia review must be review-ready before a revision round can start.")
    original_output = Path(job["review"]["output_dir"])
    if not original_output.is_dir():
        raise FileNotFoundError(original_output)

    service = _load_service(service_config)
    maximum = int((service.get("limits") or {}).get("included_revision_rounds") or 0)
    prior_rounds = list(job.get("revision_rounds") or [])
    if len(prior_rounds) >= maximum:
        raise ValueError(f"Included revision-round limit reached ({maximum}).")
    round_number = len(prior_rounds) + 1
    revision_id = f"{job_id}-R{round_number}"
    original_request_path = Path(job["source"]["request_path"])
    request = commercial.load_json(original_request_path)
    request.update({
        "job_id": revision_id,
        "document_path": str(revised_document.resolve()),
        "title": f"{request.get('title') or job_id} · Revision {round_number}",
        "human_approval_required": True,
    })
    revision_request_path = path.parent / f"REVISION_{round_number}_REQUEST.json"
    write_json(revision_request_path, request)

    revised_output = run_review(request, revision_request_path, review_root, base_url, sophia_root)
    enrichment = enrich_review_pack(
        job_id=revision_id,
        output_dir=revised_output,
        manuscript_path=revised_document.resolve(),
        sophia_root=sophia_root,
    )
    comparison = compare_revision_packs(
        original_dir=original_output,
        revised_dir=revised_output,
        original_document=Path(job["source"]["document_path"]),
        revised_document=revised_document.resolve(),
    )
    write_json(revised_output / "REVISION_INTEGRITY_REPORT.json", comparison)
    write_text(revised_output / "REVISION_INTEGRITY_REPORT.md", markdown_revision_report(comparison))
    write_json(original_output / f"REVISION_{round_number}_INTEGRITY_REPORT.json", comparison)
    write_text(original_output / f"REVISION_{round_number}_INTEGRITY_REPORT.md", markdown_revision_report(comparison))
    rebuild_archive(revised_output, revision_id)
    rebuild_archive(original_output, job_id)

    commentary = commercial.load_json(revised_output / "REVIEWER_COMMENTARY.json")
    grounded = bool((commentary.get("validation") or {}).get("passed"))
    round_state = "ready_for_human_review" if commentary.get("status") == "completed" and grounded else "blocked"
    round_record = {
        "round": round_number,
        "revision_id": revision_id,
        "state": round_state,
        "document_path": str(revised_document.resolve()),
        "output_dir": str(revised_output),
        "grounding_passed": grounded,
        "integrity_enrichment": enrichment,
        "movement": comparison["movement"],
        "approval": {"state": "pending", "reviewer": None, "reviewed_at": None},
        "delivery": {"state": "held", "released": False},
    }
    job.setdefault("revision_rounds", []).append(round_record)
    job["state"] = "revision_review_ready" if round_state == "ready_for_human_review" else "revision_blocked"
    commercial.save_job(path, job)
    commercial.emit_event(
        event_log,
        "sophia.revision_integrity_ready" if round_state == "ready_for_human_review" else "sophia.revision_integrity_blocked",
        "action" if round_state == "ready_for_human_review" else "critical",
        "sophia_job",
        job_id,
        {
            "revision_id": revision_id,
            "movement": comparison["movement"],
            "open_risk_delta": comparison["delta"]["open_scholarly_risks"],
            "reference_delta": comparison["delta"]["reference_findings"],
        },
        job_id,
    )
    return job


def approve_revision(*, job_root: Path, job_id: str, round_number: int, reviewer: str, event_log: Path) -> dict[str, Any]:
    path, job = commercial.load_job(job_root, job_id)
    rounds = list(job.get("revision_rounds") or [])
    target = next((row for row in rounds if int(row.get("round") or 0) == round_number), None)
    if not target:
        raise ValueError(f"Revision round {round_number} was not found.")
    if target.get("state") != "ready_for_human_review" or not target.get("grounding_passed"):
        raise ValueError("Only a grounded, review-ready revision pack can be approved.")
    target["approval"] = {
        "state": "approved",
        "reviewer": reviewer,
        "reviewed_at": commercial.timestamp(),
    }
    target["delivery"]["state"] = "approved_for_delivery"
    job["state"] = "revision_approved_for_delivery"
    commercial.save_job(path, job)
    commercial.emit_event(
        event_log,
        "sophia.revision_approved",
        "info",
        "sophia_job",
        job_id,
        {"round": round_number, "reviewer": reviewer},
        job_id,
    )
    return job


def main() -> int:
    parser = argparse.ArgumentParser(description="Sophia C9 scholarly-integrity commercial entrypoint.")
    parser.add_argument("--job-root", type=Path, default=DEFAULT_JOB_ROOT)
    parser.add_argument("--event-log", type=Path, default=DEFAULT_EVENT_LOG)
    parser.add_argument("--service-config", type=Path, default=DEFAULT_SERVICE_CONFIG)
    parser.add_argument("--base-url", default="http://127.0.0.1:7070")
    parser.add_argument("--sophia-root", type=Path, default=DEFAULT_SOPHIA_ROOT)
    parser.add_argument("--review-root", type=Path, default=DEFAULT_REVIEW_ROOT)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run the existing commercial review, then build the C9 integrity pack.")
    run.add_argument("job_id")

    revision = sub.add_parser("revision", help="Run the included author-owned revision integrity round.")
    revision.add_argument("job_id")
    revision.add_argument("--document", type=Path, required=True)

    approve = sub.add_parser("approve-revision", help="Record human approval of a revision integrity pack.")
    approve.add_argument("job_id")
    approve.add_argument("--round", type=int, default=1)
    approve.add_argument("--reviewer", required=True)

    args = parser.parse_args()
    common = {
        "job_root": args.job_root.expanduser().resolve(),
        "job_id": args.job_id,
        "event_log": args.event_log.expanduser().resolve(),
    }
    if args.command == "run":
        result = run_initial(
            **common,
            base_url=args.base_url,
            sophia_root=args.sophia_root.expanduser().resolve(),
            review_root=args.review_root.expanduser().resolve(),
        )
    elif args.command == "revision":
        result = run_revision(
            **common,
            revised_document=args.document.expanduser().resolve(),
            service_config=args.service_config.expanduser().resolve(),
            base_url=args.base_url,
            sophia_root=args.sophia_root.expanduser().resolve(),
            review_root=args.review_root.expanduser().resolve(),
        )
    else:
        result = approve_revision(
            **common,
            round_number=args.round,
            reviewer=args.reviewer,
        )
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Sophia C9 blocked: {error}", file=sys.stderr)
        raise SystemExit(2)
