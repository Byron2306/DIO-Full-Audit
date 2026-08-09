#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.microsoft_graph.client import GraphClient, load_config  # noqa: E402
from commerce.semantic_judgement import assert_mail_semantic_judgement_current  # noqa: E402
from scripts.manage_mail_intent import DEFAULT_EVENT_LOG, DEFAULT_INTENT_DIR, emit_event, intent_path, read_json, write_json  # noqa: E402


DEFAULT_INGRESS_DIR = ROOT / "state" / "mail_ingress"
DEFAULT_DELTA_STATE = ROOT / "state" / "microsoft_graph" / "mail_delta.json"
MAX_SIMPLE_ATTACHMENT_BYTES = 3 * 1024 * 1024
DEFAULT_LEAD_DIR = ROOT / "state" / "leads"
DEFAULT_RECEIPT_DIR = ROOT / "state" / "mail_receipts"
DEFAULT_ATTACHMENT_DIR = ROOT / "state" / "mail_attachments"
MAX_CAPTURED_ATTACHMENT_BYTES = 10 * 1024 * 1024


def timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ingress_id(message_id: str) -> str:
    return f"INGRESS-{hashlib.sha256(message_id.encode('utf-8')).hexdigest()[:16].upper()}"


def lead_reference(subject: str) -> str | None:
    match = re.search(r"\[((?:EVIDEX|HOMS|SOPHIA|VAMP|DOCUMENT_STUDIO)-\d{8}-[A-F0-9]{10})\]", subject or "", re.IGNORECASE)
    return match.group(1).upper() if match else None


def safe_attachment_name(value: str, fallback: str) -> str:
    name = Path(str(value or "")).name
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")[:180]
    return name or fallback


