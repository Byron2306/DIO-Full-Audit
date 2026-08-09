#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commerce.semantic_judgement import judge_mail_intent  # noqa: E402
from scripts.manage_mail_intent import create_intent, emit_event, write_json  # noqa: E402
from scripts.product_notification_copy import notification_bundle  # noqa: E402
from scripts.run_evidex_jobs import run_evidex  # noqa: E402
from scripts.run_homs_jobs import write_job as write_homs_job  # noqa: E402


DEFAULT_RUNS_ROOT = ROOT / "runs"
DEFAULT_STATE_ROOT = ROOT / "state" / "product_jobs"
DEFAULT_EVENT_LOG = ROOT / "telemetry" / "dio_events.jsonl"
DEFAULT_MAIL_ROOT = ROOT / "state" / "mail_intents"
PRODUCTS = {"evidex", "homs"}
CONTROLLED_MARKERS = ("demo", "dry_run", "playwright", "check", "golden", "sample", "dummy")
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_job_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,100}", value):
        raise ValueError("Invalid product job ID.")
    return value


def resolve_source_job(path: Path, runs_root: Path = DEFAULT_RUNS_ROOT) -> Path:
    resolved = path.expanduser().resolve()
    allowed = runs_root.expanduser().resolve()
    if not resolved.is_relative_to(allowed) or resolved.suffix != ".json" or not resolved.is_file():
        raise ValueError("Product workflow source must be an existing JSON job under the DIO runs directory.")
    return resolved


def workflow_path(state_root: Path, job_id: str) -> Path:
    return state_root / safe_job_id(job_id) / "JOB.json"


def _run_context(source_path: Path, runs_root: Path) -> tuple[str, str]:
    relative = source_path.relative_to(runs_root.resolve())
    run_name = relative.parts[0]
    mode = "controlled" if any(marker in run_name.lower() for marker in CONTROLLED_MARKERS) else "live"
    return run_name, mode


def _recipient(job: dict[str, Any], mode: str) -> tuple[str, bool]:
    lead_id = str((job.get("source") or {}).get("lead_id") or "")
    if lead_id:
        lead_path = ROOT / "state" / "leads" / f"{lead_id}.json"
        if lead_path.is_file():
            lead_email = str((load_json(lead_path).get("contact") or {}).get("email") or "")
            match = EMAIL_PATTERN.search(lead_email)
            if match:
                return match.group(0), False
    sender = str(((job.get("inputs") or [{}])[0]).get("sender") or "")
    match = EMAIL_PATTERN.search(sender)
    if match:
        return match.group(0), False
    if mode == "controlled":
        return "dio_workflows@outlook.com", True
    return "", False


def _existing_processing(product: str, deliverable_dir: Path) -> tuple[str, str | None]:
    receipt_name = "EVIDEX_RUN_RECEIPT.json" if product == "evidex" else "HOMS_RUN_RECEIPT.json"
    receipt_path = deliverable_dir / receipt_name
    if not receipt_path.is_file():
        return "not_started", None
    receipt = load_json(receipt_path)
    if product == "evidex":
        return ("review_ready" if receipt.get("returncode") == 0 else "failed"), str(receipt_path)
    return ("request_ready" if receipt.get("status") == "prepared_request_only" else "failed"), str(receipt_path)


