#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
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

from scripts.sync_vesper_presence_edge import (  # noqa: E402
    PermanentPresenceError,
    PresenceEdgeError,
    TransientPresenceError,
    forward_to_core,
    locally_sign_telegram_event,
)


DEFAULT_STATE_ROOT = ROOT / "state" / "presence" / "local_telegram"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    encoded = json.dumps(
        value,
        indent=2,
        sort_keys=True,
        ensure_ascii=True,
    ) + "\n"
    with temp.open("w", encoding="utf-8") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def token_for_surface(surface: str) -> str:
    if surface == "public":
        token = os.getenv("DIO_TELEGRAM_PUBLIC_BOT_TOKEN", "")
    elif surface == "operator":
        token = (
            os.getenv("DIO_TELEGRAM_OPERATOR_BOT_TOKEN", "")
            or os.getenv("TELEGRAM_BOT_TOKEN", "")
        )
    else:
        raise ValueError(f"unsupported Telegram surface: {surface}")
    if not token:
        raise RuntimeError(f"Telegram bot token is not configured for {surface}.")
    return token


def telegram_request_raw(
    token: str,
    method: str,
    params: dict[str, str] | None = None,
    *,
    timeout: float = 40.0,
) -> tuple[dict[str, Any], bytes]:
    request = Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=urlencode(params or {}).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "DIO-Sovereign-Telegram-Poller/1.0",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise TransientPresenceError(
            f"Telegram {method} request failed: {type(exc).__name__}: {str(exc)[:200]}"
        ) from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TransientPresenceError(
            f"Telegram {method} returned invalid JSON."
        ) from exc

    if not payload.get("ok"):
        raise TransientPresenceError(
            str(payload.get("description") or f"Telegram {method} failed.")
        )
    return payload, raw


class LocalTelegramLedger:
    def __init__(self, state_root: Path, surface: str):
        self.root = Path(state_root).resolve() / surface
        self.surface = surface
        self.state_path = self.root / "offset.json"
        self.batch_root = self.root / "batches"
        self.update_root = self.root / "updates"
        self.root.mkdir(parents=True, exist_ok=True)

    def offset(self) -> int:
        if not self.state_path.is_file():
            return 0
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            return max(0, int(payload.get("next_update_id") or 0))
        except Exception as exc:
            raise RuntimeError(
                f"Local Telegram offset state is unreadable: {self.state_path}"
            ) from exc

    def commit_offset(self, next_update_id: int) -> None:
        atomic_json(
            self.state_path,
            {
                "schema": "dio.sovereign_telegram_offset.v1",
                "surface": self.surface,
                "next_update_id": int(next_update_id),
                "updated_at": utc_now(),
                "cloudflare_required": False,
                "authority_created": False,
            },
        )

    def save_batch(self, raw: bytes, *, offset: int) -> str:
        digest = sha256_bytes(raw)
        path = self.batch_root / f"batch-{int(time.time() * 1000)}-{digest[:16]}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        atomic_json(
            path.with_suffix(".receipt.json"),
            {
                "schema": "dio.sovereign_telegram_batch_receipt.v1",
                "surface": self.surface,
                "requested_offset": int(offset),
                "provider_response_sha256": digest,
                "provider_response_bytes": len(raw),
                "captured_at": utc_now(),
                "authority_created": False,
            },
        )
        return digest

    def begin_update(
        self,
        update: dict[str, Any],
        *,
        batch_sha256: str,
    ) -> tuple[Path, bytes]:
        update_id = int(update.get("update_id") or 0)
        if update_id < 1:
            raise PermanentPresenceError("Telegram update_id is missing or invalid.")
        canonical = json.dumps(
            update,
            separators=(",", ":"),
            ensure_ascii=True,
            sort_keys=True,
        ).encode("utf-8")
        path = self.update_root / f"update-{update_id}.json"
        atomic_json(
            path,
            {
                "schema": "dio.sovereign_telegram_update_custody.v1",
                "surface": self.surface,
                "update_id": update_id,
                "provider_update_sha256": sha256_bytes(canonical),
                "provider_batch_sha256": batch_sha256,
                "provider_update": update,
                "state": "received",
                "received_at": utc_now(),
                "cloudflare_required": False,
                "authority_created": False,
            },
        )
        return path, canonical

    def finish_update(
        self,
        path: Path,
        *,
        state: str,
        detail: str | None = None,
        core_result: dict[str, Any] | None = None,
    ) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["state"] = state
        payload["completed_at"] = utc_now()
        if detail:
            payload["detail"] = detail[:1000]
        if core_result is not None:
            payload["core_receipt"] = {
                "schema": core_result.get("schema"),
                "conversation_id": core_result.get("conversation_id"),
                "role": core_result.get("role"),
                "decision_intent": ((core_result.get("decision") or {}).get("intent")),
                "executed_external_action": (
                    (core_result.get("authority") or {}).get("executed_external_action")
                ),
            }
        atomic_json(path, payload)


