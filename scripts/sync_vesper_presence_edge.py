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
from presence_core.voice import synthesize_voice
from presence_core.telegram_transport import normalize_spoken_text

DEFAULT_CONFIG = ROOT / "config" / "dio_presence_edge.staging.json"


class PresenceEdgeError(RuntimeError):
    pass


class PermanentPresenceError(PresenceEdgeError):
    pass


class TransientPresenceError(PresenceEdgeError):
    pass


def web_reply_outbox_dir() -> Path:
    return ROOT / "state" / "presence" / "web_reply_outbox"


def web_reply_outbox_path(event_id: int) -> Path:
    if event_id < 1:
        raise ValueError("Web reply outbox event_id must be positive.")

    return web_reply_outbox_dir() / f"event-{event_id}.json"


def save_web_reply_outbox(
    *,
    event_id: int,
    conversation_id: str,
    result: dict[str, Any],
) -> Path:
    conversation_id = str(conversation_id or "").strip()

    if event_id < 1:
        raise ValueError("Web reply outbox event_id must be positive.")

    if not conversation_id:
        raise ValueError(
            "Web reply outbox conversation_id is required."
        )

    if not isinstance(result, dict):
        raise ValueError(
            "Web reply outbox result must be an object."
        )

    directory = web_reply_outbox_dir()
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = web_reply_outbox_path(event_id)
    temp_path = path.with_suffix(".json.tmp")

    payload = {
        "schema":
            "dio.vesper.web_reply_outbox.v1",
        "event_id":
            event_id,
        "conversation_id":
            conversation_id,
        "result":
            result,
    }

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )

    with temp_path.open(
        "w",
        encoding="utf-8",
    ) as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())

    os.replace(
        temp_path,
        path,
    )

    return path


def load_web_reply_outbox(
    event_id: int,
) -> dict[str, Any] | None:
    path = web_reply_outbox_path(event_id)

    if not path.exists():
        return None

    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ) as exc:
        raise PermanentPresenceError(
            "Web reply outbox record is unreadable."
        ) from exc

    if (
        payload.get("schema")
        != "dio.vesper.web_reply_outbox.v1"
        or int(payload.get("event_id") or 0)
        != event_id
        or not str(
            payload.get("conversation_id") or ""
        ).strip()
        or not isinstance(
            payload.get("result"),
            dict,
        )
    ):
        raise PermanentPresenceError(
            "Web reply outbox record is invalid."
        )

    return payload


def delete_web_reply_outbox(
    event_id: int,
) -> bool:
    path = web_reply_outbox_path(event_id)

    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


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


def cleanup_web_reply_outbox_after_ack(
    event_ids: list[int],
    ack: dict[str, Any] | None,
) -> list[int]:
    if not event_ids:
        return []

    acknowledged = int(
        (ack or {}).get(
            "acknowledged",
            0,
        )
    )

    if acknowledged != len(event_ids):
        return []

    deleted = []

    for event_id in event_ids:
        if delete_web_reply_outbox(
            event_id
        ):
            deleted.append(event_id)

    return deleted


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



