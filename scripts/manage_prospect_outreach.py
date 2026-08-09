#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from scripts.build_operator_dashboard import utc_now, write_json
from scripts.manage_mail_intent import create_intent_from_payload, emit_event
from scripts.prospect_outreach_copy import message_for as c3_message_for
from scripts.sync_outlook_mail import GraphClient, create_outlook_draft, load_config


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "DIO_Prospect_Intelligence_Wave4.zip"
STATE_ROOT = ROOT / "state" / "prospect_outreach"
INTENT_ROOT = ROOT / "state" / "mail_intents"
EVENT_LOG = ROOT / "telemetry" / "dio_events.jsonl"
GRAPH_CONFIG = ROOT / "config" / "microsoft_graph.local.json"
ALLOWED_ROUTE_STATES = {
    "PARTNERSHIP_ROUTE_AVAILABLE",
    "INSTITUTIONAL_ROUTE_AVAILABLE",
    "PUBLIC_ROUTE_PRESENT_REVERIFY_ROLE",
}

PRODUCT_PROOF = {
    "HOMS_ASSESS": {
        "label": "HOMS Assessment Desk",
        "eyebrow": "CONTROLLED ASSESSMENT PILOT",
        "headline": "One subject. One grade. One reviewable proof.",
        "accent": "#176B5B",
        "soft": "#EAF5F1",
        "items": ["CAPS-aware brief", "Paper + memo/rubric", "Educator approval"],
    },
    "HOMS_LEARN": {
        "label": "HOMS Learning Studio",
        "eyebrow": "CONTROLLED LEARNING-MATERIAL PILOT",
        "headline": "One curriculum spine, prepared for human review.",
        "accent": "#176B5B",
        "soft": "#EAF5F1",
        "items": ["Term-aware content", "Worksheet or lesson", "Educator approval"],
    },
    "SOPHIA_LEARN": {
        "label": "HOMS Learning Studio",
        "eyebrow": "CONTROLLED LEARNING-MATERIAL PILOT",
        "headline": "One curriculum spine, prepared for human review.",
        "accent": "#176B5B",
        "soft": "#EAF5F1",
        "items": ["Term-aware guide", "Practice and assessment", "Educator approval"],
    },
    "SOPHIA_REVIEW": {
        "label": "Sophia Academic Review",
        "eyebrow": "ACADEMIC REVIEW PROOF",
        "headline": "Claims, references and reviewer notes made inspectable.",
        "accent": "#8B3D63",
        "soft": "#F8ECF2",
        "items": ["Reference checks", "Claim mapping", "Human reviewer authority"],
    },
    "EVIDEX": {
        "label": "Evidex Evidence Packs",
        "eyebrow": "EVIDENCE-PACK PROOF",
        "headline": "Messy evidence, mapped into a defensible pack.",
        "accent": "#245B78",
        "soft": "#EAF2F7",
        "items": ["Evidence table", "Mapped claims", "Review trail"],
    },
    "EVIDEX_PACK": {
        "label": "Evidex Evidence Packs",
        "eyebrow": "EVIDENCE-PACK PROOF",
        "headline": "Messy evidence, mapped into a defensible pack.",
        "accent": "#245B78",
        "soft": "#EAF2F7",
        "items": ["Evidence table", "Mapped claims", "Review trail"],
        "product_key": "evidex",
    },
    "VAMP": {
        "label": "VAMP Evidence Snapshot",
        "eyebrow": "PERFORMANCE-EVIDENCE PROOF",
        "headline": "Existing work evidence, mapped before review day.",
        "accent": "#6A4B2E",
        "soft": "#F4EFE9",
        "items": ["Criteria mapping", "Gap visibility", "Human acceptance"],
    },
}


def target_rows() -> list[dict[str, str]]:
    with zipfile.ZipFile(ARCHIVE) as archive:
        name = next(value for value in archive.namelist() if value.endswith("/buyer_unit_targets.csv"))
        text = archive.read(name).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def resolve_target(target_id: str) -> dict[str, str]:
    if not re.fullmatch(r"W4-TGT-\d{4}", target_id):
        raise ValueError("Invalid prospect target id.")
    matches = [row for row in target_rows() if row.get("target_id") == target_id]
    if len(matches) != 1:
        raise ValueError("Prospect target could not be resolved uniquely.")
    return matches[0]


def public_recipients(target: dict[str, str]) -> list[str]:
    values = [value.strip().lower() for value in (target.get("public_contact_route") or "").split(";")]
    return [value for value in values if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value)]


def proof_profile(target: dict[str, str]) -> dict[str, Any]:
    """Legacy presentation profile retained for dashboard compatibility.

    C3 no longer uses this object to choose rhetoric. Copy is rendered from a CSO and
    an explicit communicative-act contract in `scripts.prospect_outreach_copy`.
    """
    product_line_id = target.get("product_line_id") or ""
    profile = PRODUCT_PROOF.get(product_line_id)
    if profile:
        return profile
    product = target.get("product_name") or product_line_id or "DIO controlled pilot"
    return {
        "label": product,
        "eyebrow": "CONTROLLED PROFESSIONAL PILOT",
        "headline": "A bounded proof, prepared for human review.",
        "accent": "#245B78",
        "soft": "#EAF2F7",
        "items": ["Bounded input", "Reviewable output", "Human authority"],
    }


