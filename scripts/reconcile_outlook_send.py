#!/usr/bin/env python3
"""Reconcile an ambiguous Outlook draft-send against its exact Graph message."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.microsoft_graph.client import GraphClient, load_config  # noqa: E402
from scripts.manage_mail_intent import DEFAULT_EVENT_LOG, DEFAULT_INTENT_DIR, intent_path, read_json, write_json  # noqa: E402
from presence_core.events import emit_event  # noqa: E402


def _address_rows(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(((row or {}).get("emailAddress") or {}).get("address") or "").strip().lower()
            for row in value if isinstance(row, dict)}


def reconcile(graph: GraphClient, intent_dir: Path, receipt_dir: Path, event_log: Path, mail_intent_id: str) -> dict[str, Any]:
    path = intent_path(intent_dir, mail_intent_id)
    intent = read_json(path)
    if intent.get("send_state") not in {"in_doubt", "sending"}:
        raise ValueError("Only an ambiguous Outlook send can be reconciled here.")
    draft_id = str(intent.get("provider_draft_id") or "")
    if not draft_id:
        raise ValueError("Ambiguous intent has no exact provider draft identity.")
    provider = graph.json("GET", f"/me/messages/{draft_id}?$select=id,isDraft,sentDateTime,parentFolderId,toRecipients,internetMessageId")
    if str(provider.get("id") or "") != draft_id:
        raise ValueError("Graph returned a different message identity; intent remains in doubt.")
    intended_recipient = str(intent.get("recipient") or "").strip().lower()
    if intended_recipient and intended_recipient not in _address_rows(provider.get("toRecipients")):
        raise ValueError("Graph message recipient does not match the approved intent; intent remains in doubt.")
    sent_at = str(provider.get("sentDateTime") or "").strip()
    if provider.get("isDraft") is True or not sent_at:
        return {"schema": "dio.outlook_send_reconciliation.v1", "mail_intent_id": mail_intent_id,
                "state": "still_ambiguous", "provider_message_is_draft": provider.get("isDraft"),
                "sent_timestamp_present": bool(sent_at), "automatic_retry": False, "delivery_confirmed": False}
    intent["send_state"] = "sent"
    intent["sent_at"] = sent_at
    intent["send_attempt"] = {**(intent.get("send_attempt") or {}), "state": "provider_reconciled_sent",
                              "provider_draft_id": draft_id, "provider_sent_at": sent_at,
                              "reconciled_at": sent_at, "reconciliation_required": False}
    intent.setdefault("approval", {}).update({"state": "consumed", "token_sha256": None, "expires_at": None})
    intent["updated_at"] = sent_at
    write_json(path, intent)
    receipt = {
        "schema": "dio.mail_send_receipt.v1",
        "receipt_id": f"MAIL-RECEIPT-{hashlib.sha256(f'{mail_intent_id}:{draft_id}:{sent_at}'.encode()).hexdigest()[:16].upper()}",
        "mail_intent_id": mail_intent_id,
        "provider": "microsoft_graph",
        "provider_draft_id": draft_id,
        "provider_internet_message_id": provider.get("internetMessageId"),
        "conversation_id": intent.get("conversation_id"),
        "recipient": intent.get("recipient"),
        "sent_at": sent_at,
        "provider_state": "reconciled_sent",
        "delivery_confirmed": False,
        "reconciliation_required": False,
        "approval_consumed": True,
    }
    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = receipt_dir / f"{receipt['receipt_id']}.json"
    if not receipt_path.exists():
        write_json(receipt_path, receipt, exclusive=True)
    emit_event(event_log, "mail.send_reconciled_sent", "info", "mail_intent", mail_intent_id,
               {"provider": "microsoft_graph", "receipt_id": receipt["receipt_id"],
                "delivery_confirmed": False}, intent.get("job_id"))
    return {"schema": "dio.outlook_send_reconciliation.v1", "mail_intent_id": mail_intent_id,
            "state": "sent", "receipt_id": receipt["receipt_id"], "delivery_confirmed": False,
            "automatic_retry": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mail_intent_id")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "microsoft_graph.local.json")
    parser.add_argument("--device-login", action="store_true")
    parser.add_argument("--intent-dir", type=Path, default=DEFAULT_INTENT_DIR)
    parser.add_argument("--receipt-dir", type=Path, default=ROOT / "state" / "mail_receipts")
    parser.add_argument("--event-log", type=Path, default=DEFAULT_EVENT_LOG)
    args = parser.parse_args()
    try:
        graph = GraphClient(load_config(args.config.expanduser().resolve()))
        if args.device_login:
            graph.acquire_token(interactive=True)
        result = reconcile(graph, args.intent_dir.resolve(), args.receipt_dir.resolve(), args.event_log.resolve(), args.mail_intent_id)
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0 if result.get("state") == "sent" else 2
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(json.dumps({"schema": "dio.outlook_send_reconciliation.v1", "state": "needs_reconciliation",
                          "error": str(exc)[:300], "automatic_retry": False}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
