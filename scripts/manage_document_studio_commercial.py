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

from adapters.document_studio.pipeline import run_document_studio  # noqa: E402
from adapters.sophia.review_pipeline import extract_document_text  # noqa: E402
from scripts.dio_mail_branding import branded_email  # noqa: E402
from scripts.manage_mail_intent import create_intent, emit_event, write_json  # noqa: E402
from scripts.sync_dio_edge_events import EdgeError, edge_request, read_config  # noqa: E402


DEFAULT_JOB_ROOT = ROOT / "state" / "document_studio_jobs"
DEFAULT_EVENT_LOG = ROOT / "telemetry" / "dio_events.jsonl"
DEFAULT_SERVICE_CONFIG = ROOT / "config" / "document_studio_service.json"
DEFAULT_EDGE_CONFIG = ROOT / "config" / "dio_edge.live.json"
DEFAULT_OUTPUT_ROOT = ROOT / "deliverables" / "document_studio"
TRANSLATION_SERVICES = {"translation", "edit_and_translate"}
APPROVED_LANGUAGE_AUTHORITY = {"human_approved_crystallized", "approved_crystallized"}


def timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_job_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,100}", value):
        raise ValueError("Invalid Document Studio job ID.")
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
        raise FileNotFoundError(f"Document Studio job not found: {job_id}")
    return path, load_json(path)


def document_word_count(path: Path) -> int:
    text, _ = extract_document_text(path)
    return len(re.findall(r"\S+", text))


def language_authority_state(job: dict[str, Any]) -> dict[str, Any]:
    source = job.get("source") or {}
    service = str(source.get("service") or "")
    target_language = str(source.get("target_language") or "").strip()
    if service not in TRANSLATION_SERVICES:
        return {
            "required": False,
            "state": "not_applicable",
            "target_language": None,
            "qa_path": None,
            "reviewer": None,
            "approved_at": None,
        }
    output_dir_raw = str((job.get("studio") or {}).get("output_dir") or "")
    if not output_dir_raw:
        return {
            "required": True,
            "state": "pending",
            "target_language": target_language,
            "qa_path": None,
            "reviewer": None,
            "approved_at": None,
            "reason": "Translation output has not been generated yet.",
        }
    qa_path = Path(output_dir_raw) / "LINGUA_QA.json"
    if not qa_path.is_file():
        return {
            "required": True,
            "state": "pending",
            "target_language": target_language,
            "qa_path": str(qa_path),
            "reviewer": None,
            "approved_at": None,
            "reason": "LINGUA_QA.json is missing.",
        }
    qa = load_json(qa_path)
    qa_target = str(qa.get("target_language") or "").strip()
    authority = str(qa.get("semantic_authority") or "").strip()
    reviewer = str(qa.get("reviewer") or "").strip()
    approved = (
        authority in APPROVED_LANGUAGE_AUTHORITY
        and qa.get("linguistic_quality_approved") is True
        and qa.get("review_required") is False
        and bool(reviewer)
        and bool(target_language)
        and qa_target.casefold() == target_language.casefold()
    )
    return {
        "required": True,
        "state": "approved" if approved else "pending",
        "target_language": target_language,
        "qa_path": str(qa_path),
        "reviewer": reviewer or None,
        "reviewer_role": qa.get("reviewer_role"),
        "approved_at": qa.get("approved_at") if approved else None,
        "semantic_authority": authority or None,
        "release_readiness": qa.get("release_readiness"),
        "reason": None if approved else "A proficient target-language approval/crystallization receipt is required before delivery.",
    }


