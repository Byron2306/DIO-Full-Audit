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

from adapters.sophia.longitudinal_speculum import (  # noqa: E402
    build_longitudinal_export,
    ingest_review_pack,
    record_author_decision,
    resolve_lineage_candidate,
)
import scripts.manage_sophia_commercial as commercial  # noqa: E402
import scripts.run_sophia_scholarly_integrity_c9 as c9  # noqa: E402


DEFAULT_JOB_ROOT = commercial.DEFAULT_JOB_ROOT
DEFAULT_EVENT_LOG = commercial.DEFAULT_EVENT_LOG
DEFAULT_SERVICE_CONFIG = commercial.DEFAULT_SERVICE_CONFIG
DEFAULT_SOPHIA_ROOT = commercial.DEFAULT_SOPHIA_ROOT
DEFAULT_REVIEW_ROOT = commercial.DEFAULT_REVIEW_ROOT


def state_root_for_job(job_path: Path) -> Path:
    return job_path.parent / "C10_LONGITUDINAL_SPECULUM"


def _summary(payload: dict[str, Any], state_root: Path) -> dict[str, Any]:
    unresolved = len(payload.get("unresolved_continuity_candidates") or [])
    return {
        "state": "longitudinal_speculum_ready",
        "state_root": str(state_root),
        "version_count": int(payload.get("version_count") or 0),
        "lineage_count": int(payload.get("lineage_count") or 0),
        "unresolved_continuity_candidates": unresolved,
        "burden_mutation_lineages": len(payload.get("burden_mutation_lineages") or []),
        "author_decisions": len(payload.get("author_decisions") or []),
        "longitudinal_speculum_hash": payload.get("longitudinal_speculum_hash") or "",
        "native_integrity_record_hash": payload.get("native_integrity_record_hash") or "",
        "release_recommendation": "hold_for_lineage_confirmation" if unresolved else "lineage_review_clear",
    }