def transcribe_voice_with_local_whisper(
    attachment: dict[str, Any],
) -> dict[str, Any]:
    """Local read-only ASR fallback. This creates no DIO authority."""
    import tempfile

    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        raise TransientPresenceError(
            f"Local faster-whisper is unavailable: {type(exc).__name__}"
        ) from exc

    try:
        audio = base64.b64decode(
            str(attachment.get("content_b64") or ""),
            validate=True,
        )
    except Exception as exc:
        raise PermanentPresenceError(
            "Voice payload is not valid base64."
        ) from exc

    if not audio:
        raise PermanentPresenceError(
            "Voice payload is empty."
        )

    declared_sha = str(
        attachment.get("sha256") or ""
    ).lower()

    audio_sha = hashlib.sha256(audio).hexdigest()

    if declared_sha and declared_sha != audio_sha:
        raise PermanentPresenceError(
            "Voice SHA-256 mismatch before local transcription."
        )

    model_name = os.getenv(
        "DIO_PRESENCE_LOCAL_ASR_MODEL",
        "base.en",
    ).strip() or "base.en"

    mime_type = str(
        attachment.get("mime_type") or "audio/ogg"
    ).split(";", 1)[0].strip().lower()

    suffix_map = {
        "audio/ogg": ".ogg",
        "audio/webm": ".webm",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
    }

    suffix = suffix_map.get(
        mime_type,
        ".audio",
    )

    try:
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=True,
        ) as tmp:
            tmp.write(audio)
            tmp.flush()

            model = WhisperModel(
                model_name,
                device="cpu",
                compute_type="int8",
                cpu_threads=2,
                num_workers=1,
            )

            segments, info = model.transcribe(
                tmp.name,
                beam_size=1,
                vad_filter=True,
                language="en",
            )

            text = " ".join(
                segment.text.strip()
                for segment in segments
                if segment.text.strip()
            ).strip()

    except PermanentPresenceError:
        raise
    except Exception as exc:
        raise TransientPresenceError(
            "Local faster-whisper transcription failed: "
            f"{type(exc).__name__}: {str(exc)[:180]}"
        ) from exc

    if not text:
        raise TransientPresenceError(
            "Local faster-whisper returned no text."
        )

    truncated = len(text) > 4000

    if truncated:
        text = text[:4000]

    return {
        "schema":
            "dio.vesper.voice_transcription.v1",
        "text": text,
        "provider":
            "faster-whisper-local",
        "model": model_name,
        "audio_sha256": audio_sha,
        "audio_bytes": len(audio),
        "mime_type": mime_type,
        "truncated": truncated,
        "authority_created": False,
        "external_processing": False,
        "execution_authority_created": False,
        "send_authority_created": False,
        "fallback_used": True,
    }


def transcribe_voice(
    attachment: dict[str, Any],
) -> dict[str, Any]:
    """Sovereign local ASR. Remote HF transcription is disabled."""
    return transcribe_voice_with_local_whisper(
        attachment
    )


def transcribe_voice_with_hf(
    attachment: dict[str, Any],
) -> dict[str, Any]:
    """Historical compatibility name. Phase 9 forbids remote HF ASR."""
    raise PermanentPresenceError(
        "Hugging Face voice transcription is disabled by DIO Phase 9 sovereign runtime."
    )


def telegram_to_envelope(event: dict[str, Any]) -> dict[str, Any]:
    # Historical single-bot events predate durable bot_surface.
    # They belong to the existing operator surface.
    bot_surface = str(
        event.get("bot_surface") or "operator"
    ).strip().lower()

    if bot_surface not in {"public", "operator"}:
        raise PermanentPresenceError(
            "Telegram custody event has invalid bot_surface."
        )

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
    voice_source = None
    voice_transcription = None
    if bot_surface == "public":
        token = os.getenv(
            "DIO_TELEGRAM_PUBLIC_BOT_TOKEN",
            "",
        )
    else:
        token = (
            os.getenv(
                "DIO_TELEGRAM_OPERATOR_BOT_TOKEN",
                "",
            )
            or os.getenv(
                "TELEGRAM_BOT_TOKEN",
                "",
            )
        )

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
            raise TransientPresenceError("TELEGRAM_BOT_TOKEN is required locally to reconcile Telegram voice notes.")
        file_id = str(voice.get("file_id") or "")
        if not file_id:
            raise PermanentPresenceError("Telegram voice note is missing file_id.")
        downloaded_voice = telegram_download_attachment(
            token,
            file_id,
            "telegram-voice.ogg",
            voice.get("mime_type") or "audio/ogg",
        )
        voice_source = {
            "provider": downloaded_voice.get("provider"),
            "provider_file_id": downloaded_voice.get("provider_file_id"),
            "file_name": downloaded_voice.get("file_name"),
            "mime_type": downloaded_voice.get("mime_type"),
            "file_size": downloaded_voice.get("file_size"),
            "sha256": downloaded_voice.get("sha256"),
            "custody": "provider_authenticated_ephemeral_download_for_voice_input",
            "document_attachment": False,
        }
        attachment = None
        transcription_mode = os.getenv("DIO_PRESENCE_VOICE_TRANSCRIPTION", "").strip().lower()
        if transcription_mode in {"local", "whisper", "faster_whisper"}:
            voice_transcription = transcribe_voice(downloaded_voice)
            if not text:
                text = str(voice_transcription.get("text") or "").strip()
        elif transcription_mode in {"", "0", "false", "off", "none"}:
            if not text:
                text = "I sent a voice note, but local voice transcription is not enabled on this Vesper runtime."
        elif transcription_mode == "hf":
            raise PermanentPresenceError(
                "Hugging Face voice transcription is disabled by DIO Phase 9 sovereign runtime."
            )
        else:
            raise PermanentPresenceError(f"Unsupported DIO_PRESENCE_VOICE_TRANSCRIPTION mode: {transcription_mode}")
    elif not text:
        raise PermanentPresenceError("Telegram message type is not yet supported by the Presence reconciler.")

    if len(text) > 4000:
        raise PermanentPresenceError("Telegram message exceeds the Presence text limit.")
    start_payload = None
    if text.startswith("/start "):
        start_payload = text.split(" ", 1)[1].strip() or None

    metadata = {
        "telegram_update_id": str(update.get("update_id") or event.get("update_id") or ""),
        "telegram_chat_id": chat_id,
        "telegram_bot_surface": bot_surface,
        "telegram_start_payload": start_payload,
        "custody": str(
            event.get("custody")
            or "cloudflare_d1_provider_authenticated_transport_only"
        ),
    }
    if voice_source:
        metadata["voice_source"] = voice_source
    if voice_transcription:
        metadata["voice_transcription"] = voice_transcription

    return {
        "schema": "dio.presence_ingress.v2",
        "channel": "telegram",
        "external_user_id": external_user_id,
        "display_name": display_name,
        "source_message_id": source_message_id,
        "message_type": message_type,
        "text": text,
        "metadata": metadata,
        "attachment": attachment,
    }


