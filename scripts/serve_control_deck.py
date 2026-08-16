#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_operator_dashboard import ROOT, DEFAULT_POLICY, build_dashboard_state, utc_now, write_json
from commerce.orchestrator import CommercialOrchestrator
from scripts.approve_lingua_crystals import crystallize_approval
from scripts.approve_campaign import record_campaign_approval
from scripts.manage_mail_intent import approve_intent, emit_event, intent_path, read_json, reject_intent
from scripts.manage_product_workflow import (
    DEFAULT_EVENT_LOG as PRODUCT_EVENT_LOG,
    DEFAULT_STATE_ROOT as PRODUCT_STATE_ROOT,
    approve_intake as approve_product_intake,
    approve_output as approve_product_output,
    load_workflow as load_product_workflow,
    prepare_notification as prepare_product_notification,
    process_job as process_product_job,
    reject_intake as reject_product_intake,
)
from scripts.manage_sophia_commercial import (
    DEFAULT_EDGE_CONFIG,
    DEFAULT_JOB_ROOT,
    DEFAULT_REVIEW_ROOT,
    DEFAULT_SOPHIA_ROOT,
    approve_job,
    load_job,
    prepare_delivery,
    quote_job as quote_sophia_job,
    reconcile_payment,
    run_job,
)
from scripts.manage_vamp_commercial import (
    DEFAULT_EDGE_CONFIG as VAMP_EDGE_CONFIG,
    DEFAULT_EVENT_LOG as VAMP_EVENT_LOG,
    DEFAULT_JOB_ROOT as VAMP_JOB_ROOT,
    DEFAULT_OUTPUT_ROOT as VAMP_OUTPUT_ROOT,
    approve_job as approve_vamp_job,
    load_job as load_vamp_job,
    prepare_delivery as prepare_vamp_delivery,
    quote_job as quote_vamp_job,
    reconcile_payment as reconcile_vamp_payment,
    run_job as run_vamp_job,
)
from scripts.manage_document_studio_commercial import (
    DEFAULT_EDGE_CONFIG as DOCUMENT_EDGE_CONFIG,
    DEFAULT_EVENT_LOG as DOCUMENT_EVENT_LOG,
    DEFAULT_JOB_ROOT as DOCUMENT_JOB_ROOT,
    DEFAULT_OUTPUT_ROOT as DOCUMENT_OUTPUT_ROOT,
    approve_job as approve_document_job,
    load_job as load_document_job,
    prepare_delivery as prepare_document_delivery,
    quote_job as quote_document_job,
    reconcile_payment as reconcile_document_payment,
    run_job as run_document_job,
)
from scripts.sync_outlook_mail import DEFAULT_RECEIPT_DIR, GraphClient, create_outlook_draft, load_config, send_outlook_draft
from scripts.manage_video_release import approve_review as approve_video_review, release_public as release_public_video, upload_private as upload_private_video
from scripts.manage_prospect_outreach import prepare_outlook_draft as prepare_prospect_draft, upgrade_outlook_draft as upgrade_prospect_draft
from scripts.promote_lead_to_product_job import promote_lead
from market_command.catalog import load_json as load_market_json
from market_command.core import MarketStore
from scripts.build_multichannel_campaign_factory import build as build_creative_factory, promote_family
from scripts.run_nichefoundry_media_pipeline import run_media_pipeline


POLICY_PATH = ROOT / "state" / "control_policy.json"
EVENT_LOG = ROOT / "telemetry" / "dio_events.jsonl"
ALLOWED_POLICY = {
    "outbound_mail": {"off", "on"},
    "automation": {"paused", "running"},
    "fulfilment_release": {"hold", "release"},
    "lead_capture": {"hold", "accept"},
    "data_processing": {"hold", "process"},
    "campaign_release": {"hold", "release"},
    "invoice_authority": {"draft_only", "issue"},
    "payment_mode": {"sandbox", "live"},
}


def load_policy() -> dict[str, Any]:
    if not POLICY_PATH.exists():
        policy = {**DEFAULT_POLICY, "updated_at": utc_now(), "updated_by": "system_default"}
        write_json(POLICY_PATH, policy)
        return policy
    return {**DEFAULT_POLICY, **json.loads(POLICY_PATH.read_text(encoding="utf-8"))}