def create_job(spec_path: Path, job_root: Path, event_log: Path, service_path: Path, controlled: bool) -> dict[str, Any]:
    spec = load_json(spec_path)
    schema = load_json(ROOT / "schemas" / "document_studio_commercial_request.schema.json")
    jsonschema.validate(spec, schema, format_checker=jsonschema.FormatChecker())
    service = load_json(service_path)
    job_id = safe_job_id(spec["job_id"])
    path = job_path(job_root, job_id)
    if path.exists():
        raise FileExistsError(f"Document Studio job already exists: {job_id}")

    raw_document = Path(spec["document_path"]).expanduser()
    document_path = raw_document if raw_document.is_absolute() else spec_path.parent / raw_document
    document_path = document_path.resolve()
    if not document_path.is_file():
        raise FileNotFoundError(f"Source document not found: {document_path}")

    words = document_word_count(document_path)
    maximum_words = int((service.get("limits") or {}).get("maximum_words") or 0)
    if maximum_words and words > maximum_words:
        raise ValueError(f"Document exceeds the controlled-pilot limit of {maximum_words} words ({words} supplied).")

    consents = spec["consents"]
    studio_request = {
        "schema": "dio.document_studio_request.v1",
        "job_id": job_id,
        "service": spec["service"],
        "title": spec["title"],
        "document_path": str(document_path),
        "source_language": spec["source_language"],
        "target_language": spec.get("target_language"),
        "document_domain": spec.get("document_domain") or "professional document",
        "audience": spec.get("audience") or "professional reader",
        "provider": spec.get("provider") or "nim",
        "nim_model": spec.get("nim_model") or "deepseek-ai/deepseek-v4-flash-0731",
        "gemini_model": spec.get("gemini_model") or "gemini-flash-lite-latest",
        "provider_secret_file": spec.get("provider_secret_file"),
        "protected_tokens": spec.get("protected_tokens") or [],
        "preferred_terms": spec.get("preferred_terms") or [],
        "format_channels": spec.get("format_channels") or ["docx", "pdf", "html"],
        "format_style_profile": spec.get("format_style_profile") or "dio_professional",
        "format_delivery_profile": spec.get("format_delivery_profile") or "editable_review",
        "owner_authorized": consents["document_owner_authorized"],
        "remote_processing_approved": consents["remote_processing_approved"],
        "human_language_review_required": bool(consents["human_review_required"]),
        "certified_translation_required": not bool(consents["certified_translation_not_requested"]),
        "automated_language_critic": spec["service"] in TRANSLATION_SERVICES,
        "translation_review_overrides": spec.get("translation_review_overrides") or {},
        "translation_override_reviewer": spec.get("translation_override_reviewer") or "",
        "human_approval_required": True,
    }
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=False)
    request_path = directory / "DOCUMENT_STUDIO_REQUEST.json"
    write_json(request_path, studio_request)
    request_path.chmod(0o600)
    job = {
        "schema": "dio.document_studio_commercial_job.v1",
        "job_id": job_id,
        "product_code": service["product_code"],
        "service_name": service["public_name"],
        "state": "intake_authorized",
        "controlled": controlled,
        "created_at": timestamp(),
        "customer": spec["customer"],
        "consents": consents,
        "source": {
            "request_path": str(request_path),
            "document_name": document_path.name,
            "document_path": str(document_path),
            "word_count": words,
            "maximum_words": maximum_words or None,
            "service": spec["service"],
            "source_language": spec["source_language"],
            "target_language": spec.get("target_language"),
        },
        "payment": {
            "required": not controlled,
            "state": "waived" if controlled else "pending_quote",
            "order_id": None,
            "amount_minor": service["price"]["amount_minor"],
            "currency": service["price"]["currency"],
            "checkout_url": None,
        },
        "studio": {"state": "not_started", "output_dir": None, "release_readiness": None, "semantic_object_id": None},
        "approval": {"state": "pending", "reviewer": None, "reviewed_at": None},
        "language_authority": {
            "required": spec["service"] in TRANSLATION_SERVICES,
            "state": "pending" if spec["service"] in TRANSLATION_SERVICES else "not_applicable",
            "target_language": spec.get("target_language") if spec["service"] in TRANSLATION_SERVICES else None,
            "qa_path": None,
            "reviewer": None,
            "approved_at": None,
        },
        "delivery": {"state": "held", "mail_intent_id": None, "released": False},
    }
    save_job(path, job)
    emit_event(event_log, "document_studio.intake_received", "info", "document_studio_job", job_id, {"controlled": controlled, "word_count": words}, job_id)
    return job


