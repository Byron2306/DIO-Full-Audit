#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commerce.expression_guarded import CommunicativeAct, render_expression  # noqa: E402
from commerce.semantic import commercial_semantic_object_from_lead  # noqa: E402
from commerce.semantic_judgement import judge_mail_intent  # noqa: E402
from conversation_core.context import assert_valid_conversation_context  # noqa: E402
from scripts.manage_mail_intent import create_intent_from_payload, intent_path, read_json, write_json  # noqa: E402


DEFAULT_LEAD_ROOT = ROOT / "state" / "leads"
DEFAULT_CONTEXT_ROOT = ROOT / "state" / "conversation_context"
DEFAULT_INTENT_ROOT = ROOT / "state" / "mail_intents"
DEFAULT_INGRESS_ROOT = ROOT / "state" / "mail_ingress"
DEFAULT_EVENT_LOG = ROOT / "telemetry" / "dio_events.jsonl"
DEFAULT_REPLY_ROOT = ROOT / "state" / "conversation_replies"


def _safe_id(value: str) -> str:
    text = str(value or "").strip()
    if not text or any(not (char.isalnum() or char in "-_.") for char in text):
        raise ValueError("Invalid lead id")
    return text


def _load_context(context_root: Path, conversation_id: str) -> tuple[dict[str, Any], Path]:
    index_path = context_root / "INDEX.json"
    if not index_path.exists():
        raise FileNotFoundError("Conversation context index is missing. Run reconcile_conversation_context.py first.")
    index = read_json(index_path)
    row = (index.get("contexts") or {}).get(conversation_id)
    if not isinstance(row, dict):
        raise FileNotFoundError(f"No conversation context is registered for {conversation_id}")
    path_value = str(row.get("path") or "")
    context_path = (context_root.parents[1] / path_value).resolve() if path_value else context_root / f"{row.get('context_id')}.json"
    if not context_path.exists():
        context_path = context_root / f"{row.get('context_id')}.json"
    context = read_json(context_path)
    assert_valid_conversation_context(context)
    if context.get("conversation_id") != conversation_id:
        raise ValueError("Conversation context index points to a mismatched conversation")
    return context, context_path


def _load_source_ingress(root: Path, source_ref: str, conversation_id: str) -> tuple[dict[str, Any], Path]:
    if not source_ref.startswith("mail_ingress:"):
        raise ValueError("Conversation reply requires a Microsoft Graph mail-ingress source reference.")
    ingress_id = _safe_id(source_ref.removeprefix("mail_ingress:"))
    ingress_path = root / "state" / "mail_ingress" / f"{ingress_id}.json"
    if not ingress_path.is_file():
        raise FileNotFoundError(f"Latest Outlook ingress record is missing: {ingress_id}")
    ingress = read_json(ingress_path)
    if ingress.get("schema") != "dio.mail_ingress.v1":
        raise ValueError("Conversation source is not a DIO Outlook mail-ingress record.")
    if str(ingress.get("conversation_id") or "") != conversation_id:
        raise ValueError("Latest Outlook ingress record belongs to a different conversation.")
    provider_message_id = str(ingress.get("provider_message_id") or "").strip()
    if not provider_message_id:
        raise ValueError("Latest Outlook ingress record has no Microsoft Graph provider message id.")
    return ingress, ingress_path


def _reply_intent_id(lead_id: str, context_id: str, source_ref: str) -> str:
    digest = hashlib.sha256(f"{lead_id}\n{context_id}\n{source_ref}".encode("utf-8")).hexdigest()[:14].upper()
    return f"MAIL-REPLY-{digest}"


def _act_for_lead(lead: dict[str, Any]) -> CommunicativeAct:
    state = str(((lead.get("qualification") or {}).get("state")) or lead.get("state") or "").lower()
    return CommunicativeAct.QUALIFIED_LEAD_REPLY if state == "qualified" else CommunicativeAct.INBOUND_REPLY


