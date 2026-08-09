#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.vamp import build_snapshot  # noqa: E402
from scripts.dio_mail_branding import branded_email  # noqa: E402
from scripts.manage_mail_intent import create_intent, emit_event, write_json  # noqa: E402
from scripts.sync_dio_edge_events import EdgeError, edge_request, read_config  # noqa: E402


DEFAULT_JOB_ROOT = ROOT / "state" / "vamp_jobs"
DEFAULT_EVENT_LOG = ROOT / "telemetry" / "dio_events.jsonl"
DEFAULT_SERVICE_CONFIG = ROOT / "config" / "vamp_service.json"
DEFAULT_EDGE_CONFIG = ROOT / "config" / "dio_edge.live.json"
DEFAULT_OUTPUT_ROOT = ROOT / "deliverables" / "vamp_snapshots"


def timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_job_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,100}", value):
        raise ValueError("Invalid VAMP job ID.")
    return value


def job_path(job_root: Path, job_id: str) -> Path:
    return job_root / safe_job_id(job_id) / "JOB.json"


def save_job(path: Path, job: dict[str, Any]) -> None:
    job["updated_at"] = timestamp()
    write_json(path, job)
    path.chmod(0o600)


def load_job(job_root: Path, job_id: str) -> tuple[Path, dict[str, Any]]:
    path = job_path(job_root, job_id)
    if not path.is_file():
        raise FileNotFoundError(f"VAMP job not found: {job_id}")
    return path, load_json(path)


def create_job(spec_path: Path, job_root: Path, event_log: Path, service_path: Path, controlled: bool) -> dict[str, Any]:
    spec = load_json(spec_path)
    schema = load_json(ROOT / "schemas" / "vamp_commercial_request.schema.json")
    jsonschema.validate(spec, schema, format_checker=jsonschema.FormatChecker())
    service = load_json(service_path)
    job_id = safe_job_id(spec["job_id"])
    path = job_path(job_root, job_id)
    if path.exists():
        raise FileExistsError(f"VAMP job already exists: {job_id}")

    profile_path = Path(spec["profile_path"]).expanduser()
    if not profile_path.is_absolute():
        profile_path = (spec_path.parent / profile_path).resolve()
    database_path = Path(spec["source"]["database_path"]).expanduser().resolve()
    if not profile_path.is_file() or not database_path.is_file():
        raise FileNotFoundError("VAMP profile and source database must exist before intake is accepted.")

    directory = path.parent
    directory.mkdir(parents=True, exist_ok=False)
    snapshot_request = {
        "schema": "dio.vamp_snapshot_request.v1",
        "job_id": job_id,
        "profile_path": str(profile_path),
        "source": {**spec["source"], "database_path": str(database_path)},
        "review": spec["review"],
        "privacy_mode": spec["privacy_mode"],
        "consents": spec["consents"],
    }
    request_path = directory / "SNAPSHOT_REQUEST.json"
    write_json(request_path, snapshot_request)
    request_path.chmod(0o600)
    job = {
        "schema": "dio.vamp_commercial_job.v1",
        "job_id": job_id,
        "product_code": service["product_code"],
        "service_name": service["public_name"],
        "state": "intake_authorized",
        "controlled": controlled,
        "created_at": timestamp(),
        "customer": spec["customer"],
        "consents": spec["consents"],
        "source": {
            "request_path": str(request_path),
            "profile_id": profile_path.stem,
            "review_months": spec["review"]["months"],
            "privacy_mode": spec["privacy_mode"],
        },
        "payment": {
            "required": not controlled,
            "state": "waived" if controlled else "pending_quote",
            "order_id": None,
            "amount_minor": service["price"]["amount_minor"],
            "currency": service["price"]["currency"],
            "checkout_url": None,
        },
        "snapshot": {"state": "not_started", "output_dir": None, "evidence_backed_pct": None},
        "approval": {"state": "pending", "reviewer": None, "reviewed_at": None},
        "delivery": {"state": "held", "mail_intent_id": None, "released": False},
    }
    save_job(path, job)
    emit_event(event_log, "vamp.intake_received", "info", "vamp_job", job_id, {"controlled": controlled}, job_id)
    return job