def require_policy(key: str, expected: str, action: str) -> None:
    actual = load_policy().get(key)
    if actual != expected:
        raise ValueError(f"{action} is held by {key}={actual}; set it to {expected} in the Control Deck.")


def edge_config_for_policy() -> Path:
    return ROOT / "config" / ("dio_edge.live.json" if load_policy().get("payment_mode") == "live" else "dio_edge.local.json")


def update_policy(changes: dict[str, Any]) -> dict[str, Any]:
    if not changes or any(key not in ALLOWED_POLICY for key in changes):
        raise ValueError("Only documented control policy fields may be changed.")
    for key, value in changes.items():
        if value not in ALLOWED_POLICY[key]:
            raise ValueError(f"Invalid value for {key}.")
    before = load_policy()
    policy = {**before, **changes, "schema": "dio.control_policy.v1", "updated_at": utc_now(), "updated_by": "control_deck"}
    write_json(POLICY_PATH, policy)
    emit_event(
        EVENT_LOG,
        "control.policy_changed",
        "action",
        "control_policy",
        "DIO-CONTROL",
        {"changes": changes, "previous": {key: before.get(key) for key in changes}},
    )
    return policy


def operate_transaction(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "")
    if action != "reconcile" or payload.get("confirmed") is not True:
        raise ValueError("Commercial reconciliation requires explicit operator confirmation.")
    require_policy("automation", "running", "Commercial transaction reconciliation")
    receipt = CommercialOrchestrator(ROOT).run(stage_jobs=True)
    return {"status": "completed", "action": action, "receipt": receipt}


def operate_sophia(payload: dict[str, Any]) -> dict[str, Any]:
    job_id = str(payload.get("job_id") or "")
    action = str(payload.get("action") or "")
    if action == "quote":
        require_policy("invoice_authority", "issue", "Invoice issuance")
        result = quote_sophia_job(DEFAULT_JOB_ROOT, job_id, edge_config_for_policy(), EVENT_LOG)
    elif action == "reconcile-payment":
        result = reconcile_payment(DEFAULT_JOB_ROOT, job_id, edge_config_for_policy(), EVENT_LOG)
    elif action == "run":
        require_policy("automation", "running", "Sophia automation")
        require_policy("data_processing", "process", "Sophia processing")
        result = run_job(DEFAULT_JOB_ROOT, job_id, EVENT_LOG, "http://127.0.0.1:7070", DEFAULT_SOPHIA_ROOT, DEFAULT_REVIEW_ROOT)
    elif action == "approve":
        if payload.get("confirmed") is not True:
            raise ValueError("Sophia approval requires explicit operator confirmation.")
        result = approve_job(DEFAULT_JOB_ROOT, job_id, "DIO operator via control deck", EVENT_LOG)
    elif action == "prepare-delivery":
        require_policy("fulfilment_release", "release", "Sophia fulfilment")
        result = prepare_delivery(DEFAULT_JOB_ROOT, job_id, EVENT_LOG)
    elif action == "outlook-draft":
        require_policy("outbound_mail", "on", "Outlook draft creation")
        _, job = load_job(DEFAULT_JOB_ROOT, job_id)
        mail_intent_id = (job.get("delivery") or {}).get("mail_intent_id")
        if not mail_intent_id:
            raise ValueError("Prepare the Sophia delivery intent before creating an Outlook draft.")
        graph = GraphClient(load_config(ROOT / "config" / "microsoft_graph.local.json"))
        graph.acquire_token(interactive=False)
        result = create_outlook_draft(graph, ROOT / "state" / "mail_intents", EVENT_LOG, mail_intent_id)
    else:
        raise ValueError("Unknown Sophia operator action.")
    return {"status": "completed", "action": action, "result": result}