def prepare_conversation_reply(
    lead_id: str,
    *,
    root: Path = ROOT,
    lead_root: Path | None = None,
    context_root: Path | None = None,
    intent_root: Path | None = None,
    event_log: Path | None = None,
    reply_root: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    lead_root = (lead_root or root / "state" / "leads").resolve()
    context_root = (context_root or root / "state" / "conversation_context").resolve()
    intent_root = (intent_root or root / "state" / "mail_intents").resolve()
    event_log = (event_log or root / "telemetry" / "dio_events.jsonl").resolve()
    reply_root = (reply_root or root / "state" / "conversation_replies").resolve()

    lead_id = _safe_id(lead_id)
    lead_path = lead_root / f"{lead_id}.json"
    if not lead_path.exists():
        raise FileNotFoundError(f"Lead not found: {lead_id}")
    lead = read_json(lead_path)
    conversation_id = str(lead.get("conversation_id") or "").strip()
    recipient = str((lead.get("contact") or {}).get("email") or "").strip()
    if not conversation_id or not recipient:
        raise ValueError("Conversation reply requires a bound Outlook conversation and lead email")

    context, context_path = _load_context(context_root, conversation_id)
    if context["channel"] != "outlook_email":
        raise ValueError("This reply preparer accepts Outlook conversation context only")
    if context["thread"]["state"] != "awaiting_dio_response":
        raise ValueError(f"Conversation is not awaiting a DIO response: {context['thread']['state']}")

    latest = context["observations"].get("latest_inbound_excerpt") or {}
    source_ref = str(latest.get("source_ref") or "").strip()
    if not source_ref:
        raise ValueError("Conversation has no authoritative latest inbound message")
    ingress, ingress_path = _load_source_ingress(root, source_ref, conversation_id)
    provider_message_id = str(ingress["provider_message_id"])

    cso = commercial_semantic_object_from_lead(lead)
    act = _act_for_lead(lead)
    expression = render_expression(cso, act, context={"conversation_context": context})

    original_subject = str(ingress.get("subject") or (lead.get("request") or {}).get("subject") or "").strip()
    subject = original_subject if original_subject.lower().startswith("re:") else (f"Re: {original_subject}" if original_subject else str(expression.get("subject") or "DIO reply"))
    intent_id = _reply_intent_id(lead_id, context["context_id"], source_ref)
    existing_path = intent_path(intent_root, intent_id)
    if existing_path.exists():
        return read_json(existing_path)

    semantic_binding = {
        "semantic_object_id": cso["object_id"],
        "conversation_context_id": context["context_id"],
        "communicative_act": act.value,
        "conversation_context_authority": "expression_only",
        "source_ref": source_ref,
        "provider_message_id": provider_message_id,
    }
    intent = create_intent_from_payload(
        {
            "mail_intent_id": intent_id,
            "purpose": "conversation_reply",
            "communicative_act": act.value,
            "semantic_binding": semantic_binding,
            "lead_id": lead_id,
            "conversation_id": conversation_id,
            "source_message_id": provider_message_id,
            "recipient": recipient,
            "subject": subject,
            "body": expression["body"],
            "attachments": [],
            "risk": "moderate",
        },
        intent_root,
        event_log,
    )

    judgement, judgement_path = judge_mail_intent(
        root,
        cso,
        expression,
        intent,
        source_paths=[lead_path, context_path, ingress_path],
    )
    intent["semantic_judgement"] = {
        "judgement_id": judgement["judgement_id"],
        "path": str(judgement_path.relative_to(root)),
        "verdict": judgement["verdict"],
        "execution_binding_sha256": judgement["bindings"]["execution_binding_sha256"],
        "commercial_semantic_object_sha256": judgement["bindings"]["commercial_semantic_object_sha256"],
        "expression_sha256": judgement["bindings"]["expression_sha256"],
    }
    write_json(existing_path, intent)

    reply_root.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema": "dio.conversation_reply_candidate.v2",
        "lead_id": lead_id,
        "conversation_id": conversation_id,
        "mail_intent_id": intent_id,
        "communicative_act": act.value,
        "semantic_object_id": cso["object_id"],
        "conversation_context_id": context["context_id"],
        "thread_state": context["thread"]["state"],
        "source_ref": source_ref,
        "provider_message_id": provider_message_id,
        "expression": expression,
        "semantic_judgement": {
            "judgement_id": judgement["judgement_id"],
            "verdict": judgement["verdict"],
            "path": str(judgement_path.relative_to(root)),
            "metatron": judgement["triune"]["metatron"]["status"],
            "loki": judgement["triune"]["loki"]["status"],
            "beast": judgement["triune"]["beast"]["status"],
            "obligations": judgement["obligations"],
        },
        "authority": {
            "mail_send_authorized": False,
            "operator_approval_required": True,
            "semantic_judgement_grants_execution_authority": False,
            "conversation_context_may_establish_fact": False,
            "conversation_context_may_grant_execution_authority": False,
        },
    }
    write_json(reply_root / f"{intent_id}.json", receipt)
    return intent


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a Triune-judged context-aware Outlook reply as a review-required mail intent.")
    parser.add_argument("lead_id")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(prepare_conversation_reply(args.lead_id, root=args.root), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
