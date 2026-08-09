#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.sophia.review_pipeline import run_review  # noqa: E402
from scripts.dio_mail_branding import branded_email  # noqa: E402
from scripts.manage_mail_intent import create_intent, emit_event, write_json  # noqa: E402
from scripts.sync_dio_edge_events import EdgeError, edge_request, read_config  # noqa: E402


DEFAULT_JOB_ROOT = ROOT / "state" / "sophia_jobs"
DEFAULT_EVENT_LOG = ROOT / "telemetry" / "dio_events.jsonl"
DEFAULT_SERVICE_CONFIG = ROOT / "config" / "sophia_service.json"
DEFAULT_EDGE_CONFIG = ROOT / "config" / "dio_edge.live.json"
DEFAULT_SOPHIA_ROOT = Path("/home/byron/Integritas-Mechanicus")
DEFAULT_REVIEW_ROOT = ROOT / "deliverables" / "sophia_academic_reviews"


def timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_job_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,100}", value):
        raise ValueError("Invalid Sophia job ID.")
    return value


def job_path(job_root: Path, job_id: str) -> Path:
    return job_root / safe_job_id(job_id) / "JOB.json"


def save_job(path: Path, job: dict[str, Any]) -> None:
    job["updated_at"] = timestamp()
    write_json(path, job)
    path.chmod(0o600)


def load_job(job_root: Path, job_id: str) -> tuple[Path, dict[str, Any]]:
    path = job_path(job_root, job_id)
    if not path.exists():
        raise FileNotFoundError(f"Sophia job not found: {job_id}")
    return path, load_json(path)


def create_job(
    spec_path: Path,
    job_root: Path,
    event_log: Path,
    service_config_path: Path,
    controlled: bool,
) -> dict[str, Any]:
    spec = load_json(spec_path)
    schema = load_json(ROOT / "schemas" / "sophia_commercial_request.schema.json")
    jsonschema.validate(spec, schema, format_checker=jsonschema.FormatChecker())
    service = load_json(service_config_path)
    job_id = safe_job_id(str(spec.get("job_id") or f"SOPHIA-{secrets.token_hex(6).upper()}"))
    path = job_path(job_root, job_id)
    if path.exists():
        raise FileExistsError(f"Sophia job already exists: {job_id}")

    raw_document = Path(spec["document_path"]).expanduser()
    document_path = raw_document if raw_document.is_absolute() else spec_path.parent / raw_document
    document_path = document_path.resolve()
    if not document_path.is_file():
        raise FileNotFoundError(f"Manuscript not found: {document_path}")

    review_request = {
        "schema": "dio.sophia_review_request.v1",
        "job_id": job_id,
        "title": spec["title"],
        "document_path": str(document_path),
        "research_question": spec["research_question"],
        "literature_queries": spec.get("literature_queries") or [spec["research_question"]],
        "citation_style": spec.get("citation_style") or "APA 7",
        "external_retrieval": True,
        "gemini_review_approved": True,
        "gemini_model": "gemini-flash-lite-latest",
        "human_approval_required": True,
    }
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=False)
    request_path = directory / "REVIEW_REQUEST.json"
    write_json(request_path, review_request)
    request_path.chmod(0o600)
    job = {
        "schema": "dio.sophia_commercial_job.v1",
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
            "document_name": document_path.name,
            "document_path": str(document_path),
        },
        "payment": {
            "required": not controlled,
            "state": "waived" if controlled else "pending_quote",
            "order_id": None,
            "amount_minor": service["price"]["amount_minor"],
            "currency": service["price"]["currency"],
            "checkout_url": None,
        },
        "review": {"state": "not_started", "output_dir": None, "grounding_passed": False},
        "approval": {"state": "pending", "reviewer": None, "reviewed_at": None},
        "delivery": {"state": "held", "mail_intent_id": None, "released": False},
    }
    save_job(path, job)
    emit_event(
        event_log,
        "sophia.intake_received",
        "info",
        "sophia_job",
        job_id,
        {"controlled": controlled, "payment_state": job["payment"]["state"]},
        job_id,
    )
    return job


