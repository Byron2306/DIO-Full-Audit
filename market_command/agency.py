from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from commerce.semantic_judgement import judge_mail_intent
from market_command.agency_copy import mail_bundle
from market_command.catalog import load_catalogs
from market_command.core import MarketStore, utc_now
from market_command.events import emit_event
from market_command.procurement import build_media_brief
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
    """Compatibility entry point routed through the C3 RFQ communicative act."""
    bundle = mail_bundle(campaign, partner, placement)
    return bundle["subject"], bundle["body"], bundle["body_html"]


def _find_campaign_source(root: Path, campaign_id: str) -> list[Path]:
    """Bind the judgement to concrete campaign state when a durable campaign file exists."""
    candidates = [
        root / "state" / "market_command" / "campaigns" / f"{campaign_id}.json",
        root / "campaigns" / "dio_market_loop" / "wave4" / "campaigns" / campaign_id / "HIVENANCE_HYPOTHESIS.json",
    ]
    found = [path for path in candidates if path.is_file()]
    return found


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
    semantic_judgement_id = None
    semantic_judgement_verdict = None
    recipient = inquiry.get("email")
    if inquiry.get("mode") == "email" and recipient:
        bundle = mail_bundle(campaign, partner, placement)
        semantic_binding = {
            "semantic_object_id": bundle["cso"]["object_id"],
            "communicative_act": bundle["communicative_act"],
            "campaign_id": campaign_id,
            "vendor_id": agency_id,
            "source_ref": f"vendor:{agency_id}",
        }
        intent = create_intent_from_payload(
            {
                "purpose": "agency_request_for_quotation",
                "communicative_act": bundle["communicative_act"],
                "semantic_binding": semantic_binding,
                "campaign_id": campaign_id,
                "recipient": recipient,
                "subject": bundle["subject"],
                "body": bundle["body"],
                "body_html": bundle["body_html"],
                "attachments": [str(brief_path)],
                "risk": "moderate",
            },
            root / "state" / "mail_intents",
            root / "telemetry" / "dio_events.jsonl",
        )
        source_paths = [brief_path, *_find_campaign_source(root, campaign_id)]
        if not source_paths:
            raise ValueError("Agency RFQ cannot be judged without durable campaign/brief evidence.")
        judgement, judgement_path = judge_mail_intent(
            root,
            bundle["cso"],
            bundle["expression"],
            intent,
            source_paths=source_paths,
        )
        if judgement["verdict"] == "BLOCK":
            raise ValueError(f"Agency RFQ blocked by Triune semantic judgement {judgement['judgement_id']}.")
        intent["semantic_judgement"] = {
            "judgement_id": judgement["judgement_id"],
            "path": str(judgement_path.relative_to(root)),
            "verdict": judgement["verdict"],
            "execution_binding_sha256": judgement["bindings"]["execution_binding_sha256"],
        }
        write_json(root / "state" / "mail_intents" / f"{intent['mail_intent_id']}.json", intent)
        mail_intent_id = intent["mail_intent_id"]
        semantic_judgement_id = judgement["judgement_id"]
        semantic_judgement_verdict = judgement["verdict"]

    state = {
        "schema": "dio.agency_outreach.v2",
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
        "communicative_act": "request_for_quotation",
        "semantic_judgement_id": semantic_judgement_id,
        "semantic_judgement_verdict": semantic_judgement_verdict,
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
        {
            "agency_id": agency_id,
            "campaign_id": campaign_id,
            "mail_intent_id": mail_intent_id,
            "route_mode": inquiry.get("mode"),
            "communicative_act": "request_for_quotation",
            "semantic_judgement_id": semantic_judgement_id,
        },
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
