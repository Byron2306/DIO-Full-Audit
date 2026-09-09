from __future__ import annotations

from pathlib import Path
from typing import Any

from .customer_cases import create_or_attach_case, list_cases, load_case, update_case
from .state import now, read_json, write_json


INDEX_SCHEMA = "dio.customer_case_outlook_index.v1"


def _norm_email(value: Any) -> str:
    return str(value or "").strip().lower()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _index_path(state_root: Path) -> Path:
    return Path(state_root) / "customer_cases" / "outlook_index.json"


def _load_index(state_root: Path) -> dict[str, Any]:
    path = _index_path(state_root)
    if not path.exists():
        return {"schema": INDEX_SCHEMA, "threads": {}, "messages": {}}
    try:
        value = read_json(path)
    except Exception:
        return {"schema": INDEX_SCHEMA, "threads": {}, "messages": {}}
    if value.get("schema") != INDEX_SCHEMA:
        return {"schema": INDEX_SCHEMA, "threads": {}, "messages": {}}
    if not isinstance(value.get("threads"), dict):
        value["threads"] = {}
    if not isinstance(value.get("messages"), dict):
        value["messages"] = {}
    return value


def _save_index(state_root: Path, index: dict[str, Any]) -> None:
    index["schema"] = INDEX_SCHEMA
    write_json(_index_path(state_root), index)


def _verified_email_case(state_root: Path, email: str) -> dict[str, Any] | None:
    if not email:
        return None
    matches = [
        row
        for row in list_cases(Path(state_root), limit=10000)
        if _norm_email(row.get("contact_email")) == email
    ]
    # Ambiguous identity is not silently collapsed into one customer case.
    return matches[0] if len(matches) == 1 else None


def _attach_outlook_evidence(
    state_root: Path,
    case: dict[str, Any],
    *,
    message_id: str,
    thread_id: str,
    sender_email: str,
    sender_verified: bool,
    subject: str,
    body_preview: str,
    received_at: str | None,
) -> dict[str, Any]:
    channels = list(case.get("channel_origins") or [])
    if "email" not in channels:
        channels.append("email")

    outlook = dict(case.get("outlook") or {})
    message_ids = list(outlook.get("message_ids") or [])
    thread_ids = list(outlook.get("thread_ids") or [])
    if message_id and message_id not in message_ids:
        message_ids.append(message_id)
    if thread_id and thread_id not in thread_ids:
        thread_ids.append(thread_id)
    outlook["message_ids"] = message_ids
    outlook["thread_ids"] = thread_ids
    outlook.setdefault("draft_ids", list((case.get("outlook") or {}).get("draft_ids") or []))
    outlook.setdefault("send_receipt_ids", list((case.get("outlook") or {}).get("send_receipt_ids") or []))
    outlook["last_inbound"] = {
        "message_id": message_id or None,
        "thread_id": thread_id or None,
        "subject": subject[:300] or None,
        "body_preview": body_preview[:1000] or None,
        "sender_email": sender_email or None,
        "sender_verified": bool(sender_verified),
        "received_at": received_at or now(),
    }

    identities = dict(case.get("customer_identity") or {})
    external_ids = list(identities.get("external_user_ids") or [])
    if sender_verified and sender_email and sender_email not in external_ids:
        external_ids.append(sender_email)
    identities["external_user_ids"] = external_ids

    patch: dict[str, Any] = {
        "channel_origins": channels,
        "outlook": outlook,
        "customer_identity": identities,
        "last_customer_message_at": received_at or now(),
        "authority_created": False,
    }
    if sender_verified and sender_email and not case.get("contact_email"):
        patch["contact_email"] = sender_email
    return update_case(Path(state_root), case, patch=patch)


def reconcile_outlook_message(state_root: Path, message: dict[str, Any]) -> dict[str, Any]:
    """Attach one normalized Outlook inbound message to canonical customer state.

    This function performs no Microsoft Graph call and creates no send, quote,
    payment, fulfilment or release authority. Matching priority is explicit case
    marker, prior message/thread binding, one verified contact email, then a new
    email candidate case.
    """
    state_root = Path(state_root)
    message_id = _text(message.get("message_id") or message.get("id"))
    thread_id = _text(message.get("thread_id") or message.get("conversation_id") or message.get("conversationId"))
    sender_email = _norm_email(message.get("from_email") or message.get("sender_email") or message.get("contact_email"))
    sender_verified = bool(message.get("sender_verified") or message.get("identity_verified"))
    explicit_case_id = _text(message.get("case_id") or message.get("dio_case_id"))
    subject = _text(message.get("subject"))
    body_preview = _text(message.get("body_preview") or message.get("preview"))
    received_at = _text(message.get("received_at") or message.get("receivedDateTime")) or None

    if not message_id and not thread_id:
        raise ValueError("normalized Outlook message requires message_id or thread_id")

    index = _load_index(state_root)
    case: dict[str, Any] | None = None
    match_reason: str | None = None

    if explicit_case_id:
        case = load_case(state_root, explicit_case_id)
        if case is None:
            raise ValueError(f"explicit customer case not found: {explicit_case_id}")
        match_reason = "explicit_case_marker"

    if case is None and message_id:
        bound_case_id = (index.get("messages") or {}).get(message_id)
        if bound_case_id:
            case = load_case(state_root, str(bound_case_id))
            if case is not None:
                match_reason = "outlook_message_binding"

    if case is None and thread_id:
        bound_case_id = (index.get("threads") or {}).get(thread_id)
        if bound_case_id:
            case = load_case(state_root, str(bound_case_id))
            if case is not None:
                match_reason = "outlook_thread_binding"

    if case is None and sender_verified and sender_email:
        case = _verified_email_case(state_root, sender_email)
        if case is not None:
            match_reason = "verified_contact_email"

    if case is None:
        conversation_key = thread_id or message_id
        case = create_or_attach_case(
            state_root,
            conversation_id=f"OUTLOOK-{conversation_key}",
            channel="email",
            external_user_id=sender_email or f"outlook:{message_id or thread_id}",
            contact_email=sender_email if sender_verified and sender_email else None,
        )
        match_reason = "new_email_candidate"

    case = _attach_outlook_evidence(
        state_root,
        case,
        message_id=message_id,
        thread_id=thread_id,
        sender_email=sender_email,
        sender_verified=sender_verified,
        subject=subject,
        body_preview=body_preview,
        received_at=received_at,
    )

    if message_id:
        index.setdefault("messages", {})[message_id] = case["case_id"]
    if thread_id:
        index.setdefault("threads", {})[thread_id] = case["case_id"]
    _save_index(state_root, index)

    return {
        "schema": "dio.outlook_customer_case_reconciliation.v1",
        "case_id": case["case_id"],
        "match_reason": match_reason,
        "message_id": message_id or None,
        "thread_id": thread_id or None,
        "sender_verified": sender_verified,
        "authority_created": False,
        "external_effects": False,
    }