def quote_job(job_root: Path, job_id: str, edge_config_path: Path, event_log: Path) -> dict[str, Any]:
    path, job = load_job(job_root, job_id)
    if job["controlled"]:
        raise ValueError("Controlled Sophia jobs do not create payment orders.")
    if job["payment"]["state"] not in {"pending_quote", "order_registered", "checkout_failed"}:
        raise ValueError(f"Cannot quote from payment state {job['payment']['state']}.")
    config = read_config(edge_config_path)
    token = Path(config["edge_token_path"]).expanduser().read_text(encoding="utf-8").strip()
    base_url = str(config["base_url"]).rstrip("/")
    order_id = job["payment"].get("order_id") or f"ORDER-{job_id}"
    if not job["payment"].get("order_id"):
        edge_request(
            base_url + "/api/dio/orders",
            token,
            method="POST",
            payload={
                "order_id": order_id,
                "product_code": job["product_code"],
                "amount_minor": job["payment"]["amount_minor"],
                "currency": job["payment"]["currency"],
                "metadata": {"job_id": job_id},
            },
        )
        job["payment"].update({"state": "order_registered", "order_id": order_id})
        job["state"] = "payment_order_registered"
        save_job(path, job)

    try:
        checkout = edge_request(
            base_url + f"/api/dio/orders/{order_id}/checkout/paypal",
            token,
            method="POST",
        )
    except EdgeError:
        job["payment"]["state"] = "checkout_failed"
        job["state"] = "payment_checkout_failed"
        save_job(path, job)
        raise
    job["payment"].update({
        "state": "awaiting_payment",
        "order_id": order_id,
        "checkout_url": checkout["approval_url"],
        "provider_order_id": checkout.get("provider_order_id"),
    })
    job["state"] = "payment_pending"

    quote_path = path.parent / "QUOTE_MAIL_SPEC.json"
    body, body_html = branded_email(
        product="sophia",
        eyebrow="CHECKOUT READY",
        headline="Your Sophia academic review pilot is ready to start.",
        greeting=f"Hello {job['customer']['name']},",
        intro="Your request passed intake review and is ready for secure checkout.",
        body=[
            "The launch pilot covers one manuscript section of up to 5,000 words, one diagnostic review pack and one revision round.",
            "Sophia is built for postgraduate and research-facing work: literature discovery leads, technical reference checks, claim-to-source review and reviewer commentary.",
            "Processing starts only after PayPal confirms payment. A human operator reviews the pack before delivery.",
        ],
        reference=job_id,
        cta_label="Pay securely with PayPal",
        cta_url=checkout["approval_url"],
        caution="Sophia supports academic review. It does not ghostwrite, replace your scholarly judgement, or guarantee publication outcomes.",
    )
    write_json(quote_path, {
        "purpose": "quote",
        "order_id": order_id,
        "job_id": job_id,
        "recipient": job["customer"]["email"],
        "subject": f"Sophia Section Review checkout ({job_id})",
        "body": body,
        "body_html": body_html,
        "attachments": [],
        "risk": "routine",
    })
    intent = create_intent(quote_path, ROOT / "state" / "mail_intents", event_log)
    job["payment"]["quote_mail_intent_id"] = intent["mail_intent_id"]
    save_job(path, job)
    emit_event(
        event_log,
        "sophia.quote_ready",
        "action",
        "sophia_job",
        job_id,
        {"order_id": order_id, "mail_intent_id": intent["mail_intent_id"]},
        job_id,
    )
    return job


def reconcile_payment(job_root: Path, job_id: str, edge_config_path: Path, event_log: Path) -> dict[str, Any]:
    path, job = load_job(job_root, job_id)
    order_id = job["payment"].get("order_id")
    if not order_id:
        raise ValueError("Sophia job has no commerce order.")
    config = read_config(edge_config_path)
    token = Path(config["edge_token_path"]).expanduser().read_text(encoding="utf-8").strip()
    order = edge_request(str(config["base_url"]).rstrip("/") + f"/api/dio/orders/{order_id}", token)
    state = str(order.get("state") or "unknown")
    job["payment"]["state"] = state
    if state == "paid":
        job["state"] = "paid_ready_for_processing"
    elif state in {"held", "refunded"}:
        job["state"] = "payment_hold"
    save_job(path, job)
    emit_event(event_log, "sophia.payment_reconciled", "info" if state == "paid" else "action", "sophia_job", job_id, {"order_id": order_id, "state": state}, job_id)
    return job


def run_job(
    job_root: Path,
    job_id: str,
    event_log: Path,
    base_url: str,
    sophia_root: Path,
    review_root: Path,
) -> dict[str, Any]:
    path, job = load_job(job_root, job_id)
    if job["payment"]["state"] not in {"paid", "waived"}:
        raise ValueError("Payment must be verified or explicitly waived before Sophia processing.")
    if not all(bool(value) for value in job["consents"].values()):
        raise ValueError("All manuscript and Gemini processing consents are required.")
    request_path = Path(job["source"]["request_path"])
    review_request = load_json(request_path)
    output_dir = run_review(review_request, request_path, review_root, base_url, sophia_root)
    commentary = load_json(output_dir / "REVIEWER_COMMENTARY.json")
    receipt = load_json(output_dir / "SOPHIA_REVIEW_RECEIPT.json")
    grounding_passed = bool((commentary.get("validation") or {}).get("passed"))
    completed = commentary.get("status") == "completed" and grounding_passed
    job["review"] = {
        "state": "ready_for_human_review" if completed else "blocked",
        "output_dir": str(output_dir),
        "grounding_passed": grounding_passed,
        "provider": commentary.get("provider"),
        "model": commentary.get("model"),
        "reference_findings": (receipt.get("metrics") or {}).get("reference_findings"),
    }
    job["state"] = "review_ready" if completed else "blocked"
    save_job(path, job)
    emit_event(event_log, "sophia.review_ready" if completed else "sophia.review_blocked", "action" if completed else "critical", "sophia_job", job_id, {"grounding_passed": grounding_passed}, job_id)
    return job


