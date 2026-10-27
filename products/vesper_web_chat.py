from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import re
import secrets
import shutil
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

from portfolio_runtime import ROOT, load_portfolio
from products.attachment_intake import MAX_ATTACHMENTS, quarantine_attachments
from presence_core.config import state_path
from presence_core.local_ingress import LocalIngressLedger


SESSION_SCHEMA = "dio.vesper.web_chat.session.v1"
MESSAGE_RECEIPT_SCHEMA = "dio.vesper.web_chat.message_receipt.v1"
PROFESSIONAL_BINDING_SCHEMA = "dio.vesper.web_chat.professional_binding.v1"
DEFAULT_STATE_ROOT = state_path("vesper", "web_chat", dio_root=ROOT)
MAX_MESSAGE_CHARS = 12000
ROUTE_STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "into", "your", "their", "our", "you", "please",
    "need", "want", "help", "make", "give", "show", "review", "prepare", "build", "work", "ready", "human",
    "product", "studio", "proof", "dio", "one", "two", "all", "not", "but", "before", "after", "about",
}


class VesperWebChatError(RuntimeError):
    pass


class VesperWebChatValidationError(VesperWebChatError):
    """Input was refused before canonical processing began."""


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


@contextmanager
def _session_lock(state_root: Path, conversation_id: str):
    """Serialize the complete session update across threads and local workers."""
    path = _session_path(state_root, conversation_id)
    if not path.is_file():
        raise VesperWebChatError("Vesper web-chat conversation was not found")
    from presence_core.state import file_lock
    with file_lock(path.parent / "MESSAGE.lock"):
        yield


def _presence_root(state_root: Path) -> Path:
    state_root = state_root.resolve()
    if state_root.name == "web_chat" and state_root.parent.name == "vesper":
        return state_root.parent.parent / "presence"
    # Explicit professional-packet/test sessions remain isolated from live state.
    return state_root / "presence"


