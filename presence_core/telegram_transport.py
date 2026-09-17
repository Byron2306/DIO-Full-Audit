from __future__ import annotations

import hashlib
import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any

import httpx

from .fulfilment_release import AUTHORITY_SCHEMA
from .state import read_json, safe
from .authority import authorize_external_reply
from .voice import synthesize_voice


def _enabled(name: str) -> bool:
    return str(os.getenv(name, "0")).strip().lower() in {"1", "true", "yes", "on"}


def telegram_voice_reply_switch_enabled(
    bot_surface: str | None = None,
) -> bool:
    """Voice replies are opt-in and surface-scoped.

    Public Telegram may use the approved Vera public voice independently
    of the operator surface. The historical global switch remains a
    compatibility fallback only.
    """
    surface = str(bot_surface or "").strip().lower()

    if surface == "public":
        return _enabled(
            "DIO_PRESENCE_PUBLIC_TELEGRAM_VOICE_REPLIES"
        )

    if surface == "operator":
        return _enabled(
            "DIO_PRESENCE_OPERATOR_TELEGRAM_VOICE_REPLIES"
        )

    return _enabled(
        "DIO_PRESENCE_TELEGRAM_VOICE_REPLIES"
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalize_spoken_text(text: str) -> str:
    """Normalize display-oriented text for speech only.

    This does not change canonical reply text, pricing truth, or authority.
    """
    value = str(text or "")

    # South African rand forms:
    # R350, R 350, R1,800, R 1 800, ZAR 350
    value = re.sub(
        r"\bZAR\s+([0-9]+(?:[ ,][0-9]{3})*(?:\.\d{1,2})?)\b",
        r"\1 rand",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"(?<![A-Za-z])R\s*([0-9]+(?:[ ,][0-9]{3})*(?:\.\d{1,2})?)\b",
        r"\1 rand",
        value,
    )

    # Percent signs are often read unnaturally by TTS engines.
    value = re.sub(
        r"\b([0-9]+(?:\.\d+)?)\s*%",
        r"\1 percent",
        value,
    )

    return value


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


def _resolve_outbound_document(
    result: dict[str, Any],
    *,
    root: Path,
    state_root: Path | None = None,
) -> tuple[dict[str, Any] | None, Path | None, str | None]:
    artifact = result.get("outbound_artifact")

    if artifact in (None, {}):
        return None, None, None

    if not isinstance(artifact, dict):
        return None, None, "outbound_artifact_invalid"

    if str(artifact.get("kind") or "").strip().lower() != "document":
        return None, None, "outbound_artifact_kind_not_document"

    if str(artifact.get("release_state") or "").strip().upper() != "APPROVED":
        return None, None, "outbound_document_not_approved"

    mime_type = str(
        artifact.get("mime_type") or "application/pdf"
    ).strip().lower()

    if mime_type != "application/pdf":
        return None, None, "outbound_document_type_not_allowed"

    declared_sha = str(
        artifact.get("sha256") or ""
    ).strip().lower()

    if len(declared_sha) != 64:
        return None, None, "outbound_document_sha256_missing"

    raw_path = str(artifact.get("path") or "").strip()

    if not raw_path:
        return None, None, "outbound_document_path_missing"

    root = Path(root).resolve()

    allowed_root = (
        root
        / "state"
        / "presence"
        / "customer_cases"
        / "artifacts"
    ).resolve()

    candidate = Path(raw_path)

    if not candidate.is_absolute():
        candidate = root / candidate

    candidate = candidate.resolve()

    try:
        candidate.relative_to(allowed_root)
    except ValueError:
        return None, None, "outbound_document_path_outside_artifact_root"

    if not candidate.is_file():
        return None, None, "outbound_document_missing"

    data = candidate.read_bytes()

    max_bytes = int(
        os.getenv(
            "DIO_PRESENCE_TELEGRAM_DOCUMENT_MAX_BYTES",
            "8388608",
        )
    )

    if not data:
        return None, None, "outbound_document_empty"

    if len(data) > max_bytes:
        return None, None, "outbound_document_too_large"

    actual_sha = _sha256_bytes(data)

    if actual_sha != declared_sha:
        return None, None, "outbound_document_sha256_mismatch"

    purpose = str(
        artifact.get("purpose") or ""
    ).strip().lower()

    if purpose == "product_fulfilment":
        authority_id = str(
            artifact.get("release_authority_id") or ""
        ).strip()

        if not authority_id:
            return (
                None,
                None,
                "fulfilment_release_authority_missing",
            )

        authority_root = (
            Path(state_root).resolve()
            if state_root is not None
            else (
                root
                / "state"
                / "presence"
            ).resolve()
        )

        authority_path = (
            authority_root
            / "customer_cases"
            / "release_authorities"
            / f"{safe(authority_id)}.json"
        )

        if not authority_path.is_file():
            return (
                None,
                None,
                "fulfilment_release_authority_missing",
            )

        try:
            authority = read_json(authority_path)
        except Exception:
            return (
                None,
                None,
                "fulfilment_release_authority_invalid",
            )

        if authority.get("schema") != AUTHORITY_SCHEMA:
            return (
                None,
                None,
                "fulfilment_release_authority_invalid",
            )

        if str(
            authority.get("authority_id") or ""
        ) != authority_id:
            return (
                None,
                None,
                "fulfilment_release_authority_invalid",
            )

        if authority.get("consumed") is True:
            return (
                None,
                None,
                "fulfilment_release_authority_consumed",
            )

        if (
            authority.get(
                "fulfilment_release_authorized"
            )
            is not True
            or authority.get(
                "external_send_authorized"
            )
            is not True
        ):
            return (
                None,
                None,
                "fulfilment_release_not_authorized",
            )

        authorized_artifact = dict(
            authority.get("artifact") or {}
        )

        authorized_sha = str(
            authorized_artifact.get("sha256") or ""
        ).strip().lower()

        if authorized_sha != actual_sha:
            return (
                None,
                None,
                "fulfilment_release_sha_mismatch",
            )

        authorized_path = Path(
            str(
                authorized_artifact.get("path")
                or ""
            )
        ).resolve()

        if authorized_path != candidate:
            return (
                None,
                None,
                "fulfilment_release_path_mismatch",
            )

    normalized = dict(artifact)
    normalized["path"] = str(candidate)
    normalized["mime_type"] = mime_type
    normalized["sha256"] = actual_sha
    normalized["bytes"] = len(data)

    return normalized, candidate, None


def _send_document(
    *,
    token: str,
    chat_id: str,
    text: str,
    artifact: dict[str, Any],
    path: Path,
    receipt: dict[str, Any],
    timeout: float,
) -> tuple[bool, str | None, dict[str, Any]]:
    file_name = str(
        artifact.get("file_name")
        or path.name
    ).strip()

    with path.open("rb") as document_handle:
        response = httpx.post(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data={
                "chat_id": chat_id,
                "caption": text[:1024],
            },
            files={
                "document": (
                    file_name,
                    document_handle,
                    "application/pdf",
                )
            },
            timeout=timeout,
        )

    response.raise_for_status()
    payload = response.json()

    if not payload.get("ok"):
        failed = _failed_receipt(
            receipt,
            "telegram_document_api_error",
        )
        failed["delivery_mode"] = "document"
        return (
            False,
            str(
                payload.get("description")
                or "telegram_document_api_error"
            ),
            failed,
        )

    provider_result = payload.get("result") or {}
    provider_document = (
        provider_result.get("document") or {}
    )

    done = dict(receipt)
    done["delivery_mode"] = "document"
    done["external_action_type"] = (
        "telegram_document_reply"
    )
    done["document"] = {
        "purpose": artifact.get("purpose"),
        "file_name": file_name,
        "mime_type": "application/pdf",
        "sha256": artifact["sha256"],
        "bytes": artifact["bytes"],
        "telegram_message_id": (
            provider_result.get("message_id")
        ),
        "telegram_file_id": (
            provider_document.get("file_id")
        ),
        "release_state": artifact.get(
            "release_state"
        ),
        "authority_created": False,
    }

    return True, None, done


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

    metadata = envelope.get("metadata") or {}

    bot_surface = str(
        metadata.get("telegram_bot_surface")
        or "operator"
    ).strip().lower()

    if bot_surface == "public":
        token = str(
            os.getenv(
                "DIO_TELEGRAM_PUBLIC_BOT_TOKEN",
                "",
            )
        )

    elif bot_surface == "operator":
        token = str(
            os.getenv(
                "DIO_TELEGRAM_OPERATOR_BOT_TOKEN",
                "",
            )
            or os.getenv(
                "TELEGRAM_BOT_TOKEN",
                "",
            )
        )

    else:
        failed = _failed_receipt(
            receipt,
            "invalid_telegram_bot_surface",
        )
        return (
            False,
            "invalid_telegram_bot_surface",
            failed,
        )

    chat_id = str(
        metadata.get("telegram_chat_id")
        or ""
    )
    reply = result.get("reply") or {}
    text = str(reply.get("text") or "").strip()
    if not token or not chat_id or not text:
        failed = _failed_receipt(receipt, "missing_token_chat_or_text")
        return False, "missing_token_chat_or_text", failed

    artifact, document_path, document_error = (
        _resolve_outbound_document(
            result,
            root=Path(root),
            state_root=state_root,
        )
    )

    if document_error:
        failed = _failed_receipt(
            receipt,
            document_error,
        )
        failed["delivery_mode"] = "document"
        return False, document_error, failed

    if artifact is not None and document_path is not None:
        return _send_document(
            token=token,
            chat_id=chat_id,
            text=text,
            artifact=artifact,
            path=document_path,
            receipt=receipt,
            timeout=timeout,
        )

    wants_voice = bool(
        telegram_voice_reply_switch_enabled(
            bot_surface
        )
        and reply.get("voice_eligible")
        and (reply.get("voice_plan") or {}).get("state") == "ready_for_internal_render"
    )

    if not wants_voice:
        return _send_text(
            token=token,
            chat_id=chat_id,
            text=text,
            receipt=receipt,
            timeout=timeout,
        )

    plan = dict(reply.get("voice_plan") or {})
    outbox_root = Path(state_root) if state_root is not None else Path(root) / "state" / "presence"
    outbox = outbox_root / "voice_outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    stem = f"vesper-{uuid.uuid4().hex}"
    wav_path = outbox / f"{stem}.wav"
    ogg_path = outbox / f"{stem}.ogg"

    try:
        spoken_text = normalize_spoken_text(text)
        render_receipt = synthesize_voice(
            text=spoken_text,
            output_path=wav_path,
            plan=plan,
            timeout=timeout,
        )
        render_receipt["spoken_text_normalized"] = (
            spoken_text != text
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