def operate_vamp(payload: dict[str, Any]) -> dict[str, Any]:
    job_id = str(payload.get("job_id") or "")
    action = str(payload.get("action") or "")
    if action == "quote":
        require_policy("invoice_authority", "issue", "Invoice issuance")
        result = quote_vamp_job(VAMP_JOB_ROOT, job_id, edge_config_for_policy(), VAMP_EVENT_LOG)
    elif action == "reconcile-payment":
        result = reconcile_vamp_payment(VAMP_JOB_ROOT, job_id, edge_config_for_policy(), VAMP_EVENT_LOG)
    elif action == "run":
        require_policy("automation", "running", "VAMP automation")
        require_policy("data_processing", "process", "VAMP processing")
        result = run_vamp_job(VAMP_JOB_ROOT, job_id, VAMP_OUTPUT_ROOT, VAMP_EVENT_LOG)
    elif action == "approve":
        if payload.get("confirmed") is not True:
            raise ValueError("VAMP approval requires explicit operator confirmation.")
        result = approve_vamp_job(VAMP_JOB_ROOT, job_id, "DIO operator via control deck", VAMP_EVENT_LOG)
    elif action == "prepare-delivery":
        require_policy("fulfilment_release", "release", "VAMP fulfilment")
        result = prepare_vamp_delivery(VAMP_JOB_ROOT, job_id, VAMP_EVENT_LOG)
    elif action == "outlook-draft":
        require_policy("outbound_mail", "on", "Outlook draft creation")
        _, job = load_vamp_job(VAMP_JOB_ROOT, job_id)
        mail_intent_id = (job.get("delivery") or {}).get("mail_intent_id")
        if not mail_intent_id:
            raise ValueError("Prepare the VAMP delivery intent before creating an Outlook draft.")
        graph = GraphClient(load_config(ROOT / "config" / "microsoft_graph.local.json"))
        graph.acquire_token(interactive=False)
        result = create_outlook_draft(graph, ROOT / "state" / "mail_intents", VAMP_EVENT_LOG, mail_intent_id)
    else:
        raise ValueError("Unknown VAMP operator action.")
    return {"status": "completed", "action": action, "result": result}


def operate_document_studio(payload: dict[str, Any]) -> dict[str, Any]:
    job_id = str(payload.get("job_id") or "")
    action = str(payload.get("action") or "")
    if action == "quote":
        require_policy("invoice_authority", "issue", "Invoice issuance")
        result = quote_document_job(DOCUMENT_JOB_ROOT, job_id, edge_config_for_policy(), DOCUMENT_EVENT_LOG)
    elif action == "reconcile-payment":
        result = reconcile_document_payment(DOCUMENT_JOB_ROOT, job_id, edge_config_for_policy(), DOCUMENT_EVENT_LOG)
    elif action == "run":
        require_policy("automation", "running", "Document Studio automation")
        require_policy("data_processing", "process", "Document Studio processing")
        result = run_document_job(DOCUMENT_JOB_ROOT, job_id, DOCUMENT_OUTPUT_ROOT, DOCUMENT_EVENT_LOG)
    elif action == "approve":
        if payload.get("confirmed") is not True:
            raise ValueError("Document Studio approval requires explicit operator confirmation.")
        result = approve_document_job(DOCUMENT_JOB_ROOT, job_id, "DIO operator via control deck", DOCUMENT_EVENT_LOG)
    elif action == "prepare-delivery":
        require_policy("fulfilment_release", "release", "Document Studio fulfilment")
        result = prepare_document_delivery(DOCUMENT_JOB_ROOT, job_id, DOCUMENT_EVENT_LOG)
    elif action == "outlook-draft":
        require_policy("outbound_mail", "on", "Outlook draft creation")
        _, job = load_document_job(DOCUMENT_JOB_ROOT, job_id)
        mail_intent_id = (job.get("delivery") or {}).get("mail_intent_id")
        if not mail_intent_id:
            raise ValueError("Prepare the Document Studio delivery intent before creating an Outlook draft.")
        graph = GraphClient(load_config(ROOT / "config" / "microsoft_graph.local.json"))
        graph.acquire_token(interactive=False)
        result = create_outlook_draft(graph, ROOT / "state" / "mail_intents", DOCUMENT_EVENT_LOG, mail_intent_id)
    else:
        raise ValueError("Unknown Document Studio operator action.")
    return {"status": "completed", "action": action, "result": result}


