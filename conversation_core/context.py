from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "dio.conversation_context.v1"
TURN_DIRECTIONS = frozenset({"inbound", "outbound"})
DELIVERY_STATES = frozenset({"received", "sent", "prepared"})
MAX_CONTEXT_TURNS = 40
MAX_TEXT_CHARS = 4000
MAX_OBSERVATION_CHARS = 360

REQUEST_RE = re.compile(
    r"\b(please|could you|can you|would you|would it be possible|i need|i want|i(?:'|’)d like|"
    r"i would like|send|provide|confirm|quote|revise|update|let me know|tell me|share|attach|"
    r"explain|clarify|check|review)\b",
    re.IGNORECASE,
)

TONE_TERMS: dict[str, tuple[str, ...]] = {
    "appreciative": ("thank", "thanks", "appreciate", "grateful"),
    "concerned": ("concern", "worried", "problem", "issue", "frustrat", "disappoint"),
    "urgent": ("urgent", "asap", "immediately", "deadline", "today", "time-sensitive", "time sensitive"),
    "formal": ("dear ", "kindly", "regards", "sincerely", "please"),
}


def timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_context_id(conversation_id: str, channel: str) -> str:
    digest = hashlib.sha256(f"{channel}\n{conversation_id}".encode("utf-8")).hexdigest()[:20].upper()
    return f"CTX-{digest}"


def _refs(values: Iterable[Any] | None) -> list[str]:
    return list(dict.fromkeys(str(value).strip() for value in (values or []) if str(value).strip()))