def quote_job(job_root: Path, job_id: str, edge_config_path: Path, event_log: Path) -> dict[str, Any]:
    path, job = load_job(job_root, job_id)
    if job["controlled"]:
        raise ValueError("Controlled Document Studio jobs do not create payment orders.")
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
        "state": "awaiting_payment",
        "order_id": order_id,
        "checkout_url": checkout["approval_url"],
        "provider_order_id": checkout.get("provider_order_id"),
    })
    job["state"] = "payment_pending"
    spec_path = path.parent / "QUOTE_MAIL_SPEC.json"
    source = job.get("source") or {}
    body, body_html = branded_email(
        product="document-studio",
        eyebrow="CHECKOUT READY",
        headline="Your Document Studio pilot is ready to start.",
        greeting=f"Hello {job['customer']['name']},",
        intro="Your document request passed intake review and is ready for secure checkout.",
        body=[
            "The launch pilot covers one technical edit, translation, or edit-and-translate document pack within the agreed scope.",
            "DIO Document Studio produces reviewable clean copies, visible redlines, bilingual review copies where needed, terminology notes, and QA receipts.",
            "Language outputs remain human-review candidates. Proficient review is required before release or BEAST semantic reuse.",
        ],
        reference=job_id,
        cta_label="Pay securely with PayPal",
        cta_url=checkout["approval_url"],
        caution=f"Requested lane: {source.get('service')}. Certified, sworn, or legally attested translation is outside this pilot.",
    )
    write_json(spec_path, {
        "purpose": "quote",
        "order_id": order_id,
        "job_id": job_id,
        "recipient": job["customer"]["email"],
        "subject": f"DIO Document Studio checkout ({job_id})",
        "body": body,
        "body_html": body_html,
        "attachments": [],
        "risk": "moderate",
    })
    intent = create_intent(spec_path, ROOT / "state" / "mail_intents", event_log)
    job["payment"]["quote_mail_intent_id"] = intent["mail_intent_id"]
    save_job(path, job)
    emit_event(event_log, "document_studio.quote_ready", "action", "document_studio_job", job_id, {"order_id": order_id}, job_id)
    return job


def reconcile_payment(job_root: Path, job_id: str, edge_config_path: Path, event_log: Path) -> dict[str, Any]:
    path, job = load_job(job_root, job_id)
    order_id = job["payment"].get("order_id")
    if not order_id:
        raise ValueError("Document Studio job has no commerce order.")
    config = read_config(edge_config_path)
    token = Path(config["edge_token_path"]).expanduser().read_text(encoding="utf-8").strip()
    order = edge_request(str(config["base_url"]).rstrip("/") + f"/api/dio/orders/{order_id}", token)
    metadata = order.get("metadata") or {}
    mismatches: list[str] = []
    if order.get("order_id") not in {None, order_id}:
        mismatches.append("order_id")
    if order.get("product_code") not in {None, job["product_code"]}:
        mismatches.append("product_code")
    if order.get("amount_minor") not in {None, job["payment"]["amount_minor"]}:
        mismatches.append("amount_minor")
    if order.get("currency") not in {None, job["payment"]["currency"]}:
        mismatches.append("currency")
    if metadata.get("job_id") not in {None, job_id}:
        mismatches.append("metadata.job_id")
    if mismatches:
        raise ValueError(f"Commerce order does not match the Document Studio job: {', '.join(mismatches)}")
    state = str(order.get("state") or "unknown")
    job["payment"]["state"] = state
    job["state"] = "paid_ready_for_processing" if state == "paid" else "payment_hold"
    save_job(path, job)
    emit_event(event_log, "document_studio.payment_reconciled", "info" if state == "paid" else "action", "document_studio_job", job_id, {"state": state}, job_id)
    return job


def run_job(job_root: Path, job_id: str, output_root: Path, event_log: Path) -> dict[str, Any]:
    path, job = load_job(job_root, job_id)
    if job["payment"]["state"] not in {"paid", "waived"}:
        raise ValueError("Payment must be verified or explicitly waived before Document Studio processing.")
    if not all(bool(value) for value in job["consents"].values()):
        raise ValueError("All Document Studio consents are required.")
    request_path = Path(job["source"]["request_path"])
    request = load_json(request_path)
    output_dir = run_document_studio(request, request_path, output_root)
    receipt = load_json(output_dir / "DOCUMENT_STUDIO_RECEIPT.json")
    qa = load_json(output_dir / "DOCUMENT_STUDIO_QA.json")
    ready = receipt.get("status") == "human_review_required" and bool(qa.get("automated_integrity_passed", qa.get("passed")))
    job["studio"] = {
        "state": "ready_for_human_review" if ready else "blocked",
        "output_dir": str(output_dir),
        "release_readiness": (receipt.get("release") or {}).get("release_readiness") or qa.get("release_readiness"),
        "semantic_object_id": (receipt.get("processing") or {}).get("semantic_object_id"),
    }
    job["language_authority"] = language_authority_state(job)
    job["state"] = "studio_ready" if ready else "blocked"
    save_job(path, job)
    emit_event(event_log, "document_studio.pack_ready" if ready else "document_studio.pack_blocked", "action" if ready else "critical", "document_studio_job", job_id, {**job["studio"], "language_authority": job["language_authority"]["state"]}, job_id)
    return job