def operate_product(payload: dict[str, Any]) -> dict[str, Any]:
    job_id = str(payload.get("job_id") or "")
    action = str(payload.get("action") or "")
    if action in {"approve-intake", "reject-intake", "approve-output"} and payload.get("confirmed") is not True:
        raise ValueError("Product approval decisions require explicit operator confirmation.")
    if action == "approve-intake":
        require_policy("lead_capture", "accept", "Lead and intake acceptance")
        result = approve_product_intake(PRODUCT_STATE_ROOT, job_id, "DIO operator via control deck", PRODUCT_EVENT_LOG)
    elif action == "reject-intake":
        result = reject_product_intake(PRODUCT_STATE_ROOT, job_id, "DIO operator via control deck", PRODUCT_EVENT_LOG)
    elif action == "process":
        require_policy("automation", "running", "Product automation")
        require_policy("data_processing", "process", "Product processing")
        result = process_product_job(PRODUCT_STATE_ROOT, job_id, PRODUCT_EVENT_LOG)
    elif action == "approve-output":
        result = approve_product_output(PRODUCT_STATE_ROOT, job_id, "DIO operator via control deck", PRODUCT_EVENT_LOG)
    elif action == "prepare-notification":
        require_policy("fulfilment_release", "release", "Product notification")
        result = prepare_product_notification(PRODUCT_STATE_ROOT, job_id, PRODUCT_EVENT_LOG)
    elif action == "outlook-draft":
        require_policy("outbound_mail", "on", "Outlook draft creation")
        _, workflow = load_product_workflow(PRODUCT_STATE_ROOT, job_id)
        mail_intent_id = (workflow.get("notification") or {}).get("mail_intent_id")
        if not mail_intent_id:
            raise ValueError("Prepare the product notification before creating an Outlook draft.")
        graph = GraphClient(load_config(ROOT / "config" / "microsoft_graph.local.json"))
        graph.acquire_token(interactive=False)
        result = create_outlook_draft(graph, ROOT / "state" / "mail_intents", PRODUCT_EVENT_LOG, mail_intent_id)
    else:
        raise ValueError("Unknown HOMS or Evidex operator action.")
    return {"status": "completed", "action": action, "result": result}


def operate_campaign(payload: dict[str, Any]) -> dict[str, Any]:
    layer = str(payload.get("layer") or "")
    action = str(payload.get("action") or "")
    if not layer or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for char in layer):
        raise ValueError("Invalid campaign layer.")
    if action not in {"approve", "reject"} or payload.get("confirmed") is not True:
        raise ValueError("Campaign release decisions require explicit operator confirmation.")
    if action == "approve":
        require_policy("campaign_release", "release", "Campaign publication approval")
    campaign_dir = ROOT / "campaigns" / "phase3" / layer
    approval = record_campaign_approval(campaign_dir, "approved" if action == "approve" else "rejected", "DIO operator via control deck")
    emit_event(EVENT_LOG, f"campaign.{action}d", "info", "campaign", layer, {"state": approval["state"]})
    return {"status": "completed", "action": action, "result": approval}