def quote_job(job_root: Path, job_id: str, edge_config_path: Path, event_log: Path) -> dict[str, Any]:
    path, job = load_job(job_root, job_id)
    if job["controlled"]:
        raise ValueError("Controlled VAMP jobs do not create payment orders.")
    if job["payment"]["state"] not in {"pending_quote", "order_registered", "checkout_failed"}:
        raise ValueError(f"Cannot quote from payment state {job['payment']['state']}.")
    config = read_config(edge_config_path)
    token = Path(config["edge_token_path"]).expanduser().read_text(encoding="utf-8").strip()
    base_url = str(config["base_url"]).rstrip("/")
    order_id = job["payment"].get("order_id") or f"ORDER-{job_id}"
    if not job["payment"].get("order_id"):
        edge_request(base_url + "/api/dio/orders", token, method="POST", payload={
            "order_id": order_id,
            "product_code": job["product_code"],
            "amount_minor": job["payment"]["amount_minor"],
            "currency": job["payment"]["currency"],
            "metadata": {"job_id": job_id},
        })
        job["payment"].update({"state": "order_registered", "order_id": order_id})
        save_job(path, job)
    checkout = edge_request(base_url + f"/api/dio/orders/{order_id}/checkout/paypal", token, method="POST")
    job["payment"].update({
        "state": "awaiting_payment", "order_id": order_id,
        "checkout_url": checkout["approval_url"], "provider_order_id": checkout.get("provider_order_id"),
    })
    job["state"] = "payment_pending"
    quote_spec = path.parent / "QUOTE_MAIL_SPEC.json"
    body, body_html = branded_email(
        product="vamp",
        eyebrow="CHECKOUT READY",
        headline="Your VAMP performance evidence pilot is ready to start.",
        greeting=f"Hello {job['customer']['name']},",
        intro="Your VAMP snapshot request passed intake review and is ready for secure checkout.",
        body=[
            "The pilot covers one performance agreement, up to six review months, a calibrated evidence ledger, gap register, Evidex pack and one revision round.",
            "VAMP is designed for review preparation: it maps accepted evidence to objectives, shows what is missing, and keeps the final judgement with the authorised reviewer.",
            "Processing starts only after PayPal confirms payment.",
        ],
        reference=job_id,
        cta_label="Pay securely with PayPal",
        cta_url=checkout["approval_url"],
        caution="VAMP prepares evidence for human review. It does not issue an employee rating or make an employment decision.",
    )
    write_json(quote_spec, {
        "purpose": "quote", "order_id": order_id, "job_id": job_id,
        "recipient": job["customer"]["email"],
        "subject": f"VAMP Performance Evidence Snapshot checkout ({job_id})",
        "body": body,
        "body_html": body_html,
        "attachments": [], "risk": "sensitive",
    })
    intent = create_intent(quote_spec, ROOT / "state" / "mail_intents", event_log)
    job["payment"]["quote_mail_intent_id"] = intent["mail_intent_id"]
    save_job(path, job)
    emit_event(event_log, "vamp.quote_ready", "action", "vamp_job", job_id, {"order_id": order_id}, job_id)
    return job


def reconcile_payment(job_root: Path, job_id: str, edge_config_path: Path, event_log: Path) -> dict[str, Any]:
    path, job = load_job(job_root, job_id)
    order_id = job["payment"].get("order_id")
    if not order_id:
        raise ValueError("VAMP job has no commerce order.")
    config = read_config(edge_config_path)
    token = Path(config["edge_token_path"]).expanduser().read_text(encoding="utf-8").strip()
    order = edge_request(str(config["base_url"]).rstrip("/") + f"/api/dio/orders/{order_id}", token)
    state = str(order.get("state") or "unknown")
    job["payment"]["state"] = state
    job["state"] = "paid_ready_for_processing" if state == "paid" else "payment_hold"
    save_job(path, job)
    emit_event(event_log, "vamp.payment_reconciled", "info" if state == "paid" else "action", "vamp_job", job_id, {"state": state}, job_id)
    return job


def run_job(job_root: Path, job_id: str, output_root: Path, event_log: Path) -> dict[str, Any]:
    path, job = load_job(job_root, job_id)
    if job["payment"]["state"] not in {"paid", "waived"}:
        raise ValueError("Payment must be verified or explicitly waived before VAMP processing.")
    if not all(bool(value) for value in job["consents"].values()):
        raise ValueError("All evidence processing and human-review consents are required.")
    output_dir = build_snapshot(Path(job["source"]["request_path"]), output_root, run_evidex=True)
    snapshot = load_json(output_dir / "VAMP_SNAPSHOT.json")
    ready = snapshot["release"]["status"] == "ready_for_human_review"
    job["snapshot"] = {
        "state": "ready_for_human_review" if ready else "blocked",
        "output_dir": str(output_dir),
        "evidence_backed_pct": snapshot["metrics"]["evidence_backed_pct"],
        "accepted_mappings": snapshot["metrics"]["accepted_mappings"],
        "candidate_mappings": snapshot["metrics"]["candidate_mappings"],
    }
    job["state"] = "snapshot_ready" if ready else "blocked"
    save_job(path, job)
    emit_event(event_log, "vamp.snapshot_ready" if ready else "vamp.snapshot_blocked", "action" if ready else "critical", "vamp_job", job_id, job["snapshot"], job_id)
    return job


