from __future__ import annotations

import hashlib
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

import httpx

from .authority import authorize_external_reply
from .voice import synthesize_voice


def _enabled(name: str) -> bool:
    return str(os.getenv(name, "0")).strip().lower() in {"1", "true", "yes", "on"}


def telegram_voice_reply_switch_enabled() -> bool:
    """Voice replies are opt-in even when ordinary Telegram replies are enabled."""
    return _enabled("DIO_PRESENCE_TELEGRAM_VOICE_REPLIES")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def convert_wav_to_telegram_voice(wav_path: Path, ogg_path: Path) -> dict[str, Any]:
    """Encode Pocket/Piper WAV as OGG Opus for Telegram's native voice-note surface."""
    wav_path = Path(wav_path)
    ogg_path = Path(ogg_path)
    ogg_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(wav_path),
        "-vn",
        "-ac",
        "1",
        "-c:a",
        "libopus",
        "-b:a",
        "48k",
        "-application",
        "voip",
        str(ogg_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg_not_available_for_telegram_voice") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "ffmpeg_failed").strip()[:300]
        raise RuntimeError(f"telegram_voice_encoding_failed:{detail}") from exc

    audio = ogg_path.read_bytes() if ogg_path.is_file() else b""
    if len(audio) < 32 or not audio.startswith(b"OggS"):
        raise RuntimeError("telegram_voice_encoding_not_ogg_opus")
    return {
        "schema": "dio.vesper.telegram_voice_encoding.v1",
        "source_path": str(wav_path),
        "voice_path": str(ogg_path),
        "codec": "opus",
        "container": "ogg",
        "audio_bytes": len(audio),
        "audio_sha256": _sha256_bytes(audio),
        "external_action_executed": False,
        "send_authorized": False,
        "authority_created": False,
    }


def _failed_receipt(receipt: dict[str, Any], reason: str) -> dict[str, Any]:
    failed = dict(receipt)
    failed["authorized"] = False
    failed["reasons"] = list(receipt.get("reasons") or []) + [reason]
    return failed


def _send_text(*, token: str, chat_id: str, text: str, receipt: dict[str, Any], timeout: float) -> tuple[bool, str | None, dict[str, Any]]:
    response = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text[:4096]},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        failed = _failed_receipt(receipt, "telegram_api_error")
        return False, str(payload.get("description") or "telegram_api_error"), failed
    done = dict(receipt)
    done["delivery_mode"] = "text"
    done["external_action_type"] = "telegram_reply"
    return True, None, done


def send_telegram_reply(
    envelope: dict[str, Any],
    result: dict[str, Any],
    *,
    root: Path,
    state_root: Path | None = None,
    timeout: float = 12.0,
) -> tuple[bool, str | None, dict[str, Any]]:
    """Send an already-prepared Vesper reply after the existing external reply gate.

    Voice rendering is never authority. If voice preparation fails before any Telegram
    request is attempted, the already-authorized text reply is used as a safe fallback.
    Once a voice transport request is attempted, this function never also sends text.
    """
    receipt = authorize_external_reply(envelope, result)
    if not receipt["authorized"]:
        return False, ",".join(receipt["reasons"]) or "external_reply_not_authorized", receipt

    token = str(os.getenv("TELEGRAM_BOT_TOKEN", ""))
    chat_id = str(((envelope.get("metadata") or {}).get("telegram_chat_id")) or "")
    reply = result.get("reply") or {}
    text = str(reply.get("text") or "").strip()
    if not token or not chat_id or not text:
        failed = _failed_receipt(receipt, "missing_token_chat_or_text")
        return False, "missing_token_chat_or_text", failed

    wants_voice = bool(
        telegram_voice_reply_switch_enabled()
        and reply.get("voice_eligible")
        and (reply.get("voice_plan") or {}).get("state") == "ready_for_internal_render"
    )
    if not wants_voice:
        return _send_text(token=token, chat_id=chat_id, text=text, receipt=receipt, timeout=timeout)

    plan = dict(reply.get("voice_plan") or {})
    outbox_root = Path(state_root) if state_root is not None else Path(root) / "state" / "presence"
    outbox = outbox_root / "voice_outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    stem = f"vesper-{uuid.uuid4().hex}"
    wav_path = outbox / f"{stem}.wav"
    ogg_path = outbox / f"{stem}.ogg"

    try:
        render_receipt = synthesize_voice(
            text=text,
            output_path=wav_path,
            plan=plan,
            timeout=timeout,
        )
        encoding_receipt = convert_wav_to_telegram_voice(wav_path, ogg_path)
    except Exception as exc:
        fallback = dict(receipt)
        fallback["voice_fallback_reason"] = f"voice_prepare_failed:{str(exc)[:220]}"
        return _send_text(token=token, chat_id=chat_id, text=text, receipt=fallback, timeout=timeout)

    with ogg_path.open("rb") as voice_handle:
        response = httpx.post(
            f"https://api.telegram.org/bot{token}/sendVoice",
            data={"chat_id": chat_id},
            files={"voice": ("vesper.ogg", voice_handle, "audio/ogg")},
            timeout=timeout,
        )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        failed = _failed_receipt(receipt, "telegram_voice_api_error")
        failed["delivery_mode"] = "voice"
        failed["voice_render"] = render_receipt
        failed["voice_encoding"] = encoding_receipt
        failed["external_action_type"] = "telegram_voice_reply"
        return False, str(payload.get("description") or "telegram_voice_api_error"), failed

    done = dict(receipt)
    done["delivery_mode"] = "voice"
    done["voice_render"] = render_receipt
    done["voice_encoding"] = encoding_receipt
    done["external_action_type"] = "telegram_voice_reply"
    return True, None, done
