#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.manage_mail_intent import DEFAULT_EVENT_LOG, emit_event, write_json  # noqa: E402
from scripts.sync_dio_edge_events import DEFAULT_CONFIG, EdgeError, read_config  # noqa: E402


DEFAULT_CONSUMER_STATE = ROOT / "state" / "commerce" / "consumer.json"
DEFAULT_RECEIPT_DIR = ROOT / "state" / "commerce" / "payment_events"
DEFAULT_ORDER_DIR = ROOT / "state" / "commerce" / "orders"


def safe_component(value: Any) -> str:
    safe = re.sub(r"[^A-Za-z0-9._:-]+", "_", str(value)).replace("..", "_").strip("._")[:128]
    return safe or "unknown"


def process_once(
    queue_path: Path,
    consumer_state_path: Path,
    receipt_dir: Path,
    order_dir: Path,
    event_log: Path,
) -> dict[str, Any]:
    lines = [line for line in queue_path.read_text(encoding="utf-8").splitlines() if line.strip()] if queue_path.exists() else []
    state = json.loads(consumer_state_path.read_text(encoding="utf-8")) if consumer_state_path.exists() else {}
    processed = min(int(state.get("processed_lines", 0)), len(lines))
    pending = lines[processed:]
    if not pending:
        return {"status": "idle", "pending": 0, "processed_lines": processed}
    receipt_dir.mkdir(parents=True, exist_ok=True)
    order_dir.mkdir(parents=True, exist_ok=True)
    for line in pending:
        record = json.loads(line)
        payload = record.get("payload") or {}
        provider = str(payload.get("provider") or record.get("source") or "unknown")
        provider_event_id = str(payload.get("provider_event_id") or record.get("edge_event_id"))
        receipt_path = receipt_dir / f"{safe_component(provider)}-{safe_component(provider_event_id)}.json"
        write_json(receipt_path, record)
        os.chmod(receipt_path, 0o600)
        order_id = payload.get("order_id")
        outcome = str(payload.get("outcome") or "recorded")
        if order_id:
            order_path = order_dir / f"{safe_component(order_id)}.json"
            write_json(order_path, {
                "schema": "dio.local_commerce_order_state.v1",
                "order_id": order_id,
                "payment_state": outcome,
                "provider": provider,
                "provider_event_id": provider_event_id,
                "amount_minor": payload.get("amount_minor"),
                "currency": payload.get("currency"),
                "fulfilment_released": False,
            })
            os.chmod(order_path, 0o600)
        severity = "critical" if outcome in {"amount_mismatch", "held", "unmatched"} else "info"
        event_name = "payment.succeeded" if outcome == "paid" else f"payment.{outcome}"
        emit_event(event_log, event_name, severity, "commerce_order", str(order_id or provider_event_id), {
            "provider": provider,
            "provider_event_id": provider_event_id,
            "amount_minor": payload.get("amount_minor"),
            "currency": payload.get("currency"),
            "fulfilment_released": False,
        })
    write_json(consumer_state_path, {"schema": "dio.commerce_consumer.v1", "processed_lines": len(lines)})
    return {"status": "processed", "processed": len(pending), "processed_lines": len(lines)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize verified DIO commerce events locally without releasing fulfilment.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--consumer-state", type=Path, default=DEFAULT_CONSUMER_STATE)
    parser.add_argument("--receipt-dir", type=Path, default=DEFAULT_RECEIPT_DIR)
    parser.add_argument("--order-dir", type=Path, default=DEFAULT_ORDER_DIR)
    parser.add_argument("--event-log", type=Path, default=DEFAULT_EVENT_LOG)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()
    config = read_config(args.config.resolve())
    queue_path = Path(config["commerce_queue_path"]).expanduser()
    while True:
        print(json.dumps(process_once(
            queue_path,
            args.consumer_state.resolve(),
            args.receipt_dir.resolve(),
            args.order_dir.resolve(),
            args.event_log.resolve(),
        ), indent=2), flush=True)
        if not args.watch:
            return 0
        time.sleep(max(args.interval, 1.0))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EdgeError as error:
        print(f"DIO commerce setup required: {error}", file=sys.stderr)
        raise SystemExit(2)
