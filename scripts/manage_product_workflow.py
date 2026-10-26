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

from scripts.manage_mail_intent import create_intent, emit_event, write_json  # noqa: E402
from scripts.dio_mail_branding import branded_email  # noqa: E402
from scripts.run_evidex_jobs import run_evidex  # noqa: E402
from scripts.run_homs_jobs import write_job as write_homs_job  # noqa: E402
from scripts.run_homs_hymark_batch import run_batch as run_homs_hymark_batch  # noqa: E402


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
    receipt_paths = [deliverable_dir / "EVIDEX_RUN_RECEIPT.json"] if product == "evidex" else [
        deliverable_dir / "HOMS_HYMARK_BATCH_RECEIPT.json",
        deliverable_dir / "HOMS_RUN_RECEIPT.json",
    ]
    receipt_path = next((path for path in receipt_paths if path.is_file()), None)
    if not receipt_path:
        return "not_started", None
    receipt = load_json(receipt_path)
    if product == "evidex":
        return ("review_ready" if receipt.get("returncode") == 0 else "failed"), str(receipt_path)
    if receipt_path.name == "HOMS_HYMARK_BATCH_RECEIPT.json":
        return ("review_ready" if receipt.get("status") == "completed" else "failed"), str(receipt_path)
    return ("awaiting_source_files" if receipt.get("status") == "prepared_request_only" else "failed"), str(receipt_path)


def _resolve_homs_input_dir(source: dict[str, Any], workflow: dict[str, Any]) -> Path | None:
    candidates: list[str] = []
    for container in (
        source,
        source.get("source") or {},
        source.get("request") or {},
        source.get("homs") or {},
        source.get("hymark") or {},
        source.get("intake") or {},
    ):
        if not isinstance(container, dict):
            continue
        for key in ("hymark_input_dir", "input_dir", "job_folder", "batch_dir", "source_dir", "upload_dir"):
            value = container.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value)
    source_path = Path(workflow["source_job_path"])
    for raw in candidates:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = (source_path.parent / candidate).resolve()
        if (candidate / "uploads").is_dir() and (candidate / "rubric.json").is_file():
            return candidate
    return None


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
            "required": product in {"evidex", "homs"},
            "state": "pending" if processing_state == "review_ready" else "not_started",
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
        input_dir = _resolve_homs_input_dir(source, workflow)
        if input_dir:
            receipt = run_homs_hymark_batch(input_dir, out_root / "homs")
            output_dir = Path(receipt["outputs"]["job_dir"])
            receipt_path = output_dir / "HOMS_HYMARK_BATCH_RECEIPT.json"
            state = "review_ready" if receipt.get("status") == "completed" and receipt.get("submissions", 0) > 0 else "failed"
            workflow["output_review"]["state"] = "pending" if state == "review_ready" else "blocked"
        else:
            output_dir = write_homs_job(source, out_root)
            receipt_path = output_dir / "HOMS_RUN_RECEIPT.json"
            state = "awaiting_source_files"
            workflow["output_review"]["state"] = "not_started"
    if workflow["product"] == "evidex":
        output_dir = out_root / workflow["product"] / job_id
    workflow["processing"].update({"state": state, "output_dir": str(output_dir), "receipt_path": str(receipt_path)})
    workflow["state"] = "blocked" if state == "failed" else "active"
    save_workflow(path, workflow)
    emit_event(event_log, f"{workflow['product']}.processing_{state}", "critical" if state == "failed" else "action", "product_job", job_id, {"output_dir": str(output_dir)}, job_id)
    return workflow


def approve_output(state_root: Path, job_id: str, reviewer: str, event_log: Path) -> dict[str, Any]:
    path, workflow = load_workflow(state_root, job_id)
    if workflow["product"] not in {"evidex", "homs"} or workflow["processing"]["state"] != "review_ready":
        raise ValueError("Only a review-ready HOMS or Evidex output can be approved here.")
    if workflow["output_review"]["state"] != "pending":
        raise ValueError("Product output review is not pending.")
    workflow["output_review"].update({"state": "approved", "reviewer": reviewer, "reviewed_at": timestamp()})
    receipt_path = path.parent / "OUTPUT_APPROVAL.json"
    write_json(receipt_path, {
        "schema": "dio.product_output_approval.v1", "job_id": job_id, "product": workflow["product"],
        "state": "approved", "reviewer": reviewer, "reviewed_at": timestamp(),
    })
    save_workflow(path, workflow)
    emit_event(event_log, f"{workflow['product']}.output_approved", "info", "product_job", job_id, {"reviewer": reviewer}, job_id)
    return workflow


def _evidex_archive(workflow: dict[str, Any]) -> Path:
    receipt = load_json(Path(workflow["processing"]["receipt_path"]))
    archive = Path(str(receipt.get("stdout") or "").strip().splitlines()[-1])
    if not archive.is_file() or archive.suffix != ".zip":
        raise FileNotFoundError("The reviewed Evidex delivery ZIP could not be found.")
    return archive