def _process_web_turn(session: dict[str, Any], payload: dict[str, Any], *,
                      state_root: Path, quarantine_manifest: dict[str, Any] | None,
                      quarantine_root: Path, message_id: str,
                      trusted_voice_context: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    from presence_core.config import load_config
    from presence_core.engine import process_envelope
    from presence_core.state import conversation_id as canonical_id
    from presence_core.customer_cases import find_case_for_conversation

    presence_root = _presence_root(state_root)
    cfg = load_config(ROOT / "config" / "presence.json")
    cfg["state_root"] = str(presence_root)
    cfg["event_log"] = str(presence_root.parent / "telemetry" / "dio_events.jsonl")
    cfg["lingua_state_root"] = str(presence_root.parent / "lingua")
    expected_id = canonical_id("webchat", session["conversation_id"])
    previous_id = session.get("canonical_conversation_id")
    if previous_id and previous_id != expected_id:
        raise VesperWebChatError("canonical identity changed; manual reconciliation required")

    quarantined = []
    for row in (quarantine_manifest or {}).get("attachments", []):
        blob = Path(row["quarantine_path"]).resolve()
        if quarantine_root.resolve() not in blob.parents or not blob.is_file():
            raise VesperWebChatError("web attachment escaped its quarantine")
        if _sha(blob) != row["sha256"] or blob.stat().st_size != row["bytes"]:
            raise VesperWebChatError("web attachment custody changed")
        aid = "ATT-WEB-" + hashlib.sha256((expected_id + "\0" + row["source_ref"]).encode()).hexdigest()[:20].upper()
        record = {
            "schema": "dio.presence_attachment.v2", "attachment_id": aid,
            "conversation_id": expected_id, "state": "quarantined",
            "quarantine_only": True, "safe_to_parse": False, "safe_to_execute": False,
            "original_file_name": row["filename"], "extension": blob.suffix.lower(),
            "mime_type": row["declared_mime_type"], "size_bytes": row["bytes"],
            "sha256": row["sha256"], "blob_path": str(blob),
            "source_ref": row["source_ref"], "web_attachment_id": row["attachment_id"],
            "created_at": utc_now(),
            "authority": {"automatic_processing": False, "operator_review_required": True},
        }
        _write_json(presence_root / "quarantine" / aid / "ATTACHMENT.json", record)
        quarantined.append(record)

    hint = str(payload.get("incarnation_hint") or session.get("incarnation_hint") or "").strip() or None
    # A repeated initial site hint must not pin every subsequent customer turn.
    if previous_id and hint == session.get("incarnation_hint") and payload.get("product_context_changed") is not True:
        hint = None
    if hint:
        if hint not in set(canonical_incarnations()):
            raise VesperWebChatError(f"unknown canonical incarnation hint: {hint}")
        session["incarnation_hint"] = hint
    envelope = {
        "channel": "webchat", "external_user_id": session["conversation_id"],
        "source_message_id": message_id, "message_type": "text",
        "text": str(payload.get("message") or "").strip(),
        "metadata": {"provider": "vesper_web", "incarnation_hint": hint,
                     "email": str((session.get("contact") or {}).get("email") or ""),
                     "contact_identity_verified": False,
                     "attachment_count_held_in_quarantine": len(quarantined),
                     "attachment_processing_authorized": False},
    }
    if trusted_voice_context is not None:
        envelope['message_type'] = 'voice'
        envelope['metadata']['voice_source'] = dict(trusted_voice_context)
        envelope['metadata']['voice_transcription_is_untrusted_customer_input'] = True
    result = process_envelope(envelope, ROOT, cfg, quarantined_attachments=quarantined)
    authority = result.get("authority") or {}
    if (result.get("role") != "public" or result.get("conversation_id") != expected_id
            or authority.get("executed_external_action") is not False
            or any(authority.get(key) is True for key in (
                "send_authorized", "submission_authorized", "spend_authorized",
                "financial_commitment_authorized", "fulfilment_released", "attachment_processed",
                "delivery_authorized", "attachment_processing_authorized"))):
        raise VesperWebChatError("canonical web response violated its authority boundary")
    case = find_case_for_conversation(presence_root, expected_id)
    commercial = result.get("commercial")
    product = str(((commercial or {}).get("product") or {}).get("name") or "").strip() or None
    if commercial is None and case:
        product = str(case.get("product_id") or "").strip() or None
    resolved = bool(product and product in set(canonical_incarnations())
                    and (commercial is None or commercial.get("state") == "RESOLVED"))
    route = {"state": "RESOLVED" if resolved else "NEEDS_YOU",
             "incarnation": product if resolved else None,
             "basis": "canonical_presence_journey",
             "candidates": [{"incarnation": name, "score": None}
                            for name in (commercial or {}).get("candidates", [])],
             "authority_created": False}
    result["web_case"] = {key: case.get(key) for key in ("case_id", "stage", "product_id")} if case else None
    return result, route


def _safe_conversation_id(value: str) -> str:
    text = str(value or "").strip().upper()
    if not re.fullmatch(r"VWC-[A-Z0-9][A-Z0-9-]{7,63}", text):
        raise VesperWebChatError("invalid Vesper web-chat conversation id")
    return text


def _session_path(state_root: Path, conversation_id: str) -> Path:
    return state_root.resolve() / _safe_conversation_id(conversation_id) / "SESSION.json"


def _tokens(value: Any) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value or "").casefold())
        if len(token) > 2 and token not in ROUTE_STOPWORDS
    }


def canonical_incarnations() -> list[str]:
    return sorted(str(row.get("Incarnation") or "") for row in load_portfolio()["incarnations"] if row.get("Incarnation"))


@lru_cache(maxsize=1)
def _route_surfaces() -> list[dict[str, Any]]:
    from semantic_marketing import semantic_marketing_brief

    rows = []
    for incarnation in load_portfolio()["incarnations"]:
        name = str(incarnation.get("Incarnation") or "").strip()
        if not name:
            continue
        semantic_text = " ".join(
            str(incarnation.get(key) or "")
            for key in ("Incarnation", "Suite", "Product Family", "source_work_patterns", "atlas_domain_ids")
        )
        try:
            brief = semantic_marketing_brief(name).get("brief") or {}
        except Exception:
            brief = {}
        semantic_text += " " + " ".join(str(brief.get(key) or "") for key in ("audience_name", "pain", "outcome", "marketing_statement"))
        rows.append(
            {
                "incarnation": name,
                "name_tokens": _tokens(name),
                "semantic_tokens": _tokens(semantic_text),
                "suite": incarnation.get("Suite"),
                "family": incarnation.get("Product Family"),
            }
        )
    return rows


