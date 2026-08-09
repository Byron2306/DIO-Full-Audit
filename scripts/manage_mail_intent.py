#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import secrets
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INTENT_DIR = ROOT / "state" / "mail_intents"
DEFAULT_EVENT_LOG = ROOT / "telemetry" / "dio_events.jsonl"


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def timestamp(value: datetime | None = None) -> str:
    return (value or now()).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=True)
            handle.write("\n")
        return
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def canonical_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def emit_event(
    event_log: Path,
    event: str,
    severity: str,
    entity_type: str,
    entity_id: str,
    data: dict[str, Any],
    correlation_id: str | None = None,
) -> dict[str, Any]:
    event_log.parent.mkdir(parents=True, exist_ok=True)
    with event_log.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.seek(0)
        lines = [line for line in handle.read().splitlines() if line.strip()]
        previous_hash = json.loads(lines[-1]).get("event_sha256") if lines else None
        payload = {
            "schema": "dio.event.v1",
            "event_id": f"EVT-{secrets.token_hex(8).upper()}",
            "event": event,
            "occurred_at": timestamp(),
            "severity": severity,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "source": "dio_mail_core",
            "correlation_id": correlation_id,
            "data": data,
            "previous_event_sha256": previous_hash,
        }
        payload["event_sha256"] = canonical_hash(payload)
        handle.seek(0, 2)
        handle.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=True) + "\n")
        handle.flush()
        fcntl.flock(handle, fcntl.LOCK_UN)
    return payload


def intent_path(intent_dir: Path, intent_id: str) -> Path:
    if not intent_id.startswith("MAIL-") or not all(char.isalnum() or char == "-" for char in intent_id):
        raise ValueError("Invalid mail intent id.")
    return intent_dir / f"{intent_id}.json"


def create_intent_from_payload(source: dict[str, Any], intent_dir: Path, event_log: Path) -> dict[str, Any]:
    created = now()
    intent_id = source.get("mail_intent_id") or f"MAIL-{secrets.token_hex(8).upper()}"
    intent = {
        "schema": "dio.mail_intent.v1",
        "mail_intent_id": intent_id,
        "direction": "outbound",
        "purpose": source.get("purpose", "other"),
        "communicative_act": source.get("communicative_act"),
        "semantic_binding": source.get("semantic_binding"),
        "lead_id": source.get("lead_id"),
        "order_id": source.get("order_id"),
        "job_id": source.get("job_id"),
        "campaign_id": source.get("campaign_id"),
        "conversation_id": source.get("conversation_id"),
        "source_message_id": source.get("source_message_id"),
        "recipient": source["recipient"],
        "subject": source["subject"],
        "body": source.get("body"),
        "body_html": source.get("body_html"),
        "body_path": source.get("body_path"),
        "attachments": source.get("attachments", []),
        "risk": source.get("risk", "routine"),
        "approval": {"required": True, "state": "pending", "approved_at": None, "expires_at": None, "token_sha256": None},
        "send_state": "draft",
        "created_at": timestamp(created),
        "updated_at": timestamp(created),
    }
    write_json(intent_path(intent_dir, intent_id), intent, exclusive=True)
    emit_event(
        event_log,
        "mail.draft_ready",
        "action",
        "mail_intent",
        intent_id,
        {
            "purpose": intent["purpose"],
            "risk": intent["risk"],
            "communicative_act": intent.get("communicative_act"),
            "semantic_binding": bool(intent.get("semantic_binding")),
        },
        intent.get("job_id"),
    )
    return intent


def create_intent(spec_path: Path, intent_dir: Path, event_log: Path) -> dict[str, Any]:
    return create_intent_from_payload(read_json(spec_path), intent_dir, event_log)


def approve_intent(intent_id: str, intent_dir: Path, event_log: Path, ttl_minutes: int) -> tuple[dict[str, Any], str]:
    path = intent_path(intent_dir, intent_id)
    intent = read_json(path)
    if intent["send_state"] in {"sent", "sending"}:
        raise ValueError(f"Intent is already {intent['send_state']}.")
    token = secrets.token_urlsafe(32)
    approved = now()
    intent["approval"].update(
        {
            "state": "approved",
            "approved_at": timestamp(approved),
            "expires_at": timestamp(approved + timedelta(minutes=ttl_minutes)),
            "token_sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
        }
    )
    intent["send_state"] = "approved"
    intent["updated_at"] = timestamp(approved)
    write_json(path, intent)
    emit_event(event_log, "mail.approval_granted", "info", "mail_intent", intent_id, {"expires_at": intent["approval"]["expires_at"]}, intent.get("job_id"))
    return intent, token


def reject_intent(intent_id: str, intent_dir: Path, event_log: Path) -> dict[str, Any]:
    path = intent_path(intent_dir, intent_id)
    intent = read_json(path)
    intent["approval"].update({"state": "rejected", "token_sha256": None, "expires_at": None})
    intent["send_state"] = "rejected"
    intent["updated_at"] = timestamp()
    write_json(path, intent)
    emit_event(event_log, "mail.rejected", "info", "mail_intent", intent_id, {}, intent.get("job_id"))
    return intent


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and approve governed DIO mail intents.")
    parser.add_argument("--intent-dir", type=Path, default=DEFAULT_INTENT_DIR)
    parser.add_argument("--event-log", type=Path, default=DEFAULT_EVENT_LOG)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("--spec", type=Path, required=True)
    approve = subparsers.add_parser("approve")
    approve.add_argument("mail_intent_id")
    approve.add_argument("--ttl-minutes", type=int, default=10)
    reject = subparsers.add_parser("reject")
    reject.add_argument("mail_intent_id")
    status = subparsers.add_parser("status")
    status.add_argument("mail_intent_id")
    args = parser.parse_args()

    if args.command == "create":
        result = create_intent(args.spec.resolve(), args.intent_dir.resolve(), args.event_log.resolve())
        print(json.dumps(result, indent=2))
    elif args.command == "approve":
        if args.ttl_minutes < 1 or args.ttl_minutes > 60:
            raise ValueError("Approval TTL must be between 1 and 60 minutes.")
        result, token = approve_intent(args.mail_intent_id, args.intent_dir.resolve(), args.event_log.resolve(), args.ttl_minutes)
        print(json.dumps({"mail_intent_id": result["mail_intent_id"], "approval_token": token, "expires_at": result["approval"]["expires_at"]}, indent=2))
    elif args.command == "reject":
        print(json.dumps(reject_intent(args.mail_intent_id, args.intent_dir.resolve(), args.event_log.resolve()), indent=2))
    else:
        print(json.dumps(read_json(intent_path(args.intent_dir.resolve(), args.mail_intent_id)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
