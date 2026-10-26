from __future__ import annotations

import os
from typing import Any

VESPER_IDENTITY = {
    "name": "Vesper",
    "role": "DIO Presence Core",
    "authority": "bounded_presence",
}

SAFE_EXTERNAL_REPLY_INTENTS = {
    "help",
    "general_info",
    "product_info",
    "pricing_info",
    "intake_request",
    "status_request",
    "translation_info",
    "formatting_info",
    "attachment_received",
    "unknown",
    "operator_summary",
    "campaign_summary",
    "revenue_summary",
    "mail_summary",
    "job_summary",
    "needs_you",
}


def telegram_reply_switch_enabled() -> bool:
    """External replies are fail-closed unless explicitly enabled."""
    raw = os.getenv("DIO_PRESENCE_CORE_TELEGRAM_REPLIES", "0")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def authorize_external_reply(
    envelope: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    decision = result.get("decision") or {}
    authority = result.get("authority") or {}
    intent = str(decision.get("intent") or "")
    channel = str(envelope.get("channel") or "")
    reasons: list[str] = []

    if not telegram_reply_switch_enabled():
        reasons.append("external_reply_switch_disabled")
    if channel != "telegram":
        reasons.append("channel_not_telegram")
    if intent not in SAFE_EXTERNAL_REPLY_INTENTS:
        reasons.append("intent_not_reply_authorized")
    if authority.get("spend_authorized"):
        reasons.append("reply_path_cannot_spend")
    if authority.get("fulfilment_released"):
        reasons.append("reply_path_cannot_release_fulfilment")
    if authority.get("attachment_processed"):
        reasons.append("reply_path_cannot_process_attachment")

    text = str(((result.get("reply") or {}).get("text")) or "").strip()
    if not text:
        reasons.append("reply_text_missing")

    return {
        "schema": "dio.vesper.external_reply_authority.v1",
        "identity": dict(VESPER_IDENTITY),
        "authorized": not reasons,
        "channel": channel,
        "intent": intent,
        "reasons": reasons,
        "external_action_type": "telegram_reply",
        "spend_authorized": False,
        "fulfilment_release_authorized": False,
        "attachment_processing_authorized": False,
    }


def bind_external_action_receipt(
    result: dict[str, Any],
    receipt: dict[str, Any],
    *,
    sent: bool,
    error: str | None = None,
) -> dict[str, Any]:
    authority = dict(result.get("authority") or {})
    authority["presence_identity"] = dict(VESPER_IDENTITY)
    authority["external_reply_authority"] = receipt
    authority["executed_external_action"] = bool(sent)
    authority["external_action_type"] = str(receipt.get("external_action_type") or "telegram_reply") if sent else None
    result["authority"] = authority
    result["core_reply_sent"] = bool(sent)
    if error:
        result["core_reply_send_error"] = str(error)[:300]
    else:
        result.pop("core_reply_send_error", None)
    return result
