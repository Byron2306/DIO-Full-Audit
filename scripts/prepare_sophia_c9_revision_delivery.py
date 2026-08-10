#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dio_mail_branding import branded_email  # noqa: E402
from scripts.manage_mail_intent import create_intent, write_json  # noqa: E402
import scripts.manage_sophia_commercial as commercial  # noqa: E402


def prepare_revision_delivery(
    *,
    job_root: Path,
    job_id: str,
    round_number: int,
    event_log: Path,
) -> dict:
    path, job = commercial.load_job(job_root, job_id)
    target = next(
        (row for row in job.get("revision_rounds") or [] if int(row.get("round") or 0) == round_number),
        None,
    )
    if not target:
        raise ValueError(f"Revision round {round_number} was not found.")
    if (target.get("approval") or {}).get("state") != "approved":
        raise ValueError("Human approval is required before preparing revision delivery.")
    if not target.get("grounding_passed") or target.get("state") != "ready_for_human_review":
        raise ValueError("Only a grounded, review-ready revision pack may be delivered.")
    output_dir = Path(target["output_dir"])
    revision_id = str(target["revision_id"])
    archive = output_dir / f"{revision_id}_SOPHIA_REVIEW_PACK.zip"
    if not archive.is_file():
        raise FileNotFoundError(archive)

    comparison_path = output_dir / "REVISION_INTEGRITY_REPORT.json"
    comparison = json.loads(comparison_path.read_text(encoding="utf-8")) if comparison_path.is_file() else {}
    delta = comparison.get("delta") or {}
    movement = comparison.get("movement") or "reviewed"
    spec_path = path.parent / f"REVISION_{round_number}_DELIVERY_MAIL_SPEC.json"
    body, body_html = branded_email(
        product="sophia",
        eyebrow="REVISION INTEGRITY REVIEW READY",
        headline="Your Sophia revision integrity pack is ready.",
        greeting=f"Hello {job['customer']['name']},",
        intro=(
            "Your revised manuscript section has completed the governed Sophia review route and passed the DIO human release gate."
        ),
        body=[
            f"Revision movement: {movement}.",
            (
                "The comparison records changes in visible scholarly risks and reference findings. "
                "It does not determine who authored the revised prose and it is not a misconduct finding."
            ),
            (
                f"Open scholarly-risk delta: {delta.get('open_scholarly_risks', 'not calculated')}; "
                f"reference-finding delta: {delta.get('reference_findings', 'not calculated')}."
            ),
            (
                "Inside the attached pack you can inspect the revised reviewer commentary, scholarly risk register, "
                "source verification queue, Speculum integrity record, integrity passport and before-to-after revision report."
            ),
            "Final wording, source retention and submission decisions remain yours.",
        ],
        reference=revision_id,
        cta_label="View Sophia",
        cta_url="https://byron2306.github.io/DIO-Workflows/sites/sophia/",
        caution=(
            "Sophia provides diagnostic scholarly-integrity support. Similarity, authorship-preservation signals and revision movement are not plagiarism, AI-authorship or misconduct verdicts."
        ),
    )
    write_json(
        spec_path,
        {
            "purpose": "revision_delivery",
            "order_id": job.get("payment", {}).get("order_id"),
            "job_id": job_id,
            "revision_id": revision_id,
            "round": round_number,
            "recipient": job["customer"]["email"],
            "subject": f"Your Sophia revision integrity pack is ready ({revision_id})",
            "body": body,
            "body_html": body_html,
            "attachments": [str(archive)],
            "risk": "moderate",
        },
    )
    intent = create_intent(spec_path, ROOT / "state" / "mail_intents", event_log)
    target["delivery"].update(
        {
            "state": "draft_ready",
            "mail_intent_id": intent["mail_intent_id"],
            "released": False,
        }
    )
    job["state"] = "revision_delivery_draft_ready"
    commercial.save_job(path, job)
    commercial.emit_event(
        event_log,
        "sophia.revision_delivery_prepared",
        "action",
        "sophia_job",
        job_id,
        {
            "round": round_number,
            "revision_id": revision_id,
            "mail_intent_id": intent["mail_intent_id"],
            "movement": movement,
        },
        job_id,
    )
    return job


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare the human-approved Sophia C9 revision delivery draft.")
    parser.add_argument("job_id")
    parser.add_argument("--round", type=int, default=1)
    parser.add_argument("--job-root", type=Path, default=commercial.DEFAULT_JOB_ROOT)
    parser.add_argument("--event-log", type=Path, default=commercial.DEFAULT_EVENT_LOG)
    args = parser.parse_args()
    result = prepare_revision_delivery(
        job_root=args.job_root.expanduser().resolve(),
        job_id=args.job_id,
        round_number=args.round,
        event_log=args.event_log.expanduser().resolve(),
    )
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Sophia C9 revision delivery blocked: {error}", file=sys.stderr)
        raise SystemExit(2)