def operate_market_campaign(payload: dict[str, Any]) -> dict[str, Any]:
    campaign_id = str(payload.get("campaign_id") or "").upper()
    action = str(payload.get("action") or "")
    if not campaign_id.startswith("CMP-") or not campaign_id.replace("-", "").isalnum():
        raise ValueError("Invalid market campaign id.")
    if action not in {"release-publication", "hold-publication", "refresh-research"} or payload.get("confirmed") is not True:
        raise ValueError("Market campaign actions require explicit operator confirmation.")
    if action == "refresh-research":
        foundry_env = Path("/home/byron/Downloads/NicheFoundry_Phase11/.env")
        command = ["node"]
        if foundry_env.exists():
            command.append(f"--env-file={foundry_env}")
        command.extend([str(ROOT / "scripts" / "refresh_campaign_market_signals.js"), f"--campaign-id={campaign_id}"])
        completed = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, timeout=90)
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout or "Live research refresh failed.").strip()[-1200:])
        result = json.loads(completed.stdout)
        agent_completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "run_hivenance_market_agents.py"), f"--campaign-id={campaign_id}"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if agent_completed.returncode != 0:
            raise RuntimeError((agent_completed.stderr or agent_completed.stdout or "Hivenance market-agent run failed.").strip()[-1200:])
        agent_result = json.loads(agent_completed.stdout)
        event_data = {"signals": result, "agents": agent_result}
        emit_event(EVENT_LOG, "marketing.intelligence_refreshed", "info", "campaign", campaign_id, event_data)
        return {"status": "completed", "action": action, "result": event_data}
    if action == "release-publication":
        require_policy("campaign_release", "release", "Campaign publication approval")
    campaign_root = ROOT / "campaigns" / "dio_market_loop" / "wave4" / "campaigns"
    matches = []
    for hypothesis_path in campaign_root.glob("*/HIVENANCE_HYPOTHESIS.json"):
        hypothesis = read_json(hypothesis_path)
        if str(hypothesis.get("campaign_id") or "").upper() == campaign_id:
            matches.append((hypothesis_path.parent, hypothesis))
    if len(matches) != 1:
        raise ValueError("Market campaign could not be resolved uniquely.")
    campaign_dir, hypothesis = matches[0]
    gates = hypothesis.get("gates") or {}
    if action == "release-publication" and gates.get("publication") != "operator_approval_required":
        raise ValueError("This campaign is not eligible for operator-reviewed publication.")
    now = utc_now()
    decision = {
        "schema": "dio.marketing.operator_release.v1",
        "campaign_id": campaign_id,
        "publication": "released" if action == "release-publication" else "held",
        "direct_outreach": "blocked",
        "direct_outreach_reason": gates.get("reason") or "No permission-safe direct outreach authority is recorded.",
        "decided_at": now,
        "decided_by": "DIO operator via control deck",
    }
    write_json(campaign_dir / "OPERATOR_RELEASE.json", decision)
    emit_event(EVENT_LOG, f"marketing.publication_{'released' if action == 'release-publication' else 'held'}", "info", "campaign", campaign_id, {"publication": decision["publication"], "direct_outreach": "blocked"})
    return {"status": "completed", "action": action, "result": decision}


def operate_market_command(payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "")
    if payload.get("confirmed") is not True:
        raise ValueError("Market Command actions require explicit operator confirmation.")
    store = MarketStore(
        ROOT / "state" / "market_command" / "market_command.sqlite",
        EVENT_LOG,
        load_market_json(ROOT / "config" / "market_command.json"),
    )
    if action == "approve-content":
        return store.approve_content(str(payload.get("content_id") or ""), True)
    campaign_id = str(payload.get("campaign_id") or "")
    if not campaign_id:
        raise ValueError("Market Command campaign id is required.")
    if action == "approve-campaign":
        return store.approve_campaign(campaign_id, True)
    if action == "activate":
        require_policy("campaign_release", "release", "Market Command activation")
        return store.activate_campaign(campaign_id, True)
    if action == "settle":
        return store.settle_campaign(campaign_id, True)
    raise ValueError("Unsupported Market Command action.")


