#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from presence_core.signing import sign_body

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
            "User-Agent": "DIO-Presence-Edge-Reconciler/1.1",
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


def forward_to_core(event: dict[str, Any], core_url: str, *, replay_is_success: bool = False) -> dict[str, Any]:
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
        if replay_is_success and exc.code == 409 and "Replay detected" in detail:
            return {"ok": True, "duplicate_delivery": True}
        if 400 <= exc.code < 500:
            raise PermanentPresenceError(f"Presence Core rejected event with HTTP {exc.code}: {detail}") from exc
        raise TransientPresenceError(f"Presence Core returned HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise TransientPresenceError(f"Presence Core unavailable: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise TransientPresenceError("Presence Core returned invalid JSON.") from exc


def acknowledge(base_url: str, token: str, path: str, ids: list[int], status: str, error: str | None = None) -> dict[str, Any] | None:
    if not ids:
        return None
    payload: dict[str, Any] = {"ids": ids, "status": status}
    if error:
        payload["error"] = error[:500]
    return edge_request(base_url + path, token, method="POST", payload=payload)


def telegram_api_json(token: str, method: str, params: dict[str, str]) -> dict[str, Any]:
    data = urlencode(params).encode("utf-8")
    request = Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise TransientPresenceError(f"Telegram provider API unavailable while reconciling attachment: {exc}") from exc
    if not payload.get("ok"):
        raise PermanentPresenceError(str(payload.get("description") or "Telegram getFile failed."))
    return payload


def telegram_download_attachment(token: str, file_id: str, file_name: str, mime_type: str | None) -> dict[str, Any]:
    metadata = telegram_api_json(token, "getFile", {"file_id": file_id}).get("result") or {}
    file_path = str(metadata.get("file_path") or "")
    if not file_path:
        raise PermanentPresenceError("Telegram attachment did not resolve to a provider file path.")
    max_bytes = int(os.getenv("DIO_PRESENCE_MAX_ATTACHMENT_BYTES", "8388608"))
    request = Request(f"https://api.telegram.org/file/bot{token}/{file_path}")
    try:
        with urlopen(request, timeout=30) as response:
            declared = int(response.headers.get("content-length") or 0)
            if declared and declared > max_bytes:
                raise PermanentPresenceError(f"Telegram attachment exceeds the local Presence limit of {max_bytes} bytes.")
            data = response.read(max_bytes + 1)
    except PermanentPresenceError:
        raise
    except (HTTPError, URLError, TimeoutError) as exc:
        raise TransientPresenceError(f"Telegram attachment download failed: {exc}") from exc
    if len(data) > max_bytes:
        raise PermanentPresenceError(f"Telegram attachment exceeds the local Presence limit of {max_bytes} bytes.")
    resolved_mime = mime_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    return {
        "provider": "telegram",
        "provider_file_id": file_id,
        "file_name": file_name,
        "mime_type": resolved_mime,
        "file_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "content_b64": base64.b64encode(data).decode("ascii"),
    }


def telegram_to_envelope(event: dict[str, Any]) -> dict[str, Any]:
    body_text = event.get("body_text")
    if not isinstance(body_text, str) or not body_text:
        raise PermanentPresenceError("Telegram custody event is missing its raw provider body.")
    try:
        update = json.loads(body_text)
    except json.JSONDecodeError as exc:
        raise PermanentPresenceError("Telegram custody event contains invalid JSON.") from exc
    message = update.get("message") or update.get("edited_message")
    if not isinstance(message, dict):
        raise PermanentPresenceError("Telegram update does not contain a supported message or edited_message.")
    sender = message.get("from") or {}
    chat = message.get("chat") or {}
    external_user_id = str(sender.get("id") or "")
    chat_id = str(chat.get("id") or "")
    source_message_id = str(message.get("message_id") or "")
    if not external_user_id or not chat_id or not source_message_id:
        raise PermanentPresenceError("Telegram message is missing sender, chat, or message identity.")

    first = str(sender.get("first_name") or "").strip()
    last = str(sender.get("last_name") or "").strip()
    username = str(sender.get("username") or "").strip()
    display_name = " ".join(part for part in (first, last) if part).strip() or username or None
    text = str(message.get("text") or message.get("caption") or "").strip()
    message_type = "text"
    attachment = None
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")

    if message.get("document"):
        message_type = "document"
        document = message["document"]
        if not token:
            raise TransientPresenceError("TELEGRAM_BOT_TOKEN is required locally to reconcile Telegram attachments.")
        file_id = str(document.get("file_id") or "")
        if not file_id:
            raise PermanentPresenceError("Telegram document is missing file_id.")
        file_name = str(document.get("file_name") or "telegram-document")
        attachment = telegram_download_attachment(token, file_id, file_name, document.get("mime_type"))
        if not text:
            text = f"I uploaded a document named {file_name} and want DIO to route it."
    elif message.get("photo"):
        message_type = "photo"
        photos = message.get("photo") or []
        photo = photos[-1] if photos else {}
        if not token:
            raise TransientPresenceError("TELEGRAM_BOT_TOKEN is required locally to reconcile Telegram attachments.")
        file_id = str(photo.get("file_id") or "")
        if not file_id:
            raise PermanentPresenceError("Telegram photo is missing file_id.")
        attachment = telegram_download_attachment(token, file_id, "telegram-image.jpg", "image/jpeg")
        if not text:
            text = "I uploaded an image and want DIO to route it."
    elif message.get("voice"):
        message_type = "voice"
        voice = message["voice"]
        if not token:
            raise TransientPresenceError("TELEGRAM_BOT_TOKEN is required locally to reconcile Telegram attachments.")
        file_id = str(voice.get("file_id") or "")
        if not file_id:
            raise PermanentPresenceError("Telegram voice note is missing file_id.")
        attachment = telegram_download_attachment(token, file_id, "telegram-voice.ogg", voice.get("mime_type") or "audio/ogg")
        if not text:
            text = "I sent a voice note. Please quarantine it for human review; do not infer a transcript."
    elif not text:
        raise PermanentPresenceError("Telegram message type is not yet supported by the Presence reconciler.")

    if len(text) > 4000:
        raise PermanentPresenceError("Telegram message exceeds the Presence text limit.")
    start_payload = None
    if text.startswith("/start "):
        start_payload = text.split(" ", 1)[1].strip() or None

    return {
        "schema": "dio.presence_ingress.v2",
        "channel": "telegram",
        "external_user_id": external_user_id,
        "display_name": display_name,
        "source_message_id": source_message_id,
        "message_type": message_type,
        "text": text,
        "metadata": {
            "telegram_update_id": str(update.get("update_id") or event.get("update_id") or ""),
            "telegram_chat_id": chat_id,
            "telegram_start_payload": start_payload,
            "custody": "cloudflare_d1_provider_authenticated_transport_only",
        },
        "attachment": attachment,
    }


def locally_sign_telegram_event(event: dict[str, Any]) -> dict[str, Any]:
    secret = os.getenv("DIO_PRESENCE_OPERATOR_SHARED_SECRET", "")
    if not secret:
        raise TransientPresenceError("DIO_PRESENCE_OPERATOR_SHARED_SECRET is required locally for Telegram reconciliation.")
    envelope = telegram_to_envelope(event)
    body = json.dumps(envelope, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    timestamp = str(int(time.time()))
    update_id = str(event.get("update_id") or "unknown")
    nonce = f"tg_{update_id}_{hashlib.sha256(body).hexdigest()[:24]}"
    signature = sign_body(secret, timestamp, nonce, body)
    return {
        "key_id": "operator-edge",
        "signature": signature,
        "signed_timestamp": timestamp,
        "nonce": nonce,
        "body_text": body.decode("utf-8"),
    }


def sync_event_batch(
    *,
    events: list[dict[str, Any]],
    core_url: str,
    transform=None,
    replay_is_success: bool = False,
) -> tuple[list[int], list[int], list[int], list[str]]:
    processed: list[int] = []
    rejected: list[int] = []
    deferred: list[int] = []
    rejection_messages: list[str] = []
    for event in events:
        event_id = int(event.get("id") or 0)
        if event_id < 1:
            continue
        try:
            outgoing = transform(event) if transform else event
            forward_to_core(outgoing, core_url, replay_is_success=replay_is_success)
            processed.append(event_id)
        except PermanentPresenceError as exc:
            rejected.append(event_id)
            rejection_messages.append(f"{event_id}:{exc}")
        except TransientPresenceError:
            deferred.append(event_id)
    return processed, rejected, deferred, rejection_messages


def sync_once(config: dict[str, Any]) -> dict[str, Any]:
    token_path = Path(config["edge_token_path"]).expanduser()
    if not token_path.exists():
        raise PresenceEdgeError(f"Missing Presence edge token at {token_path}.")
    token = token_path.read_text(encoding="utf-8").strip()
    if not token:
        raise PresenceEdgeError("Presence edge token file is empty.")

    base_url = str(config["base_url"]).rstrip("/")
    core_url = str(config["core_url"])

    signed_path = str(config.get("event_api_path", "/api/presence/events"))
    signed_ack_path = str(config.get("ack_api_path", "/api/presence/events/ack"))
    signed_batch = edge_request(base_url + signed_path + "?limit=100", token)
    signed_events = signed_batch.get("events") or []
    sp, sr, sd, sm = sync_event_batch(events=signed_events, core_url=core_url)
    signed_processed_ack = acknowledge(base_url, token, signed_ack_path, sp, "processed")
    signed_rejected_ack = acknowledge(base_url, token, signed_ack_path, sr, "failed", "; ".join(sm) if sm else "presence_core_rejected")

    telegram_path = str(config.get("telegram_event_api_path", "/api/presence/telegram-events"))
    telegram_ack_path = str(config.get("telegram_ack_api_path", "/api/presence/telegram-events/ack"))
    telegram_batch = edge_request(base_url + telegram_path + "?limit=100", token)
    telegram_events = telegram_batch.get("events") or []
    tp, tr, td, tm = sync_event_batch(
        events=telegram_events,
        core_url=core_url,
        transform=locally_sign_telegram_event,
        replay_is_success=True,
    )
    telegram_processed_ack = acknowledge(base_url, token, telegram_ack_path, tp, "processed")
    telegram_rejected_ack = acknowledge(base_url, token, telegram_ack_path, tr, "failed", "; ".join(tm) if tm else "telegram_presence_rejected")

    processed = len(sp) + len(tp)
    rejected = len(sr) + len(tr)
    deferred = len(sd) + len(td)
    received = len(signed_events) + len(telegram_events)
    return {
        "schema": "dio.vesper.presence_edge_sync.v2",
        "status": "processed" if processed or rejected else ("deferred" if deferred else "idle"),
        "received": received,
        "processed": processed,
        "rejected": rejected,
        "deferred": deferred,
        "processed_acknowledged": int((signed_processed_ack or {}).get("acknowledged", 0)) + int((telegram_processed_ack or {}).get("acknowledged", 0)),
        "rejected_acknowledged": int((signed_rejected_ack or {}).get("acknowledged", 0)) + int((telegram_rejected_ack or {}).get("acknowledged", 0)),
        "signed_received": len(signed_events),
        "telegram_received": len(telegram_events),
        "telegram_processed": len(tp),
        "telegram_rejected": len(tr),
        "telegram_deferred": len(td),
        "authority": "presence_core_only",
        "cloudflare_role": "provider_authenticated_durable_transport_custody",
        "telegram_signing_authority": "local_reconciler_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Pull Cloudflare-custodied Vesper traffic into local DIO Presence Core.")
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
