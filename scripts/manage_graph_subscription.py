#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.microsoft_graph.client import GraphClient, GraphError, load_config  # noqa: E402
from scripts.manage_mail_intent import write_json  # noqa: E402


DEFAULT_CONFIG = ROOT / "config" / "microsoft_graph.local.json"


def webhook_settings(config: dict[str, Any]) -> dict[str, Any]:
    settings = config.get("webhook") or {}
    for key in ("notification_url", "lifecycle_url", "client_state_path", "subscription_state_path"):
        if not settings.get(key):
            raise GraphError(f"Set webhook.{key} in the Microsoft Graph config.")
    for key in ("notification_url", "lifecycle_url"):
        parsed = urlparse(settings[key])
        if parsed.scheme != "https" or not parsed.netloc or "REPLACE_" in settings[key]:
            raise GraphError(f"webhook.{key} must be the deployed public HTTPS endpoint.")
    return settings


def client_state(path: Path) -> str:
    path = path.expanduser()
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if len(value) < 32:
            raise GraphError(f"Invalid webhook client state at {path}.")
        return value
    path.parent.mkdir(parents=True, exist_ok=True)
    value = secrets.token_urlsafe(48)
    path.write_text(value + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    return value


def expiration() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=6, hours=23)).replace(microsecond=0).isoformat()


def write_subscription_state(path: Path, result: dict[str, Any]) -> None:
    write_json(path, {"schema": "dio.graph_subscription_state.v1", "subscription": result})
    os.chmod(path, 0o600)


def redact_client_state(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key == "clientState" and item else redact_client_state(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_client_state(item) for item in value]
    return value


def create_subscription(graph: GraphClient, settings: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "changeType": "created",
        "notificationUrl": settings["notification_url"],
        "lifecycleNotificationUrl": settings["lifecycle_url"],
        "resource": "me/mailFolders('inbox')/messages",
        "expirationDateTime": expiration(),
        "clientState": client_state(Path(settings["client_state_path"])),
        "latestSupportedTlsVersion": "v1_2",
    }
    result = graph.json("POST", "/subscriptions", json=payload)
    write_subscription_state(Path(settings["subscription_state_path"]).expanduser(), result)
    return result


def renew_subscription(graph: GraphClient, settings: dict[str, Any]) -> dict[str, Any]:
    state_path = Path(settings["subscription_state_path"]).expanduser()
    if not state_path.exists():
        raise GraphError("No local subscription receipt exists. Run create first.")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    subscription_id = (state.get("subscription") or {}).get("id")
    if not subscription_id:
        raise GraphError("The local subscription receipt has no subscription id.")
    result = graph.json("PATCH", f"/subscriptions/{subscription_id}", json={"expirationDateTime": expiration()})
    write_subscription_state(state_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Create, inspect or renew the DIO Outlook webhook subscription.")
    parser.add_argument("command", choices=["create", "renew", "list", "delete"])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config = load_config(args.config.resolve())
    settings = webhook_settings(config)
    graph = GraphClient(config)
    if args.command == "create":
        result = create_subscription(graph, settings)
    elif args.command == "renew":
        result = renew_subscription(graph, settings)
    elif args.command == "list":
        result = graph.json("GET", "/subscriptions")
    else:
        state_path = Path(settings["subscription_state_path"]).expanduser()
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        subscription_id = (state.get("subscription") or {}).get("id")
        if not subscription_id:
            raise GraphError("No local subscription receipt exists.")
        graph.request("DELETE", f"/subscriptions/{subscription_id}")
        result = {"status": "deleted", "subscription_id": subscription_id}
        state_path.unlink(missing_ok=True)
    print(json.dumps(redact_client_state(result), indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GraphError as error:
        print(f"Microsoft Graph subscription setup required: {error}", file=sys.stderr)
        raise SystemExit(2)