def approve_job(job_root: Path, job_id: str, reviewer: str, event_log: Path) -> dict[str, Any]:
    path, job = load_job(job_root, job_id)
    if job["studio"]["state"] != "ready_for_human_review":
        raise ValueError("Only a review-ready Document Studio pack can be approved.")
    job["language_authority"] = language_authority_state(job)
    job["approval"] = {"state": "approved", "reviewer": reviewer, "reviewed_at": timestamp()}
    language_required = bool(job["language_authority"].get("required"))
    language_approved = job["language_authority"].get("state") == "approved"
    job["state"] = "approved_for_delivery" if not language_required or language_approved else "approved_pending_language_authority"
    save_job(path, job)
    emit_event(event_log, "document_studio.pack_approved", "info", "document_studio_job", job_id, {"reviewer": reviewer, "language_authority": job["language_authority"]["state"]}, job_id)
    return job


def prepare_delivery(job_root: Path, job_id: str, event_log: Path) -> dict[str, Any]:
    path, job = load_job(job_root, job_id)
    if job["approval"]["state"] != "approved":
        raise ValueError("Human approval is required before Document Studio delivery preparation.")
    job["language_authority"] = language_authority_state(job)
    if job["language_authority"].get("required") and job["language_authority"].get("state") != "approved":
        save_job(path, job)
        raise ValueError("Proficient target-language authority is required before translation delivery preparation.")
    output_dir = Path(job["studio"]["output_dir"])
    archive = output_dir / f"{job_id}_DOCUMENT_STUDIO_REVIEW_PACK.zip"
    if not archive.is_file():
        raise FileNotFoundError(archive)
    spec_path = path.parent / "DELIVERY_MAIL_SPEC.json"
    body, body_html = branded_email(
        product="document-studio",
        eyebrow="DOCUMENT PACK READY",
        headline="Your DIO Document Studio pack is ready.",
        greeting=f"Hello {job['customer']['name']},",
        intro="The attached pack has passed the DIO human review gate and is ready for your review.",
        body=[
            "Inside the pack: clean copy, redline copy, QA receipt, terminology notes, and bilingual review files where translation was requested.",
            "Use the QA receipt to inspect what changed, what remained protected, and which language-review gates still apply.",
            "Reply with requested corrections, terminology preferences, or the next document scope.",
        ],
        reference=job_id,
        cta_label="View Document Studio",
        cta_url="https://byron2306.github.io/DIO-Workflows/sites/document-studio/",
        caution="Translation outputs require proficient target-language authority before this delivery draft can be prepared. This is not a certified translation service.",
    )
    write_json(spec_path, {
        "purpose": "delivery",
        "order_id": job["payment"].get("order_id"),
        "job_id": job_id,
        "recipient": job["customer"]["email"],
        "subject": f"Your DIO Document Studio pack is ready ({job_id})",
        "body": body,
        "body_html": body_html,
        "attachments": [str(archive)],
        "risk": "moderate",
    })
    intent = create_intent(spec_path, ROOT / "state" / "mail_intents", event_log)
    job["delivery"].update({"state": "draft_ready", "mail_intent_id": intent["mail_intent_id"], "released": False})
    job["state"] = "delivery_draft_ready"
    save_job(path, job)
    emit_event(event_log, "document_studio.delivery_prepared", "action", "document_studio_job", job_id, {"mail_intent_id": intent["mail_intent_id"], "language_authority": job["language_authority"]["state"]}, job_id)
    return job


def main() -> int:
    parser = argparse.ArgumentParser(description="Operate the governed DIO Document Studio commercial lane.")
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
        print(f"Document Studio commercial lane blocked: {error}", file=sys.stderr)
        raise SystemExit(2)
