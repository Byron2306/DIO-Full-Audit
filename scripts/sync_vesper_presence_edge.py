#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "dio_presence_edge.staging.json"


class PresenceEdgeError(RuntimeError):
    pass


class PermanentPresenceError(PresenceEdgeError):
    pass


class TransientPresenceError(PresenceEdgeError):
    pass


def read_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    base_url = str(config.get("base_url", "")).rstrip("/")
    core_url = str(config.get("core_url", "http://127.0.0.1:8787")).rstrip("/")
    if not base_url.startswith("https://") or "REPLACE_" in base_url:
        raise PresenceEdgeError("Presence edge base_url must be a deployed HTTPS Worker URL.")
    if core_url not in {"http://127.0.0.1:8787", "http://localhost:8787"} and os.getenv("DIO_PRESENCE_ALLOW_REMOTE_CORE") != "1":
        raise PresenceEdgeError("Presence reconciler refuses a non-local Core unless DIO_PRESENCE_ALLOW_REMOTE_CORE=1.")
    config["base_url"] = base_url
    config["core_url"] = core_url
    return config


def edge_request(url: str, token: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8") if payload is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "DIO-Presence-Edge-Reconciler/1.0",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read())
    except HTTPError as exc:
        raise PresenceEdgeError(f"Presence edge API returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise PresenceEdgeError(f"Presence edge API unavailable: {exc}") from exc


def core_headers(event: dict[str, Any]) -> dict[str, str]:
    required = {
        "X-DIO-Presence-Signature": str(event.get("signature") or ""),
        "X-DIO-Presence-Timestamp": str(event.get("signed_timestamp") or ""),
        "X-DIO-Presence-Nonce": str(event.get("nonce") or ""),
        "X-DIO-Presence-Key-Id": str(event.get("key_id") or ""),
    }
    if any(not value for value in required.values()):
        raise PermanentPresenceError("Presence edge event is missing signed custody headers.")
    return {"Content-Type": "application/json", **required}


def forward_to_core(event: dict[str, Any], core_url: str) -> dict[str, Any]:
    body_text = event.get("body_text")
    if not isinstance(body_text, str) or not body_text:
        raise PermanentPresenceError("Presence edge event is missing the original signed body.")
    request = Request(
        core_url.rstrip("/") + "/api/presence/ingress",
        data=body_text.encode("utf-8"),
        method="POST",
        headers=core_headers(event),
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read()
            return json.loads(payload) if payload else {"ok": True}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        if 400 <= exc.code < 500:
            raise PermanentPresenceError(f"Presence Core rejected event with HTTP {exc.code}: {detail}") from exc
        raise TransientPresenceError(f"Presence Core returned HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise TransientPresenceError(f"Presence Core unavailable: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise TransientPresenceError("Presence Core returned invalid JSON.") from exc


def acknowledge(base_url: str, token: str, ids: list[int], status: str, error: str | None = None) -> dict[str, Any] | None:
    if not ids:
        return None
    payload: dict[str, Any] = {"ids": ids, "status": status}
    if error:
        payload["error"] = error[:500]
    return edge_request(base_url + "/api/presence/events/ack", token, method="POST", payload=payload)


def sync_once(config: dict[str, Any]) -> dict[str, Any]:
    token_path = Path(config["edge_token_path"]).expanduser()
    if not token_path.exists():
        raise PresenceEdgeError(f"Missing Presence edge token at {token_path}.")
    token = token_path.read_text(encoding="utf-8").strip()
    if not token:
        raise PresenceEdgeError("Presence edge token file is empty.")

    base_url = str(config["base_url"]).rstrip("/")
    event_path = str(config.get("event_api_path", "/api/presence/events"))
    batch = edge_request(base_url + event_path + "?limit=100", token)
    events = batch.get("events") or []

    processed: list[int] = []
    rejected: list[int] = []
    deferred: list[int] = []
    rejection_messages: list[str] = []

    for event in events:
        event_id = int(event.get("id") or 0)
        if event_id < 1:
            continue
        try:
            forward_to_core(event, str(config["core_url"]))
            processed.append(event_id)
        except PermanentPresenceError as exc:
            rejected.append(event_id)
            rejection_messages.append(f"{event_id}:{exc}")
        except TransientPresenceError:
            deferred.append(event_id)

    processed_ack = acknowledge(base_url, token, processed, "processed")
    rejected_ack = acknowledge(
        base_url,
        token,
        rejected,
        "failed",
        "; ".join(rejection_messages) if rejection_messages else "presence_core_rejected",
    )

    return {
        "schema": "dio.vesper.presence_edge_sync.v1",
        "status": "processed" if processed or rejected else ("deferred" if deferred else "idle"),
        "received": len(events),
        "processed": len(processed),
        "rejected": len(rejected),
        "deferred": len(deferred),
        "processed_acknowledged": int((processed_ack or {}).get("acknowledged", 0)),
        "rejected_acknowledged": int((rejected_ack or {}).get("acknowledged", 0)),
        "authority": "presence_core_only",
        "cloudflare_role": "durable_transport_custody",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Pull Cloudflare-custodied Vesper envelopes into local DIO Presence Core.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=None)
    args = parser.parse_args()
    config = read_config(args.config.resolve())
    interval = args.interval if args.interval is not None else float(config.get("poll_interval_seconds", 1.0))
    while True:
        print(json.dumps(sync_once(config), indent=2), flush=True)
        if not args.watch:
            return 0
        time.sleep(max(interval, 1.0))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PresenceEdgeError as error:
        print(f"DIO Presence edge setup required: {error}", file=sys.stderr)
        raise SystemExit(2)