def approve_job(job_root: Path, job_id: str, reviewer: str, event_log: Path) -> dict[str, Any]:
    path, job = load_job(job_root, job_id)
    if job["review"]["state"] != "ready_for_human_review" or not job["review"]["grounding_passed"]:
        raise ValueError("Only a grounded, review-ready Sophia pack can be approved.")
    job["approval"] = {"state": "approved", "reviewer": reviewer, "reviewed_at": timestamp()}
    job["state"] = "approved_for_delivery"
    save_job(path, job)
    emit_event(event_log, "sophia.review_approved", "info", "sophia_job", job_id, {"reviewer": reviewer}, job_id)
    return job


def prepare_delivery(job_root: Path, job_id: str, event_log: Path) -> dict[str, Any]:
    path, job = load_job(job_root, job_id)
    if job["approval"]["state"] != "approved":
        raise ValueError("Human approval is required before preparing delivery.")
    output_dir = Path(job["review"]["output_dir"])
    archive = output_dir / f"{job_id}_SOPHIA_REVIEW_PACK.zip"
    if not archive.is_file():
        raise FileNotFoundError(archive)
    spec_path = path.parent / "DELIVERY_MAIL_SPEC.json"
    body, body_html = branded_email(
        product="sophia",
        eyebrow="REVIEW PACK READY",
        headline="Your Sophia academic review pack is ready.",
        greeting=f"Hello {job['customer']['name']},",
        intro="The attached pack has passed the DIO human review gate and is ready for your scholarly review.",
        body=[
            "Inside the pack: reviewer commentary, technical reference audit, literature discovery leads and a claim-to-source ledger.",
            "Use it to see where the argument is supported, where sources need checking, and where revision decisions remain yours.",
            "After you review the pack, reply with any requested revision notes or ask for the next review scope.",
        ],
        reference=job_id,
        cta_label="View Sophia",
        cta_url="https://byron2306.github.io/DIO-Workflows/sites/sophia/",
        caution="This pack is diagnostic support, not a rewritten submission. Verify retained sources against the full publication and keep final academic decisions your own.",
    )
    write_json(spec_path, {
        "purpose": "delivery",
        "order_id": job["payment"].get("order_id"),
        "job_id": job_id,
        "recipient": job["customer"]["email"],
        "subject": f"Your Sophia academic review pack is ready ({job_id})",
        "body": body,
        "body_html": body_html,
        "attachments": [str(archive)],
        "risk": "moderate",
    })
    intent = create_intent(spec_path, ROOT / "state" / "mail_intents", event_log)
    job["delivery"].update({"state": "draft_ready", "mail_intent_id": intent["mail_intent_id"], "released": False})
    job["state"] = "delivery_draft_ready"
    save_job(path, job)
    emit_event(event_log, "sophia.delivery_prepared", "action", "sophia_job", job_id, {"mail_intent_id": intent["mail_intent_id"]}, job_id)
    return job


def main() -> int:
    parser = argparse.ArgumentParser(description="Operate the controlled Sophia commercial transaction lane.")
    parser.add_argument("--job-root", type=Path, default=DEFAULT_JOB_ROOT)
    parser.add_argument("--event-log", type=Path, default=DEFAULT_EVENT_LOG)
    parser.add_argument("--service-config", type=Path, default=DEFAULT_SERVICE_CONFIG)
    parser.add_argument("--edge-config", type=Path, default=DEFAULT_EDGE_CONFIG)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--spec", type=Path, required=True)
    create.add_argument("--controlled", action="store_true")
    quote = sub.add_parser("quote")
    quote.add_argument("job_id")
    reconcile = sub.add_parser("reconcile-payment")
    reconcile.add_argument("job_id")
    run = sub.add_parser("run")
    run.add_argument("job_id")
    run.add_argument("--base-url", default="http://127.0.0.1:7070")
    run.add_argument("--sophia-root", type=Path, default=DEFAULT_SOPHIA_ROOT)
    run.add_argument("--review-root", type=Path, default=DEFAULT_REVIEW_ROOT)
    approve = sub.add_parser("approve")
    approve.add_argument("job_id")
    approve.add_argument("--reviewer", required=True)
    delivery = sub.add_parser("prepare-delivery")
    delivery.add_argument("job_id")
    status = sub.add_parser("status")
    status.add_argument("job_id")
    args = parser.parse_args()
    job_root = args.job_root.resolve()
    event_log = args.event_log.resolve()

    if args.command == "create":
        result = create_job(args.spec.resolve(), job_root, event_log, args.service_config.resolve(), args.controlled)
    elif args.command == "quote":
        result = quote_job(job_root, args.job_id, args.edge_config.resolve(), event_log)
    elif args.command == "reconcile-payment":
        result = reconcile_payment(job_root, args.job_id, args.edge_config.resolve(), event_log)
    elif args.command == "run":
        result = run_job(job_root, args.job_id, event_log, args.base_url, args.sophia_root.resolve(), args.review_root.resolve())
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
    except (EdgeError, jsonschema.ValidationError, OSError, ValueError) as error:
        print(f"Sophia commercial lane blocked: {error}", file=sys.stderr)
        raise SystemExit(2)