def clean_text(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return " ".join(text.replace("\u00a0", " ").split())[:MAX_TEXT_CHARS]


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _sort_key(turn: dict[str, Any]) -> tuple[datetime, str]:
    parsed = _parse_time(turn.get("observed_at")) or datetime.min.replace(tzinfo=timezone.utc)
    return parsed, str(turn.get("source_ref") or "")


def normalize_turn(turn: dict[str, Any]) -> dict[str, Any]:
    direction = str(turn.get("direction") or "").lower()
    delivery_state = str(turn.get("delivery_state") or "").lower()
    if direction not in TURN_DIRECTIONS:
        raise ValueError(f"conversation turn direction must be one of {sorted(TURN_DIRECTIONS)}")
    if delivery_state not in DELIVERY_STATES:
        raise ValueError(f"conversation turn delivery_state must be one of {sorted(DELIVERY_STATES)}")
    source_ref = str(turn.get("source_ref") or "").strip()
    if not source_ref:
        raise ValueError("conversation turn requires source_ref")
    text = clean_text(turn.get("text"))
    if not text:
        raise ValueError("conversation turn requires non-empty text")
    observed_at = str(turn.get("observed_at") or timestamp())
    return {
        "source_ref": source_ref,
        "direction": direction,
        "delivery_state": delivery_state,
        "observed_at": observed_at,
        "text": text,
        "actor_role": str(turn.get("actor_role") or "unknown")[:80],
    }


def _sentences(text: str) -> list[str]:
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [" ".join(part.split())[:MAX_OBSERVATION_CHARS] for part in parts if part.strip()]


def _questions(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for turn in turns:
        if turn["direction"] != "inbound" or turn["delivery_state"] != "received":
            continue
        for sentence in _sentences(turn["text"]):
            if "?" not in sentence:
                continue
            rows.append({
                "text": sentence,
                "source_ref": turn["source_ref"],
                "observed_at": turn["observed_at"],
                "state": "observed_message_text",
            })
    return rows[-12:]


def _requests(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for turn in turns:
        if turn["direction"] != "inbound" or turn["delivery_state"] != "received":
            continue
        for sentence in _sentences(turn["text"]):
            if not REQUEST_RE.search(sentence):
                continue
            rows.append({
                "text": sentence,
                "source_ref": turn["source_ref"],
                "observed_at": turn["observed_at"],
                "state": "observed_message_text",
            })
    return rows[-12:]


def _tone(turns: list[dict[str, Any]]) -> dict[str, Any]:
    inbound = [turn for turn in turns if turn["direction"] == "inbound" and turn["delivery_state"] == "received"]
    latest = inbound[-1] if inbound else None
    if not latest:
        return {
            "labels": ["unknown"],
            "state": "derived",
            "method": "bounded_lexical_tone_v1",
            "source_refs": [],
        }
    text = latest["text"].lower()
    labels = [name for name, terms in TONE_TERMS.items() if any(term in text for term in terms)]
    word_count = len(latest["text"].split())
    if word_count <= 24:
        labels.append("brief")
    if not labels:
        labels = ["neutral"]
    return {
        "labels": list(dict.fromkeys(labels)),
        "state": "derived",
        "method": "bounded_lexical_tone_v1",
        "source_refs": [latest["source_ref"]],
    }


def _external_turns(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        turn for turn in turns
        if (turn["direction"] == "inbound" and turn["delivery_state"] == "received")
        or (turn["direction"] == "outbound" and turn["delivery_state"] == "sent")
    ]


def _thread_state(turns: list[dict[str, Any]]) -> str:
    external = _external_turns(turns)
    if not external:
        return "no_external_turns"
    latest = external[-1]
    return "awaiting_dio_response" if latest["direction"] == "inbound" else "waiting_on_external"


def _open_questions(turns: list[dict[str, Any]], questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sent_outbound = [
        _parse_time(turn["observed_at"])
        for turn in turns
        if turn["direction"] == "outbound" and turn["delivery_state"] == "sent"
    ]
    last_sent = max((value for value in sent_outbound if value), default=None)
    rows = []
    for question in questions:
        q_time = _parse_time(question["observed_at"])
        if last_sent is None or q_time is None or q_time > last_sent:
            rows.append({**question, "resolution_state": "no_later_recorded_outbound_reply"})
    return rows[-8:]


def build_conversation_context(
    *,
    conversation_id: str,
    channel: str,
    turns: Iterable[dict[str, Any]],
    source_refs: Iterable[Any] | None = None,
) -> dict[str, Any]:
    conversation_id = str(conversation_id or "").strip()
    channel = str(channel or "").strip().lower()
    if not conversation_id or not channel:
        raise ValueError("conversation context requires conversation_id and channel")

    normalized = sorted((normalize_turn(dict(turn)) for turn in turns), key=_sort_key)[-MAX_CONTEXT_TURNS:]
    questions = _questions(normalized)
    requests = _requests(normalized)
    open_questions = _open_questions(normalized, questions)
    inbound = [turn for turn in normalized if turn["direction"] == "inbound" and turn["delivery_state"] == "received"]
    sent_outbound = [turn for turn in normalized if turn["direction"] == "outbound" and turn["delivery_state"] == "sent"]
    prepared_outbound = [turn for turn in normalized if turn["direction"] == "outbound" and turn["delivery_state"] == "prepared"]
    all_refs = _refs([*(source_refs or []), *(turn["source_ref"] for turn in normalized)])
    last_request = requests[-1] if requests else None
    last_inbound = inbound[-1] if inbound else None
    last_sent = sent_outbound[-1] if sent_outbound else None

    context = {
        "schema": SCHEMA,
        "context_id": stable_context_id(conversation_id, channel),
        "conversation_id": conversation_id,
        "channel": channel,
        "created_at": timestamp(),
        "updated_at": timestamp(),
        "source_refs": all_refs,
        "thread": {
            "state": _thread_state(normalized),
            "turn_count": len(normalized),
            "external_turn_count": len(_external_turns(normalized)),
            "inbound_received": len(inbound),
            "outbound_sent": len(sent_outbound),
            "outbound_prepared": len(prepared_outbound),
            "last_inbound_at": last_inbound.get("observed_at") if last_inbound else None,
            "last_outbound_sent_at": last_sent.get("observed_at") if last_sent else None,
        },
        "observations": {
            "questions": questions,
            "open_questions": open_questions,
            "requested_actions": requests,
            "last_requested_action": last_request,
            "latest_inbound_excerpt": {
                "text": last_inbound["text"][:MAX_OBSERVATION_CHARS],
                "source_ref": last_inbound["source_ref"],
                "observed_at": last_inbound["observed_at"],
                "state": "observed_message_text",
            } if last_inbound else None,
        },
        "interpretation": {
            "tone": _tone(normalized),
            "style_hints": _style_hints(_tone(normalized)),
        },
        "authority": {
            "may_shape_expression": True,
            "may_select_response_order": True,
            "may_surface_message_questions": True,
            "may_establish_commercial_fact": False,
            "may_grant_consent": False,
            "may_set_scope": False,
            "may_set_budget": False,
            "may_set_payment_state": False,
            "may_confirm_identity": False,
            "may_grant_execution_authority": False,
        },
        "turns": normalized,
    }
    assert_valid_conversation_context(context)
    return context


def _style_hints(tone: dict[str, Any]) -> list[str]:
    labels = set(tone.get("labels") or [])
    hints: list[str] = []
    if "formal" in labels:
        hints.append("match_formality_without_inventing_relationship")
    if "brief" in labels:
        hints.append("prefer_concise_reply")
    if "concerned" in labels:
        hints.append("acknowledge_concern_without_accepting_unverified_fault")
    if "urgent" in labels:
        hints.append("do_not_manufacture_deadlines_or_priority")
    if "appreciative" in labels:
        hints.append("warm_acknowledgement")
    if not hints:
        hints.append("neutral_professional")
    return hints


def validate_conversation_context(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["conversation context must be an object"]
    if payload.get("schema") != SCHEMA:
        errors.append(f"schema must equal {SCHEMA}")
    for field in ("context_id", "conversation_id", "channel"):
        if not str(payload.get(field) or "").strip():
            errors.append(f"{field} is required")
    refs = payload.get("source_refs")
    if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        errors.append("source_refs must be a list of non-empty strings")
    thread = payload.get("thread")
    if not isinstance(thread, dict):
        errors.append("thread must be an object")
    observations = payload.get("observations")
    if not isinstance(observations, dict):
        errors.append("observations must be an object")
    else:
        for name in ("questions", "open_questions", "requested_actions"):
            if not isinstance(observations.get(name), list):
                errors.append(f"observations.{name} must be a list")
    interpretation = payload.get("interpretation")
    if not isinstance(interpretation, dict):
        errors.append("interpretation must be an object")
    authority = payload.get("authority")
    if not isinstance(authority, dict):
        errors.append("authority must be an object")
    else:
        forbidden_true = (
            "may_establish_commercial_fact",
            "may_grant_consent",
            "may_set_scope",
            "may_set_budget",
            "may_set_payment_state",
            "may_confirm_identity",
            "may_grant_execution_authority",
        )
        for name in forbidden_true:
            if authority.get(name) is not False:
                errors.append(f"authority.{name} must remain false")
    turns = payload.get("turns")
    if not isinstance(turns, list) or len(turns) > MAX_CONTEXT_TURNS:
        errors.append(f"turns must be a list capped at {MAX_CONTEXT_TURNS}")
    else:
        for index, turn in enumerate(turns):
            try:
                normalize_turn(turn)
            except ValueError as exc:
                errors.append(f"turns[{index}]: {exc}")
    return errors


def assert_valid_conversation_context(payload: Any) -> None:
    errors = validate_conversation_context(payload)
    if errors:
        raise ValueError("invalid conversation context: " + "; ".join(errors))


def expression_context_view(payload: dict[str, Any]) -> dict[str, Any]:
    """Return only the bounded conversation fields an expression engine may consume."""
    assert_valid_conversation_context(payload)
    observations = payload["observations"]
    return {
        "schema": payload["schema"],
        "context_id": payload["context_id"],
        "conversation_id": payload["conversation_id"],
        "channel": payload["channel"],
        "thread_state": payload["thread"].get("state"),
        "open_questions": list(observations.get("open_questions") or [])[-4:],
        "last_requested_action": observations.get("last_requested_action"),
        "latest_inbound_excerpt": observations.get("latest_inbound_excerpt"),
        "tone": dict((payload.get("interpretation") or {}).get("tone") or {}),
        "style_hints": list((payload.get("interpretation") or {}).get("style_hints") or []),
        "source_refs": list(payload.get("source_refs") or []),
        "authority": dict(payload["authority"]),
    }


def write_conversation_context(path: Path, payload: dict[str, Any]) -> Path:
    assert_valid_conversation_context(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path