def approve_job(job_root: Path, job_id: str, reviewer: str, event_log: Path) -> dict[str, Any]:
    path, job = load_job(job_root, job_id)
    if job["snapshot"]["state"] != "ready_for_human_review":
        raise ValueError("Only a review-ready VAMP snapshot can be approved.")
    job["approval"] = {"state": "approved", "reviewer": reviewer, "reviewed_at": timestamp()}
    job["state"] = "approved_for_delivery"
    save_job(path, job)
    emit_event(event_log, "vamp.snapshot_approved", "info", "vamp_job", job_id, {"reviewer": reviewer}, job_id)
    return job


def prepare_delivery(job_root: Path, job_id: str, event_log: Path) -> dict[str, Any]:
    path, job = load_job(job_root, job_id)
    if job["approval"]["state"] != "approved":
        raise ValueError("Human approval is required before VAMP delivery preparation.")
    output_dir = Path(job["snapshot"]["output_dir"])
    archive = output_dir / f"{job_id}_VAMP_EVIDENCE_SNAPSHOT.zip"
    if not archive.is_file():
        raise FileNotFoundError(archive)
    spec_path = path.parent / "DELIVERY_MAIL_SPEC.json"
    body, body_html = branded_email(
        product="vamp",
        eyebrow="SNAPSHOT READY",
        headline="Your VAMP performance evidence snapshot is ready.",
        greeting=f"Hello {job['customer']['name']},",
        intro="The attached snapshot has passed the DIO human review gate and is ready for your performance-review preparation.",
        body=[
            "Inside the pack: accepted mappings, review candidates, duplicates, declarations, open gaps and the supporting evidence archive.",
            "Use it to see what evidence is strong, what still needs human acceptance, and what remains missing before review day.",
            "Reply with revision notes, missing evidence or the next review scope if you want the snapshot extended.",
        ],
        reference=job_id,
        cta_label="View VAMP",
        cta_url="https://byron2306.github.io/DIO-Workflows/sites/vamp/",
        caution="This pack supports evidence preparation only. Your organisation's authorised reviewer retains all interpretation, rating and employment decisions.",
    )
    write_json(spec_path, {
        "purpose": "delivery", "order_id": job["payment"].get("order_id"), "job_id": job_id,
        "recipient": job["customer"]["email"],
        "subject": f"Your VAMP performance evidence snapshot is ready ({job_id})",
        "body": body,
        "body_html": body_html,
        "attachments": [str(archive)], "risk": "sensitive",
    })
    intent = create_intent(spec_path, ROOT / "state" / "mail_intents", event_log)
    job["delivery"].update({"state": "draft_ready", "mail_intent_id": intent["mail_intent_id"], "released": False})
    job["state"] = "delivery_draft_ready"
    save_job(path, job)
    emit_event(event_log, "vamp.delivery_prepared", "action", "vamp_job", job_id, {"mail_intent_id": intent["mail_intent_id"]}, job_id)
    return job


def main() -> int:
    parser = argparse.ArgumentParser(description="Operate the governed VAMP commercial lane.")
    parser.add_argument("--job-root", type=Path, default=DEFAULT_JOB_ROOT)
    parser.add_argument("--event-log", type=Path, default=DEFAULT_EVENT_LOG)
    parser.add_argument("--service-config", type=Path, default=DEFAULT_SERVICE_CONFIG)
    parser.add_argument("--edge-config", type=Path, default=DEFAULT_EDGE_CONFIG)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create"); create.add_argument("--spec", type=Path, required=True); create.add_argument("--controlled", action="store_true")
    quote = sub.add_parser("quote"); quote.add_argument("job_id")
    reconcile = sub.add_parser("reconcile-payment"); reconcile.add_argument("job_id")
    run = sub.add_parser("run"); run.add_argument("job_id")
    approve = sub.add_parser("approve"); approve.add_argument("job_id"); approve.add_argument("--reviewer", required=True)
    delivery = sub.add_parser("prepare-delivery"); delivery.add_argument("job_id")
    status = sub.add_parser("status"); status.add_argument("job_id")
    args = parser.parse_args()
    job_root, event_log = args.job_root.resolve(), args.event_log.resolve()
    if args.command == "create":
        result = create_job(args.spec.resolve(), job_root, event_log, args.service_config.resolve(), args.controlled)
    elif args.command == "quote":
        result = quote_job(job_root, args.job_id, args.edge_config.resolve(), event_log)
    elif args.command == "reconcile-payment":
        result = reconcile_payment(job_root, args.job_id, args.edge_config.resolve(), event_log)
    elif args.command == "run":
        result = run_job(job_root, args.job_id, args.output_root.resolve(), event_log)
    elif args.command == "approve":
        result = approve_job(job_root, args.job_id, args.reviewer, event_log)
    elif args.command == "prepare-delivery":
        result = prepare_delivery(job_root, args.job_id, event_log)
    else:
        _, result = load_job(job_root, args.job_id)
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EdgeError, jsonschema.ValidationError, OSError, RuntimeError, ValueError) as error:
        print(f"VAMP commercial lane blocked: {error}", file=sys.stderr)
        raise SystemExit(2)