def message_for(target: dict[str, str]) -> tuple[str, str, str]:
    """Compatibility entry point routed through the C3 communicative-act engine."""
    return c3_message_for(target)


def write_preview(target_id: str, body_html: str) -> Path:
    preview_path = STATE_ROOT / "previews" / f"{target_id}.html"
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.write_text(body_html, encoding="utf-8")
    return preview_path


def prepare_outlook_draft(target_id: str, actor: str, route_confirmed: bool) -> dict[str, Any]:
    if not route_confirmed:
        raise ValueError("Confirm that you reviewed the current public route before drafting outreach.")
    target = resolve_target(target_id)
    if target.get("do_not_contact", "").strip().lower() == "yes":
        raise ValueError("This prospect is marked do-not-contact.")
    if target.get("route_state") not in ALLOWED_ROUTE_STATES:
        raise ValueError("This target does not have an email-eligible public partnership route. Use its submission or self-service link instead.")
    recipients = public_recipients(target)
    if not recipients:
        raise ValueError("No public email route is recorded for this target.")
    state_path = STATE_ROOT / f"{target_id}.json"
    if state_path.exists():
        existing = json.loads(state_path.read_text(encoding="utf-8"))
        if existing.get("mail_intent_id"):
            return existing
    subject, body, body_html = message_for(target)
    preview_path = write_preview(target_id, body_html)
    intent = create_intent_from_payload(
        {
            "purpose": "prospect_partnership_enquiry",
            "campaign_id": target_id,
            "recipient": recipients[0],
            "subject": subject,
            "body": body,
            "body_html": body_html,
            "attachments": [],
            "risk": "moderate",
        },
        INTENT_ROOT,
        EVENT_LOG,
    )
    graph = GraphClient(load_config(GRAPH_CONFIG))
    graph.acquire_token(interactive=False)
    draft = create_outlook_draft(graph, INTENT_ROOT, EVENT_LOG, intent["mail_intent_id"])
    state = {
        "schema": "dio.prospect_outreach.v1",
        "target_id": target_id,
        "organisation": target["organisation"],
        "product_line_id": target["product_line_id"],
        "recipient": recipients[0],
        "alternate_public_recipients": recipients[1:],
        "source_url": target.get("contact_source"),
        "source_verified_date": target.get("contact_verified_date"),
        "route_state": target.get("route_state"),
        "route_confirmed_at": utc_now(),
        "route_confirmed_by": actor,
        "mail_intent_id": intent["mail_intent_id"],
        "provider_draft_id": draft.get("provider_draft_id"),
        "email_preview": str(preview_path),
        "creative_state": "communicative_act_rendered_proof_card_ready",
        "communicative_act": "cold_permission_request",
        "consent_mode": "once_off_request",
        "state": "outlook_draft_ready",
        "created_at": utc_now(),
    }
    write_json(state_path, state)
    emit_event(EVENT_LOG, "prospect.outlook_draft_ready", "action", "prospect", target_id, {"mail_intent_id": intent["mail_intent_id"], "organisation": target["organisation"], "communicative_act": "cold_permission_request"})
    return state


def upgrade_outlook_draft(target_id: str, actor: str) -> dict[str, Any]:
    target = resolve_target(target_id)
    state_path = STATE_ROOT / f"{target_id}.json"
    if not state_path.exists():
        raise ValueError("Prepare the Outlook draft before upgrading its creative.")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    mail_intent_id = state.get("mail_intent_id")
    intent_path = INTENT_ROOT / f"{mail_intent_id}.json"
    if not mail_intent_id or not intent_path.exists():
        raise ValueError("The prospect mail intent is missing.")
    intent = json.loads(intent_path.read_text(encoding="utf-8"))
    if intent.get("send_state") == "sent":
        raise ValueError("A sent prospect email cannot be rewritten.")
    provider_draft_id = intent.get("provider_draft_id") or state.get("provider_draft_id")
    if not provider_draft_id:
        raise ValueError("The Outlook provider draft is missing.")
    subject, body, body_html = message_for(target)
    graph = GraphClient(load_config(GRAPH_CONFIG))
    graph.acquire_token(interactive=False)
    graph.json(
        "PATCH",
        f"/me/messages/{provider_draft_id}",
        headers={"Content-Type": "application/json"},
        json={"subject": subject, "body": {"contentType": "HTML", "content": body_html}},
    )
    preview_path = write_preview(target_id, body_html)
    intent["subject"] = subject
    intent["body"] = body
    intent["body_html"] = body_html
    intent["updated_at"] = utc_now()
    write_json(intent_path, intent)
    state.update(
        {
            "email_preview": str(preview_path),
            "creative_state": "communicative_act_rendered_proof_card_ready",
            "communicative_act": "cold_permission_request",
            "consent_mode": "once_off_request",
            "draft_upgraded_at": utc_now(),
            "draft_upgraded_by": actor,
        }
    )
    write_json(state_path, state)
    emit_event(
        EVENT_LOG,
        "prospect.outlook_draft_upgraded",
        "info",
        "prospect",
        target_id,
        {"mail_intent_id": mail_intent_id, "creative_state": "communicative_act_rendered_proof_card_ready", "communicative_act": "cold_permission_request", "consent_mode": "once_off_request"},
    )
    return state
