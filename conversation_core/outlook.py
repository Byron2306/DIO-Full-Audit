from __future__ import annotations

from typing import Any, Iterable

from .context import build_conversation_context, clean_text


def _inbound_text(row: dict[str, Any]) -> str:
    body = row.get("body") or {}
    return clean_text(body.get("content") or row.get("body_preview") or "")


def _outbound_text(row: dict[str, Any]) -> str:
    return clean_text(row.get("body") or row.get("body_html") or "")


def build_outlook_conversation_context(
    *,
    conversation_id: str,
    mail_ingress: Iterable[dict[str, Any]],
    mail_intents: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Build context only from provider-captured inbound mail and actually sent mail.

    Outlook drafts and approved-but-unsent intents are deliberately excluded from the
    external conversation history. They may exist operationally, but they are not
    evidence that a customer saw or received anything.
    """
    cid = str(conversation_id or "").strip()
    if not cid:
        raise ValueError("Outlook context requires conversation_id")

    turns: list[dict[str, Any]] = []
    source_refs: list[str] = []
    for row in mail_ingress:
        if str(row.get("conversation_id") or "") != cid:
            continue
        text = _inbound_text(row)
        if not text:
            continue
        ingress_id = str(row.get("mail_ingress_id") or row.get("provider_message_id") or "").strip()
        source_ref = f"mail_ingress:{ingress_id}" if ingress_id else f"outlook_conversation:{cid}"
        source_refs.append(source_ref)
        turns.append({
            "source_ref": source_ref,
            "direction": "inbound",
            "delivery_state": "received",
            "observed_at": row.get("received_at") or row.get("captured_at"),
            "text": text,
            "actor_role": "external_sender",
        })

    for row in mail_intents:
        if str(row.get("conversation_id") or "") != cid:
            continue
        if str(row.get("send_state") or "") != "sent":
            continue
        text = _outbound_text(row)
        if not text:
            continue
        intent_id = str(row.get("mail_intent_id") or "").strip()
        source_ref = f"mail_intent:{intent_id}" if intent_id else f"outlook_conversation:{cid}"
        source_refs.append(source_ref)
        turns.append({
            "source_ref": source_ref,
            "direction": "outbound",
            "delivery_state": "sent",
            "observed_at": row.get("sent_at") or row.get("updated_at") or row.get("created_at"),
            "text": text,
            "actor_role": "dio_operator_approved",
        })

    return build_conversation_context(
        conversation_id=cid,
        channel="outlook_email",
        turns=turns,
        source_refs=source_refs,
    )
