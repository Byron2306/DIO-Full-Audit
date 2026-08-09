from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .context import build_conversation_context, clean_text, timestamp


JOURNAL_SCHEMA = "dio.presence_turn_journal.v1"
MAX_JOURNAL_TURNS = 40


def incoming_provider_message_id(envelope: dict[str, Any]) -> str | None:
    metadata = envelope.get("metadata") or {}
    candidates = (
        envelope.get("source_message_id"),
        metadata.get("source_message_id"),
        metadata.get("telegram_message_id"),
        metadata.get("provider_message_id"),
        metadata.get("update_id"),
    )
    value = next((str(item).strip() for item in candidates if str(item or "").strip()), "")
    return value or None


def _journal_path(presence_root: Path, conversation_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(conversation_id))[:140]
    return presence_root / "conversation_turns" / f"{safe}.json"


def _turn_ref(conversation_id: str, direction: str, source_message_id: str | None, text: str, observed_at: str) -> str:
    if source_message_id:
        seed = f"{conversation_id}\n{direction}\nprovider:{source_message_id}"
    else:
        seed = f"{conversation_id}\n{direction}\n{observed_at}\n{text}"
    return "presence_turn:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20].upper()


def load_presence_turns(presence_root: Path, conversation_id: str) -> list[dict[str, Any]]:
    path = _journal_path(presence_root, conversation_id)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if payload.get("schema") != JOURNAL_SCHEMA or not isinstance(payload.get("turns"), list):
        return []
    return list(payload["turns"])[-MAX_JOURNAL_TURNS:]


def append_presence_turn(
    presence_root: Path,
    *,
    conversation_id: str,
    direction: str,
    delivery_state: str,
    text: str,
    actor_role: str,
    source_message_id: str | None = None,
    observed_at: str | None = None,
) -> dict[str, Any] | None:
    cleaned = clean_text(text)
    if not cleaned:
        return None
    when = str(observed_at or timestamp())
    source_ref = _turn_ref(conversation_id, direction, source_message_id, cleaned, when)
    turn = {
        "source_ref": source_ref,
        "source_message_id": source_message_id,
        "direction": direction,
        "delivery_state": delivery_state,
        "observed_at": when,
        "text": cleaned,
        "actor_role": actor_role,
    }
    turns = load_presence_turns(presence_root, conversation_id)
    if not any(existing.get("source_ref") == source_ref for existing in turns):
        turns.append(turn)
    turns = turns[-MAX_JOURNAL_TURNS:]
    payload = {
        "schema": JOURNAL_SCHEMA,
        "conversation_id": conversation_id,
        "updated_at": timestamp(),
        "turns": turns,
    }
    path = _journal_path(presence_root, conversation_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return turn


def build_presence_conversation_context(
    presence_root: Path,
    conversation: dict[str, Any],
) -> dict[str, Any]:
    conversation_id = str(conversation.get("conversation_id") or "").strip()
    channel = str(conversation.get("channel") or "presence").strip().lower()
    if not conversation_id:
        raise ValueError("Presence conversation requires conversation_id")
    turns = load_presence_turns(presence_root, conversation_id)
    return build_conversation_context(
        conversation_id=conversation_id,
        channel=channel,
        turns=turns,
        source_refs=[f"presence_conversation:{conversation_id}"],
    )