def bootstrap_job(
    source_path: Path,
    state_root: Path = DEFAULT_STATE_ROOT,
    runs_root: Path = DEFAULT_RUNS_ROOT,
) -> dict[str, Any]:
    source_path = resolve_source_job(source_path, runs_root)
    source = load_json(source_path)
    product = str((source.get("route") or {}).get("product") or "")
    if product not in PRODUCTS:
        raise ValueError("Only HOMS and Evidex jobs use this workflow manager.")
    job_id = safe_job_id(str(source.get("job_id") or ""))
    path = workflow_path(state_root, job_id)
    if path.exists():
        return load_json(path)
    run_name, mode = _run_context(source_path, runs_root)
    deliverable_dir = ROOT / "deliverables" / run_name / product / job_id
    processing_state, receipt_path = _existing_processing(product, deliverable_dir)
    intake = source.get("approval") or {}
    intake_state = str(intake.get("state") or "pending")
    recipient, fallback = _recipient(source, mode)
    workflow = {
        "schema": "dio.product_workflow.v1",
        "job_id": job_id,
        "product": product,
        "state": "blocked" if intake_state == "rejected" else "active",
        "mode": mode,
        "run_name": run_name,
        "created_at": timestamp(),
        "updated_at": timestamp(),
        "source_job_path": str(source_path),
        "customer": {"recipient": recipient, "controlled_fallback": fallback},
        "intake": {
            "state": intake_state,
            "reviewer": intake.get("reviewer"),
            "reviewed_at": intake.get("reviewed_at"),
        },
        "processing": {
            "state": processing_state,
            "output_dir": str(deliverable_dir) if deliverable_dir.exists() else None,
            "receipt_path": receipt_path,
        },
        "output_review": {
            "required": product == "evidex",
            "state": "pending" if product == "evidex" and processing_state == "review_ready" else "not_required" if product == "homs" else "not_started",
            "reviewer": None,
            "reviewed_at": None,
        },
        "notification": {"state": "held", "mail_intent_id": None},
    }
    write_json(path, workflow)
    path.chmod(0o600)
    return workflow


def load_workflow(state_root: Path, job_id: str) -> tuple[Path, dict[str, Any]]:
    path = workflow_path(state_root, job_id)
    if not path.is_file():
        raise FileNotFoundError(f"Product workflow not found: {job_id}")
    return path, load_json(path)


def save_workflow(path: Path, workflow: dict[str, Any]) -> None:
    workflow["updated_at"] = timestamp()
    write_json(path, workflow)
    path.chmod(0o600)


def _save_source_approval(workflow: dict[str, Any], state: str, reviewer: str, note: str) -> None:
    source_path = Path(workflow["source_job_path"])
    source = load_json(source_path)
    approval = source.setdefault("approval", {})
    approval.update({"required": True, "state": state, "reviewer": reviewer, "reviewed_at": timestamp(), "note": note})
    source["status"] = "approved" if state == "approved" else "blocked"
    write_json(source_path, source)
    write_json(source_path.with_suffix(".approval.json"), {
        "job_id": workflow["job_id"], "created_at": timestamp(), "stage": "intake",
        "state": state, "reviewer": reviewer, "note": note, "job_path": str(source_path),
    })


def approve_intake(state_root: Path, job_id: str, reviewer: str, event_log: Path) -> dict[str, Any]:
    path, workflow = load_workflow(state_root, job_id)
    if workflow["intake"]["state"] != "pending":
        raise ValueError("Only pending product intake can be approved.")
    note = "Intake route and supplied source summary approved for controlled processing."
    _save_source_approval(workflow, "approved", reviewer, note)
    workflow["intake"].update({"state": "approved", "reviewer": reviewer, "reviewed_at": timestamp()})
    save_workflow(path, workflow)
    emit_event(event_log, f"{workflow['product']}.intake_approved", "info", "product_job", job_id, {"reviewer": reviewer}, job_id)
    return workflow


def reject_intake(state_root: Path, job_id: str, reviewer: str, event_log: Path) -> dict[str, Any]:
    path, workflow = load_workflow(state_root, job_id)
    if workflow["intake"]["state"] != "pending":
        raise ValueError("Only pending product intake can be rejected.")
    note = "Intake rejected by the DIO operator."
    _save_source_approval(workflow, "rejected", reviewer, note)
    workflow["intake"].update({"state": "rejected", "reviewer": reviewer, "reviewed_at": timestamp()})
    workflow["state"] = "blocked"
    save_workflow(path, workflow)
    emit_event(event_log, f"{workflow['product']}.intake_rejected", "info", "product_job", job_id, {"reviewer": reviewer}, job_id)
    return workflow


