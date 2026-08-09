#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.dio_mail_branding import branded_email, product_profile  # noqa: E402
from scripts.manage_mail_intent import DEFAULT_EVENT_LOG, create_intent_from_payload, emit_event, write_json  # noqa: E402


DEFAULT_CONFIG = ROOT / "config" / "dio_edge.local.json"
DEFAULT_LEAD_ROOT = ROOT / "state" / "leads"
DEFAULT_INTENT_ROOT = ROOT / "state" / "mail_intents"


class EdgeError(RuntimeError):
    pass


def read_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    base_url = str(config.get("base_url", "")).rstrip("/")
    if not base_url.startswith("https://") or "REPLACE_" in base_url:
        raise EdgeError("Set the deployed HTTPS Worker URL in config/dio_edge.local.json.")
    return config


def edge_request(url: str, token: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "DIO-Edge-Reconciler/1.0",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read())
    except HTTPError as exc:
        raise EdgeError(f"Edge API returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise EdgeError(f"Edge API unavailable: {exc}") from exc


def append_records(queue_path: Path, records: list[dict[str, Any]]) -> int:
    if not records:
        return 0
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    with queue_path.open("a", encoding="utf-8") as handle:
        os.chmod(queue_path, 0o600)
        fcntl.flock(handle, fcntl.LOCK_EX)
        for record in records:
            handle.write(json.dumps(record, separators=(",", ":"), ensure_ascii=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle, fcntl.LOCK_UN)
    return len(records)


def append_edge_queues(config: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, int]:
    graph_records = []
    commerce_records = []
    for event in events:
        payload = event.get("payload") or {}
        if event.get("source") == "microsoft_graph":
            graph_records.append({
                "schema": "dio.graph_notification.v1",
                "lifecycle": bool(payload.get("lifecycle")),
                "notification": payload.get("notification") or {},
                "edge_event_id": event.get("id"),
                "edge_event_key": event.get("event_key"),
            })
        else:
            commerce_records.append({
                "schema": "dio.commerce_edge_event.v1",
                "edge_event_id": event.get("id"),
                "edge_event_key": event.get("event_key"),
                "source": event.get("source"),
                "event_type": event.get("event_type"),
                "received_at": event.get("received_at"),
                "payload": payload,
            })
    return {
        "graph": append_records(Path(config["graph_queue_path"]).expanduser(), graph_records),
        "commerce": append_records(Path(config["commerce_queue_path"]).expanduser(), commerce_records),
    }


def acknowledgement_message(lead_id: str, envelope: dict[str, Any]) -> tuple[str, str]:
    product_key = str(envelope.get("product") or "dio")
    profile = product_profile(product_key)
    offer = str(envelope.get("offer") or "pilot request").replace("_", " ")
    request = envelope.get("request") or {}
    summary = "\n".join(f"{str(key).replace('_', ' ').title()}: {value}" for key, value in list(request.items())[:8])
    return branded_email(
        product=product_key,
        eyebrow="REQUEST RECEIVED",
        headline=f"Your {profile['name']} request is in the DIO queue.",
        greeting="Hello,",
        intro="Thanks for reaching out. This is now a tracked DIO workflow lead, not a loose inbox note.",
        body=[
            f"Offer requested: {offer}.",
            "We will review the scope before asking for private files, payment or delivery authority.",
            "What we received:\n" + (summary or "A controlled pilot request."),
            "Reply to this email if anything needs changing. The same conversation can carry the work forward.",
        ],
        reference=lead_id,
        cta_label=f"View {profile['name']}",
        cta_url=profile["url"],
        caution="No payment, private-file processing or delivery release happens from this acknowledgement alone. A human approval gate remains in place.",
    )


def materialize_public_intakes(
    events: list[dict[str, Any]],
    lead_root: Path,
    intent_root: Path,
    event_log: Path,
) -> int:
    created = 0
    lead_root.mkdir(parents=True, exist_ok=True)
    for event in events:
        if event.get("source") != "public_intake" or event.get("event_type") != "public.intake.received":
            continue
        payload = event.get("payload") or {}
        lead_id = str(payload.get("lead_id") or "")
        envelope = payload.get("envelope") or {}
        if not lead_id or not lead_id.replace("-", "").isalnum() or envelope.get("schema") != "dio.public_intake.v1":
            raise EdgeError("Public intake event failed its local contract check.")
        lead_path = lead_root / f"{lead_id}.json"
        if lead_path.exists():
            continue
        contact = envelope.get("contact") or {}
        product = str(envelope.get("product") or "dio")
        body, body_html = acknowledgement_message(lead_id, envelope)
        intent = create_intent_from_payload(
            {
                "purpose": "lead_acknowledgement",
                "lead_id": lead_id,
                "recipient": contact.get("email"),
                "subject": f"{product_profile(product)['name']} request received [{lead_id}]",
                "body": body,
                "body_html": body_html,
                "risk": "routine",
            },
            intent_root,
            event_log,
        )
        record = {
            "schema": "dio.lead.v1",
            "lead_id": lead_id,
            "product": product,
            "offer": envelope.get("offer"),
            "contact": contact,
            "request": envelope.get("request") or {},
            "consents": envelope.get("consents") or {},
            "attribution": envelope.get("attribution") or {},
            "state": "new",
            "qualification": {"state": "pending", "decided_at": None, "decided_by": None},
            "conversation_id": None,
            "acknowledgement": {"mail_intent_id": intent["mail_intent_id"], "state": "draft_ready"},
            "created_at": event.get("received_at") or envelope.get("submitted_at"),
            "updated_at": event.get("received_at") or envelope.get("submitted_at"),
            "edge_event_id": event.get("id"),
        }
        write_json(lead_path, record, exclusive=True)
        emit_event(event_log, "lead.created", "action", "lead", lead_id, {"product": product, "offer": envelope.get("offer")}, lead_id)
        created += 1
    return created


def pull_public_leads(config: dict[str, Any], token: str, event_log: Path) -> int:
    base_url = str(config["base_url"]).rstrip("/")
    listing = edge_request(base_url + "/api/dio/leads", token)
    lead_root = Path(config.get("lead_state_path", DEFAULT_LEAD_ROOT)).expanduser()
    missing = [lead for lead in listing.get("leads") or [] if not (lead_root / f"{lead.get('lead_id')}.json").exists()]
    created = 0
    for summary in missing:
        lead_id = str(summary.get("lead_id") or "")
        detail = edge_request(base_url + f"/api/dio/leads/{lead_id}", token)
        created += materialize_public_intakes(
            [{
                "id": f"lead:{lead_id}",
                "source": "public_intake",
                "event_type": "public.intake.received",
                "received_at": detail.get("created_at"),
                "payload": {"lead_id": lead_id, "envelope": detail.get("envelope") or {}},
            }],
            lead_root,
            Path(config.get("mail_intent_path", DEFAULT_INTENT_ROOT)).expanduser(),
            event_log,
        )
    return created


def sync_once(config: dict[str, Any], event_log: Path) -> dict[str, Any]:
    base_url = str(config["base_url"]).rstrip("/")
    token_path = Path(config["edge_token_path"]).expanduser()
    if not token_path.exists():
        raise EdgeError(f"Missing edge token at {token_path}.")
    token = token_path.read_text(encoding="utf-8").strip()
    batch = edge_request(base_url + config.get("event_api_path", "/api/dio/events") + "?limit=100", token)
    events = batch.get("events") or []
    recovered_leads = pull_public_leads(config, token, event_log)
    if not events:
        return {"status": "processed" if recovered_leads else "idle", "received": 0, "queued": 0, "leads_created": recovered_leads}
    leads = recovered_leads + materialize_public_intakes(
        events,
        Path(config.get("lead_state_path", DEFAULT_LEAD_ROOT)).expanduser(),
        Path(config.get("mail_intent_path", DEFAULT_INTENT_ROOT)).expanduser(),
        event_log,
    )
    queued = append_edge_queues(config, events)
    ids = [event["id"] for event in events]
    acknowledgement = edge_request(
        base_url + config.get("ack_api_path", "/api/dio/events/ack"),
        token,
        method="POST",
        payload={"ids": ids, "status": "processed"},
    )
    emit_event(
        event_log,
        "edge.events_reconciled",
        "info",
        "edge_batch",
        str(max(ids)),
        {"received": len(events), "queued": queued, "leads_created": leads, "acknowledged": acknowledgement.get("acknowledged", 0)},
    )
    return {"status": "processed", "received": len(events), "queued": queued, "leads_created": leads, "ack": acknowledgement}


def main() -> int:
    parser = argparse.ArgumentParser(description="Pull durable Cloudflare events into the local DIO queues.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--event-log", type=Path, default=DEFAULT_EVENT_LOG)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=5.0)
    args = parser.parse_args()
    config = read_config(args.config.resolve())
    while True:
        print(json.dumps(sync_once(config, args.event_log.resolve()), indent=2), flush=True)
        if not args.watch:
            return 0
        time.sleep(max(args.interval, 1.0))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EdgeError as error:
        print(f"DIO edge setup required: {error}", file=sys.stderr)
        raise SystemExit(2)