def ensure_polling_mode(
    token: str,
    *,
    remove_webhook: bool,
) -> dict[str, Any]:
    info, _ = telegram_request_raw(token, "getWebhookInfo", timeout=20)
    webhook = info.get("result") or {}
    url = str(webhook.get("url") or "").strip()
    if url and not remove_webhook:
        raise RuntimeError(
            "Telegram webhook is still configured. Re-run with --remove-webhook "
            "to perform the explicit Cloudflare/webhook cutover."
        )
    if url:
        deleted, _ = telegram_request_raw(
            token,
            "deleteWebhook",
            {"drop_pending_updates": "false"},
            timeout=20,
        )
        if not deleted.get("result"):
            raise RuntimeError("Telegram refused webhook removal.")
    return {
        "schema": "dio.sovereign_telegram_mode.v1",
        "webhook_removed": bool(url),
        "polling_ready": True,
        "cloudflare_required": False,
        "authority_created": False,
    }


def process_update(
    ledger: LocalTelegramLedger,
    update: dict[str, Any],
    *,
    batch_sha256: str,
    core_url: str,
) -> str:
    path, canonical = ledger.begin_update(
        update,
        batch_sha256=batch_sha256,
    )
    update_id = int(update["update_id"])
    event = {
        "id": update_id,
        "update_id": update_id,
        "bot_surface": ledger.surface,
        "body_text": canonical.decode("utf-8"),
        "custody": "local_telegram_long_poll_durable_custody",
    }

    try:
        signed = locally_sign_telegram_event(event)
        result = forward_to_core(
            signed,
            core_url,
            replay_is_success=True,
        )
    except PermanentPresenceError as exc:
        ledger.finish_update(
            path,
            state="rejected",
            detail=str(exc),
        )
        ledger.commit_offset(update_id + 1)
        return "rejected"
    except (TransientPresenceError, PresenceEdgeError) as exc:
        ledger.finish_update(
            path,
            state="deferred",
            detail=str(exc),
        )
        return "deferred"

    ledger.finish_update(
        path,
        state="processed",
        core_result=result,
    )
    ledger.commit_offset(update_id + 1)
    return "processed"


def poll_once(
    *,
    token: str,
    ledger: LocalTelegramLedger,
    core_url: str,
    long_poll_seconds: int,
) -> dict[str, Any]:
    offset = ledger.offset()
    payload, raw = telegram_request_raw(
        token,
        "getUpdates",
        {
            "offset": str(offset),
            "timeout": str(max(0, int(long_poll_seconds))),
            "allowed_updates": json.dumps(["message", "edited_message"]),
        },
        timeout=max(10.0, float(long_poll_seconds) + 10.0),
    )
    batch_sha256 = ledger.save_batch(raw, offset=offset)
    updates = payload.get("result") or []
    if not isinstance(updates, list):
        raise TransientPresenceError("Telegram getUpdates result is not a list.")

    counts = {"processed": 0, "rejected": 0, "deferred": 0}
    for update in sorted(
        (row for row in updates if isinstance(row, dict)),
        key=lambda row: int(row.get("update_id") or 0),
    ):
        update_id = int(update.get("update_id") or 0)
        if update_id < offset:
            continue
        outcome = process_update(
            ledger,
            update,
            batch_sha256=batch_sha256,
            core_url=core_url,
        )
        counts[outcome] += 1
        if outcome == "deferred":
            break

    return {
        "schema": "dio.sovereign_telegram_poll.v1",
        "surface": ledger.surface,
        "starting_offset": offset,
        "next_update_id": ledger.offset(),
        "received": len(updates),
        **counts,
        "custody": "local_disk_fsync",
        "cloudflare_required": False,
        "hf_required": False,
        "authority_created": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run DIO Telegram Presence by outbound long polling, "
            "without Cloudflare/HF ingress."
        )
    )
    parser.add_argument(
        "--surface",
        choices=["operator", "public"],
        default="operator",
    )
    parser.add_argument(
        "--core-url",
        default="http://127.0.0.1:8787",
    )
    parser.add_argument(
        "--state-root",
        type=Path,
        default=DEFAULT_STATE_ROOT,
    )
    parser.add_argument(
        "--long-poll-seconds",
        type=int,
        default=25,
    )
    parser.add_argument(
        "--remove-webhook",
        action="store_true",
        help=(
            "Explicitly remove any existing Telegram webhook before polling. "
            "Pending updates are retained."
        ),
    )
    parser.add_argument(
        "--watch",
        action="store_true",
    )
    args = parser.parse_args()

    core_url = str(args.core_url).rstrip("/")
    if core_url not in {
        "http://127.0.0.1:8787",
        "http://localhost:8787",
    } and os.getenv("DIO_PRESENCE_ALLOW_REMOTE_CORE") != "1":
        raise SystemExit(
            "Sovereign Telegram poller refuses a non-local Presence Core."
        )

    token = token_for_surface(args.surface)
    mode = ensure_polling_mode(
        token,
        remove_webhook=args.remove_webhook,
    )
    print(json.dumps(mode, indent=2), flush=True)

    ledger = LocalTelegramLedger(args.state_root, args.surface)
    while True:
        try:
            result = poll_once(
                token=token,
                ledger=ledger,
                core_url=core_url,
                long_poll_seconds=args.long_poll_seconds,
            )
            print(json.dumps(result, indent=2), flush=True)
        except TransientPresenceError as exc:
            print(
                json.dumps(
                    {
                        "schema": "dio.sovereign_telegram_poll.v1",
                        "surface": args.surface,
                        "status": "transient_error",
                        "error": str(exc)[:500],
                        "cloudflare_required": False,
                    },
                    indent=2,
                ),
                flush=True,
            )
            if not args.watch:
                return 2
            time.sleep(3.0)

        if not args.watch:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
