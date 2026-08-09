#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import re
import urllib.parse
import zipfile
from pathlib import Path
from typing import Any

from scripts.build_operator_dashboard import utc_now, write_json
from scripts.commercial_language import prospect_consent_context, render_consent_request
from scripts.dio_mail_branding import MAIN_SITE, branded_email, product_profile
from scripts.manage_mail_intent import create_intent_from_payload, emit_event
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
        "headline": "One subject. One grade. One proof you can inspect.",
        "items": ["CAPS-aware brief", "Paper + memo/rubric", "Educator approval"],
        "product_key": "homs",
        "proof_summary": "the assessment proof shows the brief, generated paper, memo or rubric, and the educator approval point",
    },
    "HOMS_LEARN": {
        "label": "HOMS Learning Studio",
        "eyebrow": "CONTROLLED LEARNING-MATERIAL PILOT",
        "headline": "One curriculum spine, carried through the whole pack.",
        "items": ["Term-aware content", "Worksheet or lesson", "Educator approval"],
        "product_key": "homs_learning",
        "proof_summary": "the learning proof connects the curriculum topic to the guide, activity, assessment and educator review point",
    },
    "SOPHIA_LEARN": {
        "label": "HOMS Learning Studio",
        "eyebrow": "CONTROLLED LEARNING-MATERIAL PILOT",
        "headline": "One curriculum spine, carried through the whole pack.",
        "items": ["Term-aware guide", "Practice and assessment", "Educator approval"],
        "product_key": "homs_learning",
        "proof_summary": "the learning proof connects the curriculum topic to the guide, practice, assessment and educator review point",
    },
    "SOPHIA_REVIEW": {
        "label": "Sophia Academic Review",
        "eyebrow": "ACADEMIC REVIEW PROOF",
        "headline": "See exactly what the review flags and why.",
        "items": ["Reference checks", "Claim mapping", "Reviewer commentary"],
        "product_key": "sophia",
        "proof_summary": "the review proof separates reference problems, claim-to-source fit and reviewer commentary without rewriting the author's work",
    },
    "EVIDEX": {
        "label": "Evidex Evidence Packs",
        "eyebrow": "EVIDENCE-PACK PROOF",
        "headline": "From scattered evidence to a pack you can defend.",
        "items": ["Evidence table", "Mapped claims", "Review trail"],
        "product_key": "evidex",
        "proof_summary": "the evidence proof shows source files becoming an evidence table, mapped claims, visible gaps and a final review trail",
    },
    "EVIDEX_PACK": {
        "label": "Evidex Evidence Packs",
        "eyebrow": "EVIDENCE-PACK PROOF",
        "headline": "From scattered evidence to a pack you can defend.",
        "items": ["Evidence table", "Mapped claims", "Review trail"],
        "product_key": "evidex",
        "proof_summary": "the evidence proof shows source files becoming an evidence table, mapped claims, visible gaps and a final review trail",
    },
    "VAMP": {
        "label": "VAMP Evidence Snapshot",
        "eyebrow": "PERFORMANCE-EVIDENCE PROOF",
        "headline": "Know what evidence you have before review day.",
        "items": ["Objective mapping", "Gap visibility", "Human acceptance"],
        "product_key": "vamp",
        "proof_summary": "the performance proof maps existing evidence to objectives, shows gaps and leaves acceptance and ratings with the authorised reviewer",
    },
    "VAMP_ACADEMIC": {
        "label": "VAMP Evidence Snapshot",
        "eyebrow": "PERFORMANCE-EVIDENCE PROOF",
        "headline": "Know what evidence you have before review day.",
        "items": ["Objective mapping", "Gap visibility", "Human acceptance"],
        "product_key": "vamp",
        "proof_summary": "the performance proof maps existing evidence to objectives, shows gaps and leaves acceptance and ratings with the authorised reviewer",
    },
    "DOCUMENT_STUDIO": {
        "label": "DIO Document Studio",
        "eyebrow": "CONTROLLED DOCUMENT PILOT",
        "headline": "See every important edit, term and translation decision.",
        "items": ["Clean copy", "Visible change trail", "Human language review"],
        "product_key": "document_studio",
        "proof_summary": "the document proof shows the clean copy, visible edits, terminology controls and the human language-review boundary",
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
    product_line_id = target.get("product_line_id") or ""
    profile = PRODUCT_PROOF.get(product_line_id)
    if profile:
        return profile
    product = target.get("product_name") or product_line_id or "DIO controlled pilot"
    return {
        "label": product,
        "eyebrow": "CONTROLLED PROFESSIONAL PILOT",
        "headline": "See the real work before deciding on a pilot.",
        "items": ["Source input", "Concrete output", "Professional review"],
        "product_key": "dio",
        "proof_summary": "the proof shows the original input, the produced work and the point where professional review remains required",
    }


def _reply_link(subject: str, body: str) -> str:
    return "mailto:dio_workflows@outlook.com?" + urllib.parse.urlencode({"subject": subject, "body": body})


def message_for(target: dict[str, str]) -> tuple[str, str, str]:
    profile = proof_profile(target)
    product = profile["label"]
    product_key = profile["product_key"]
    product_url = product_profile(product_key)["url"]
    context = prospect_consent_context(
        target,
        product_name=product,
        proof_summary=str(target.get("proof_summary") or profile["proof_summary"]),
    )
    rendered = render_consent_request(context)
    organisation = context.organisation or "your organisation"

    identity = "I am Byron Bunt from DIO Workflows. I am testing this as a small professional service, not asking you to buy software or book a sales call."
    plain_paragraphs = [rendered["intro"], identity, *rendered["body"]]
    body = "\n\n".join(
        [
            rendered["greeting"],
            *plain_paragraphs,
            f"DIO Workflows: {MAIN_SITE}\n{product}: {product_url}",
            "If you are happy to receive the example, reply YES. If not, reply NO and I will record that preference.",
            "This is a once-off consent request. This address will not be added to a mailing list and no further marketing message will be sent without consent.",
            "Regards,\nByron Bunt\nDIO Workflows\ndio_workflows@outlook.com",
        ]
    ) + "\n"

    yes_url = _reply_link(
        f"YES - {product} proof example",
        f"YES, {organisation} consents to receive one {product} proof example by email.\n\nPreferred contact method: Email",
    )
    no_url = _reply_link(
        f"NO - {product} outreach",
        f"NO, {organisation} does not consent to receive marketing about {product}. Please record this preference.",
    )
    _, body_html = branded_email(
        product=product_key,
        eyebrow=profile["eyebrow"],
        headline=profile["headline"],
        greeting=rendered["greeting"],
        intro=rendered["intro"],
        body=[identity, *rendered["body"]],
        bullets=profile["items"],
        cta_label="YES, send the proof",
        cta_url=yes_url,
        secondary_label="NO, thank you",
        secondary_url=no_url,
        caution=(
            "This is a once-off request for consent. DIO Workflows will not add this address to a mailing list "
            "or send further marketing without consent. Reply NO at any time to record that communications must cease."
        ),
    )
    return rendered["subject"], body, body_html


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
        "creative_state": "commercial_context_v1",
        "consent_mode": "once_off_request",
        "state": "outlook_draft_ready",
        "created_at": utc_now(),
    }
    write_json(state_path, state)
    emit_event(
        EVENT_LOG,
        "prospect.outlook_draft_ready",
        "action",
        "prospect",
        target_id,
        {"mail_intent_id": intent["mail_intent_id"], "organisation": target["organisation"], "copy_engine": "dio.commercial.message_context.v1"},
    )
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
            "creative_state": "commercial_context_v1",
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
        {"mail_intent_id": mail_intent_id, "creative_state": "commercial_context_v1", "consent_mode": "once_off_request"},
    )
    return state