def resolve_incarnation(message: str, *, incarnation_hint: str | None = None) -> dict[str, Any]:
    names = set(canonical_incarnations())
    hint = str(incarnation_hint or "").strip()
    if hint:
        if hint not in names:
            raise VesperWebChatError(f"unknown canonical incarnation hint: {hint}")
        return {
            "state": "RESOLVED",
            "incarnation": hint,
            "basis": "exact_product_site_context",
            "candidates": [{"incarnation": hint, "score": 1000}],
            "authority_created": False,
        }

    text = str(message or "").strip()
    if not text:
        return {"state": "NEEDS_YOU", "incarnation": None, "basis": "message_required", "candidates": [], "authority_created": False}
    lowered = text.casefold()
    message_tokens = _tokens(text)
    scored = []
    for row in _route_surfaces():
        exact = 120 if row["incarnation"].casefold() in lowered else 0
        name_overlap = len(message_tokens & row["name_tokens"]) * 12
        semantic_overlap = len(message_tokens & row["semantic_tokens"]) * 2
        score = exact + name_overlap + semantic_overlap
        if score:
            scored.append({"incarnation": row["incarnation"], "score": score})
    scored.sort(key=lambda row: (-int(row["score"]), str(row["incarnation"])))
    candidates = scored[:3]
    if not candidates:
        return {"state": "NEEDS_YOU", "incarnation": None, "basis": "no_semantic_route", "candidates": [], "authority_created": False}
    top = int(candidates[0]["score"])
    second = int(candidates[1]["score"]) if len(candidates) > 1 else -999
    if top < 4 or top - second < 3:
        return {
            "state": "NEEDS_YOU",
            "incarnation": None,
            "basis": "ambiguous_semantic_route",
            "candidates": candidates,
            "authority_created": False,
        }
    return {
        "state": "RESOLVED",
        "incarnation": candidates[0]["incarnation"],
        "basis": "portfolio_semantic_route",
        "candidates": candidates,
        "authority_created": False,
    }


def _public_session(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": session["schema"],
        "conversation_id": session["conversation_id"],
        "identity": session["identity"],
        "channel": session["channel"],
        "surface": session["surface"],
        "canonical_conversation_id": session.get("canonical_conversation_id"),
        "canonical_case_id": session.get("canonical_case_id"),
        "canonical_case_stage": session.get("canonical_case_stage"),
        "incarnation_hint": session.get("incarnation_hint"),
        "route": session.get("route") or {},
        "state": session["state"],
        "messages": session["messages"],
        "attachment_count": len(session.get("attachments") or []),
        "handoff": session.get("handoff") or {},
        "human_gate": session["human_gate"],
        "external_send": session["external_send"],
        "external_release": session["external_release"],
        "authority_created": False,
        "external_effects": False,
    }


