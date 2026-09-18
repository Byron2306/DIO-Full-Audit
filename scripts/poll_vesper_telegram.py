#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from presence_core.signing import new_nonce, sign_body


STATE_SCHEMA = "dio.phase9.telegram_long_poll_state.v1"
CUSTODY_SCHEMA = "dio.phase9.telegram_poll_custody.v1"


class TelegramPollError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    try:
        os.chmod(temp, 0o600)
    except OSError:
        pass
    os.replace(temp, path)


def _surface_token(surface: str) -> str:
    if surface == "operator":
        token = (
            os.getenv("DIO_TELEGRAM_OPERATOR_BOT_TOKEN")
            or os.getenv("TELEGRAM_BOT_TOKEN")
            or ""
        )
    else:
        token = os.getenv("DIO_TELEGRAM_PUBLIC_BOT_TOKEN") or ""
    if not token:
        raise TelegramPollError(f"Telegram {surface} bot token is not configured")
    return token


def _surface_secret(surface: str) -> tuple[str, str]:
    if surface == "operator":
        secret = os.getenv("DIO_PRESENCE_OPERATOR_SHARED_SECRET") or ""
        key_id = "operator-edge"
    else:
        secret = os.getenv("DIO_PRESENCE_PUBLIC_SHARED_SECRET") or ""
        key_id = "public-edge"
    if len(secret) < 32:
        raise TelegramPollError(
            f"Presence {surface} shared secret must be at least 32 characters"
        )
    return secret, key_id


def _api_raw(
    token: str,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    timeout: float = 45.0,
) -> tuple[dict[str, Any], bytes]:
    encoded = urlencode(
        {
            key: json.dumps(value) if isinstance(value, (list, dict)) else str(value)
            for key, value in (params or {}).items()
        }
    ).encode("utf-8")
    request = Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=encoded,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise TelegramPollError(f"Telegram {method} failed: {exc}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TelegramPollError(f"Telegram {method} returned invalid JSON") from exc
    if payload.get("ok") is not True:
        raise TelegramPollError(
            str(payload.get("description") or f"Telegram {method} refused request")
        )
    return payload, raw


def _download_file(token: str, file_id: str) -> bytes:
    metadata, _ = _api_raw(token, "getFile", {"file_id": file_id}, timeout=20)
    file_path = str((metadata.get("result") or {}).get("file_path") or "")
    if not file_path:
        raise TelegramPollError("Telegram file did not resolve to a provider path")
    request = Request(f"https://api.telegram.org/file/bot{token}/{file_path}")
    try:
        with urlopen(request, timeout=45) as response:
            maximum = int(os.getenv("DIO_PRESENCE_MAX_ATTACHMENT_BYTES", "8388608"))
            raw = response.read(maximum + 1)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise TelegramPollError(f"Telegram file download failed: {exc}") from exc
    if len(raw) > int(os.getenv("DIO_PRESENCE_MAX_ATTACHMENT_BYTES", "8388608")):
        raise TelegramPollError("Telegram attachment exceeds local DIO size limit")
    return raw


def _start_payload(text: str) -> str | None:
    match = re.match(r"^/start(?:@[A-Za-z0-9_]+)?(?:\s+(.+))?$", text.strip())
    if not match or not match.group(1):
        return None
    value = match.group(1).strip()
    return value if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value) else None


def _attachment(
    token: str,
    message: dict[str, Any],
) -> tuple[dict[str, Any] | None, str]:
    document = message.get("document")
    if isinstance(document, dict):
        file_id = str(document.get("file_id") or "")
        data = _download_file(token, file_id)
        file_name = str(document.get("file_name") or "telegram-document")
        mime_type = str(
            document.get("mime_type")
            or mimetypes.guess_type(file_name)[0]
            or "application/octet-stream"
        )
        return {
            "provider": "telegram",
            "provider_file_id": file_id,
            "file_name": file_name,
            "mime_type": mime_type,
            "file_size": len(data),
            "sha256": _sha256(data),
            "content_b64": base64.b64encode(data).decode("ascii"),
        }, "document"

    photos = message.get("photo")
    if isinstance(photos, list) and photos:
        photo = photos[-1]
        file_id = str(photo.get("file_id") or "")
        data = _download_file(token, file_id)
        file_name = f"telegram-photo-{message.get('message_id')}.jpg"
        return {
            "provider": "telegram",
            "provider_file_id": file_id,
            "file_name": file_name,
            "mime_type": "image/jpeg",
            "file_size": len(data),
            "sha256": _sha256(data),
            "content_b64": base64.b64encode(data).decode("ascii"),
        }, "photo"

    if message.get("voice"):
        return None, "voice"
    if message.get("audio"):
        return None, "audio"
    return None, "text"