def _homs_archive(workflow: dict[str, Any]) -> Path:
    receipt_path = Path(workflow["processing"]["receipt_path"])
    receipt = load_json(receipt_path)
    outputs = receipt.get("outputs") or {}
    archive = Path(str(outputs.get("review_zip") or ""))
    if not archive.is_file() or archive.suffix != ".zip":
        fallback = Path(workflow["processing"]["output_dir"]) / "HOMS_HYMARK_REVIEW_PACK.zip"
        if fallback.is_file():
            return fallback
        raise FileNotFoundError("The reviewed HOMS delivery ZIP could not be found.")
    return archive


def prepare_notification(state_root: Path, job_id: str, event_log: Path, mail_root: Path = DEFAULT_MAIL_ROOT) -> dict[str, Any]:
    path, workflow = load_workflow(state_root, job_id)
    recipient = workflow["customer"].get("recipient")
    if not recipient:
        raise ValueError("A valid recipient email is required before notification preparation.")
    if workflow["notification"]["state"] != "held":
        raise ValueError("A notification has already been prepared for this workflow.")
    product = workflow["product"]
    if product == "homs":
        if workflow["processing"]["state"] in {"awaiting_source_files", "request_ready"}:
            purpose = "intake"
            subject = f"HOMS source upload request - assessment workflow opened ({job_id})"
            body, body_html = branded_email(
                product="homs",
                eyebrow="SOURCE FILES REQUIRED",
                headline="Your HOMS assessment job is open and waiting for the batch.",
                greeting="Hello,",
                intro="We have opened a governed HOMS workflow for your assessment or marking request.",
                body=[
                    "Please send the electronic submission batch, rubric or memo, task instructions, and gradebook or mark list where mark collation is required.",
                    "Once the complete intake folder contains uploads and a rubric, HOMS runs the HyMark assessor and prepares a review pack for educator approval.",
                    "Final classroom use remains with the authorised teacher, lecturer or moderator.",
                ],
                reference=job_id,
                cta_label="View HOMS Assessment Desk",
                cta_url="https://byron2306.github.io/DIO-Workflows/sites/homs/",
            )
            attachments = []
        else:
            if workflow["output_review"]["state"] != "approved":
                raise ValueError("Human output approval is required before HOMS delivery preparation.")
            purpose = "delivery"
            subject = f"Your reviewed HOMS assessment support pack is ready ({job_id})"
            body, body_html = branded_email(
                product="homs",
                eyebrow="ASSESSMENT PACK READY",
                headline="Your HOMS assessment support pack is ready.",
                greeting="Hello,",
                intro="The attached HyMark review pack has passed the DIO human review gate.",
                body=[
                    "Inside the pack: draft feedback, marks CSV, optional marked gradebook, lecturer review summary and the full review archive.",
                    "Use it to check scoring consistency, feedback quality and rubric alignment before any classroom or institutional use.",
                    "Reply with moderation notes, mark adjustments or the next batch scope.",
                ],
                reference=job_id,
                cta_label="View HOMS Assessment Desk",
                cta_url="https://byron2306.github.io/DIO-Workflows/sites/homs/",
                caution="HOMS prepares marking support. The educator remains the final assessor.",
            )
            attachments = [str(_homs_archive(workflow))]
    else:
        if workflow["output_review"]["state"] != "approved":
            raise ValueError("Human output approval is required before Evidex delivery preparation.")
        purpose = "delivery"
        subject = f"Your reviewed Evidex evidence pack is ready ({job_id})"
        body, body_html = branded_email(
            product="evidex",
            eyebrow="REVIEWED DELIVERY READY",
            headline="Your Evidex evidence pack is ready for use.",
            greeting="Hello,",
            intro="Your reviewed Evidex delivery pack is attached.",
            body=[
                "The pack is prepared to help you inspect evidence, provenance, mapped claims and quality notes without digging through scattered source material.",
                "Please retain the original source archive for audit, revision requests or future updates. If anything needs adjustment, reply to this message with the job reference.",
                "The Evidex service page is included below for your records or for forwarding to a colleague who needs the same workflow.",
            ],
            reference=job_id,
            cta_label="View Evidex Evidence Packs",
            cta_url="https://byron2306.github.io/DIO-Workflows/sites/evidex/",
        )
        attachments = [str(_evidex_archive(workflow))]
    spec_path = path.parent / "MAIL_SPEC.json"
    write_json(spec_path, {
        "purpose": purpose, "job_id": job_id, "recipient": recipient, "subject": subject,
        "body": body, "body_html": body_html, "attachments": attachments, "risk": "moderate",
    })
    intent = create_intent(spec_path, mail_root, event_log)
    workflow["notification"].update({"state": "draft_ready", "mail_intent_id": intent["mail_intent_id"]})
    save_workflow(path, workflow)
    emit_event(event_log, f"{product}.notification_prepared", "action", "product_job", job_id, {"mail_intent_id": intent["mail_intent_id"]}, job_id)
    return workflow


def next_action(workflow: dict[str, Any], mail_root: Path = DEFAULT_MAIL_ROOT) -> str | None:
    if workflow["state"] == "blocked":
        return None
    if workflow["intake"]["state"] == "pending":
        return "approve-intake"
    if workflow["processing"]["state"] == "not_started":
        return "process"
    if workflow["product"] in {"evidex", "homs"} and workflow["output_review"]["state"] == "pending":
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