def create_session(
    payload: dict[str, Any] | None = None,
    *,
    state_root: Path = DEFAULT_STATE_ROOT,
    conversation_id: str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    payload = dict(payload or {})
    now = now or utc_now()
    hint = str(payload.get("incarnation_hint") or "").strip() or None
    if hint and hint not in set(canonical_incarnations()):
        raise VesperWebChatError(f"unknown canonical incarnation hint: {hint}")
    if conversation_id is None:
        conversation_id = "VWC-" + secrets.token_hex(8).upper()
    conversation_id = _safe_conversation_id(conversation_id)
    path = _session_path(state_root, conversation_id)
    if path.exists():
        raise VesperWebChatError("Vesper web-chat conversation already exists")
    surface = str(payload.get("surface") or ("product_site" if hint else "dio_web")).strip() or "dio_web"
    greeting = (
        f"You are speaking with Vesper, DIO Presence Core, in the {hint} workflow. "
        "Tell me what you need and attach the source material you want DIO to work from."
        if hint
        else "You are speaking with Vesper, DIO Presence Core. Tell me what you need done and I will route the work to the bounded DIO product that best fits."
    )
    greeting += " Nothing is sent, published, paid, or externally released from this chat without a separate authorised gate."
    route = resolve_incarnation("", incarnation_hint=hint) if hint else {"state": "UNRESOLVED", "incarnation": None, "basis": "awaiting_customer_message", "candidates": [], "authority_created": False}
    session = {
        "schema": SESSION_SCHEMA,
        "conversation_id": conversation_id,
        "identity": "Vesper, DIO Presence Core",
        "channel": "web_chat",
        "surface": surface,
        "incarnation_hint": hint,
        "created_at": now,
        "updated_at": now,
        "contact": {
            "name": str(payload.get("name") or "").strip(),
            "email": str(payload.get("email") or "").strip(),
            "organisation": str(payload.get("organisation") or "").strip(),
        },
        "messages": [{"message_id": "MSG-0001", "role": "vesper", "text": greeting, "created_at": now, "attachment_ids": []}],
        "attachments": [],
        "route": route,
        "state": "open",
        "handoff": {"state": "NOT_READY", "product_execution_started": False},
        "human_gate": "NEEDS_YOU",
        "external_send": "REFUSE",
        "external_release": "REFUSE",
        "payment": "REFUSE",
        "authority_created": False,
        "external_effects": False,
        "whatsapp_used": False,
        "telegram_used": False,
    }
    session["session_fingerprint"] = _fingerprint({key: value for key, value in session.items() if key != "session_fingerprint"})
    _write_json(path, session)
    return _public_session(session)


def load_session(conversation_id: str, *, state_root: Path = DEFAULT_STATE_ROOT) -> dict[str, Any]:
    path = _session_path(state_root, conversation_id)
    if not path.is_file():
        raise VesperWebChatError("Vesper web-chat conversation was not found")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != SESSION_SCHEMA:
        raise VesperWebChatError("unsupported Vesper web-chat session schema")
    return payload


def post_message(
    conversation_id: str,
    payload: dict[str, Any],
    *,
    state_root: Path = DEFAULT_STATE_ROOT,
    quarantine_output_root: Path | None = None,
    now: str | None = None,
    trusted_voice_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(payload)
    event = str(payload.get("message_id") or payload.get("client_message_id") or "").strip()
    if event and not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", event):
        raise VesperWebChatValidationError("invalid web message id")
    text = str(payload.get("message") or "").strip()
    attachments = payload.get("attachments") or []
    if not isinstance(attachments, list):
        raise VesperWebChatValidationError("attachments must be a list")
    if not text and not attachments:
        raise VesperWebChatValidationError("send a message or attach at least one source file")
    if len(text) > MAX_MESSAGE_CHARS:
        raise VesperWebChatValidationError(f"message exceeds {MAX_MESSAGE_CHARS} characters")
    if len(attachments) > MAX_ATTACHMENTS:
        raise VesperWebChatValidationError(f"a single chat message may contain at most {MAX_ATTACHMENTS} attachments")
    hint = str(payload.get("incarnation_hint") or "").strip()
    if hint and hint not in set(canonical_incarnations()):
        raise VesperWebChatValidationError(f"unknown canonical incarnation hint: {hint}")
    event = event or "WEB-" + secrets.token_hex(16).upper()
    key = f"web:{_safe_conversation_id(conversation_id)}:{event}"
    body = _canonical(payload)
    if trusted_voice_context is not None:
        body = _canonical({'payload': payload, 'voice_source': trusted_voice_context})
    with _session_lock(state_root, conversation_id):
        session = load_session(conversation_id, state_root=state_root)
        if len(session.get("messages", [])) > 1 and not session.get("canonical_conversation_id"):
            raise VesperWebChatError("legacy web session requires canonical history reconciliation")
        ledger = LocalIngressLedger(_session_path(state_root, conversation_id).parent / "INGRESS.sqlite")
        try:
            cached = ledger.claim(key, body, reject_other_pending=True)
        except ValueError as exc:
            raise VesperWebChatError(str(exc)) from exc
        if cached is not None:
            if cached.get("rejected_no_canonical_effect"):
                raise VesperWebChatValidationError(cached["error"])
            return {**cached, "session": _public_session(session)}
        try:
            response = _post_message(conversation_id, payload, state_root=state_root,
                                     quarantine_output_root=quarantine_output_root, now=now,
                                     canonical_message_id=key, trusted_voice_context=trusted_voice_context)
            ledger.complete(key, body, response)
            return response
        except VesperWebChatValidationError as exc:
            ledger.complete(key, body, {"rejected_no_canonical_effect": True, "error": str(exc)})
            raise
        except Exception as exc:
            raise VesperWebChatError("canonical web processing failed; event is in doubt and requires reconciliation") from exc


def _post_message(
    conversation_id: str,
    payload: dict[str, Any],
    *,
    state_root: Path = DEFAULT_STATE_ROOT,
    quarantine_output_root: Path | None = None,
    now: str | None = None,
    canonical_message_id: str,
    trusted_voice_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = now or utc_now()
    session = load_session(conversation_id, state_root=state_root)
    text = str(payload.get("message") or "").strip()
    attachments = list(payload.get("attachments") or [])
    if not text and not attachments:
        raise VesperWebChatError("send a message or attach at least one source file")
    if len(text) > MAX_MESSAGE_CHARS:
        raise VesperWebChatError(f"message exceeds {MAX_MESSAGE_CHARS} characters")
    if len(attachments) > MAX_ATTACHMENTS:
        raise VesperWebChatError(f"a single chat message may contain at most {MAX_ATTACHMENTS} attachments")

    message_number = len(session["messages"]) + 1
    attachment_ids: list[str] = []
    quarantine_manifest = None
    if attachments:
        intake_id = f"{conversation_id}-M{message_number:04d}"
        try:
            quarantine_manifest = quarantine_attachments(
                attachments, output_dir=quarantine_output_root or ROOT, intake_id=intake_id,
                state_root=_presence_root(state_root).parent if quarantine_output_root is None else None,
            )
        except Exception as exc:
            raise VesperWebChatValidationError("attachment intake refused; correct the source files before retrying") from exc
        for row in quarantine_manifest["attachments"]:
            attachment_ids.append(str(row["attachment_id"]))
            session["attachments"].append(
                {
                    "attachment_id": row["attachment_id"],
                    "filename": row["filename"],
                    "role": row["role"],
                    "bytes": row["bytes"],
                    "sha256": row["sha256"],
                    "source_ref": row["source_ref"],
                    "extraction_state": row["extraction_state"],
                    "trust_state": row["trust_state"],
                    "freshness_state": row["freshness_state"],
                }
            )

    session["messages"].append(
        {
            "message_id": f"MSG-{message_number:04d}",
            "role": "customer",
            "text": text,
            "created_at": now,
            "attachment_ids": attachment_ids,
        }
    )
    quarantine_root = ((quarantine_output_root / "state") if quarantine_output_root is not None
                       else _presence_root(state_root).parent) / "vesper" / "quarantine"
    presence, route = _process_web_turn(session, payload, state_root=state_root,
                                       quarantine_manifest=quarantine_manifest,
                                       quarantine_root=quarantine_root,
                                       message_id=canonical_message_id, trusted_voice_context=trusted_voice_context)
    session["canonical_conversation_id"] = presence["conversation_id"]
    case = presence.get("web_case") or {}
    session["canonical_case_id"] = case.get("case_id")
    session["canonical_case_stage"] = case.get("stage")
    session["route"] = route
    session["state"] = "ready_for_handoff" if route["state"] == "RESOLVED" else "needs_route_clarification"
    session["handoff"] = {
        "state": "READY_FOR_PRODUCT_EXECUTION" if route["state"] == "RESOLVED" else "NOT_READY",
        "incarnation": route["incarnation"], "product_execution_started": False,
        "canonical_conversation_id": presence["conversation_id"],
        "canonical_case_id": case.get("case_id"), "canonical_case_stage": case.get("stage"),
        "source_attachment_ids": [row["attachment_id"] for row in session["attachments"]],
        "external_effects": False,
    }
    answer = str((presence.get("reply") or {}).get("text") or "").strip()
    if not answer:
        raise VesperWebChatError("canonical Presence returned no reply")

    assistant_number = len(session["messages"]) + 1
    assistant_message = {"message_id": f"MSG-{assistant_number:04d}", "role": "vesper", "text": answer, "created_at": now, "attachment_ids": []}
    reply = presence.get("reply") or {}
    if reply.get("voice_eligible") and (reply.get("voice_plan") or {}).get("state") == "ready_for_internal_render":
        from presence_core.voice import synthesize_voice
        from presence_core.telegram_transport import normalize_spoken_text
        try:
            voice_receipt = synthesize_voice(
                text=normalize_spoken_text(answer),
                output_path=_presence_root(state_root) / "voice_outbox" / f"{conversation_id}-{assistant_number}.wav",
                plan=reply["voice_plan"], timeout=30.0,
            )
            audio = Path(voice_receipt["audio_path"]).read_bytes()
            if len(audio) > int(os.getenv("DIO_PRESENCE_WEB_VOICE_REPLY_MAX_BYTES", "3145728")):
                raise ValueError("voice_reply_exceeds_web_limit")
            assistant_message["audio"] = {
                "state": "ready", "mime_type": "audio/wav", "content_b64": base64.b64encode(audio).decode("ascii"),
                "profile_id": voice_receipt.get("profile_id"), "backend": voice_receipt.get("backend"),
                "audio_sha256": voice_receipt.get("audio_sha256"), "presentation_only": True, "authority_created": False,
            }
        except Exception:
            # Audio availability must not discard an already accepted canonical text response.
            assistant_message["audio"] = {"state": "text_only", "reason": "voice_render_unavailable",
                                          "presentation_only": True, "authority_created": False}
    session["messages"].append(assistant_message)
    session["updated_at"] = now
    session["session_fingerprint"] = _fingerprint({key: value for key, value in session.items() if key != "session_fingerprint"})
    _write_json(_session_path(state_root, conversation_id), session)
    receipt = {
        "schema": MESSAGE_RECEIPT_SCHEMA,
        "conversation_id": conversation_id,
        "message_id": f"MSG-{message_number:04d}",
        "route": route,
        "canonical_conversation_id": presence["conversation_id"],
        "canonical_case_id": case.get("case_id"),
        "canonical_case_stage": case.get("stage"),
        "decision": presence.get("decision") or {},
        "lingua_object_id": (presence.get("lingua") or {}).get("object_id"),
        "source_message_id": canonical_message_id,
        "attachment_count": len(attachment_ids),
        "quarantine_manifest_schema": (quarantine_manifest or {}).get("schema"),
        "handoff_state": session["handoff"]["state"],
        "channel": "web_chat",
        "whatsapp_used": False,
        "telegram_used": False,
        "human_gate": "NEEDS_YOU",
        "external_send": "REFUSE",
        "external_release": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    receipt["receipt_fingerprint"] = _fingerprint(receipt)
    _write_json(_session_path(state_root, conversation_id).parent / f"MESSAGE_RECEIPT_{message_number:04d}.json", receipt)
    return {"session": _public_session(session), "assistant_message": answer, "receipt": receipt}


def _source_files(packet: dict[str, Any]) -> list[Path]:
    packet_dir = Path(packet["packet_dir"]).resolve()
    files = []
    for row in packet["manifest"].get("files") or []:
        relative = str(row.get("path") or "")
        if not relative.startswith("SOURCES/"):
            continue
        path = (packet_dir / relative).resolve()
        if packet_dir not in path.parents or not path.is_file():
            raise VesperWebChatError(f"professional customer source path is invalid: {relative}")
        if _sha(path) != str(row.get("sha256") or ""):
            raise VesperWebChatError(f"professional customer source hash drifted: {relative}")
        files.append(path)
    if not files:
        raise VesperWebChatError("professional customer packet has no source files for Vesper")
    return files


def bind_professional_customer_packet(
    packet: dict[str, Any],
    incarnation: str,
    *,
    output_dir: Path,
    now: str | None = None,
) -> dict[str, Any]:
    now = now or utc_now()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    packet_fingerprint = str(packet.get("packet_fingerprint") or "")
    if not packet_fingerprint.startswith("sha256:"):
        raise VesperWebChatError("professional packet fingerprint is missing")
    conversation_id = "VWC-PRO-" + hashlib.sha256((packet_fingerprint + "\n" + incarnation).encode()).hexdigest()[:16].upper()
    state_root = output_dir / "sessions"
    create_session(
        {
            "surface": "product_site",
            "incarnation_hint": incarnation,
            "organisation": str((packet.get("intake") or {}).get("customer", {}).get("organisation") or ""),
            "name": str((packet.get("intake") or {}).get("customer", {}).get("buyer_role") or ""),
        },
        state_root=state_root,
        conversation_id=conversation_id,
        now=now,
    )
    sources = _source_files(packet)
    message = str((packet.get("intake") or {}).get("request") or "").strip()
    manifests = []
    final = None
    for batch_index in range(0, len(sources), MAX_ATTACHMENTS):
        batch = sources[batch_index : batch_index + MAX_ATTACHMENTS]
        encoded = [
            {
                "filename": path.name,
                "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                "role": "customer_source",
                "content_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
            }
            for path in batch
        ]
        final = post_message(
            conversation_id,
            {
                "message": message if batch_index == 0 else "Additional customer source files for the same governed request.",
                "attachments": encoded,
                "incarnation_hint": incarnation,
            },
            state_root=state_root,
            quarantine_output_root=output_dir,
            now=now,
        )
        manifest_paths = sorted((output_dir / "state" / "vesper" / "quarantine").glob("*/ATTACHMENT_INTAKE.json"))
        manifests = [{"path": str(path.relative_to(output_dir)), "sha256": _sha(path)} for path in manifest_paths]
    if final is None:
        raise VesperWebChatError("professional Vesper binding produced no chat message")
    session = load_session(conversation_id, state_root=state_root)
    route = session.get("route") or {}
    if route.get("state") != "RESOLVED" or route.get("incarnation") != incarnation:
        raise VesperWebChatError("Vesper product-site route did not resolve to the intended canonical incarnation")
    if session.get("handoff", {}).get("state") != "READY_FOR_PRODUCT_EXECUTION":
        raise VesperWebChatError("Vesper web-chat handoff did not reach READY_FOR_PRODUCT_EXECUTION")
    session_path = _session_path(state_root, conversation_id)
    receipt = {
        "schema": PROFESSIONAL_BINDING_SCHEMA,
        "identity": "Vesper, DIO Presence Core",
        "conversation_id": conversation_id,
        "channel": "web_chat",
        "surface": "product_site",
        "resolved_incarnation": incarnation,
        "route_basis": route.get("basis"),
        "packet_fingerprint": packet_fingerprint,
        "customer_message_bound": bool(message),
        "source_attachment_count": len(sources),
        "session_sha256": _sha(session_path),
        "quarantine_manifests": manifests,
        "handoff_state": "READY_FOR_PRODUCT_EXECUTION",
        "sequence": ["VESPER_WEB_CHAT_INTAKE", "PRODUCT_EXECUTION"],
        "product_execution_started": False,
        "examiner_data_used": False,
        "golden_fixture_used": False,
        "whatsapp_used": False,
        "telegram_used": False,
        "human_gate": "NEEDS_YOU",
        "external_send": "REFUSE",
        "external_release": "REFUSE",
        "authority_created": False,
        "external_effects": False,
    }
    receipt["binding_fingerprint"] = _fingerprint(receipt)
    _write_json(output_dir / "VESPER_WEB_CHAT_BINDING.json", receipt)
    return receipt


__all__ = [
    "DEFAULT_STATE_ROOT",
    "MESSAGE_RECEIPT_SCHEMA",
    "PROFESSIONAL_BINDING_SCHEMA",
    "SESSION_SCHEMA",
    "VesperWebChatError",
    "bind_professional_customer_packet",
    "canonical_incarnations",
    "create_session",
    "load_session",
    "post_message",
    "resolve_incarnation",
]