def process_job(state_root: Path, job_id: str, event_log: Path) -> dict[str, Any]:
    path, workflow = load_workflow(state_root, job_id)
    if workflow["intake"]["state"] != "approved":
        raise ValueError("Product intake approval is required before processing.")
    if workflow["processing"]["state"] != "not_started":
        raise ValueError("Product processing has already started or completed.")
    source = load_json(Path(workflow["source_job_path"]))
    out_root = ROOT / "deliverables" / workflow["run_name"]
    if workflow["product"] == "evidex":
        receipt = run_evidex(source, out_root)
        state = "review_ready" if receipt["returncode"] == 0 else "failed"
        receipt_path = out_root / "evidex" / job_id / "EVIDEX_RUN_RECEIPT.json"
        workflow["output_review"]["state"] = "pending" if state == "review_ready" else "blocked"
    else:
        output_dir = write_homs_job(source, out_root)
        receipt_path = output_dir / "HOMS_RUN_RECEIPT.json"
        state = "request_ready"
    output_dir = out_root / workflow["product"] / job_id
    workflow["processing"].update({"state": state, "output_dir": str(output_dir), "receipt_path": str(receipt_path)})
    workflow["state"] = "blocked" if state == "failed" else "active"
    save_workflow(path, workflow)
    emit_event(event_log, f"{workflow['product']}.processing_{state}", "critical" if state == "failed" else "action", "product_job", job_id, {"output_dir": str(output_dir)}, job_id)
    return workflow


def approve_output(state_root: Path, job_id: str, reviewer: str, event_log: Path) -> dict[str, Any]:
    path, workflow = load_workflow(state_root, job_id)
    if workflow["product"] != "evidex" or workflow["processing"]["state"] != "review_ready":
        raise ValueError("Only a review-ready Evidex output can be approved here.")
    if workflow["output_review"]["state"] != "pending":
        raise ValueError("Evidex output review is not pending.")
    workflow["output_review"].update({"state": "approved", "reviewer": reviewer, "reviewed_at": timestamp()})
    receipt_path = path.parent / "OUTPUT_APPROVAL.json"
    write_json(receipt_path, {
        "schema": "dio.product_output_approval.v1", "job_id": job_id, "product": "evidex",
        "state": "approved", "reviewer": reviewer, "reviewed_at": timestamp(),
    })
    save_workflow(path, workflow)
    emit_event(event_log, "evidex.output_approved", "info", "product_job", job_id, {"reviewer": reviewer}, job_id)
    return workflow


def _evidex_archive(workflow: dict[str, Any]) -> Path:
    receipt = load_json(Path(workflow["processing"]["receipt_path"]))
    archive = Path(str(receipt.get("stdout") or "").strip().splitlines()[-1])
    if not archive.is_file() or archive.suffix != ".zip":
        raise FileNotFoundError("The reviewed Evidex delivery ZIP could not be found.")
    return archive


def _notification_source_paths(path: Path, workflow: dict[str, Any], attachments: list[str]) -> list[Path]:
    sources = [path, Path(workflow["source_job_path"])]
    receipt_path = str((workflow.get("processing") or {}).get("receipt_path") or "").strip()
    if receipt_path:
        sources.append(Path(receipt_path))
    if workflow["product"] == "evidex":
        approval_path = path.parent / "OUTPUT_APPROVAL.json"
        if approval_path.is_file():
            sources.append(approval_path)
    sources.extend(Path(value) for value in attachments)
    return sources


