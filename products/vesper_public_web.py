"""The existing website's session-token protocol over canonical Vesper custody."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import json
from pathlib import Path
import secrets
import time

from products import vesper_web_chat as web

STATE_ROOT = web.DEFAULT_STATE_ROOT
PUBLIC_SESSION_TTL_SECONDS = 24 * 60 * 60


class PublicWebAccessError(web.VesperWebChatError):
    pass


class PublicWebInputError(web.VesperWebChatValidationError):
    pass


class PublicWebVoiceUnavailable(web.VesperWebChatError):
    pass


def open_session(payload):
    if payload.get("surface") not in {None, "dio_web", "vesper"}:
        raise PublicWebInputError("unsupported website surface")
    created = web.create_session({}, state_root=STATE_ROOT)
    cid = created["conversation_id"]
    token = secrets.token_urlsafe(32)
    with web._session_lock(STATE_ROOT, cid):
        session = web.load_session(cid, state_root=STATE_ROOT)
        session["public_web_token_sha256"] = hashlib.sha256(token.encode()).hexdigest()
        session["public_web_token_expires_at"] = int(time.time()) + PUBLIC_SESSION_TTL_SECONDS
        session["session_fingerprint"] = web._fingerprint({k: v for k, v in session.items() if k != "session_fingerprint"})
        web._write_json(web._session_path(STATE_ROOT, cid), session)
    return {"session": {"conversation_id": cid, "session_token": token}, "authority_created": False}


def owning_session(cid, token):
    if not token or len(str(token)) > 256:
        raise PublicWebAccessError("website session token required")
    try:
        with web._session_lock(STATE_ROOT, cid):
            session = web.load_session(cid, state_root=STATE_ROOT)
    except (web.VesperWebChatError, ValueError) as exc:
        raise PublicWebAccessError("website session is unavailable") from exc
    expires_at = session.get("public_web_token_expires_at")
    # Fail closed for legacy sessions without an explicit public-token expiry.
    if (isinstance(expires_at, bool) or not isinstance(expires_at, (int, float))
            or expires_at <= time.time()):
        raise PublicWebAccessError("website session expired")
    if not hmac.compare_digest(str(session.get("public_web_token_sha256") or ""),
                               hashlib.sha256(str(token).encode()).hexdigest()):
        raise PublicWebAccessError("website session token refused")
    return session


def _message(payload, *, text=None):
    event = str(payload.get("client_message_id") or "").strip()
    if not event:
        raise PublicWebInputError("client message identity is required")
    attachments = payload.get("attachments") or []
    if not isinstance(attachments, list) or len(attachments) > 1:
        raise PublicWebInputError("the website accepts one attachment per message")
    converted = []
    for row in attachments:
        if not isinstance(row, dict):
            raise PublicWebInputError("invalid attachment")
        try:
            data = base64.b64decode(str(row.get("content_b64") or ""), validate=True)
        except ValueError as exc:
            raise PublicWebInputError("invalid attachment bytes") from exc
        if not 0 < len(data) <= 2097152:
            raise PublicWebInputError("attachment must be between 1 byte and 2 MiB")
        converted.append({"filename": str(row.get("file_name") or ""),
                          "mime_type": str(row.get("mime_type") or "application/octet-stream"),
                          "content_base64": str(row.get("content_b64") or "")})
    hint = str(payload.get("incarnation_hint") or "").strip()
    if hint.casefold() == "vesper":
        hint = ""
    return {"message": str(payload.get("message") or "") if text is None else str(text),
            "client_message_id": event, "attachments": converted,
            "incarnation_hint": hint or None,
            "product_context_changed": payload.get("product_context_changed") is True}


def accept_message(payload, token):
    cid = str(payload.get("conversation_id") or "")
    owning_session(cid, token)
    result = web.post_message(cid, _message(payload), state_root=STATE_ROOT)
    return {"state": "completed", "receipt": result["receipt"], "authority_created": False}


def read_replies(cid, token, *, after=0):
    session = owning_session(cid, token)
    try:
        cursor = int(after or 0)
    except (TypeError, ValueError) as exc:
        raise PublicWebInputError("invalid reply cursor") from exc
    if cursor < 0:
        raise PublicWebInputError("invalid reply cursor")
    rows = []
    for index, message in enumerate(session.get("messages") or [], 1):
        # Preserve the archived transport greeting, but do not duplicate it in
        # the actual website, which already owns its own introduction.
        if index == 1 or index <= cursor or message.get("role") != "vesper":
            continue
        receipt_path = web._session_path(STATE_ROOT, cid).parent / f"MESSAGE_RECEIPT_{index-1:04d}.json"
        receipt = json.loads(receipt_path.read_text())
        rows.append({"sequence": index, "reply": {"text": message["text"]},
                     "canonical_conversation_id": receipt.get("canonical_conversation_id"),
                     "canonical_case_id": receipt.get("canonical_case_id"),
                     "source_message_id": receipt.get("source_message_id")})
    return {"replies": rows, "next_after": rows[-1]["sequence"] if rows else cursor}


def accept_voice(payload, token):
    cid = str(payload.get("conversation_id") or "")
    owning_session(cid, token)
    _message({**payload, "attachments": []}, text="voice preflight")
    # Reuse the local Whisper adapter, without triggering a model download.
    model = str(os.getenv("DIO_PRESENCE_LOCAL_ASR_MODEL") or "").strip()
    if not model or not Path(model).expanduser().is_dir():
        raise PublicWebVoiceUnavailable("Voice input is not ready on this device yet. You can type your message.")
    mime = str(payload.get("mime_type") or "").split(";", 1)[0].lower()
    if mime not in {"audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/wav", "audio/x-wav"}:
        raise PublicWebInputError("unsupported voice format")
    try:
        audio = base64.b64decode(str(payload.get("audio_b64") or ""), validate=True)
    except ValueError as exc:
        raise PublicWebInputError("invalid voice bytes") from exc
    if not 0 < len(audio) <= 2097152:
        raise PublicWebInputError("voice note must be between 1 byte and 2 MiB")
    from scripts.sync_vesper_presence_edge import transcribe_voice
    try:
        transcription = transcribe_voice({"content_b64": payload["audio_b64"], "mime_type": mime})
    except Exception as exc:
        raise PublicWebVoiceUnavailable("Voice input is not ready on this device yet. You can type your message.") from exc
    if transcription.get('audio_sha256') != hashlib.sha256(audio).hexdigest() or transcription.get('audio_bytes') != len(audio):
        raise PublicWebInputError('voice transcription custody mismatch')
    voice_context = {k: transcription[k] for k in
                     ("provider", "audio_sha256", "audio_bytes", "mime_type")}
    result = web.post_message(cid, _message(payload, text=transcription["text"]),
                              state_root=STATE_ROOT, trusted_voice_context=voice_context)
    return {"state": "completed", "receipt": result["receipt"], "authority_created": False}