def _persist_summary(job_root: Path, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    path, job = commercial.load_job(job_root, job_id)
    state_root = state_root_for_job(path)
    job["longitudinal_speculum"] = _summary(payload, state_root)
    commercial.save_job(path, job)
    return job


def sync_job(
    *,
    job_root: Path,
    job_id: str,
    sophia_root: Path,
) -> dict[str, Any]:
    path, job = commercial.load_job(job_root, job_id)
    state_root = state_root_for_job(path)
    review = job.get("review") or {}
    if review.get("state") != "ready_for_human_review":
        raise ValueError("Initial Sophia review is not ready for C10 longitudinal binding.")
    if (review.get("c9_integrity") or {}).get("state") != "integrity_pack_ready":
        raise ValueError("C10 requires the complete C9 integrity pack before longitudinal binding.")

    initial_output = Path(review["output_dir"])
    ingest_review_pack(
        project_id=job_id,
        state_root=state_root,
        output_dir=initial_output,
        manuscript_path=Path(job["source"]["document_path"]),
        revision_label="initial",
        review_id=job_id,
        sophia_root=sophia_root,
    )

    for round_row in sorted(job.get("revision_rounds") or [], key=lambda row: int(row.get("round") or 0)):
        if round_row.get("state") not in {"ready_for_human_review", "approved_for_delivery"}:
            continue
        if (round_row.get("integrity_enrichment") or {}).get("state") != "integrity_pack_ready":
            continue
        round_number = int(round_row.get("round") or 0)
        ingest_review_pack(
            project_id=job_id,
            state_root=state_root,
            output_dir=Path(round_row["output_dir"]),
            manuscript_path=Path(round_row["document_path"]),
            revision_label=f"revision_{round_number}",
            review_id=str(round_row["revision_id"]),
            sophia_root=sophia_root,
        )

    payload = build_longitudinal_export(
        state_root=state_root,
        project_id=job_id,
        sophia_root=sophia_root,
    )
    return _persist_summary(job_root, job_id, payload)


def run_initial(
    *,
    job_root: Path,
    job_id: str,
    event_log: Path,
    base_url: str,
    sophia_root: Path,
    review_root: Path,
) -> dict[str, Any]:
    c9.run_initial(
        job_root=job_root,
        job_id=job_id,
        event_log=event_log,
        base_url=base_url,
        sophia_root=sophia_root,
        review_root=review_root,
    )
    job = sync_job(job_root=job_root, job_id=job_id, sophia_root=sophia_root)
    commercial.emit_event(
        event_log,
        "sophia.c10_longitudinal_ready",
        "action",
        "sophia_job",
        job_id,
        job.get("longitudinal_speculum") or {},
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
    c9.run_revision(
        job_root=job_root,
        job_id=job_id,
        revised_document=revised_document,
        event_log=event_log,
        service_config=service_config,
        base_url=base_url,
        sophia_root=sophia_root,
        review_root=review_root,
    )
    job = sync_job(job_root=job_root, job_id=job_id, sophia_root=sophia_root)
    commercial.emit_event(
        event_log,
        "sophia.c10_revision_lineage_ready",
        "action",
        "sophia_job",
        job_id,
        job.get("longitudinal_speculum") or {},
        job_id,
    )
    return job


def record_decision_for_job(
    *,
    job_root: Path,
    job_id: str,
    lineage_id: str,
    decision: str,
    rationale: str,
    actor: str,
    sophia_root: Path,
    event_log: Path,
) -> dict[str, Any]:
    path, _job = commercial.load_job(job_root, job_id)
    state_root = state_root_for_job(path)
    payload = record_author_decision(
        project_id=job_id,
        state_root=state_root,
        lineage_id=lineage_id,
        decision=decision,
        rationale=rationale,
        actor=actor,
        sophia_root=sophia_root,
    )
    job = _persist_summary(job_root, job_id, payload)
    commercial.emit_event(
        event_log,
        "sophia.c10_author_decision_recorded",
        "info",
        "sophia_job",
        job_id,
        {"lineage_id": lineage_id, "decision": decision, "actor": actor},
        job_id,
    )
    return job


def resolve_candidate_for_job(
    *,
    job_root: Path,
    job_id: str,
    provisional_lineage_id: str,
    accept_parent: bool,
    actor: str,
    rationale: str,
    sophia_root: Path,
    event_log: Path,
) -> dict[str, Any]:
    path, _job = commercial.load_job(job_root, job_id)
    state_root = state_root_for_job(path)
    payload = resolve_lineage_candidate(
        project_id=job_id,
        state_root=state_root,
        provisional_lineage_id=provisional_lineage_id,
        accept_parent=accept_parent,
        actor=actor,
        rationale=rationale,
        sophia_root=sophia_root,
    )
    job = _persist_summary(job_root, job_id, payload)
    commercial.emit_event(
        event_log,
        "sophia.c10_lineage_resolved",
        "info",
        "sophia_job",
        job_id,
        {
            "provisional_lineage_id": provisional_lineage_id,
            "resolution": "continuation" if accept_parent else "new_claim",
            "actor": actor,
        },
        job_id,
    )
    return job


def require_lineage_clear(job: dict[str, Any], *, minimum_versions: int) -> None:
    c10 = job.get("longitudinal_speculum") or {}
    if c10.get("state") != "longitudinal_speculum_ready":
        raise ValueError("C10 longitudinal Speculum is not ready.")
    if int(c10.get("version_count") or 0) < minimum_versions:
        raise ValueError(f"C10 needs at least {minimum_versions} bound draft version(s) for this gate.")
    if c10.get("unresolved_continuity_candidates"):
        raise ValueError("Resolve ambiguous claim-lineage candidates before C10 approval.")
    if len(str(c10.get("longitudinal_speculum_hash") or "")) != 64:
        raise ValueError("C10 longitudinal Speculum hash is missing or invalid.")
    if len(str(c10.get("native_integrity_record_hash") or "")) != 64:
        raise ValueError("Native Sophia integrity-record hash is missing or invalid.")


def approve_initial(
    *,
    job_root: Path,
    job_id: str,
    reviewer: str,
    event_log: Path,
) -> dict[str, Any]:
    _path, job = commercial.load_job(job_root, job_id)
    require_lineage_clear(job, minimum_versions=1)
    return commercial.approve_job(job_root, job_id, reviewer, event_log)


def approve_revision(
    *,
    job_root: Path,
    job_id: str,
    round_number: int,
    reviewer: str,
    event_log: Path,
) -> dict[str, Any]:
    _path, job = commercial.load_job(job_root, job_id)
    require_lineage_clear(job, minimum_versions=2)
    return c9.approve_revision(
        job_root=job_root,
        job_id=job_id,
        round_number=round_number,
        reviewer=reviewer,
        event_log=event_log,
    )


def export_for_job(*, job_root: Path, job_id: str, sophia_root: Path) -> dict[str, Any]:
    path, _job = commercial.load_job(job_root, job_id)
    return build_longitudinal_export(
        state_root=state_root_for_job(path),
        project_id=job_id,
        sophia_root=sophia_root,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Sophia C10 longitudinal Speculum operator workflow.")
    parser.add_argument("--job-root", type=Path, default=DEFAULT_JOB_ROOT)
    parser.add_argument("--event-log", type=Path, default=DEFAULT_EVENT_LOG)
    parser.add_argument("--service-config", type=Path, default=DEFAULT_SERVICE_CONFIG)
    parser.add_argument("--base-url", default="http://127.0.0.1:7070")
    parser.add_argument("--sophia-root", type=Path, default=DEFAULT_SOPHIA_ROOT)
    parser.add_argument("--review-root", type=Path, default=DEFAULT_REVIEW_ROOT)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run C9 initial review and bind it into the C10 living Speculum.")
    run.add_argument("job_id")

    revision = sub.add_parser("revision", help="Run C9 revision review and append it to the living Speculum.")
    revision.add_argument("job_id")
    revision.add_argument("--document", type=Path, required=True)

    sync = sub.add_parser("sync", help="Bind any existing C9 initial/revision packs into C10 state.")
    sync.add_argument("job_id")

    decision = sub.add_parser("record-decision", help="Record the human author's decision on a claim lineage.")
    decision.add_argument("job_id")
    decision.add_argument("--lineage", required=True)
    decision.add_argument("--decision", required=True)
    decision.add_argument("--rationale", default="")
    decision.add_argument("--actor", required=True)

    resolve = sub.add_parser("resolve-lineage", help="Confirm or reject an ambiguous claim-continuity candidate.")
    resolve.add_argument("job_id")
    resolve.add_argument("--lineage", required=True, help="Provisional lineage ID.")
    group = resolve.add_mutually_exclusive_group(required=True)
    group.add_argument("--accept-parent", action="store_true")
    group.add_argument("--confirm-new", action="store_true")
    resolve.add_argument("--actor", required=True)
    resolve.add_argument("--rationale", default="")

    export = sub.add_parser("export", help="Export the current longitudinal Speculum JSON.")
    export.add_argument("job_id")

    approve = sub.add_parser("approve", help="C10-gated approval of the initial review.")
    approve.add_argument("job_id")
    approve.add_argument("--reviewer", required=True)

    approve_r = sub.add_parser("approve-revision", help="C10-gated approval of a revision review.")
    approve_r.add_argument("job_id")
    approve_r.add_argument("--round", type=int, default=1)
    approve_r.add_argument("--reviewer", required=True)

    args = parser.parse_args()
    job_root = args.job_root.expanduser().resolve()
    event_log = args.event_log.expanduser().resolve()
    sophia_root = args.sophia_root.expanduser().resolve()
    common = {"job_root": job_root, "job_id": args.job_id}

    if args.command == "run":
        result = run_initial(
            **common,
            event_log=event_log,
            base_url=args.base_url,
            sophia_root=sophia_root,
            review_root=args.review_root.expanduser().resolve(),
        )
    elif args.command == "revision":
        result = run_revision(
            **common,
            revised_document=args.document.expanduser().resolve(),
            event_log=event_log,
            service_config=args.service_config.expanduser().resolve(),
            base_url=args.base_url,
            sophia_root=sophia_root,
            review_root=args.review_root.expanduser().resolve(),
        )
    elif args.command == "sync":
        result = sync_job(**common, sophia_root=sophia_root)
    elif args.command == "record-decision":
        result = record_decision_for_job(
            **common,
            lineage_id=args.lineage,
            decision=args.decision,
            rationale=args.rationale,
            actor=args.actor,
            sophia_root=sophia_root,
            event_log=event_log,
        )
    elif args.command == "resolve-lineage":
        result = resolve_candidate_for_job(
            **common,
            provisional_lineage_id=args.lineage,
            accept_parent=bool(args.accept_parent),
            actor=args.actor,
            rationale=args.rationale,
            sophia_root=sophia_root,
            event_log=event_log,
        )
    elif args.command == "approve":
        result = approve_initial(**common, reviewer=args.reviewer, event_log=event_log)
    elif args.command == "approve-revision":
        result = approve_revision(
            **common,
            round_number=args.round,
            reviewer=args.reviewer,
            event_log=event_log,
        )
    else:
        result = export_for_job(**common, sophia_root=sophia_root)

    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Sophia C10 blocked: {error}", file=sys.stderr)
        raise SystemExit(2)