def operate_creative_factory(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("confirmed") is not True:
        raise ValueError("Creative Factory actions require explicit operator confirmation.")
    action = str(payload.get("action") or "")
    if action == "refresh":
        result = build_creative_factory(render_reels=False)
        return {"status": "completed", "action": action, "result": result}
    if action == "media-pipeline":
        result = run_media_pipeline(family_id=str(payload.get("family_id") or ""), render_reel=True)
        return {"status": "completed", "action": action, "result": result}
    if action == "promote":
        return promote_family(str(payload.get("family_id") or ""), str(payload.get("channel_id") or ""))
    raise ValueError("Unsupported Creative Factory action.")


def operate_lead(payload: dict[str, Any]) -> dict[str, Any]:
    lead_id = str(payload.get("lead_id") or "").upper()
    action = str(payload.get("action") or "")
    if action not in {"qualify", "reject", "close", "promote-to-job"} or payload.get("confirmed") is not True:
        raise ValueError("Lead decisions require explicit operator confirmation.")
    if not lead_id.replace("-", "").isalnum():
        raise ValueError("Invalid lead id.")
    path = ROOT / "state" / "leads" / f"{lead_id}.json"
    if not path.exists():
        raise ValueError("Lead does not exist.")
    if action == "promote-to-job":
        require_policy("lead_capture", "accept", "Lead-to-product promotion")
        result = promote_lead(lead_id, controlled=bool(payload.get("controlled")))
        return {"status": "completed", "action": action, "result": result}
    lead = read_json(path)
    if action == "qualify":
        require_policy("lead_capture", "accept", "Lead qualification")
    state = {"qualify": "qualified", "reject": "rejected", "close": "closed"}[action]
    lead["state"] = state
    lead["qualification"] = {
        "state": state if state in {"qualified", "rejected"} else (lead.get("qualification") or {}).get("state"),
        "decided_at": utc_now(),
        "decided_by": "DIO operator via control deck",
    }
    lead["updated_at"] = utc_now()
    write_json(path, lead)
    emit_event(EVENT_LOG, f"lead.{state}", "info", "lead", lead_id, {"product": lead.get("product"), "offer": lead.get("offer")}, lead_id)
    return {"status": "completed", "action": action, "result": lead}


def operate_mail(payload: dict[str, Any]) -> dict[str, Any]:
    mail_intent_id = str(payload.get("mail_intent_id") or "")
    action = str(payload.get("action") or "")
    intent_dir = ROOT / "state" / "mail_intents"
    path = intent_path(intent_dir, mail_intent_id)
    intent = read_json(path)
    if action == "reject":
        if payload.get("confirmed") is not True:
            raise ValueError("Mail rejection requires explicit operator confirmation.")
        result = reject_intent(mail_intent_id, intent_dir, EVENT_LOG)
        return {"status": "completed", "action": action, "result": result}
    if action == "outlook-draft":
        require_policy("outbound_mail", "on", "Outlook draft creation")
        graph = GraphClient(load_config(ROOT / "config" / "microsoft_graph.local.json"))
        graph.acquire_token(interactive=False)
        result = create_outlook_draft(graph, intent_dir, EVENT_LOG, mail_intent_id)
        return {"status": "completed", "action": action, "result": result}
    if action != "approve-send" or payload.get("confirmed") is not True:
        raise ValueError("Approve and send requires explicit operator confirmation.")
    require_policy("outbound_mail", "on", "Outbound mail")
    if not intent.get("provider_draft_id"):
        raise ValueError("Create and review the exact Outlook draft before sending.")
    missing = [value for value in intent.get("attachments") or [] if not Path(value).expanduser().is_file()]
    if missing:
        raise ValueError("Mail send blocked because an attachment is missing.")
    if intent.get("risk") in {"sensitive", "restricted"} and payload.get("recipient_confirmed") is not True:
        raise ValueError("Sensitive mail requires explicit recipient verification.")
    _, token = approve_intent(mail_intent_id, intent_dir, EVENT_LOG, 5)
    graph = GraphClient(load_config(ROOT / "config" / "microsoft_graph.local.json"))
    graph.acquire_token(interactive=False)
    receipt = send_outlook_draft(graph, intent_dir, DEFAULT_RECEIPT_DIR, EVENT_LOG, mail_intent_id, token)
    return {"status": "completed", "action": action, "result": receipt}


def operate_video(payload: dict[str, Any]) -> dict[str, Any]:
    episode_id = str(payload.get("episode_id") or "")
    action = str(payload.get("action") or "")
    if payload.get("confirmed") is not True:
        raise ValueError("Video release actions require explicit operator confirmation.")
    if action == "approve-review":
        result = approve_video_review(episode_id, "DIO operator via control deck")
    elif action == "upload-private":
        require_policy("campaign_release", "release", "Private YouTube upload")
        result = upload_private_video(episode_id, "DIO operator via control deck")
    elif action == "publish-public":
        require_policy("campaign_release", "release", "Public YouTube release")
        result = release_public_video(episode_id, "DIO operator via control deck")
    else:
        raise ValueError("Unknown video release action.")
    return {"status": "completed", "action": action, "result": result}


def operate_prospect(payload: dict[str, Any]) -> dict[str, Any]:
    target_id = str(payload.get("target_id") or "")
    action = str(payload.get("action") or "")
    if payload.get("confirmed") is not True:
        raise ValueError("Prospect outreach actions require explicit operator confirmation.")
    require_policy("outbound_mail", "on", "Prospect Outlook workflow")
    if action == "prepare-draft":
        result = prepare_prospect_draft(
            target_id,
            "DIO operator via control deck",
            payload.get("route_confirmed") is True,
        )
    elif action == "upgrade-draft":
        result = upgrade_prospect_draft(target_id, "DIO operator via control deck")
    elif action == "send":
        state_path = ROOT / "state" / "prospect_outreach" / f"{target_id}.json"
        if not state_path.exists():
            raise ValueError("Prepare and review the prospect Outlook draft first.")
        outreach = read_json(state_path)
        mail_intent_id = str(payload.get("mail_intent_id") or "")
        if not mail_intent_id or mail_intent_id != outreach.get("mail_intent_id"):
            raise ValueError("Prospect mail intent does not match the reviewed target draft.")
        result = operate_mail({
            "mail_intent_id": mail_intent_id,
            "action": "approve-send",
            "confirmed": True,
            "recipient_confirmed": True,
        })
        outreach["state"] = "sent"
        outreach["sent_at"] = utc_now()
        write_json(state_path, outreach)
    else:
        raise ValueError("Unknown prospect outreach action.")
    return {"status": "completed", "action": action, "result": result}


def _lingua_review_path(object_id: str, language: str) -> Path:
    safe_object = "".join(character for character in object_id if character.isalnum() or character in "-_.")
    safe_language = "".join(character for character in language if character.isalnum() or character in "-_")
    if safe_object != object_id or not safe_language:
        raise ValueError("Invalid Lingua semantic object or language identifier.")
    return ROOT / "state" / "lingua" / "reviews" / f"{safe_object}__{safe_language}.json"


def operate_lingua(payload: dict[str, Any]) -> dict[str, Any]:
    object_id = str(payload.get("semantic_object_id") or "")
    language = str(payload.get("target_language") or "")
    action = str(payload.get("action") or "")
    if action not in {"save-review", "approve-language"}:
        raise ValueError("Unknown Lingua review action.")
    object_path = ROOT / "state" / "lingua" / "objects" / f"{object_id}.json"
    if not object_path.is_file():
        raise ValueError("Lingua semantic object does not exist.")
    semantic = read_json(object_path)
    lane = (semantic.get("translations") or {}).get(language)
    if not lane:
        raise ValueError("Target-language lane does not exist on this semantic object.")
    source_hashes = {str(row["unit_id"]): str(row["source_hash"]) for row in (semantic.get("source") or {}).get("units") or []}
    submitted_units = list(payload.get("units") or [])
    if {str(row.get("unit_id") or "") for row in submitted_units} != set(source_hashes):
        raise ValueError("Review must include every current semantic unit exactly once.")
    canonical_units = []
    for row in submitted_units:
        unit_id = str(row.get("unit_id") or "")
        target_text = str(row.get("target_text") or "").strip()
        if not target_text:
            raise ValueError(f"Target text is required for {unit_id}.")
        if row.get("source_hash") != source_hashes[unit_id]:
            raise ValueError(f"Source changed while reviewing {unit_id}; refresh the workspace.")
        flag_resolutions = list(row.get("flag_resolutions") or [])
        canonical_units.append({
            "unit_id": unit_id,
            "source_hash": source_hashes[unit_id],
            "target_text": target_text,
            "approved": bool(row.get("approved")),
            "flag_resolutions": flag_resolutions,
        })
    review = {
        "schema": "dio.lingua.human_approval.v1",
        "approval_state": "approved" if action == "approve-language" else "in_progress",
        "semantic_object_id": object_id,
        "source_version": (semantic.get("source") or {}).get("version"),
        "target_language": language,
        "domain": semantic.get("domain"),
        "origin": semantic.get("origin") or {},
        "reviewer": str(payload.get("reviewer") or "").strip(),
        "reviewer_role": str(payload.get("reviewer_role") or "").strip(),
        "approved_at": utc_now() if action == "approve-language" else "",
        "updated_at": utc_now(),
        "units": canonical_units,
        "terms": list(payload.get("terms") or []),
    }
    review_path = _lingua_review_path(object_id, language)
    if action == "save-review":
        write_json(review_path, review)
        emit_event(EVENT_LOG, "lingua.review_saved", "info", "lingua_semantic_object", object_id, {"target_language": language})
        return {"status": "saved", "action": action, "review_path": str(review_path)}
    if payload.get("confirmed") is not True:
        raise ValueError("Lingua semantic approval requires explicit confirmation.")
    if not review["reviewer"] or not review["reviewer_role"]:
        raise ValueError("Reviewer name and proficient-language role are required.")
    if not all(row["approved"] for row in canonical_units):
        raise ValueError("Every semantic unit must be approved before crystallization.")
    lane_units = {str(row.get("unit_id") or ""): row for row in lane.get("units") or []}
    for submitted in canonical_units:
        lane_unit = lane_units[submitted["unit_id"]]
        flags = list(lane_unit.get("qa_flags") or [])
        resolutions = submitted["flag_resolutions"]
        if len(resolutions) != len(flags) or any(item.get("resolution") not in {"accepted_as_is", "corrected", "not_applicable"} for item in resolutions):
            raise ValueError(f"Resolve every material flag before approving {submitted['unit_id']}.")
    write_json(review_path, review)
    receipt_path = crystallize_approval(review_path)
    emit_event(
        EVENT_LOG,
        "lingua.semantic_authority_crystallized",
        "info",
        "lingua_semantic_object",
        object_id,
        {"target_language": language, "reviewer": review["reviewer"], "receipt": str(receipt_path)},
    )
    return {"status": "crystallized", "action": action, "review_path": str(review_path), "receipt_path": str(receipt_path)}


class ControlDeckHandler(SimpleHTTPRequestHandler):
    server_version = "DIOControlDeck/1.0"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[control-deck] {self.address_string()} {format % args}")

    def send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_GET(self) -> None:
        route = urlsplit(self.path).path
        if route == "/api/control/state":
            state = build_dashboard_state()
            write_json(ROOT / "dashboard" / "state.json", state)
            self.send_json(state)
            return
        if route == "/api/control/policy":
            self.send_json(load_policy())
            return
        if route == "/":
            self.path = "/dashboard/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        route = urlsplit(self.path).path
        if route not in {"/api/control/policy", "/api/control/transaction/action", "/api/control/sophia/action", "/api/control/vamp/action", "/api/control/document-studio/action", "/api/control/product/action", "/api/control/campaign/action", "/api/control/market-campaign/action", "/api/control/market-command/action", "/api/control/creative-factory/action", "/api/control/lead/action", "/api/control/mail/action", "/api/control/video/action", "/api/control/prospect/action", "/api/control/lingua/action"}:
            self.send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            maximum = 65536 if route == "/api/control/lingua/action" else 4096
            if length < 2 or length > maximum:
                raise ValueError(f"Control request must be between 2 and {maximum} bytes.")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Control request must be a JSON object.")
            if route == "/api/control/policy":
                result = update_policy(payload)
            elif route == "/api/control/transaction/action":
                result = operate_transaction(payload)
            elif route == "/api/control/sophia/action":
                result = operate_sophia(payload)
            elif route == "/api/control/vamp/action":
                result = operate_vamp(payload)
            elif route == "/api/control/document-studio/action":
                result = operate_document_studio(payload)
            elif route == "/api/control/campaign/action":
                result = operate_campaign(payload)
            elif route == "/api/control/market-campaign/action":
                result = operate_market_campaign(payload)
            elif route == "/api/control/market-command/action":
                result = operate_market_command(payload)
            elif route == "/api/control/creative-factory/action":
                result = operate_creative_factory(payload)
            elif route == "/api/control/lead/action":
                result = operate_lead(payload)
            elif route == "/api/control/mail/action":
                result = operate_mail(payload)
            elif route == "/api/control/video/action":
                result = operate_video(payload)
            elif route == "/api/control/prospect/action":
                result = operate_prospect(payload)
            elif route == "/api/control/lingua/action":
                result = operate_lingua(payload)
            else:
                result = operate_product(payload)
            self.send_json(result)
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": "control_action_blocked", "message": str(exc)}, HTTPStatus.BAD_REQUEST)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the localhost-only DIO Control Deck.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("The Control Deck must bind to localhost.")
    server = ThreadingHTTPServer((args.host, args.port), ControlDeckHandler)
    print(f"DIO Control Deck: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