def capture_message_attachments(
    graph: GraphClient,
    message_id: str,
    record_id: str,
    attachment_root: Path = DEFAULT_ATTACHMENT_DIR,
) -> list[dict[str, Any]]:
    """Capture ordinary file attachments as untrusted evidence.

    Nothing captured here is opened, executed, or promoted into product input.
    The quarantine state must be cleared by a later scanner or operator action.
    """
    page = graph.json("GET", f"/me/messages/{message_id}/attachments")
    target = attachment_root / record_id
    target.mkdir(parents=True, exist_ok=True)
    os.chmod(target, 0o700)
    receipts: list[dict[str, Any]] = []
    total = 0
    for index, attachment in enumerate(page.get("value") or []):
        provider_id = str(attachment.get("id") or "")
        kind = str(attachment.get("@odata.type") or "")
        name = safe_attachment_name(str(attachment.get("name") or ""), f"attachment-{index + 1}")
        size = int(attachment.get("size") or 0)
        receipt = {
            "provider_attachment_id": provider_id,
            "name": name,
            "content_type": attachment.get("contentType"),
            "size": size,
            "inline": bool(attachment.get("isInline")),
            "provider_type": kind,
            "trust_state": "captured_untrusted",
            "path": None,
            "sha256": None,
        }
        if receipt["inline"] or kind not in {"#microsoft.graph.fileAttachment", "microsoft.graph.fileAttachment"}:
            receipt["capture_state"] = "metadata_only"
            receipts.append(receipt)
            continue
        if size < 0 or size > MAX_CAPTURED_ATTACHMENT_BYTES or total + size > MAX_CAPTURED_ATTACHMENT_BYTES:
            receipt["capture_state"] = "held_size_limit"
            receipts.append(receipt)
            continue
        content = attachment.get("contentBytes")
        if not content and provider_id:
            detail = graph.json("GET", f"/me/messages/{message_id}/attachments/{provider_id}")
            content = detail.get("contentBytes")
        try:
            raw = base64.b64decode(str(content or ""), validate=True)
        except (ValueError, TypeError):
            receipt["capture_state"] = "capture_failed"
            receipts.append(receipt)
            continue
        if len(raw) > MAX_CAPTURED_ATTACHMENT_BYTES or total + len(raw) > MAX_CAPTURED_ATTACHMENT_BYTES:
            receipt["capture_state"] = "held_size_limit"
            receipts.append(receipt)
            continue
        path = target / name
        if path.exists() and hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(raw).digest():
            path = target / f"{path.stem}-{index + 1}{path.suffix}"
        path.write_bytes(raw)
        os.chmod(path, 0o600)
        total += len(raw)
        receipt.update({
            "capture_state": "captured_quarantined",
            "path": str(path),
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
        receipts.append(receipt)
    return receipts


def bind_lead_conversation(lead_dir: Path, lead_id: str | None, conversation_id: str | None, mail_intent_id: str | None = None) -> None:
    if not lead_id or not conversation_id:
        return
    path = lead_dir / f"{lead_id}.json"
    if not path.exists():
        return
    lead = read_json(path)
    lead["conversation_id"] = conversation_id
    lead["updated_at"] = timestamp()
    if mail_intent_id:
        lead.setdefault("acknowledgement", {})["mail_intent_id"] = mail_intent_id
        lead["acknowledgement"]["state"] = "outlook_draft_ready"
    write_json(path, lead)


def pull_messages(
    graph: GraphClient,
    ingress_dir: Path,
    delta_state_path: Path,
    event_log: Path,
) -> dict[str, Any]:
    state = read_json(delta_state_path) if delta_state_path.exists() else {}
    resource = state.get("delta_link") or (
        "/me/mailFolders/inbox/messages/delta"
        "?$select=id,conversationId,internetMessageId,subject,from,toRecipients,receivedDateTime,isRead,hasAttachments,bodyPreview,body"
        "&$top=50"
    )
    ingress_dir.mkdir(parents=True, exist_ok=True)
    received = []
    removed = []
    latest_delta = None
    while resource:
        page = graph.json("GET", resource)
        for message in page.get("value", []):
            if "@removed" in message:
                removed.append(message.get("id"))
                continue
            message_id = message["id"]
            record_id = ingress_id(message_id)
            sender = message.get("from", {}).get("emailAddress", {})
            record = {
                "schema": "dio.mail_ingress.v1",
                "mail_ingress_id": record_id,
                "provider": "microsoft_graph",
                "provider_message_id": message_id,
                "internet_message_id": message.get("internetMessageId"),
                "conversation_id": message.get("conversationId"),
                "received_at": message.get("receivedDateTime"),
                "captured_at": timestamp(),
                "sender": {"name": sender.get("name"), "address": sender.get("address")},
                "subject": message.get("subject") or "",
                "body": message.get("body", {}),
                "body_preview": message.get("bodyPreview") or "",
                "has_attachments": bool(message.get("hasAttachments")),
                "is_read": bool(message.get("isRead")),
                "routing_state": "pending_triage",
                "lead_id": lead_reference(message.get("subject") or ""),
            }
            if record["has_attachments"]:
                record["attachments"] = capture_message_attachments(graph, message_id, record_id)
            else:
                record["attachments"] = []
            path = ingress_dir / f"{record_id}.json"
            is_new = not path.exists()
            write_json(path, record)
            bind_lead_conversation(ingress_dir.parent / "leads", record["lead_id"], record["conversation_id"])
            if is_new:
                emit_event(
                    event_log,
                    "mail.received",
                    "info",
                    "mail_ingress",
                    record_id,
                    {"has_attachments": record["has_attachments"], "routing_state": record["routing_state"]},
                    message.get("conversationId"),
                )
            received.append({"mail_ingress_id": record_id, "state": "created" if is_new else "updated"})
        latest_delta = page.get("@odata.deltaLink") or latest_delta
        resource = page.get("@odata.nextLink")
    if latest_delta:
        write_json(delta_state_path, {"schema": "dio.graph_delta_state.v1", "updated_at": timestamp(), "delta_link": latest_delta})
    return {
        "schema": "dio.mail_ingress_sync_receipt.v1",
        "created_at": timestamp(),
        "received": received,
        "removed_provider_ids": removed,
        "delta_state": str(delta_state_path),
    }


def _dio_root_from_intent_dir(intent_dir: Path) -> Path:
    return intent_dir.resolve().parents[1]


def _draft_recipient_addresses(draft: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for row in draft.get("toRecipients") or []:
        address = str(((row.get("emailAddress") or {}).get("address")) or "").strip().lower()
        if address:
            values.add(address)
    return values


def _discard_draft(graph: GraphClient, draft_id: str) -> None:
    try:
        graph.request("DELETE", f"/me/messages/{draft_id}")
    except Exception:
        pass


def _create_provider_draft(graph: GraphClient, intent: dict[str, Any], body: str, body_html: str | None) -> tuple[dict[str, Any], str]:
    if intent.get("purpose") == "conversation_reply":
        source_message_id = str(intent.get("source_message_id") or "").strip()
        expected_conversation = str(intent.get("conversation_id") or "").strip()
        expected_recipient = str(intent.get("recipient") or "").strip().lower()
        if not source_message_id or not expected_conversation:
            raise ValueError("SEMANTIC_JUDGEMENT_REFUSED: conversation reply lacks its bound Graph source message or conversation.")
        draft = graph.json("POST", f"/me/messages/{source_message_id}/createReply")
        draft_id = str(draft.get("id") or "").strip()
        if not draft_id:
            raise ValueError("Microsoft Graph created a reply draft without an ID.")
        actual_conversation = str(draft.get("conversationId") or "").strip()
        recipients = _draft_recipient_addresses(draft)
        if actual_conversation != expected_conversation:
            _discard_draft(graph, draft_id)
            raise ValueError(
                "SEMANTIC_JUDGEMENT_REFUSED: Graph reply draft conversation does not match the judged conversation lineage."
            )
        if not expected_recipient or expected_recipient not in recipients:
            _discard_draft(graph, draft_id)
            raise ValueError(
                "SEMANTIC_JUDGEMENT_REFUSED: Graph reply draft recipient does not match the judged recipient."
            )
        updated = graph.json(
            "PATCH",
            f"/me/messages/{draft_id}",
            headers={"Content-Type": "application/json"},
            json={
                "subject": intent["subject"],
                "body": {"contentType": "HTML" if body_html else "Text", "content": body or ""},
            },
        )
        return (updated or draft), "createReply"

    draft = graph.json(
        "POST",
        "/me/messages",
        headers={"Content-Type": "application/json"},
        json={
            "subject": intent["subject"],
            "body": {"contentType": "HTML" if body_html else "Text", "content": body or ""},
            "toRecipients": [{"emailAddress": {"address": intent["recipient"]}}],
        },
    )
    return draft, "new_message"


def create_outlook_draft(graph: GraphClient, intent_dir: Path, event_log: Path, mail_intent_id: str) -> dict[str, Any]:
    path = intent_path(intent_dir, mail_intent_id)
    intent = read_json(path)
    if intent["direction"] != "outbound" or intent["send_state"] not in {"draft", "approved", "failed"}:
        raise ValueError(f"Mail intent cannot become a draft from state {intent['send_state']}.")
    judgement = assert_mail_semantic_judgement_current(
        _dio_root_from_intent_dir(intent_dir),
        intent,
        require_execution_ready=False,
    )
    attachments = []
    for value in intent.get("attachments") or []:
        attachment = Path(value).expanduser().resolve()
        if not attachment.is_file():
            raise FileNotFoundError(f"Mail attachment not found: {attachment}")
        if attachment.stat().st_size > MAX_SIMPLE_ATTACHMENT_BYTES:
            raise ValueError(f"Attachment exceeds the 3 MiB governed draft limit: {attachment.name}")
        attachments.append(attachment)
    body_html = intent.get("body_html")
    body = body_html or intent.get("body")
    if not body and intent.get("body_path"):
        body = Path(intent["body_path"]).expanduser().read_text(encoding="utf-8")
    draft, draft_mode = _create_provider_draft(graph, intent, body or "", body_html)
    draft_id = str(draft.get("id") or "").strip()
    if not draft_id:
        raise ValueError("Microsoft Graph created a draft without an ID.")
    draft_conversation = str(draft.get("conversationId") or "").strip() or str(intent.get("conversation_id") or "").strip()
    if intent.get("purpose") == "conversation_reply" and draft_conversation != str(intent.get("conversation_id") or ""):
        _discard_draft(graph, draft_id)
        raise ValueError("SEMANTIC_JUDGEMENT_REFUSED: provider draft escaped the judged conversation.")

    attachment_receipts = []
    for attachment in attachments:
        uploaded = graph.json(
            "POST",
            f"/me/messages/{draft_id}/attachments",
            headers={"Content-Type": "application/json"},
            json={
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": attachment.name,
                "contentType": mimetypes.guess_type(attachment.name)[0] or "application/octet-stream",
                "contentBytes": base64.b64encode(attachment.read_bytes()).decode("ascii"),
            },
        )
        attachment_receipts.append({
            "name": attachment.name,
            "size": attachment.stat().st_size,
            "sha256": hashlib.sha256(attachment.read_bytes()).hexdigest(),
            "provider_attachment_id": uploaded.get("id"),
        })
    intent["provider"] = "microsoft_graph"
    intent["provider_draft_id"] = draft_id
    intent["provider_draft_mode"] = draft_mode
    if not intent.get("conversation_id"):
        intent["conversation_id"] = draft_conversation or None
    intent["updated_at"] = timestamp()
    write_json(path, intent)
    bind_lead_conversation(intent_dir.parent / "leads", intent.get("lead_id"), intent.get("conversation_id"), mail_intent_id)
    emit_event(
        event_log,
        "mail.outlook_draft_created",
        "action",
        "mail_intent",
        mail_intent_id,
        {
            "provider": "microsoft_graph",
            "provider_draft_mode": draft_mode,
            "approval_state": intent["approval"]["state"],
            "attachment_count": len(attachment_receipts),
            "semantic_judgement_id": judgement.get("judgement_id") if judgement else None,
        },
        intent.get("job_id"),
    )
    return {
        "schema": "dio.outlook_draft_receipt.v2" if judgement else "dio.outlook_draft_receipt.v1",
        "created_at": timestamp(),
        "mail_intent_id": mail_intent_id,
        "provider_draft_id": draft_id,
        "provider_draft_mode": draft_mode,
        "conversation_id": intent.get("conversation_id"),
        "attachments": attachment_receipts,
        "semantic_judgement_id": judgement.get("judgement_id") if judgement else None,
        "sent": False,
        "next_gate": "operator approval; semantic judgement does not grant Mail.Send authority",
    }


def send_outlook_draft(
    graph: GraphClient,
    intent_dir: Path,
    receipt_dir: Path,
    event_log: Path,
    mail_intent_id: str,
    approval_token: str,
) -> dict[str, Any]:
    path = intent_path(intent_dir, mail_intent_id)
    intent = read_json(path)
    approval = intent.get("approval") or {}
    if intent.get("send_state") != "approved" or approval.get("state") != "approved":
        raise ValueError("SEND_AUTHORITY_REFUSED: mail intent is not approved.")
    expected = str(approval.get("token_sha256") or "")
    actual = hashlib.sha256(approval_token.encode("utf-8")).hexdigest()
    try:
        expires_at = datetime.fromisoformat(str(approval.get("expires_at") or "").replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("SEND_AUTHORITY_REFUSED: approval lease has no valid expiry.") from exc
    if not expected or not secrets.compare_digest(actual, expected):
        raise ValueError("SEND_AUTHORITY_REFUSED: approval lease is invalid.")
    if datetime.now(timezone.utc) >= expires_at:
        raise ValueError("SEND_AUTHORITY_REFUSED: approval lease expired.")
    judgement = assert_mail_semantic_judgement_current(
        _dio_root_from_intent_dir(intent_dir),
        intent,
        require_execution_ready=True,
    )
    draft_id = intent.get("provider_draft_id")
    if not draft_id:
        raise ValueError("SEND_AUTHORITY_REFUSED: exact Outlook draft is missing.")
    intent["send_state"] = "sending"
    intent["updated_at"] = timestamp()
    write_json(path, intent)
    try:
        graph.json("POST", f"/me/messages/{draft_id}/send")
    except Exception as exc:
        intent["send_state"] = "failed"
        intent["approval"].update({"state": "consumed", "token_sha256": None, "expires_at": None})
        intent["last_error"] = str(exc)
        intent["updated_at"] = timestamp()
        write_json(path, intent)
        emit_event(event_log, "mail.send_failed", "critical", "mail_intent", mail_intent_id, {"provider": "microsoft_graph"}, intent.get("job_id"))
        raise
    sent_at = timestamp()
    intent["send_state"] = "sent"
    intent["sent_at"] = sent_at
    intent["updated_at"] = sent_at
    intent["approval"].update({"state": "consumed", "token_sha256": None, "expires_at": None})
    write_json(path, intent)
    receipt = {
        "schema": "dio.mail_send_receipt.v2" if judgement else "dio.mail_send_receipt.v1",
        "receipt_id": f"MAIL-RECEIPT-{hashlib.sha256(f'{mail_intent_id}:{sent_at}'.encode()).hexdigest()[:16].upper()}",
        "mail_intent_id": mail_intent_id,
        "provider": "microsoft_graph",
        "provider_draft_id": draft_id,
        "provider_draft_mode": intent.get("provider_draft_mode"),
        "conversation_id": intent.get("conversation_id"),
        "recipient": intent.get("recipient"),
        "sent_at": sent_at,
        "approval_consumed": True,
        "semantic_judgement_id": judgement.get("judgement_id") if judgement else None,
        "semantic_judgement_verdict": judgement.get("verdict") if judgement else None,
    }
    write_json(receipt_dir / f"{receipt['receipt_id']}.json", receipt, exclusive=True)
    emit_event(
        event_log,
        "mail.sent",
        "info",
        "mail_intent",
        mail_intent_id,
        {
            "provider": "microsoft_graph",
            "receipt_id": receipt["receipt_id"],
            "semantic_judgement_id": judgement.get("judgement_id") if judgement else None,
        },
        intent.get("job_id"),
    )
    if intent.get("lead_id"):
        bind_lead_conversation(intent_dir.parent / "leads", intent["lead_id"], intent.get("conversation_id"), mail_intent_id)
        lead_path = intent_dir.parent / "leads" / f"{intent['lead_id']}.json"
        if lead_path.exists():
            lead = read_json(lead_path)
            lead.setdefault("acknowledgement", {})["state"] = "sent"
            lead["updated_at"] = sent_at
            write_json(lead_path, lead)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronise Outlook ingress or create governed Outlook drafts through Microsoft Graph.")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "microsoft_graph.local.json")
    parser.add_argument("--device-login", action="store_true")
    parser.add_argument("--event-log", type=Path, default=DEFAULT_EVENT_LOG)
    subparsers = parser.add_subparsers(dest="command", required=True)
    pull = subparsers.add_parser("pull")
    pull.add_argument("--ingress-dir", type=Path, default=DEFAULT_INGRESS_DIR)
    pull.add_argument("--delta-state", type=Path, default=DEFAULT_DELTA_STATE)
    draft = subparsers.add_parser("draft")
    draft.add_argument("mail_intent_id")
    draft.add_argument("--intent-dir", type=Path, default=DEFAULT_INTENT_DIR)
    send = subparsers.add_parser("send")
    send.add_argument("mail_intent_id")
    send.add_argument("--approval-token", required=True)
    send.add_argument("--intent-dir", type=Path, default=DEFAULT_INTENT_DIR)
    send.add_argument("--receipt-dir", type=Path, default=DEFAULT_RECEIPT_DIR)
    args = parser.parse_args()

    graph = GraphClient(load_config(args.config.resolve()))
    graph.acquire_token(interactive=args.device_login)
    if args.command == "pull":
        receipt = pull_messages(graph, args.ingress_dir.resolve(), args.delta_state.resolve(), args.event_log.resolve())
    elif args.command == "draft":
        receipt = create_outlook_draft(graph, args.intent_dir.resolve(), args.event_log.resolve(), args.mail_intent_id)
    else:
        receipt = send_outlook_draft(graph, args.intent_dir.resolve(), args.receipt_dir.resolve(), args.event_log.resolve(), args.mail_intent_id, args.approval_token)
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
