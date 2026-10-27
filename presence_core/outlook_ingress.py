from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .local_ingress import LocalIngressLedger
from .outlook_identity import verify_outlook_identity
from .engine import process_envelope


def dispatch_outlook_capture(dio_root: Path, state_root: Path, capture_id: str, **binding: Any) -> dict[str, Any]:
    capture_path = Path(dio_root) / "outlook_captures" / f"{capture_id}.json"
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    message = capture.get("message") or {}
    sender = ((message.get("from") or {}).get("emailAddress") or {}).get("address")
    identity = verify_outlook_identity({"sender": sender, **binding})
    body = json.dumps({"capture_id": capture_id, "identity": identity}, sort_keys=True).encode()
    ledger = LocalIngressLedger(Path(state_root) / "outlook_ingress.sqlite")
    cached = ledger.claim(f"outlook:{capture_id}", body)
    if cached is not None:
        return cached
    text = str((message.get("body") or {}).get("content") or message.get("bodyPreview") or "")
    envelope = {"channel": "outlook", "external_user_id": identity["customer_id"], "source_message_id": capture_id, "message_type": "text", "text": text, "identity_binding": identity}
    source_root = Path(__file__).resolve().parents[1]
    response = process_envelope(envelope, source_root, {"state_root": str(Path(state_root) / "presence"), "event_log": str(Path(state_root) / "events.jsonl"), "routes_path": str(source_root / "config" / "routes.json")}, quarantined_attachments=list(capture.get("attachments") or []))
    receipt = {"schema": "dio.outlook_ingress_receipt.v1", "capture_id": capture_id, "customer_id": identity["customer_id"], "state": "completed", "canonical_envelope": envelope, "canonical_conversation_id": response.get("conversation_id"), "attachments": capture.get("attachments") or []}
    ledger.complete(f"outlook:{capture_id}", body, receipt)
    return receipt