def prepare_notification(state_root: Path, job_id: str, event_log: Path, mail_root: Path = DEFAULT_MAIL_ROOT) -> dict[str, Any]:
    path, workflow = load_workflow(state_root, job_id)
    recipient = workflow["customer"].get("recipient")
    if not recipient:
        raise ValueError("A valid recipient email is required before notification preparation.")
    if workflow["notification"]["state"] != "held":
        raise ValueError("A notification has already been prepared for this workflow.")
    product = workflow["product"]
    if product == "homs":
        if workflow["processing"]["state"] != "request_ready":
            raise ValueError("The HOMS intake request must be ready before notifying the client.")
        attachments: list[str] = []
    else:
        if workflow["output_review"]["state"] != "approved":
            raise ValueError("Human output approval is required before Evidex delivery preparation.")
        attachments = [str(_evidex_archive(workflow))]

    bundle = notification_bundle(workflow)
    semantic_binding = {
        "semantic_object_id": bundle["cso"]["object_id"],
        "communicative_act": bundle["communicative_act"],
        "product_job_id": job_id,
        "source_ref": f"product_job:{job_id}",
    }
    spec_path = path.parent / "MAIL_SPEC.json"
    write_json(spec_path, {
        "purpose": bundle["purpose"],
        "communicative_act": bundle["communicative_act"],
        "semantic_binding": semantic_binding,
        "job_id": job_id,
        "recipient": recipient,
        "subject": bundle["subject"],
        "body": bundle["body"],
        "body_html": bundle["body_html"],
        "attachments": attachments,
        "risk": "moderate",
    })
    intent = create_intent(spec_path, mail_root, event_log)

    workflow["notification"].update({
        "state": "draft_ready",
        "mail_intent_id": intent["mail_intent_id"],
        "communicative_act": bundle["communicative_act"],
    })
    save_workflow(path, workflow)

    judgement, judgement_path = judge_mail_intent(
        ROOT,
        bundle["cso"],
        bundle["expression"],
        intent,
        source_paths=_notification_source_paths(path, workflow, attachments),
    )
    intent["semantic_judgement"] = {
        "judgement_id": judgement["judgement_id"],
        "path": str(judgement_path.relative_to(ROOT)),
        "verdict": judgement["verdict"],
        "execution_binding_sha256": judgement["bindings"]["execution_binding_sha256"],
    }
    write_json(mail_root / f"{intent['mail_intent_id']}.json", intent)
    if judgement["verdict"] == "BLOCK":
        raise ValueError(f"{product.upper()} notification blocked by Triune semantic judgement {judgement['judgement_id']}.")

    emit_event(
        event_log,
        f"{product}.notification_prepared",
        "action",
        "product_job",
        job_id,
        {
            "mail_intent_id": intent["mail_intent_id"],
            "communicative_act": bundle["communicative_act"],
            "semantic_judgement_id": judgement["judgement_id"],
        },
        job_id,
    )
    return workflow


def next_action(workflow: dict[str, Any], mail_root: Path = DEFAULT_MAIL_ROOT) -> str | None:
    if workflow["state"] == "blocked":
        return None
    if workflow["intake"]["state"] == "pending":
        return "approve-intake"
    if workflow["processing"]["state"] == "not_started":
        return "process"
    if workflow["product"] == "evidex" and workflow["output_review"]["state"] == "pending":
        return "approve-output"
    if workflow["notification"]["state"] == "held":
        return "prepare-notification"
    mail_intent_id = workflow["notification"].get("mail_intent_id")
    if mail_intent_id:
        mail_path = mail_root / f"{mail_intent_id}.json"
        mail = load_json(mail_path) if mail_path.exists() else {}
        if not mail.get("provider_draft_id"):
            return "outlook-draft"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Operate streamlined HOMS and Evidex workflows.")
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    parser.add_argument("--event-log", type=Path, default=DEFAULT_EVENT_LOG)
    sub = parser.add_subparsers(dest="command", required=True)
    bootstrap = sub.add_parser("bootstrap"); bootstrap.add_argument("--job", type=Path, required=True)
    for command in ("approve-intake", "reject-intake", "approve-output"):
        item = sub.add_parser(command); item.add_argument("job_id"); item.add_argument("--reviewer", default="operator")
    process = sub.add_parser("process"); process.add_argument("job_id")
    notify = sub.add_parser("prepare-notification"); notify.add_argument("job_id")
    status = sub.add_parser("status"); status.add_argument("job_id")
    args = parser.parse_args()
    state_root, event_log = args.state_root.resolve(), args.event_log.resolve()
    if args.command == "bootstrap":
        result = bootstrap_job(args.job, state_root)
    elif args.command == "approve-intake":
        result = approve_intake(state_root, args.job_id, args.reviewer, event_log)
    elif args.command == "reject-intake":
        result = reject_intake(state_root, args.job_id, args.reviewer, event_log)
    elif args.command == "process":
        result = process_job(state_root, args.job_id, event_log)
    elif args.command == "approve-output":
        result = approve_output(state_root, args.job_id, args.reviewer, event_log)
    elif args.command == "prepare-notification":
        result = prepare_notification(state_root, args.job_id, event_log)
    else:
        _, result = load_workflow(state_root, args.job_id)
    print(json.dumps({**result, "next_action": next_action(result)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
