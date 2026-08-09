#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.microsoft_graph.client import GraphClient, GraphError, load_config  # noqa: E402
from scripts.manage_mail_intent import DEFAULT_EVENT_LOG, write_json  # noqa: E402
from scripts.sync_outlook_mail import DEFAULT_DELTA_STATE, DEFAULT_INGRESS_DIR, pull_messages  # noqa: E402


DEFAULT_CONFIG = ROOT / "config" / "microsoft_graph.local.json"
DEFAULT_CONSUMER_STATE = ROOT / "state" / "microsoft_graph" / "webhook_consumer.json"


def timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def process_once(
    graph: GraphClient,
    queue_path: Path,
    consumer_state_path: Path,
    ingress_dir: Path,
    delta_state_path: Path,
    event_log: Path,
) -> dict[str, object]:
    lines = [line for line in queue_path.read_text(encoding="utf-8").splitlines() if line.strip()] if queue_path.exists() else []
    state = json.loads(consumer_state_path.read_text(encoding="utf-8")) if consumer_state_path.exists() else {}
    processed = int(state.get("processed_lines", 0))
    if processed > len(lines):
        processed = 0
    pending = len(lines) - processed
    if pending <= 0:
        return {"status": "idle", "pending_notifications": 0, "processed_lines": processed}
    receipt = pull_messages(graph, ingress_dir, delta_state_path, event_log)
    write_json(
        consumer_state_path,
        {
            "schema": "dio.graph_webhook_consumer.v1",
            "updated_at": timestamp(),
            "processed_lines": len(lines),
            "last_pull_receipt": receipt,
        },
    )
    return {"status": "processed", "pending_notifications": pending, "processed_lines": len(lines), "mail_pull": receipt}


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile queued Graph notifications through the mailbox delta cursor.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--consumer-state", type=Path, default=DEFAULT_CONSUMER_STATE)
    parser.add_argument("--ingress-dir", type=Path, default=DEFAULT_INGRESS_DIR)
    parser.add_argument("--delta-state", type=Path, default=DEFAULT_DELTA_STATE)
    parser.add_argument("--event-log", type=Path, default=DEFAULT_EVENT_LOG)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()
    config = load_config(args.config.resolve())
    queue_path = Path((config.get("webhook") or {}).get("queue_path", "")).expanduser()
    if not str(queue_path) or str(queue_path) == ".":
        raise GraphError("Set webhook.queue_path in the Microsoft Graph config.")
    graph = GraphClient(config)
    while True:
        result = process_once(
            graph,
            queue_path,
            args.consumer_state.resolve(),
            args.ingress_dir.resolve(),
            args.delta_state.resolve(),
            args.event_log.resolve(),
        )
        print(json.dumps(result, indent=2), flush=True)
        if not args.watch:
            return 0
        time.sleep(max(args.interval, 0.5))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GraphError as error:
        print(f"Microsoft Graph notification processing requires setup: {error}", file=sys.stderr)
        raise SystemExit(2)