def update_to_envelope(
    update: dict[str, Any],
    *,
    token: str,
    surface: str,
    poll_sha256: str,
) -> dict[str, Any] | None:
    message = update.get("message")
    if not isinstance(message, dict):
        return None
    sender = message.get("from") or {}
    chat = message.get("chat") or {}
    external_user_id = str(sender.get("id") or "")
    chat_id = str(chat.get("id") or "")
    if not external_user_id or not chat_id:
        return None

    attachment, message_type = _attachment(token, message)
    text = str(message.get("text") or message.get("caption") or "").strip()
    if not text and message_type in {"voice", "audio"}:
        text = (
            "Voice message received. Local speech transcription is not enabled "
            "for this sovereign runtime yet."
        )
    elif not text and attachment is not None:
        text = "Attachment received for governed DIO intake."
    elif not text:
        return None

    names = [
        str(sender.get("first_name") or "").strip(),
        str(sender.get("last_name") or "").strip(),
    ]
    display_name = " ".join(value for value in names if value).strip() or None
    update_id = int(update["update_id"])
    message_id = str(message.get("message_id") or "")
    metadata = {
        "telegram_chat_id": chat_id,
        "telegram_bot_surface": surface,
        "telegram_update_id": update_id,
        "telegram_message_id": message_id,
        "telegram_start_payload": _start_payload(text),
        "provider_event_key": f"telegram:{surface}:{update_id}",
        "provider_poll_sha256": poll_sha256,
        "sovereign_local_ingress": True,
    }

    envelope: dict[str, Any] = {
        "channel": "telegram",
        "external_user_id": external_user_id,
        "display_name": display_name,
        "text": text,
        "message_type": message_type,
        "source_message_id": message_id,
        "metadata": metadata,
    }
    if attachment is not None:
        envelope["attachment"] = attachment
    return envelope


def _post_core(
    core_url: str,
    envelope: dict[str, Any],
    *,
    secret: str,
    key_id: str,
) -> dict[str, Any]:
    body = json.dumps(
        envelope,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    timestamp = str(int(time.time()))
    nonce = new_nonce()
    signature = sign_body(secret, timestamp, nonce, body)
    request = Request(
        core_url.rstrip("/") + "/api/presence/ingress",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-DIO-Presence-Signature": signature,
            "X-DIO-Presence-Timestamp": timestamp,
            "X-DIO-Presence-Nonce": nonce,
            "X-DIO-Presence-Key-Id": key_id,
        },
    )
    try:
        with urlopen(request, timeout=60) as response:
            raw = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:800]
        raise TelegramPollError(
            f"Presence Core rejected Telegram update with HTTP {exc.code}: {detail}"
        ) from exc
    except (URLError, TimeoutError) as exc:
        raise TelegramPollError(f"Presence Core unavailable: {exc}") from exc
    try:
        return json.loads(raw) if raw else {"ok": True}
    except json.JSONDecodeError as exc:
        raise TelegramPollError("Presence Core returned invalid JSON") from exc


