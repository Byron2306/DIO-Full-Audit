#!/usr/bin/env python3
"""Inspect, clear, and dispatch captured Outlook messages into canonical Vesper."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from presence_core.mail_attachment_clearance import (  # noqa: E402
    ClamAvCommandScanner,
    clear_mail_attachments,
    inspect_mail_attachments,
)
from presence_core.outlook_ingress import dispatch_outlook_capture  # noqa: E402


DEFAULT_STATE_ROOT = Path(os.getenv("DIO_STATE_ROOT", str(ROOT / "state"))).expanduser().resolve()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object at {path.name}.")
    return value


def _write_exclusive(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    try:
        with path.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        path.chmod(0o600)
    except FileExistsError:
        existing = _read(path)
        if existing.get("receipt_sha256") != value.get("receipt_sha256"):
            raise ValueError("An immutable receipt already exists for this Outlook capture.")


def _capture(state_root: Path, capture_id: str) -> dict[str, Any]:
    if not capture_id.startswith("MAILCAP-") or not capture_id[8:].isalnum():
        raise ValueError("Invalid Outlook capture id.")
    path = state_root / "outlook_captures" / f"{capture_id}.json"
    if not path.is_file():
        raise ValueError("Outlook capture was not found.")
    capture = _read(path)
    if capture.get("capture_id") != capture_id:
        raise ValueError("Outlook capture identity mismatch.")
    return capture


def _ingress_record(state_root: Path, capture: dict[str, Any]) -> dict[str, Any]:
    provider_message_id = str(capture.get("provider_message_id") or "")
    if not provider_message_id:
        raise ValueError("Capture has no provider message identity.")
    ingress_id = "INGRESS-" + hashlib.sha256(provider_message_id.encode("utf-8")).hexdigest()[:16].upper()
    path = state_root / "mail_ingress" / f"{ingress_id}.json"
    record = _read(path)
    if (record.get("capture_id") != capture.get("capture_id")
            or record.get("capture_content_sha256") != capture.get("content_sha256")):
        raise ValueError("Polled ingress record does not match immutable Outlook capture.")
    return record


def _safe_attachment_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "sha256": row.get("sha256"),
        "size": row.get("size"),
        "inspection_state": row.get("inspection_state"),
        "clearance_state": row.get("clearance_state"),
        "capture_state": row.get("capture_state"),
    } for row in rows]


def list_captures(state_root: Path, limit: int) -> dict[str, Any]:
    rows = []
    for path in sorted((state_root / "outlook_captures").glob("MAILCAP-*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
        capture = _read(path)
        record = {}
        try:
            record = _ingress_record(state_root, capture)
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        rows.append({
            "capture_id": capture.get("capture_id"),
            "captured_at": capture.get("captured_at"),
            "capture_state": capture.get("capture_state"),
            "routing_state": record.get("routing_state") or "needs_reconciliation",
            "attachment_count": len(record.get("attachments") or capture.get("attachments") or []),
        })
    return {"schema": "dio.outlook_ingress_queue.v1", "captures": rows, "message_bodies_emitted": False}


def inspect_capture(state_root: Path, capture_id: str) -> dict[str, Any]:
    capture = _capture(state_root, capture_id)
    record = _ingress_record(state_root, capture)
    attachments = list(record.get("attachments") or [])
    return {
        "schema": "dio.outlook_ingress_inspection.v1",
        "capture_id": capture_id,
        "capture_content_sha256": capture.get("content_sha256"),
        "provider_message_id_present": bool(capture.get("provider_message_id")),
        "provider_conversation_id_present": bool((capture.get("message") or {}).get("conversationId")),
        "sender_identity": "captured_unverified",
        "capture_state": capture.get("capture_state"),
        "subject_present": bool((capture.get("message") or {}).get("subject")),
        "body_present": bool(((capture.get("message") or {}).get("body") or {}).get("content")
                              or (capture.get("message") or {}).get("bodyPreview")),
        "attachments": _safe_attachment_rows(attachments),
        "message_body_emitted": False,
        "attachment_paths_emitted": False,
    }


def clear_attachments(state_root: Path, capture_id: str, actor_id: str) -> dict[str, Any]:
    capture = _capture(state_root, capture_id)
    record = _ingress_record(state_root, capture)
    rows = list(record.get("attachments") or [])
    if not rows:
        raise ValueError("This Outlook capture has no clearable file attachments.")
    scanner = ClamAvCommandScanner()
    inspection = inspect_mail_attachments(rows, scanner=scanner)
    inspected = inspection["attachments"]
    if any(row.get("inspection_state") != "clean" for row in inspected):
        return {
            "schema": "dio.outlook_attachment_clearance_decision.v1",
            "capture_id": capture_id,
            "state": "held",
            "reason": "one_or_more_attachments_failed_current_scan",
            "attachments": _safe_attachment_rows(inspected),
            "scanner_engine_version": scanner.engine_version,
            "scanner_signature_version": scanner.signature_version,
            "external_effects": False,
        }
    clearance = clear_mail_attachments(inspection, actor_id=actor_id)
    receipt = {
        **clearance,
        "capture_id": capture_id,
        "capture_content_sha256": capture.get("content_sha256"),
        "scanner_engine_version": scanner.engine_version,
        "scanner_signature_version": scanner.signature_version,
        "external_effects": False,
    }
    basis = dict(receipt)
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(basis, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    path = state_root / "outlook_attachment_clearances" / f"{capture_id}.json"
    _write_exclusive(path, receipt)
    return {
        "schema": "dio.outlook_attachment_clearance_decision.v1",
        "capture_id": capture_id,
        "state": "cleared_for_presence_quarantine",
        "clearance_receipt_sha256": receipt["receipt_sha256"],
        "actor_id": actor_id,
        "attachments": _safe_attachment_rows(receipt["attachments"]),
        "external_effects": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    queue = sub.add_parser("list", help="List recent captures without message content.")
    queue.add_argument("--limit", type=int, default=25)
    inspect = sub.add_parser("inspect", help="Inspect one capture and its attachment gate.")
    inspect.add_argument("capture_id")
    clear = sub.add_parser("clear-attachments", help="Re-scan and explicitly clear clean attachments.")
    clear.add_argument("capture_id")
    clear.add_argument("--actor-id", required=True)
    dispatch = sub.add_parser("dispatch", help="Bind a capture to a customer and dispatch it into Vesper.")
    dispatch.add_argument("capture_id")
    dispatch.add_argument("--session-token-file", type=Path)
    dispatch.add_argument("--operator-id")
    dispatch.add_argument("--customer-id")
    dispatch.add_argument("--binding-reason")
    dispatch.add_argument("--evidence-ref")
    dispatch.add_argument("--shared-mailbox", action="store_true")
    args = parser.parse_args()
    state_root = args.state_root.expanduser().resolve()
    try:
        if args.command == "list":
            if args.limit < 1 or args.limit > 200:
                raise ValueError("limit must be from 1 to 200")
            receipt = list_captures(state_root, args.limit)
        elif args.command == "inspect":
            receipt = inspect_capture(state_root, args.capture_id)
        elif args.command == "clear-attachments":
            if not args.actor_id.strip():
                raise ValueError("actor-id must not be blank")
            receipt = clear_attachments(state_root, args.capture_id, args.actor_id.strip())
        else:
            binding: dict[str, Any] = {"shared_mailbox": bool(args.shared_mailbox)}
            if args.session_token_file:
                token_path = args.session_token_file.expanduser().resolve()
                token = token_path.read_text(encoding="utf-8").strip()
                if not token:
                    raise ValueError("session token file is empty")
                binding["session_token"] = token
            else:
                if not args.operator_id or not args.customer_id:
                    raise ValueError("dispatch requires a signed session token or both operator-id and customer-id")
                if not args.binding_reason or not args.evidence_ref:
                    raise ValueError("operator binding requires binding-reason and evidence-ref")
                binding.update({
                    "operator_id": args.operator_id,
                    "customer_id": args.customer_id,
                    "binding_reason": args.binding_reason,
                    "evidence_ref": args.evidence_ref,
                })
            receipt = dispatch_outlook_capture(ROOT, state_root, args.capture_id, **binding)
        print(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False))
        return 0 if receipt.get("state") not in {"held", "needs_operator"} else 2
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"schema": "dio.outlook_ingress_command_error.v1", "error": str(exc)[:300],
                          "message_body_emitted": False, "secret_emitted": False}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
