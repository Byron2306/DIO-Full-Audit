#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVENT_LOG = ROOT / "telemetry" / "dio_events.jsonl"
DEFAULT_POLICY = ROOT / "config" / "notification_policy.json"
DEFAULT_STATE = ROOT / "state" / "notifications"


def read_json(path: Path, fallback: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def message_for(event: dict[str, Any]) -> tuple[str, str]:
    event_name = str(event.get("event") or "DIO event").replace(".", " ").title()
    entity = f"{event.get('entity_type') or 'item'} {event.get('entity_id') or ''}".strip()
    return f"DIO {str(event.get('severity') or 'info').upper()}", f"{event_name}\n{entity}"


def desktop_notify(title: str, body: str) -> bool:
    if not shutil.which("notify-send") or not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        return False
    subprocess.run(["notify-send", "--app-name=DIO", title, body], check=False, timeout=5)
    return True


def ntfy_notify(url: str, token: str | None, title: str, body: str, severity: str) -> bool:
    if not url.startswith("https://"):
        return False
    headers = {"Title": title, "Priority": "urgent" if severity == "critical" else "default"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=body.encode("utf-8"), method="POST", headers=headers)
    with urlopen(request, timeout=10) as response:
        return 200 <= response.status < 300


def dispatch_once(event_log: Path, policy_path: Path, state_root: Path) -> dict[str, Any]:
    policy = read_json(policy_path, {})
    cursor_path = state_root / "cursor.json"
    feed_path = state_root / "feed.json"
    cursor = int(read_json(cursor_path, {"line": 0}).get("line", 0))
    lines = event_log.read_text(encoding="utf-8").splitlines() if event_log.exists() else []
    events = []
    for line in lines[cursor:]:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    feed = read_json(feed_path, {"schema": "dio.notification_feed.v1", "notifications": []})
    notifications = list(feed.get("notifications") or [])
    delivered = {"dashboard": 0, "desktop": 0, "ntfy": 0}
    for event in events:
        severity = str(event.get("severity") or "info")
        routes = (policy.get("severity_routes") or {}).get(severity, ["dashboard"])
        title, body = message_for(event)
        record = {
            "notification_id": event.get("event_id"),
            "severity": severity,
            "title": title,
            "body": body,
            "event": event.get("event"),
            "entity_type": event.get("entity_type"),
            "entity_id": event.get("entity_id"),
            "occurred_at": event.get("occurred_at"),
            "routes": ["dashboard"],
        }
        if "desktop" in routes and policy.get("desktop_notifications") and desktop_notify(title, body):
            record["routes"].append("desktop")
            delivered["desktop"] += 1
        ntfy = policy.get("ntfy") or {}
        if "ntfy" in routes and ntfy.get("enabled"):
            url = os.environ.get(str(ntfy.get("url_env") or "DIO_NTFY_URL"), "")
            token = os.environ.get(str(ntfy.get("token_env") or "DIO_NTFY_TOKEN"))
            if ntfy_notify(url, token, title, body, severity):
                record["routes"].append("ntfy")
                delivered["ntfy"] += 1
        notifications.insert(0, record)
        delivered["dashboard"] += 1
    write_json(feed_path, {"schema": "dio.notification_feed.v1", "notifications": notifications[:100]})
    write_json(cursor_path, {"schema": "dio.notification_cursor.v1", "line": len(lines)})
    return {"status": "processed" if events else "idle", "events": len(events), "delivered": delivered, "feed": str(feed_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Dispatch DIO ledger events through policy-controlled notification routes.")
    parser.add_argument("--event-log", type=Path, default=DEFAULT_EVENT_LOG)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE)
    args = parser.parse_args()
    print(json.dumps(dispatch_once(args.event_log.resolve(), args.policy.resolve(), args.state_root.resolve()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