class TelegramLongPoller:
    def __init__(
        self,
        *,
        surface: str,
        state_root: Path,
        core_url: str,
    ):
        if surface not in {"operator", "public"}:
            raise ValueError("Telegram surface must be operator or public")
        self.surface = surface
        self.state_root = Path(state_root)
        self.core_url = core_url.rstrip("/")
        self.token = _surface_token(surface)
        self.secret, self.key_id = _surface_secret(surface)
        self.state_path = (
            self.state_root
            / "provider_polling"
            / f"telegram-{surface}-state.json"
        )
        self.custody_root = (
            self.state_root
            / "provider_custody"
            / "telegram"
            / surface
        )

    def state(self) -> dict[str, Any]:
        if not self.state_path.is_file():
            return {
                "schema": STATE_SCHEMA,
                "surface": self.surface,
                "last_update_id": None,
                "updated_at": None,
            }
        value = json.loads(self.state_path.read_text(encoding="utf-8"))
        if value.get("schema") != STATE_SCHEMA or value.get("surface") != self.surface:
            raise TelegramPollError("Telegram poll state is invalid")
        return value

    def _save_state(self, update_id: int) -> None:
        _atomic_json(
            self.state_path,
            {
                "schema": STATE_SCHEMA,
                "surface": self.surface,
                "last_update_id": int(update_id),
                "updated_at": _now(),
            },
        )

    def _custody(
        self,
        raw_poll: bytes,
        updates: list[dict[str, Any]],
    ) -> str:
        digest = _sha256(raw_poll)
        directory = self.custody_root / digest[:16]
        directory.mkdir(parents=True, exist_ok=True)
        raw_path = directory / "provider-response.json"
        if not raw_path.exists():
            raw_path.write_bytes(raw_poll)
            try:
                os.chmod(raw_path, 0o600)
            except OSError:
                pass
        receipt = {
            "schema": CUSTODY_SCHEMA,
            "surface": self.surface,
            "provider_response_sha256": digest,
            "provider_response_bytes": len(raw_poll),
            "update_ids": [int(row["update_id"]) for row in updates],
            "captured_at": _now(),
            "cloudflare_used": False,
            "hf_used": False,
        }
        _atomic_json(directory / "CUSTODY.json", receipt)
        return digest

    def drop_webhook(self) -> None:
        payload, _ = _api_raw(
            self.token,
            "deleteWebhook",
            {"drop_pending_updates": "false"},
            timeout=20,
        )
        if payload.get("result") is not True:
            raise TelegramPollError("Telegram webhook was not removed")

    def poll_once(self, *, timeout_seconds: int = 25) -> dict[str, Any]:
        state = self.state()
        last = state.get("last_update_id")
        params: dict[str, Any] = {
            "timeout": max(1, min(int(timeout_seconds), 50)),
            "allowed_updates": ["message"],
        }
        if last is not None:
            params["offset"] = int(last) + 1
        payload, raw = _api_raw(
            self.token,
            "getUpdates",
            params,
            timeout=float(params["timeout"]) + 15,
        )
        updates = list(payload.get("result") or [])
        poll_sha = self._custody(raw, updates)
        processed = 0
        skipped = 0
        for update in updates:
            update_id = int(update["update_id"])
            envelope = update_to_envelope(
                update,
                token=self.token,
                surface=self.surface,
                poll_sha256=poll_sha,
            )
            if envelope is None:
                self._save_state(update_id)
                skipped += 1
                continue
            _post_core(
                self.core_url,
                envelope,
                secret=self.secret,
                key_id=self.key_id,
            )
            self._save_state(update_id)
            processed += 1
        return {
            "schema": "dio.phase9.telegram_long_poll_result.v1",
            "surface": self.surface,
            "received": len(updates),
            "processed": processed,
            "skipped": skipped,
            "provider_response_sha256": poll_sha,
            "cloudflare_used": False,
            "hf_used": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Vesper Telegram from local outbound Bot API long polling."
    )
    parser.add_argument("--surface", choices=["operator", "public"], default="operator")
    parser.add_argument(
        "--state-root",
        type=Path,
        default=ROOT / "state" / "presence",
    )
    parser.add_argument(
        "--core-url",
        default="http://127.0.0.1:8787",
    )
    parser.add_argument("--drop-webhook", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--retry-seconds", type=float, default=3.0)
    args = parser.parse_args()

    if args.core_url.rstrip("/") not in {
        "http://127.0.0.1:8787",
        "http://localhost:8787",
    } and os.getenv("DIO_PHASE9_ALLOW_REMOTE_PRESENCE_CORE") != "1":
        raise SystemExit(
            "Phase 9 Telegram poller refuses a non-local Presence Core."
        )

    poller = TelegramLongPoller(
        surface=args.surface,
        state_root=args.state_root,
        core_url=args.core_url,
    )
    if args.drop_webhook:
        poller.drop_webhook()

    while True:
        try:
            result = poller.poll_once(timeout_seconds=args.timeout)
            print(json.dumps(result, sort_keys=True), flush=True)
        except TelegramPollError as exc:
            print(
                json.dumps(
                    {
                        "schema": "dio.phase9.telegram_long_poll_error.v1",
                        "surface": args.surface,
                        "error": str(exc),
                    }
                ),
                file=sys.stderr,
                flush=True,
            )
            if args.once:
                return 2
            time.sleep(max(args.retry_seconds, 1.0))
            continue
        if args.once:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
