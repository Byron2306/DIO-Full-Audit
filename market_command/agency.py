from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from market_command.catalog import load_catalogs
from market_command.core import MarketStore, utc_now
from market_command.events import emit_event
from market_command.procurement import build_media_brief
from scripts.dio_mail_branding import MAIN_SITE, branded_email
from scripts.manage_mail_intent import create_intent_from_payload, write_json


def agency_by_id(root: Path, agency_id: str) -> dict[str, Any]:
    partners = load_catalogs(root)["agencies"]["partners"]
    partner = next((row for row in partners if row.get("id") == agency_id), None)
    if not partner:
        raise ValueError(f"Unknown agency_id: {agency_id}")
    return partner


def outreach_path(root: Path, campaign_id: str, agency_id: str) -> Path:
    safe_campaign = "".join(c for c in campaign_id if c.isalnum() or c in "-_")
    safe_agency = "".join(c for c in agency_id if c.isalnum() or c in "-_")
    if safe_campaign != campaign_id or safe_agency != agency_id:
        raise ValueError("Invalid campaign or agency identifier")
    return root / "state" / "market_command" / "agency_outreach" / safe_campaign / f"{safe_agency}.json"


def list_agency_outreach(root: Path) -> list[dict[str, Any]]:
    base = root / "state" / "market_command" / "agency_outreach"
    rows: list[dict[str, Any]] = []
    if base.exists():
        for path in base.glob("*/*.json"):
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
                row["state_path"] = str(path)
                rows.append(row)
            except (OSError, json.JSONDecodeError):
                continue
    return sorted(rows, key=lambda row: row.get("updated_at") or row.get("created_at") or "", reverse=True)


def _mail_copy(campaign: dict[str, Any], partner: dict[str, Any], placement: str) -> tuple[str, str, str]:
    subject = f"RFQ: bounded South African pilot for {campaign['name']}"
    placement_text = placement or "the most suitable measurable placement for this audience"
    return (
        subject,
        *branded_email(
            product="dio",
            eyebrow="MEDIA PILOT RFQ",
            headline="Request for a measurable South African campaign pilot.",
            greeting=f"Hello {partner['name']} team,",
            intro="DIO Workflows is preparing a small, controlled campaign pilot and would like a clear quotation before any spend is authorised.",
            body=[
                f"Product: {campaign['name']}",
                f"Audience: {campaign['audience']}",
                f"Objective: {campaign['objective']}",
                f"Placement interest: {placement_text}",
                "Please propose your minimum viable pilot, with agency fees, media spend and third-party costs separated. The attached brief lists the measurement, attribution and commercial fields we need to compare options.",
                "This is a request for quotation only. It is not a booking, insertion order or spend authorisation.",
            ],
            reference=str(campaign.get("campaign_id") or campaign.get("id") or ""),
            cta_label="View DIO Workflows",
            cta_url=MAIN_SITE,
            bullets=["Measured pilots", "Human spend approval", "Attribution before scale"],
        ),
    )


def prepare_agency_rfq(
    root: Path,
    store: MarketStore,
    campaign_id: str,
    agency_id: str,
    placement: str,
    actor: str,
    route_confirmed: bool,
) -> dict[str, Any]:
    if not route_confirmed:
        raise ValueError("Confirm the current public agency enquiry route before preparing an RFQ.")
    partner = agency_by_id(root, agency_id)
    if partner.get("status") != "public_route_verified":
        raise ValueError("This agency has not passed public-route qualification and remains research-only.")
    inquiry = partner.get("inquiry") or {}
    if inquiry.get("permission") not in {"single_rfq_only", "rfq_after_scale_proof"}:
        raise ValueError("No qualified RFQ permission route is recorded for this agency.")
    if inquiry.get("permission") == "rfq_after_scale_proof":
        raise ValueError("This enterprise route is held until DIO has external scale proof.")

    path = outreach_path(root, campaign_id, agency_id)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    campaign = store.get_campaign(campaign_id)
    brief = build_media_brief(root, campaign, partner, placement)
    brief_path = Path(brief["output_dir"]) / "MEDIA_BUY_BRIEF.md"
    buy = store.create_media_buy({
        "vendor_id": agency_id,
        "product_line_id": campaign["product_line_id"],
        "campaign_id": campaign_id,
        "placement": placement or "agency recommendation requested",
        "quote_minor": 0,
        "approved_cap_minor": 0,
        "currency": campaign.get("currency") or "ZAR",
        "creative_spec": campaign.get("creative_brief"),
        "notes": f"Governed agency RFQ package: {brief_path}",
    })

    mail_intent_id = None
    recipient = inquiry.get("email")
    if inquiry.get("mode") == "email" and recipient:
        subject, body, body_html = _mail_copy(campaign, partner, placement)
        intent = create_intent_from_payload(
            {
                "purpose": "agency_request_for_quotation",
                "campaign_id": campaign_id,
                "recipient": recipient,
                "subject": subject,
                "body": body,
                "body_html": body_html,
                "attachments": [str(brief_path)],
                "risk": "moderate",
            },
            root / "state" / "mail_intents",
            root / "telemetry" / "dio_events.jsonl",
        )
        mail_intent_id = intent["mail_intent_id"]

    state = {
        "schema": "dio.agency_outreach.v1",
        "campaign_id": campaign_id,
        "agency_id": agency_id,
        "agency_name": partner["name"],
        "media_buy_id": buy["media_buy_id"],
        "route_mode": inquiry.get("mode"),
        "route_url": inquiry.get("url"),
        "recipient": recipient,
        "route_verified_at": utc_now(),
        "route_verified_by": actor,
        "brief_dir": brief["output_dir"],
        "mail_intent_id": mail_intent_id,
        "provider_draft_id": None,
        "state": "mail_intent_ready" if mail_intent_id else "public_form_package_ready",
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    write_json(path, state)
    emit_event(
        root / "telemetry" / "dio_events.jsonl",
        "market.agency_rfq_prepared",
        "action",
        "media_buy",
        buy["media_buy_id"],
        {"agency_id": agency_id, "campaign_id": campaign_id, "mail_intent_id": mail_intent_id, "route_mode": inquiry.get("mode")},
        campaign_id,
    )
    return state


def bind_outlook_draft(root: Path, campaign_id: str, agency_id: str, receipt: dict[str, Any]) -> dict[str, Any]:
    path = outreach_path(root, campaign_id, agency_id)
    state = json.loads(path.read_text(encoding="utf-8"))
    state.update({
        "provider_draft_id": receipt.get("provider_draft_id"),
        "conversation_id": receipt.get("conversation_id"),
        "state": "outlook_draft_ready",
        "updated_at": utc_now(),
    })
    write_json(path, state)
    return state
