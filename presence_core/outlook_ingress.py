"""Replay-safe, explicitly bound Microsoft Graph ingress into Vesper Presence."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from products.attachment_intake import quarantine_attachments

from .local_ingress import LocalIngressLedger
from .outlook_identity import verify_outlook_identity
from .engine import process_envelope
from .state import conversation_id


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _ingress_record(state_root: Path, capture: dict[str, Any]) -> dict[str, Any]:
    message = capture.get("message") or {}
    provider_message_id = str(message.get("id") or "")
    if not provider_message_id:
        raise ValueError("Outlook capture has no provider message identity.")
    ingress_id = "INGRESS-" + hashlib.sha256(provider_message_id.encode("utf-8")).hexdigest()[:16].upper()
    path = Path(state_root) / "mail_ingress" / f"{ingress_id}.json"
    if not path.is_file():
        raise ValueError("Full Outlook ingress record is missing; attachment custody cannot be verified.")
    record = json.loads(path.read_text(encoding="utf-8"))
    if (str(record.get("capture_id") or "") != str(capture.get("capture_id") or "")
            or str(record.get("capture_content_sha256") or "") != str(capture.get("content_sha256") or "")):
        raise ValueError("Outlook capture does not match its polled ingress record.")
    captured = sorted(
        (str(row.get("name") or ""), str(row.get("sha256") or ""), int(row.get("size") or 0))
        for row in capture.get("attachments") or []
    )
    ingress = sorted(
        (str(row.get("name") or ""), str(row.get("sha256") or ""), int(row.get("size") or 0))
        for row in record.get("attachments") or []
    )
    if captured != ingress:
        raise ValueError("Outlook attachment metadata changed between immutable capture and ingress.")
    return record


def _cleared_customer_attachments(
    state_root: Path,
    capture: dict[str, Any],
    record: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    rows = list(record.get("attachments") or [])
    if not rows:
        return [], None
    capture_id = str(capture.get("capture_id") or "")
    receipt_path = Path(state_root) / "outlook_attachment_clearances" / f"{capture_id}.json"
    if not receipt_path.is_file():
        raise ValueError("Outlook attachments remain held; an identified clean-scan clearance is required.")
    clearance = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (clearance.get("schema") != "dio.outlook_attachment_clearance.v1"
            or str(clearance.get("capture_id") or "") != capture_id
            or str(clearance.get("capture_content_sha256") or "") != str(capture.get("content_sha256") or "")):
        raise ValueError("Outlook attachment clearance is not bound to this immutable capture.")
    cleared_rows = list(clearance.get("attachments") or [])
    expected = sorted((str(row.get("name") or ""), str(row.get("sha256") or ""), int(row.get("size") or 0)) for row in rows)
    supplied = sorted((str(row.get("name") or ""), str(row.get("sha256") or ""), int(row.get("size") or 0)) for row in cleared_rows)
    if expected != supplied or any(row.get("clearance_state") != "cleared" for row in cleared_rows):
        raise ValueError("Outlook attachment clearance does not match every captured attachment.")
    customer_sources = []
    for row in cleared_rows:
        path = Path(str(row.get("path") or ""))
        if not path.is_file():
            raise ValueError("A cleared Outlook attachment is no longer in quarantine.")
        raw = path.read_bytes()
        digest = _sha256(raw)
        if digest != str(row.get("sha256") or "").lower():
            raise ValueError("An Outlook attachment changed after scanner clearance.")
        customer_sources.append({
            "filename": str(row.get("name") or ""),
            "mime_type": str(row.get("content_type") or "application/octet-stream"),
            "role": "customer_source",
            "content_base64": base64.b64encode(raw).decode("ascii"),
        })
    return customer_sources, clearance


def _plain_message(message: dict[str, Any]) -> str:
    body = message.get("body") or {}
    content = str(body.get("content") or message.get("bodyPreview") or "")
    if str(body.get("contentType") or "").lower() != "html":
        return content
    from html.parser import HTMLParser

    class TextOnly(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.parts: list[str] = []
            self.suppressed = 0

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag.lower() in {"script", "style", "noscript"}:
                self.suppressed += 1
            elif tag.lower() in {"br", "p", "div", "li", "tr"} and not self.suppressed:
                self.parts.append("\n")

        def handle_endtag(self, tag: str) -> None:
            if tag.lower() in {"script", "style", "noscript"} and self.suppressed:
                self.suppressed -= 1
            elif tag.lower() in {"p", "div", "li", "tr"} and not self.suppressed:
                self.parts.append("\n")

        def handle_data(self, data: str) -> None:
            if not self.suppressed:
                self.parts.append(data)

    parser = TextOnly()
    parser.feed(content)
    return "\n".join(line.strip() for line in "".join(parser.parts).splitlines() if line.strip())


def dispatch_outlook_capture(
    dio_root: Path,
    state_root: Path,
    capture_id: str,
    **binding: Any,
) -> dict[str, Any]:
    dio_root = Path(dio_root).resolve()
    state_root = Path(state_root).resolve()
    capture_path = state_root / "outlook_captures" / f"{capture_id}.json"
    if not capture_path.is_file():
        raise ValueError("Outlook immutable capture was not found.")
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    if capture.get("schema") != "dio.outlook_mail_capture.v1" or capture.get("capture_state") != "captured":
        raise ValueError("Only a live captured Outlook message can enter Vesper.")
    message = capture.get("message") or {}
    sender = ((message.get("from") or {}).get("emailAddress") or {}).get("address")
    identity = verify_outlook_identity({"sender": sender, **binding})
    ingress = _ingress_record(state_root, capture)
    try:
        customer_sources, clearance = _cleared_customer_attachments(state_root, capture, ingress)
    except ValueError as exc:
        # An unscanned or mismatched attachment is a visible operator hold,
        # not a failed command and never a reason to route the message bytes.
        return {
            "schema": "dio.outlook_ingress_receipt.v2",
            "capture_id": capture_id,
            "capture_content_sha256": capture.get("content_sha256"),
            "customer_id": identity["customer_id"],
            "state": "needs_operator",
            "hold_reason": str(exc),
            "attachment_count": len(ingress.get("attachments") or []),
            "message_body_emitted": False,
            "authority_created": False,
            "external_effects": False,
        }

    external_user_id = str(identity["customer_id"])
    canonical_conversation_id = conversation_id("outlook", external_user_id)
    subject = str(message.get("subject") or "").strip()
    body_text = _plain_message(message)
    text = (f"Subject: {subject}\n\n" if subject else "") + body_text
    envelope = {
        "channel": "outlook",
        "external_user_id": external_user_id,
        "source_message_id": str(message.get("internetMessageId") or capture_id),
        "message_type": "text",
        "text": text,
        "metadata": {
            "email": str(sender or "").strip().lower(),
            "customer_id": external_user_id,
            "outlook_capture_id": capture_id,
            "outlook_provider_message_id": capture.get("provider_message_id"),
            "outlook_provider_conversation_id": message.get("conversationId"),
            "outlook_identity_binding_method": identity.get("method"),
        },
    }
    capture_body_sha256 = _sha256(_canonical({
        "capture_content_sha256": capture.get("content_sha256"),
        "body_sha256": _sha256(text.encode("utf-8")),
        "customer_id": external_user_id,
        "attachments": sorted(
            _sha256(base64.b64decode(row["content_base64"], validate=True))
            for row in customer_sources
        ),
    }))
    ledger = LocalIngressLedger(state_root / "outlook_ingress.sqlite")
    event_key = f"outlook:{capture_id}"
    cached = ledger.claim(event_key, capture_body_sha256.encode("ascii"))
    if cached is not None:
        return cached

    quarantined_attachments: list[dict[str, Any]] = []
    attachment_intake = None
    if customer_sources:
        attachment_intake = quarantine_attachments(
            customer_sources,
            output_dir=state_root,
            state_root=state_root,
            intake_id=f"OUTLOOK-{capture_id}",
        )
        for row in attachment_intake["attachments"]:
            quarantined_attachments.append({
                "attachment_id": row["attachment_id"],
                "conversation_id": canonical_conversation_id,
                "state": "quarantined",
                "sha256": row["sha256"],
                "size_bytes": row["bytes"],
                "original_file_name": row["filename"],
                "mime_type": row["declared_mime_type"],
                "source_ref": row["source_ref"],
                "safe_to_parse": False,
                "safe_to_execute": False,
                "external_effects": False,
            })

    response = process_envelope(
        envelope,
        dio_root,
        {
            "state_root": str(state_root / "presence"),
            "event_log": str(state_root / "telemetry" / "dio_events.jsonl"),
            "routes_path": str(dio_root / "config" / "routes.json"),
            "attachments": {"max_bytes": 10 * 1024 * 1024},
        },
        quarantined_attachments=quarantined_attachments,
    )
    response_case = response.get("customer_case") or {}
    receipt = {
        "schema": "dio.outlook_ingress_receipt.v2",
        "capture_id": capture_id,
        "capture_content_sha256": capture.get("content_sha256"),
        "source_body_sha256": _sha256(text.encode("utf-8")),
        "customer_id": external_user_id,
        "identity_binding_method": identity.get("method"),
        "canonical_conversation_id": response.get("conversation_id"),
        "canonical_case_id": response_case.get("case_id"),
        "case_stage": response_case.get("stage"),
        "product_id": response_case.get("product_id"),
        "attachments": {
            "count": len(quarantined_attachments),
            "attachment_ids": [row.get("attachment_id") for row in quarantined_attachments],
            "sha256": [row.get("sha256") for row in quarantined_attachments],
            "intake_id": attachment_intake.get("intake_id") if attachment_intake else None,
            "intake_state": attachment_intake.get("human_gate") if attachment_intake else "NOT_APPLICABLE",
            "clearance_actor_id": clearance.get("actor_id") if clearance else None,
        },
        "envelope_sha256": _sha256(_canonical(envelope)),
        "state": "completed",
        "authority_created": False,
        "external_effects": False,
    }
    ledger.complete(event_key, capture_body_sha256.encode("ascii"), receipt)
    receipt_dir = state_root / "outlook_ingress_receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_dir / f"{capture_id}.json"
    if not receipt_path.exists():
        receipt_path.write_bytes(_canonical(receipt) + b"\n")
        receipt_path.chmod(0o600)
    return receipt
