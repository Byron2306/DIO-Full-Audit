#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import hmac
import json
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.manage_mail_intent import emit_event  # noqa: E402


DEFAULT_CONFIG = ROOT / "config" / "microsoft_graph.local.json"
DEFAULT_EVENT_LOG = ROOT / "telemetry" / "dio_events.jsonl"
NOTIFICATION_PATH = "/webhooks/microsoft-graph/notifications"
LIFECYCLE_PATH = "/webhooks/microsoft-graph/lifecycle"


def load_webhook_settings(config_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    settings = config.get("webhook") or {}
    required = ("client_state_path", "queue_path")
    missing = [key for key in required if not settings.get(key)]
    if missing:
        raise ValueError(f"Microsoft Graph webhook config is missing: {', '.join(missing)}")
    return settings


def read_client_state(path: Path) -> str:
    try:
        value = path.expanduser().read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise ValueError("Graph webhook client state has not been created. Run manage_graph_subscription.py create.") from exc
    if len(value) < 32:
        raise ValueError("Graph webhook client state is invalid.")
    return value


def validate_notifications(items: list[Any], expected_state: str) -> list[dict[str, Any]]:
    if not items:
        raise ValueError("Notification payload has no value entries.")
    accepted = []
    for item in items:
        if not isinstance(item, dict) or not hmac.compare_digest(str(item.get("clientState", "")), expected_state):
            raise PermissionError("Notification clientState did not match the active subscription.")
        accepted.append({key: value for key, value in item.items() if key != "clientState"})
    return accepted


def append_queue(queue_path: Path, records: list[dict[str, Any]]) -> None:
    queue_path = queue_path.expanduser()
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    with queue_path.open("a", encoding="utf-8") as handle:
        os.chmod(queue_path, 0o600)
        fcntl.flock(handle, fcntl.LOCK_EX)
        for record in records:
            handle.write(json.dumps(record, separators=(",", ":"), ensure_ascii=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle, fcntl.LOCK_UN)


def notification_event(record: dict[str, Any], lifecycle: bool) -> tuple[str, str, str, str, dict[str, Any]]:
    if lifecycle:
        lifecycle_event = str(record.get("lifecycleEvent", "unknown"))
        severity = "critical" if lifecycle_event in {"subscriptionRemoved", "missed"} else "action"
        return (
            "graph.subscription_lifecycle",
            severity,
            "graph_subscription",
            str(record.get("subscriptionId", "unknown")),
            {"lifecycle_event": lifecycle_event, "resource": record.get("resource")},
        )
    resource_data = record.get("resourceData") or {}
    return (
        "mail.notification_received",
        "info",
        "mail_message",
        str(resource_data.get("id") or record.get("resource") or "unknown"),
        {
            "change_type": record.get("changeType"),
            "resource": record.get("resource"),
            "subscription_id": record.get("subscriptionId"),
        },
    )


def build_handler(settings: dict[str, Any], event_log: Path) -> type[BaseHTTPRequestHandler]:
    client_state_path = Path(settings["client_state_path"]).expanduser()
    queue_path = Path(settings["queue_path"]).expanduser()

    class MicrosoftGraphWebhookHandler(BaseHTTPRequestHandler):
        server_version = "DIOGraphWebhook/1.0"

        def log_message(self, format: str, *args: Any) -> None:
            print(f"[graph-webhook] {self.address_string()} {format % args}")

        def reply(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if urlsplit(self.path).path == "/health":
                self.reply(HTTPStatus.OK, b'{"status":"ready"}', "application/json; charset=utf-8")
                return
            self.reply(HTTPStatus.NOT_FOUND, b'{"error":"not_found"}', "application/json; charset=utf-8")

        def do_POST(self) -> None:
            parsed = urlsplit(self.path)
            if parsed.path not in {NOTIFICATION_PATH, LIFECYCLE_PATH}:
                self.reply(HTTPStatus.NOT_FOUND, b'{"error":"not_found"}', "application/json; charset=utf-8")
                return
            validation_token = parse_qs(parsed.query).get("validationToken", [None])[0]
            if validation_token is not None:
                self.reply(HTTPStatus.OK, validation_token.encode("utf-8"), "text/plain; charset=utf-8")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 2 or length > 1_048_576:
                    raise ValueError("Webhook payload must be between 2 bytes and 1 MiB.")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
                    raise ValueError("Webhook payload must contain a value array.")
                records = validate_notifications(payload["value"], read_client_state(client_state_path))
                lifecycle = parsed.path == LIFECYCLE_PATH
                queued = [{"schema": "dio.graph_notification.v1", "lifecycle": lifecycle, "notification": item} for item in records]
                append_queue(queue_path, queued)
                for item in records:
                    emit_event(event_log, *notification_event(item, lifecycle))
                self.reply(HTTPStatus.ACCEPTED, b'{"status":"queued"}', "application/json; charset=utf-8")
            except PermissionError as exc:
                self.reply(HTTPStatus.FORBIDDEN, json.dumps({"error": str(exc)}).encode(), "application/json; charset=utf-8")
            except (ValueError, json.JSONDecodeError) as exc:
                self.reply(HTTPStatus.BAD_REQUEST, json.dumps({"error": str(exc)}).encode(), "application/json; charset=utf-8")
            except OSError:
                self.reply(HTTPStatus.INTERNAL_SERVER_ERROR, b'{"error":"queue_unavailable"}', "application/json; charset=utf-8")

    return MicrosoftGraphWebhookHandler


def main() -> int:
    parser = argparse.ArgumentParser(description="Receive and durably queue Microsoft Graph change notifications.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--event-log", type=Path, default=DEFAULT_EVENT_LOG)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Bind locally and expose this service through a managed HTTPS reverse proxy or tunnel.")
    settings = load_webhook_settings(args.config.resolve())
    server = ThreadingHTTPServer((args.host, args.port), build_handler(settings, args.event_log.resolve()))
    print(f"DIO Graph webhook receiver: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