def locally_sign_telegram_event(event: dict[str, Any]) -> dict[str, Any]:
    envelope = telegram_to_envelope(event)

    bot_surface = str(
        ((envelope.get("metadata") or {}).get(
            "telegram_bot_surface"
        ))
        or "operator"
    ).strip().lower()

    external_user_id = str(
        envelope.get("external_user_id") or ""
    )

    if bot_surface == "public":
        key_id = "public-edge"

        secret = os.getenv(
            "DIO_PRESENCE_PUBLIC_SHARED_SECRET",
            "",
        )

        if not secret:
            raise TransientPresenceError(
                "DIO_PRESENCE_PUBLIC_SHARED_SECRET "
                "is required for public Telegram "
                "reconciliation."
            )

    elif bot_surface == "operator":
        operator_ids = {
            value.strip()
            for value in os.getenv(
                "DIO_OPERATOR_TELEGRAM_IDS",
                "",
            ).split(",")
            if value.strip()
        }

        if (
            not external_user_id
            or external_user_id not in operator_ids
        ):
            raise PermanentPresenceError(
                "Telegram sender is not allowlisted "
                "for the DIO operator surface."
            )

        key_id = "operator-edge"

        secret = os.getenv(
            "DIO_PRESENCE_OPERATOR_SHARED_SECRET",
            "",
        )

        if not secret:
            raise TransientPresenceError(
                "DIO_PRESENCE_OPERATOR_SHARED_SECRET "
                "is required for operator Telegram "
                "reconciliation."
            )

    else:
        raise PermanentPresenceError(
            "Unsupported Telegram bot surface."
        )

    body = json.dumps(
        envelope,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")

    timestamp = str(int(time.time()))

    update_id = str(
        event.get("update_id") or "unknown"
    )

    nonce = (
        f"tg_{bot_surface}_{update_id}_"
        f"{hashlib.sha256(body).hexdigest()[:24]}"
    )

    signature = sign_body(
        secret,
        timestamp,
        nonce,
        body,
    )

    return {
        "key_id": key_id,
        "signature": signature,
        "signed_timestamp": timestamp,
        "nonce": nonce,
        "body_text": body.decode("utf-8"),
    }



def prepare_web_semantic_envelope(
    event: dict[str, Any],
    envelope: dict[str, Any],
) -> dict[str, Any]:
    """Convert web transport custody into semantic input before signing.

    Browser audio is transport input only. It creates no authority.
    """
    result = dict(envelope)
    metadata = dict(result.get("metadata") or {})

    web_attachment_input = metadata.get(
        "web_attachment_input"
    )

    if web_attachment_input is not None:
        if not isinstance(web_attachment_input, dict):
            raise PermanentPresenceError(
                "Web attachment custody must be an object."
            )

        file_name = str(
            web_attachment_input.get("file_name") or ""
        ).strip()

        mime_type = str(
            web_attachment_input.get("mime_type")
            or "application/octet-stream"
        ).split(";", 1)[0].strip().lower()

        content_b64 = str(
            web_attachment_input.get("content_b64") or ""
        ).strip()

        if not file_name:
            raise PermanentPresenceError(
                "Web attachment is missing its file name."
            )

        try:
            data = base64.b64decode(
                content_b64,
                validate=True,
            )
        except Exception as exc:
            raise PermanentPresenceError(
                "Web attachment payload is not valid base64."
            ) from exc

        max_bytes = 2097152

        if not data:
            raise PermanentPresenceError(
                "Web attachment payload is empty."
            )

        if len(data) > max_bytes:
            raise PermanentPresenceError(
                "Web attachment exceeds the 2 MiB "
                "web transport limit."
            )

        try:
            declared_size = int(
                web_attachment_input.get(
                    "transport_size_bytes"
                )
            )
        except (TypeError, ValueError) as exc:
            raise PermanentPresenceError(
                "Web attachment transport size is invalid."
            ) from exc

        if declared_size != len(data):
            raise PermanentPresenceError(
                "Web attachment byte count does not "
                "match transport custody."
            )

        actual_sha = hashlib.sha256(data).hexdigest()

        metadata.pop(
            "web_attachment_input",
            None,
        )

        result["attachment"] = {
            "provider": "web",
            "provider_file_id":
                f"web_presence_event:{event.get('id')}",
            "file_name": file_name,
            "mime_type": mime_type,
            "file_size": len(data),
            "sha256": actual_sha,
            "content_b64": content_b64,
        }

        result["metadata"] = metadata

    message_type = str(
        result.get("message_type") or "text"
    ).strip().lower()

    if message_type not in {"voice", "audio"}:
        return result

    voice_input = metadata.get("voice_input")

    if not isinstance(voice_input, dict):
        raise PermanentPresenceError(
            "Web voice event is missing voice_input custody."
        )

    content_b64 = str(
        voice_input.get("content_b64") or ""
    ).strip()

    mime_type = str(
        voice_input.get("mime_type") or ""
    ).split(";", 1)[0].strip().lower()

    allowed = {
        "audio/webm",
        "audio/ogg",
        "audio/mp4",
        "audio/mpeg",
        "audio/wav",
        "audio/x-wav",
    }

    if mime_type not in allowed:
        raise PermanentPresenceError(
            f"Unsupported web voice MIME type: {mime_type}"
        )

    attachment = {
        "content_b64": content_b64,
        "mime_type": mime_type,
    }

    transcription = transcribe_voice(
        attachment
    )

    text = str(
        transcription.get("text") or ""
    ).strip()

    if not text:
        raise TransientPresenceError(
            "Web voice transcription returned no text."
        )

    metadata.pop("voice_input", None)

    metadata["voice_source"] = {
        "provider": "web",
        "mime_type": mime_type,
        "file_size": transcription.get(
            "audio_bytes"
        ),
        "sha256": transcription.get(
            "audio_sha256"
        ),
        "custody":
            "cloudflare_d1_transport_only",
        "authority_created": False,
    }

    metadata["voice_transcription"] = (
        transcription
    )

    result["text"] = text
    result["message_type"] = "voice"
    result["metadata"] = metadata

    return result


def render_web_voice_reply(
    *,
    event_id: int,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Attach Vera audio as presentation-only web output."""
    reply = result.get("reply") or {}

    if not isinstance(reply, dict):
        return result

    if not reply.get("voice_eligible"):
        return result

    plan = reply.get("voice_plan") or {}

    if (
        not isinstance(plan, dict)
        or plan.get("state")
        != "ready_for_internal_render"
    ):
        return result

    text = str(
        reply.get("text") or ""
    ).strip()

    if not text:
        return result

    spoken_text = normalize_spoken_text(text)

    outbox = (
        ROOT
        / "state"
        / "presence"
        / "voice_outbox"
    )

    outbox.mkdir(
        parents=True,
        exist_ok=True,
    )

    wav_path = (
        outbox
        / f"vesper-web-{event_id}.wav"
    )

    receipt = synthesize_voice(
        text=spoken_text,
        output_path=wav_path,
        plan=dict(plan),
        timeout=30.0,
    )

    audio = wav_path.read_bytes()

    max_bytes = int(
        os.getenv(
            "DIO_PRESENCE_WEB_VOICE_REPLY_MAX_BYTES",
            "3145728",
        )
    )

    reply = dict(reply)

    if len(audio) > max_bytes:
        reply["audio"] = {
            "state": "text_only",
            "reason":
                "voice_reply_exceeds_web_limit",
            "presentation_only": True,
            "authority_created": False,
        }
    else:
        reply["audio"] = {
            "state": "ready",
            "mime_type": "audio/wav",
            "content_b64": base64.b64encode(
                audio
            ).decode("ascii"),
            "profile_id": receipt.get(
                "profile_id"
            ),
            "backend": receipt.get(
                "backend"
            ),
            "audio_sha256": receipt.get(
                "audio_sha256"
            ),
            "audio_bytes": len(audio),
            "spoken_text_normalized":
                spoken_text != text,
            "presentation_only": True,
            "authority_created": False,
        }

    rendered = dict(result)
    rendered["reply"] = reply

    return rendered

def locally_sign_web_event(
    event: dict[str, Any],
) -> dict[str, Any]:
    body_text = event.get("body_text")

    if not isinstance(body_text, str) or not body_text:
        raise PermanentPresenceError(
            "Web Presence event is missing body_text."
        )

    try:
        envelope = json.loads(body_text)
    except json.JSONDecodeError as exc:
        raise PermanentPresenceError(
            "Web Presence event body is invalid JSON."
        ) from exc

    if not isinstance(envelope, dict):
        raise PermanentPresenceError(
            "Web Presence envelope must be an object."
        )

    if envelope.get("channel") != "webchat":
        raise PermanentPresenceError(
            "Web Presence channel must be webchat."
        )

    if any(
        field in envelope
        for field in (
            "role",
            "_trusted_edge_role",
            "_trusted_edge_key_id",
        )
    ):
        raise PermanentPresenceError(
            "Web Presence envelope attempted to supply authority fields."
        )

    external_user_id = str(
        envelope.get("external_user_id") or ""
    ).strip()

    if not external_user_id.startswith("WEB-"):
        raise PermanentPresenceError(
            "Web Presence external user id is invalid."
        )

    conversation_id = str(
        event.get("conversation_id") or ""
    ).strip()

    metadata = envelope.get("metadata") or {}

    if not isinstance(metadata, dict):
        raise PermanentPresenceError(
            "Web Presence metadata must be an object."
        )

    if (
        str(metadata.get("web_conversation_id") or "").strip()
        != conversation_id
    ):
        raise PermanentPresenceError(
            "Web Presence conversation provenance does not match custody."
        )

    secret = os.getenv(
        "DIO_PRESENCE_PUBLIC_SHARED_SECRET",
        "",
    ).strip()

    if not secret:
        raise TransientPresenceError(
            "DIO_PRESENCE_PUBLIC_SHARED_SECRET "
            "is required for web reconciliation."
        )

    envelope = prepare_web_semantic_envelope(
        event,
        envelope,
    )

    body_text = json.dumps(
        envelope,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    body = body_text.encode("utf-8")
    timestamp = str(int(time.time()))

    event_id = str(
        event.get("id") or "unknown"
    )

    nonce = (
        f"web_{event_id}_"
        f"{hashlib.sha256(body).hexdigest()[:24]}"
    )

    signature = sign_body(
        secret,
        timestamp,
        nonce,
        body,
    )

    return {
        "key_id": "public-edge",
        "signature": signature,
        "signed_timestamp": timestamp,
        "nonce": nonce,
        "body_text": body_text,
    }


def sync_web_event_batch(
    *,
    events: list[dict[str, Any]],
    core_url: str,
    base_url: str,
    token: str,
    reply_path: str,
) -> tuple[
    list[int],
    list[int],
    list[int],
    list[str],
]:
    processed: list[int] = []
    rejected: list[int] = []
    deferred: list[int] = []
    rejection_messages: list[str] = []

    for event in events:
        event_id = int(event.get("id") or 0)

        if event_id < 1:
            continue

        conversation_id = str(
            event.get("conversation_id") or ""
        ).strip()

        if not conversation_id:
            rejected.append(event_id)
            rejection_messages.append(
                f"{event_id}:missing conversation_id"
            )
            continue

        try:
            stored = load_web_reply_outbox(event_id)

            if stored is not None:
                if (
                    stored["conversation_id"]
                    != conversation_id
                ):
                    raise PermanentPresenceError(
                        "Web reply outbox conversation mismatch."
                    )

                result = stored["result"]

            else:
                outgoing = locally_sign_web_event(event)

                result = forward_to_core(
                    outgoing,
                    core_url,
                    replay_is_success=True,
                )

                if result.get("duplicate_delivery"):
                    raise TransientPresenceError(
                        "Core replay detected without "
                        "durable web reply outbox."
                    )

                result = render_web_voice_reply(
                    event_id=event_id,
                    result=result,
                )

                save_web_reply_outbox(
                    event_id=event_id,
                    conversation_id=conversation_id,
                    result=result,
                )

            edge_request(
                base_url + reply_path,
                token,
                method="POST",
                payload={
                    "event_id": event_id,
                    "conversation_id": conversation_id,
                    "result": result,
                },
            )

            processed.append(event_id)

        except PermanentPresenceError as exc:
            rejected.append(event_id)
            rejection_messages.append(
                f"{event_id}:{exc}"
            )

        except (
            TransientPresenceError,
            PresenceEdgeError,
        ):
            deferred.append(event_id)

    return (
        processed,
        rejected,
        deferred,
        rejection_messages,
    )


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

    web_path = str(
        config.get(
            "web_event_api_path",
            "/api/presence/web-events",
        )
    )

    web_ack_path = str(
        config.get(
            "web_ack_api_path",
            "/api/presence/web-events/ack",
        )
    )

    web_reply_path = str(
        config.get(
            "web_reply_api_path",
            "/api/presence/web-replies",
        )
    )

    web_batch = edge_request(
        base_url + web_path + "?limit=100",
        token,
    )

    web_events = (
        web_batch.get("events") or []
    )

    wp, wr, wd, wm = sync_web_event_batch(
        events=web_events,
        core_url=core_url,
        base_url=base_url,
        token=token,
        reply_path=web_reply_path,
    )

    web_processed_ack = acknowledge(
        base_url,
        token,
        web_ack_path,
        wp,
        "processed",
    )

    cleanup_web_reply_outbox_after_ack(
        wp,
        web_processed_ack,
    )

    web_rejected_ack = acknowledge(
        base_url,
        token,
        web_ack_path,
        wr,
        "failed",
        "; ".join(wm)
        if wm
        else "web_presence_rejected",
    )


    processed = len(sp) + len(tp) + len(wp)
    rejected = len(sr) + len(tr) + len(wr)
    deferred = len(sd) + len(td) + len(wd)
    received = len(signed_events) + len(telegram_events) + len(web_events)
    return {
        "schema": "dio.vesper.presence_edge_sync.v2",
        "status": "processed" if processed or rejected else ("deferred" if deferred else "idle"),
        "received": received,
        "processed": processed,
        "rejected": rejected,
        "deferred": deferred,
        "processed_acknowledged": int((signed_processed_ack or {}).get("acknowledged", 0)) + int((telegram_processed_ack or {}).get("acknowledged", 0)) + int((web_processed_ack or {}).get("acknowledged", 0)),
        "rejected_acknowledged": int((signed_rejected_ack or {}).get("acknowledged", 0)) + int((telegram_rejected_ack or {}).get("acknowledged", 0)) + int((web_rejected_ack or {}).get("acknowledged", 0)),
        "signed_received": len(signed_events),
        "telegram_received": len(telegram_events),
        "telegram_processed": len(tp),
        "telegram_rejected": len(tr),
        "telegram_deferred": len(td),
        "web_received": len(web_events),
        "web_processed": len(wp),
        "web_rejected": len(wr),
        "web_deferred": len(wd),
        "web_signing_authority": "local_public_edge_only",
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
