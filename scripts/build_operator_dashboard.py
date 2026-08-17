#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import os
import re
import socket
import sys
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.manage_product_workflow import next_action as product_next_action  # noqa: E402
from market_command.catalog import load_catalogs  # noqa: E402
from market_command.core import MarketStore  # noqa: E402
from market_command.intelligence import IntelligenceStore  # noqa: E402
from adapters.marketing.readiness import adapter_readiness  # noqa: E402


DEFAULT_POLICY = {
    "schema": "dio.control_policy.v1",
    "outbound_mail": "off",
    "automation": "paused",
    "fulfilment_release": "hold",
    "lead_capture": "accept",
    "data_processing": "process",
    "campaign_release": "hold",
    "invoice_authority": "draft_only",
    "payment_mode": "live",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    return slug or "product-class"


def mail_preview_path(intent: dict[str, Any], source_path: Path) -> str:
    preview_root = ROOT / "state" / "mail_previews"
    intent_id = str(intent.get("mail_intent_id") or source_path.stem)
    safe_id = "".join(character for character in intent_id if character.isalnum() or character in "-_")
    if not safe_id:
        return ""
    preview_path = preview_root / f"{safe_id}.html"
    body_html = intent.get("body_html")
    body = intent.get("body")
    if not body_html and not body:
        return ""
    preview_root.mkdir(parents=True, exist_ok=True)
    if body_html:
        preview_path.write_text(str(body_html), encoding="utf-8")
    else:
        preview_path.write_text(
            "<!doctype html><meta charset='utf-8'>"
            "<body style='font-family:Arial,Helvetica,sans-serif;white-space:pre-wrap;line-height:1.45;padding:24px'>"
            f"{html.escape(str(body or ''), quote=False)}</body>",
            encoding="utf-8",
        )
    return rel(preview_path)


def run_mode(run_name: str, input_path: str) -> str:
    marker = f"{run_name} {input_path}".lower()
    controlled_markers = ("demo", "dry_run", "playwright", "check", "golden", "samples/", "dummy_")
    return "controlled" if any(value in marker for value in controlled_markers) else "live"


def collect_runs(runs_root: Path, deliverables_root: Path) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for summary_path in sorted(runs_root.glob("*/run_summary.json"), reverse=True):
        summary = load_json(summary_path)
        run_name = summary_path.parent.name
        mode = run_mode(run_name, summary.get("input", ""))
        jobs = []
        for item in summary.get("jobs", []):
            job_path = ROOT / item.get("path", "")
            if not job_path.exists():
                job_path = summary_path.parent / item.get("product", "") / f"{item.get('job_id')}.json"
            job = load_json(job_path) if job_path.exists() else {}
            product = item.get("product", job.get("route", {}).get("product", "unknown"))
            job_id = item.get("job_id", job.get("job_id", "unknown"))
            deliverable_dir = deliverables_root / run_name / product / job_id
            approval_path = job_path.with_suffix(".approval.json")
            jobs.append(
                {
                    "job_id": job_id,
                    "product": product,
                    "status": job.get("status", "unknown"),
                    "approval": (job.get("approval") or {}).get("state", "unknown"),
                    "risk": job.get("risk", "unknown"),
                    "route_reason": (job.get("route") or {}).get("reason", ""),
                    "job_path": rel(job_path) if job_path.exists() else "",
                    "deliverable_dir": rel(deliverable_dir) if deliverable_dir.exists() else "",
                    "approval_path": rel(approval_path) if approval_path.exists() else "",
                    "run_name": run_name,
                    "created_at": summary.get("created_at", ""),
                    "mode": mode,
                }
            )
        runs.append({"run_name": run_name, "created_at": summary.get("created_at", ""), "input": summary.get("input", ""), "mode": mode, "jobs": jobs})
    return sorted(runs, key=lambda item: (item.get("created_at", ""), item["run_name"]), reverse=True)


def latest_unique_jobs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep run history intact while presenting one current row per durable job id."""
    jobs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for run in runs:
        for job in run["jobs"]:
            key = job["job_id"]
            if key in seen:
                continue
            seen.add(key)
            jobs.append(job)
    return jobs


def collect_campaigns(campaign_root: Path) -> list[dict[str, Any]]:
    campaigns = []
    for receipt_path in sorted(campaign_root.glob("*/PHASE3_RECEIPT.json")):
        layer_dir = receipt_path.parent
        receipt = load_json(receipt_path)
        opportunity_path = layer_dir / "foundry_opportunity.json"
        metadata_path = layer_dir / "metadata_package.json"
        approval_path = layer_dir / "PHASE3_APPROVAL.json"
        opportunity = load_json(opportunity_path) if opportunity_path.exists() else {}
        metadata = load_json(metadata_path) if metadata_path.exists() else {}
        approval = load_json(approval_path) if approval_path.exists() else {}
        episode = receipt.get("episode") or {}
        free_preview = receipt.get("free_media_preview") or {}
        visual_assets = receipt.get("visual_assets") or {}
        landing_page = receipt.get("landing_page") or {}
        campaigns.append(
            {
                "layer": receipt.get("product_layer", layer_dir.name),
                "status": receipt.get("status", "unknown"),
                "approval": approval.get("state", (receipt.get("approval") or {}).get("state", "unknown")),
                "title": opportunity.get("title", layer_dir.name),
                "video_title": ((metadata.get("snippet") or {}).get("title") or ""),
                "campaign_pack": rel(layer_dir / "CAMPAIGN_PACK.md"),
                "receipt": rel(receipt_path),
                "approval_path": rel(approval_path) if approval_path.exists() else "",
                "episode_dir": episode.get("episode_dir", ""),
                "free_preview": free_preview.get("output", ""),
                "thumbnail": visual_assets.get("thumbnail", ""),
                "landing_page": landing_page.get("path", ""),
            }
        )
    return campaigns


def collect_market_campaigns(root: Path) -> list[dict[str, Any]]:
    campaigns = []
    for campaign_dir in sorted(root.glob("*")):
        if not campaign_dir.is_dir():
            continue
        hypothesis_path = campaign_dir / "HIVENANCE_HYPOTHESIS.json"
        if not hypothesis_path.exists():
            continue
        hypothesis = load_json(hypothesis_path)
        score = load_json(campaign_dir / "NICHEFOUNDRY_SCORE.json") if (campaign_dir / "NICHEFOUNDRY_SCORE.json").exists() else {}
        settlement = load_json(campaign_dir / "HIVENANCE_SETTLEMENT.json") if (campaign_dir / "HIVENANCE_SETTLEMENT.json").exists() else {}
        release = load_json(campaign_dir / "OPERATOR_RELEASE.json") if (campaign_dir / "OPERATOR_RELEASE.json").exists() else {}
        observation = load_json(campaign_dir / "MARKET_OBSERVATION.json") if (campaign_dir / "MARKET_OBSERVATION.json").exists() else {}
        live_signals = load_json(campaign_dir / "LIVE_MARKET_SIGNALS.json") if (campaign_dir / "LIVE_MARKET_SIGNALS.json").exists() else {}
        agent_receipt = load_json(campaign_dir / "HIVENANCE_MARKET_AGENTS.json") if (campaign_dir / "HIVENANCE_MARKET_AGENTS.json").exists() else {}
        proof_update = load_json(campaign_dir / "GOLDEN_PROOF_UPDATE.json") if (campaign_dir / "GOLDEN_PROOF_UPDATE.json").exists() else {}
        latest = settlement.get("latest") or {}
        live_depth = live_signals.get("depth") or {}
        oracle = agent_receipt.get("oracle") or {}
        council = agent_receipt.get("council") or {}
        campaigns.append(
            {
                "campaign_id": hypothesis.get("campaign_id"),
                "product": (hypothesis.get("product") or {}).get("public_name"),
                "mode": (hypothesis.get("experiment") or {}).get("mode"),
                "channel": (hypothesis.get("experiment") or {}).get("channel"),
                "publication": (hypothesis.get("gates") or {}).get("publication"),
                "outreach": (hypothesis.get("gates") or {}).get("electronic_sales_outreach"),
                "foundry_score": (score.get("result") or {}).get("opportunity_score"),
                "foundry_decision": (score.get("result") or {}).get("decision"),
                "registry_observed_at": observation.get("observed_at"),
                "registry_source": ((observation.get("source") or {}).get("kind") or "prospect_registry_wave"),
                "live_search_state": ((live_signals.get("interpretation") or {}).get("status") or "not_refreshed"),
                "live_search_at": ((live_signals.get("search") or {}).get("finished_at")),
                "live_search_query": ((live_signals.get("search") or {}).get("query")),
                "live_result_count": live_depth.get("returned_videos", 0),
                "live_relevant_count": live_depth.get("relevant_videos", 0),
                "live_web_result_count": live_depth.get("returned_news_or_blog_items", 0),
                "live_web_relevant_count": live_depth.get("relevant_news_or_blog_items", 0),
                "live_median_views": live_depth.get("median_views_in_sample", 0),
                "live_top_score": ((live_signals.get("top_opportunities") or [{}])[0].get("opportunity_score") if live_signals.get("top_opportunities") else None),
                "live_signals": rel(campaign_dir / "LIVE_MARKET_SIGNALS.json") if live_signals else "",
                "agent_decision": council.get("decision", "not_run"),
                "agent_regime": oracle.get("regime", "not_run"),
                "agent_family": council.get("selected_family", ""),
                "agent_harmony": council.get("harmony_index"),
                "agent_receipt": rel(campaign_dir / "HIVENANCE_MARKET_AGENTS.json") if agent_receipt else "",
                "proof_state": proof_update.get("proof_state"),
                "proof_review": proof_update.get("subject_expert_review"),
                "proof_update": rel(campaign_dir / "GOLDEN_PROOF_UPDATE.md") if proof_update else "",
                "proof_pointer": proof_update.get("proof_pointer"),
                "settlement": latest.get("decision", "pending"),
                "release_state": release.get("publication", "pending_operator_review"),
                "release_path": rel(campaign_dir / "OPERATOR_RELEASE.json") if release else "",
                "pack": rel(campaign_dir / "CAMPAIGN_PACK.md"),
                "measurement": rel(campaign_dir / "measurement.json"),
            }
        )
    return campaigns


def collect_market_command() -> dict[str, Any]:
    config_path = ROOT / "config" / "market_command.json"
    if not config_path.exists():
        return {"state": "not_installed", "campaigns": [], "content_items": [], "media_buys": [], "attention": [], "totals": {}, "intelligence": {}}
    db_path = ROOT / "state" / "market_command" / "market_command.sqlite"
    store = MarketStore(db_path, ROOT / "telemetry" / "dio_events.jsonl", load_json(config_path))
    state = store.state(load_catalogs(ROOT))
    state["state"] = "operational"
    state["dashboard_url"] = "http://127.0.0.1:8770/"
    state["intelligence"] = IntelligenceStore(db_path, ROOT / "telemetry" / "dio_events.jsonl").state()
    state["adapter_readiness"] = {
        channel["id"]: adapter_readiness(channel["id"])
        for channel in state["catalogs"]["channels"]["channels"]
    }
    factory_path = ROOT / "state" / "marketing_factory" / "CREATIVE_FAMILY_REGISTRY.json"
    state["creative_factory"] = load_json(factory_path) if factory_path.exists() else {
        "schema": "dio.marketing.creative_family_registry.v1",
        "summary": {},
        "families": [],
    }
    return state


def collect_video_candidates(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    registry = load_json(path)
    candidates = []
    for candidate in registry.get("candidates", []):
        gates = candidate.get("gates") or {}
        candidates.append({
            "product_id": candidate.get("product_id"),
            "episode_id": candidate.get("episode_id"),
            "title": candidate.get("title"),
            "status": candidate.get("status"),
            "channel_title": (candidate.get("channel") or {}).get("title"),
            "channel_id": (candidate.get("channel") or {}).get("id"),
            "duration_seconds": candidate.get("duration_seconds"),
            "preflight_passed": bool(candidate.get("preflight_passed")),
            "private_upload_ready": bool(candidate.get("private_upload_ready")),
            "watch_approved": bool(gates.get("video_watch_through_approved")),
            "voice_approved": bool(gates.get("voice_approved")),
            "thumbnail_approved": bool(gates.get("thumbnail_approved")),
            "metadata_approved": bool(gates.get("metadata_approved")),
            "upload_authorised": bool(gates.get("youtube_upload_authorised")),
            "youtube": candidate.get("youtube") or {},
            "video": candidate.get("video"),
            "thumbnail": candidate.get("thumbnail"),
            "candidate": candidate.get("candidate"),
            "compliance_report": candidate.get("compliance_report"),
        })
    return candidates


def collect_product_portfolio(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "state": "not_imported",
            "summary": {},
            "suites": [],
            "incarnations": [],
            "candidates": [],
            "report_path": "",
        }
    registry = load_json(path)
    activation_path = ROOT / "state" / "product_portfolio" / "DIO_PRODUCT_CLASS_ACTIVATION_PLAN.json"
    activation_plan = load_json(activation_path) if activation_path.exists() else {}
    activation_by_product = {
        entry.get("product_class"): entry
        for entry in activation_plan.get("entries", [])
        if entry.get("product_class")
    }
    for row in registry.get("incarnations", []):
        row["activation_plan"] = activation_by_product.get(row.get("Incarnation"), {})
        slug = slugify(row.get("Incarnation", ""))
        manifest_path = ROOT / "state" / "product_class_packages" / slug / "PACKAGE_MANIFEST.json"
        smoke_path = ROOT / "state" / "product_class_packages" / slug / "SMOKE_TEST_RECEIPT.json"
        if manifest_path.exists():
            manifest = load_json(manifest_path)
            row["product_package"] = {
                "slug": slug,
                "manifest_path": str(manifest_path.relative_to(ROOT)),
                "package_dir": manifest.get("package_dir"),
                "site_path": manifest.get("site_path"),
                "golden_proof_path": f"state/product_class_packages/{slug}/GOLDEN_PROOF.html",
                "zip_path": manifest.get("deliverable_zip"),
                "smoke_receipt": str(smoke_path.relative_to(ROOT)) if smoke_path.exists() else "",
                "state": manifest.get("state"),
            }
    registry["activation_plan"] = {
        "summary": activation_plan.get("summary", {}),
        "wave_meanings": activation_plan.get("wave_meanings", {}),
        "report_path": str(activation_path.relative_to(ROOT)) if activation_path.exists() else "",
        "doc_path": "docs/DIO_PRODUCT_CLASS_ACTIVATION_PLAN_2026-08-16.md" if (ROOT / "docs" / "DIO_PRODUCT_CLASS_ACTIVATION_PLAN_2026-08-16.md").exists() else "",
    }
    registry["state"] = "imported"
    return registry


def collect_incidents(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    incidents = []
    for path in sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        incident = load_json(path)
        incident["path"] = rel(path)
        incidents.append(incident)
    return incidents


def collect_leads(root: Path) -> list[dict[str, Any]]:
    leads = []
    if not root.exists():
        return leads
    for path in sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        lead = load_json(path)
        acknowledgement = lead.get("acknowledgement") or {}
        promotion = lead.get("promotion") or {}
        promotion_receipt_raw = str(promotion.get("receipt_path") or "")
        promotion_receipt = Path(promotion_receipt_raw) if promotion_receipt_raw else None
        if not promotion and lead.get("lead_id"):
            candidate = ROOT / "state" / "lead_promotions" / str(lead.get("lead_id")) / "LEAD_PROMOTION_RECEIPT.json"
            if candidate.exists():
                promotion = load_json(candidate)
                promotion_receipt = candidate
        mail_intent_id = acknowledgement.get("mail_intent_id")
        mail_path = ROOT / "state" / "mail_intents" / f"{mail_intent_id}.json" if mail_intent_id else None
        mail = load_json(mail_path) if mail_path and mail_path.exists() else {}
        leads.append({
            "lead_id": lead.get("lead_id"),
            "product": lead.get("product"),
            "offer": lead.get("offer"),
            "name": (lead.get("contact") or {}).get("name"),
            "email": (lead.get("contact") or {}).get("email"),
            "organisation": (lead.get("contact") or {}).get("organisation"),
            "state": lead.get("state"),
            "qualification": (lead.get("qualification") or {}).get("state"),
            "conversation_id": lead.get("conversation_id"),
            "acknowledgement_state": acknowledgement.get("state"),
            "mail_intent_id": mail_intent_id,
            "mail_path": rel(mail_path) if mail_path and mail_path.exists() else "",
            "mail_preview_path": mail_preview_path(mail, mail_path) if mail_path and mail_path.exists() else "",
            "promotion_state": promotion.get("state"),
            "promotion_receipt": rel(promotion_receipt) if promotion_receipt and promotion_receipt.exists() else "",
            "promotion_outputs": promotion.get("outputs") or {},
            "missing_inputs": promotion.get("missing_inputs") or [],
            "created_at": lead.get("created_at"),
            "path": rel(path),
        })
    return leads


def collect_business_telemetry(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def collect_orders(root: Path) -> list[dict[str, Any]]:
    orders = []
    if not root.exists():
        return orders
    for path in sorted(root.glob("**/orders/*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        order = load_json(path)
        metadata = order.get("metadata") or {}
        orders.append({
            "order_id": order.get("order_id"),
            "environment": "live" if "live" in path.parts else "sandbox",
            "product_code": order.get("product_code") or metadata.get("product_code") or "unrecorded",
            "job_id": metadata.get("job_id"),
            "amount_minor": order.get("amount_minor") or 0,
            "currency": order.get("currency") or "USD",
            "payment_state": order.get("payment_state") or order.get("state") or "unknown",
            "provider": order.get("provider") or "unknown",
            "fulfilment_released": bool(order.get("fulfilment_released")),
            "path": rel(path),
        })
    return orders


def collect_transactions(root: Path) -> list[dict[str, Any]]:
    transactions = []
    if not root.exists():
        return transactions
    for path in sorted(root.glob("*/TRANSACTION.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        transaction = load_json(path)
        triune = transaction.get("triune") or {}
        lineage = transaction.get("lineage") or {}
        selected = (triune.get("michael") or {}).get("selected_action") or {}
        harmonic = triune.get("harmonic") or {}
        loki = triune.get("loki") or {}
        transactions.append({
            "transaction_id": transaction.get("transaction_id"),
            "product": transaction.get("product"),
            "offer": transaction.get("offer"),
            "stage": transaction.get("stage"),
            "verdict": triune.get("verdict"),
            "lead_id": lineage.get("lead_id"),
            "conversation_id": lineage.get("conversation_id"),
            "job_id": lineage.get("job_id"),
            "order_id": lineage.get("order_id"),
            "selected_action": selected.get("action"),
            "selected_authority": selected.get("authority"),
            "loki_status": loki.get("status"),
            "loki_challenges": len(loki.get("challenges") or []),
            "harmonic_mode": harmonic.get("mode_recommendation"),
            "discord_score": harmonic.get("discord_score"),
            "payment_state": (transaction.get("payment") or {}).get("state"),
            "path": rel(path),
            "decision_path": rel(path.parent / "TRIUNE_DECISION.json"),
            "updated_at": transaction.get("updated_at"),
        })
    return transactions


def collect_prospect_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"counts": {}, "top_targets": [], "electronic_sales_allowed": 0}
    receipt = load_json(path)
    manifest = receipt.get("manifest") or {}
    top_targets = []
    archive_path = Path(str(receipt.get("archive") or ""))
    if archive_path.is_file():
        with zipfile.ZipFile(archive_path) as archive:
            member = next((name for name in archive.namelist() if name.endswith("/buyer_unit_targets.csv")), None)
            rows = list(csv.DictReader(io.StringIO(archive.read(member).decode("utf-8-sig")))) if member else []
        for target in sorted(rows, key=lambda row: int(row.get("rank") or 999999))[:10]:
            target_id = target.get("target_id")
            outreach_path = ROOT / "state" / "prospect_outreach" / f"{target_id}.json"
            outreach = load_json(outreach_path) if outreach_path.exists() else {}
            mail_id = outreach.get("mail_intent_id")
            mail_path = ROOT / "state" / "mail_intents" / f"{mail_id}.json"
            intent = load_json(mail_path) if mail_id and mail_path.exists() else {}
            public_route = target.get("public_contact_route") or ""
            has_email = "@" in public_route
            top_targets.append({
                "rank": target.get("rank"),
                "target_id": target_id,
                "organisation": target.get("organisation"),
                "product_line_id": target.get("product_line_id"),
                "product_name": target.get("product_name"),
                "attack_score": target.get("attack_score"),
                "route_state": target.get("route_state"),
                "route_type": target.get("route_type"),
                "public_contact_route": public_route,
                "source_url": target.get("contact_source"),
                "source_verified_date": target.get("contact_verified_date"),
                "email_eligible": has_email and target.get("route_state") in {"PARTNERSHIP_ROUTE_AVAILABLE", "INSTITUTIONAL_ROUTE_AVAILABLE", "PUBLIC_ROUTE_PRESENT_REVERIFY_ROLE"},
                "outreach_state": "sent" if intent.get("send_state") == "sent" else outreach.get("state", "not_started"),
                "mail_intent_id": mail_id,
                "mail_send_state": intent.get("send_state"),
                "provider_draft_ready": bool(intent.get("provider_draft_id")),
                "creative_state": outreach.get("creative_state") or ("plain_text" if intent.get("provider_draft_id") else "not_started"),
                "consent_mode": outreach.get("consent_mode"),
                "email_preview": rel(Path(outreach["email_preview"])) if outreach.get("email_preview") else "",
            })
    return {
        "counts": receipt.get("validated_counts") or {},
        "top_targets": top_targets or manifest.get("top_10") or [],
        "electronic_sales_allowed": manifest.get("electronic_sales_allowed") or 0,
        "source": rel(path),
    }


def collect_mail_intents(root: Path) -> list[dict[str, Any]]:
    intents = []
    if not root.exists():
        return intents
    for path in sorted(root.glob("MAIL-*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        intent = load_json(path)
        preview_path = mail_preview_path(intent, path)
        intents.append(
            {
                "mail_intent_id": intent.get("mail_intent_id"),
                "purpose": intent.get("purpose"),
                "recipient": intent.get("recipient"),
                "subject": intent.get("subject"),
                "risk": intent.get("risk"),
                "approval": (intent.get("approval") or {}).get("state"),
                "send_state": intent.get("send_state"),
                "provider_draft_ready": bool(intent.get("provider_draft_id")),
                "provider_draft_id": intent.get("provider_draft_id"),
                "job_id": intent.get("job_id"),
                "lead_id": intent.get("lead_id"),
                "campaign_id": intent.get("campaign_id"),
                "has_html": bool(intent.get("body_html")),
                "attachment_count": len(intent.get("attachments") or []),
                "preview_path": preview_path,
                "body_preview": (str(intent.get("body") or "")[:180]).replace("\n", " "),
                "updated_at": intent.get("updated_at") or intent.get("created_at"),
                "path": rel(path),
            }
        )
    return intents


def collect_product_workflows(root: Path) -> list[dict[str, Any]]:
    workflows = []
    if not root.exists():
        return workflows
    for path in sorted(root.glob("*/JOB.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        workflow = load_json(path)
        notification = workflow.get("notification") or {}
        mail_intent_id = notification.get("mail_intent_id")
        mail_path = ROOT / "state" / "mail_intents" / f"{mail_intent_id}.json" if mail_intent_id else None
        mail = load_json(mail_path) if mail_path and mail_path.exists() else {}
        workflows.append({
            "job_id": workflow.get("job_id"),
            "product": workflow.get("product"),
            "state": workflow.get("state"),
            "mode": workflow.get("mode"),
            "run_name": workflow.get("run_name"),
            "recipient": (workflow.get("customer") or {}).get("recipient"),
            "controlled_fallback": bool((workflow.get("customer") or {}).get("controlled_fallback")),
            "intake_state": (workflow.get("intake") or {}).get("state"),
            "processing_state": (workflow.get("processing") or {}).get("state"),
            "output_review_state": (workflow.get("output_review") or {}).get("state"),
            "notification_state": "outlook_ready" if mail.get("provider_draft_id") else notification.get("state"),
            "mail_intent_id": mail_intent_id,
            "mail_path": rel(mail_path) if mail_path and mail_path.exists() else "",
            "mail_preview_path": mail_preview_path(mail, mail_path) if mail_path and mail_path.exists() else "",
            "action": product_next_action(workflow),
            "can_reject": (workflow.get("intake") or {}).get("state") == "pending",
            "output_dir": (workflow.get("processing") or {}).get("output_dir"),
            "source_job_path": workflow.get("source_job_path"),
            "path": rel(path),
            "updated_at": workflow.get("updated_at") or workflow.get("created_at"),
        })
    return workflows


def collect_sophia_jobs(root: Path) -> list[dict[str, Any]]:
    jobs = []
    if not root.exists():
        return jobs
    for path in sorted(root.glob("*/JOB.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        job = load_json(path)
        review = job.get("review") or {}
        payment = job.get("payment") or {}
        approval = job.get("approval") or {}
        delivery = job.get("delivery") or {}
        mail_intent_id = delivery.get("mail_intent_id")
        mail_path = ROOT / "state" / "mail_intents" / f"{mail_intent_id}.json" if mail_intent_id else None
        mail = load_json(mail_path) if mail_path and mail_path.exists() else {}
        action = None
        if payment.get("state") in {"pending_quote", "order_registered", "checkout_failed"} and not job.get("controlled"):
            action = "quote"
        elif payment.get("state") == "awaiting_payment":
            action = "reconcile-payment"
        elif payment.get("state") in {"paid", "waived"} and review.get("state") == "not_started":
            action = "run"
        elif review.get("state") == "ready_for_human_review" and approval.get("state") == "pending":
            action = "approve"
        elif approval.get("state") == "approved" and delivery.get("state") == "held":
            action = "prepare-delivery"
        elif delivery.get("state") == "draft_ready" and not mail.get("provider_draft_id"):
            action = "outlook-draft"
        jobs.append({
            "job_id": job.get("job_id"),
            "state": job.get("state"),
            "controlled": bool(job.get("controlled")),
            "payment_state": payment.get("state"),
            "order_id": payment.get("order_id"),
            "review_state": review.get("state"),
            "grounding_passed": bool(review.get("grounding_passed")),
            "provider": review.get("provider"),
            "model": review.get("model"),
            "approval_state": approval.get("state"),
            "delivery_state": delivery.get("state"),
            "mail_intent_id": mail_intent_id,
            "mail_path": rel(mail_path) if mail_path and mail_path.exists() else "",
            "mail_preview_path": mail_preview_path(mail, mail_path) if mail_path and mail_path.exists() else "",
            "outlook_draft_ready": bool(mail.get("provider_draft_id")),
            "action": action,
            "output_dir": review.get("output_dir"),
            "updated_at": job.get("updated_at") or job.get("created_at"),
            "path": rel(path),
        })
    return jobs


def collect_vamp_jobs(root: Path) -> list[dict[str, Any]]:
    jobs = []
    if not root.exists():
        return jobs
    for path in sorted(root.glob("*/JOB.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        job = load_json(path)
        payment = job.get("payment") or {}
        snapshot = job.get("snapshot") or {}
        approval = job.get("approval") or {}
        delivery = job.get("delivery") or {}
        mail_intent_id = delivery.get("mail_intent_id")
        mail_path = ROOT / "state" / "mail_intents" / f"{mail_intent_id}.json" if mail_intent_id else None
        mail = load_json(mail_path) if mail_path and mail_path.exists() else {}
        action = None
        if payment.get("state") in {"pending_quote", "order_registered", "checkout_failed"} and not job.get("controlled"):
            action = "quote"
        elif payment.get("state") == "awaiting_payment":
            action = "reconcile-payment"
        elif payment.get("state") in {"paid", "waived"} and snapshot.get("state") == "not_started":
            action = "run"
        elif snapshot.get("state") == "ready_for_human_review" and approval.get("state") == "pending":
            action = "approve"
        elif approval.get("state") == "approved" and delivery.get("state") == "held":
            action = "prepare-delivery"
        elif delivery.get("state") == "draft_ready" and not mail.get("provider_draft_id"):
            action = "outlook-draft"
        jobs.append({
            "job_id": job.get("job_id"),
            "state": job.get("state"),
            "controlled": bool(job.get("controlled")),
            "profile_id": (job.get("source") or {}).get("profile_id"),
            "payment_state": payment.get("state"),
            "order_id": payment.get("order_id"),
            "snapshot_state": snapshot.get("state"),
            "evidence_backed_pct": snapshot.get("evidence_backed_pct"),
            "accepted_mappings": snapshot.get("accepted_mappings"),
            "candidate_mappings": snapshot.get("candidate_mappings"),
            "approval_state": approval.get("state"),
            "delivery_state": delivery.get("state"),
            "mail_intent_id": mail_intent_id,
            "mail_path": rel(mail_path) if mail_path and mail_path.exists() else "",
            "mail_preview_path": mail_preview_path(mail, mail_path) if mail_path and mail_path.exists() else "",
            "outlook_draft_ready": bool(mail.get("provider_draft_id")),
            "action": action,
            "output_dir": snapshot.get("output_dir"),
            "updated_at": job.get("updated_at") or job.get("created_at"),
            "path": rel(path),
        })
    return jobs


def collect_document_studio_jobs(root: Path) -> list[dict[str, Any]]:
    jobs = []
    if not root.exists():
        return jobs
    for path in sorted(root.glob("*/JOB.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        job = load_json(path)
        payment = job.get("payment") or {}
        studio = job.get("studio") or {}
        approval = job.get("approval") or {}
        delivery = job.get("delivery") or {}
        source = job.get("source") or {}
        mail_intent_id = delivery.get("mail_intent_id")
        mail_path = ROOT / "state" / "mail_intents" / f"{mail_intent_id}.json" if mail_intent_id else None
        mail = load_json(mail_path) if mail_path and mail_path.exists() else {}
        action = None
        if payment.get("state") in {"pending_quote", "order_registered", "checkout_failed"} and not job.get("controlled"):
            action = "quote"
        elif payment.get("state") == "awaiting_payment":
            action = "reconcile-payment"
        elif payment.get("state") in {"paid", "waived"} and studio.get("state") == "not_started":
            action = "run"
        elif studio.get("state") == "ready_for_human_review" and approval.get("state") == "pending":
            action = "approve"
        elif approval.get("state") == "approved" and delivery.get("state") == "held":
            action = "prepare-delivery"
        elif delivery.get("state") == "draft_ready" and not mail.get("provider_draft_id"):
            action = "outlook-draft"
        jobs.append({
            "job_id": job.get("job_id"),
            "state": job.get("state"),
            "controlled": bool(job.get("controlled")),
            "service": source.get("service"),
            "source_language": source.get("source_language"),
            "target_language": source.get("target_language"),
            "payment_state": payment.get("state"),
            "order_id": payment.get("order_id"),
            "studio_state": studio.get("state"),
            "release_readiness": studio.get("release_readiness"),
            "semantic_object_id": studio.get("semantic_object_id"),
            "approval_state": approval.get("state"),
            "delivery_state": delivery.get("state"),
            "mail_intent_id": mail_intent_id,
            "mail_path": rel(mail_path) if mail_path and mail_path.exists() else "",
            "mail_preview_path": mail_preview_path(mail, mail_path) if mail_path and mail_path.exists() else "",
            "outlook_draft_ready": bool(mail.get("provider_draft_id")),
            "action": action,
            "output_dir": studio.get("output_dir"),
            "updated_at": job.get("updated_at") or job.get("created_at"),
            "path": rel(path),
        })
    return jobs


def collect_events(path: Path, limit: int = 100) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(events))


def collect_notifications(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return (load_json(path).get("notifications") or [])[:100]


def verify_lingua_chain(path: Path) -> dict[str, Any]:
    """Verify the BEAST-compatible local hash chain without importing BEAST."""
    genesis = "sha256:" + "0" * 64
    previous = genesis
    errors = []
    blocks = []
    if path.exists():
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                blocks.append(json.loads(line))
            except json.JSONDecodeError:
                errors.append({"line": line_number, "reason": "invalid_json"})
    for expected_index, block in enumerate(blocks):
        payload = block.get("payload") or {}
        canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        payload_hash = "sha256:" + hashlib.sha256(canonical_payload).hexdigest()
        header = {
            key: block.get(key)
            for key in ("index", "previous_hash", "payload_hash", "event_type", "artifact_id", "node_id", "timestamp")
        }
        canonical_header = json.dumps(header, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        block_hash = "sha256:" + hashlib.sha256(canonical_header).hexdigest()
        checks = {
            "index": block.get("index") == expected_index,
            "previous_hash": block.get("previous_hash") == previous,
            "payload_hash": block.get("payload_hash") == payload_hash,
            "block_hash": block.get("block_hash") == block_hash,
        }
        errors.extend({"index": expected_index, "reason": f"{name}_mismatch"} for name, passed in checks.items() if not passed)
        previous = str(block.get("block_hash") or previous)
    return {
        "valid": not errors,
        "block_count": len(blocks),
        "head_hash": previous,
        "errors": errors,
    }


def collect_lingua_state(root: Path, deliverables_root: Path) -> dict[str, Any]:
    object_root = root / "objects"
    credit_root = root / "beast_credits"
    qa_by_language: dict[str, dict[str, Any]] = {}
    for qa_path in deliverables_root.glob("*/LINGUA_QA.json"):
        qa = load_json(qa_path)
        language = str(qa.get("target_language") or "")
        if language:
            qa_by_language[language] = {**qa, "path": rel(qa_path), "pack": rel(qa_path.parent)}

    credit_counts: Counter[str] = Counter()
    for credit_path in credit_root.glob("scc_*.json"):
        try:
            credit_counts[load_json(credit_path).get("task_class", "unknown")] += 1
        except (json.JSONDecodeError, OSError):
            credit_counts["invalid_credit"] += 1

    objects = []
    for object_path in sorted(object_root.glob("*.json")):
        semantic = load_json(object_path)
        source = semantic.get("source") or {}
        source_by_id = {str(row.get("unit_id") or ""): row for row in source.get("units") or []}
        languages = []
        for language, lane in sorted((semantic.get("translations") or {}).items()):
            units = lane.get("units") or []
            qa = qa_by_language.get(language) or {}
            safe_language = "".join(character for character in language if character.isalnum() or character in "-_")
            review_path = root / "reviews" / f"{semantic.get('object_id', object_path.stem)}__{safe_language}.json"
            review = load_json(review_path) if review_path.exists() else {}
            reviewed_by_id = {str(row.get("unit_id") or ""): row for row in review.get("units") or []}
            flags = sum(len(unit.get("qa_flags") or []) for unit in units)
            stale = sum(unit.get("status") == "stale_source_changed" for unit in units)
            approved = sum(unit.get("status") == "human_approved_crystallized" for unit in units)
            review_units = []
            for unit in units:
                unit_id = str(unit.get("unit_id") or "")
                saved = reviewed_by_id.get(unit_id) or {}
                resolutions = saved.get("flag_resolutions") or unit.get("flag_resolutions") or []
                unit_flags = []
                for index, flag in enumerate(unit.get("qa_flags") or []):
                    resolution = resolutions[index] if index < len(resolutions) else {}
                    unit_flags.append({
                        "index": index,
                        "severity": flag.get("severity", "unknown"),
                        "issue": flag.get("issue", ""),
                        "resolution": resolution.get("resolution", "unresolved"),
                        "note": resolution.get("note", ""),
                    })
                review_units.append({
                    "unit_id": unit_id,
                    "unit_type": (source_by_id.get(unit_id) or {}).get("unit_type", "body"),
                    "source_text": (source_by_id.get(unit_id) or {}).get("source_text", ""),
                    "source_hash": unit.get("source_hash", ""),
                    "target_text": saved.get("target_text", unit.get("target_text", "")),
                    "approved": bool(saved.get("approved")) or unit.get("status") == "human_approved_crystallized",
                    "status": unit.get("status", "unknown"),
                    "flags": unit_flags,
                })
            languages.append({
                "language": language,
                "status": lane.get("status", "unknown"),
                "source_version": lane.get("source_version", ""),
                "unit_count": len(units),
                "approved_units": approved,
                "stale_units": stale,
                "material_flags": qa.get("material_review_flags", flags),
                "anchor_coverage": qa.get("source_anchor_coverage_percent"),
                "numerals": qa.get("numerals", "not_recorded"),
                "protected_tokens": qa.get("protected_tokens", "not_recorded"),
                "release_readiness": qa.get("release_readiness", "human_review_required"),
                "approved_units_reused": qa.get("approved_units_reused", 0),
                "approved_terms_reused": qa.get("approved_terminology_reused", 0),
                "semantic_authority": "approved_crystallized" if lane.get("status") == "human_approved_crystallized" else "pending_proficient_review",
                "review_state": review.get("approval_state", "not_started"),
                "reviewer": review.get("reviewer", (lane.get("review") or {}).get("reviewer", "")),
                "reviewer_role": review.get("reviewer_role", (lane.get("review") or {}).get("reviewer_role", "")),
                "units": review_units,
                "qa_path": qa.get("path", ""),
                "pack": qa.get("pack", ""),
                "review_path": rel(review_path) if review_path.exists() else "",
            })
        objects.append({
            "object_id": semantic.get("object_id", object_path.stem),
            "domain": semantic.get("domain", ""),
            "source_language": source.get("language", ""),
            "source_version": source.get("version", ""),
            "source_unit_count": len(source.get("units") or []),
            "language_count": len(languages),
            "languages": languages,
            "origin": semantic.get("origin") or {"product": "document_studio", "artifact_type": "document"},
            "path": rel(object_path),
            "updated_at": semantic.get("updated_at", ""),
        })

    chain = verify_lingua_chain(root / "beast_crystal_chain.jsonl")
    beast_status_path = root / "BEAST_ORGANS_STATUS.json"
    beast_status = load_json(beast_status_path) if beast_status_path.exists() else {}
    learning = beast_status.get("learning") or {}
    negative_capability = beast_status.get("negative_capability") or {}
    memory_hull = beast_status.get("memory_hull") or {}
    prec = beast_status.get("prec") or {}
    return {
        "objects": objects,
        "product_count": len({str((item.get("origin") or {}).get("product") or "unknown") for item in objects}),
        "source_only_objects": sum(not item["languages"] for item in objects),
        "credit_counts": dict(credit_counts),
        "automatic_guard_credits": credit_counts["dio_lingua_deterministic_guard"],
        "automatic_risk_credits": credit_counts["dio_lingua_risk_pattern"] + credit_counts["dio_lingua_deterministic_failure_pattern"],
        "approved_semantic_credits": credit_counts["dio_lingua_translation_unit"] + credit_counts["dio_lingua_approved_term"],
        "chain": chain,
        "automatic_learning": "active",
        "semantic_authority": "human_approval_required",
        "beast_organs": beast_status.get("organs") or {},
        "beast_learning_events": learning.get("event_count", 0),
        "beast_capabilities": learning.get("capability_count", 0),
        "beast_reuse_hits": learning.get("reuse_hits", 0),
        "beast_provider_calls_avoided": learning.get("provider_calls_avoided", 0),
        "negative_capability": negative_capability,
        "memory_residue": sum(
            int(section.get("sidecars") or 0)
            for section in (memory_hull.get("sections") or {}).values()
        ),
        "memory_residue_failed": memory_hull.get("failed_sidecars", 0),
        "prec_lifecycles": prec.get("count", 0),
        "beast_status_path": rel(beast_status_path) if beast_status_path.exists() else "",
    }


def load_control_policy(path: Path) -> dict[str, Any]:
    if path.exists():
        return {**DEFAULT_POLICY, **load_json(path)}
    policy = {**DEFAULT_POLICY, "updated_at": utc_now(), "updated_by": "system_default"}
    write_json(path, policy)
    return policy


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.08):
            return True
    except OSError:
        return False


def collect_systems(policy: dict[str, Any]) -> list[dict[str, Any]]:
    graph_config_path = ROOT / "config" / "microsoft_graph.local.json"
    graph_config = load_json(graph_config_path) if graph_config_path.exists() else {}
    client_id = graph_config.get("client_id", "")
    cache_path = Path(graph_config.get("token_cache_path", "/nonexistent")).expanduser()
    graph_configured = bool(client_id and not client_id.startswith("REPLACE_"))
    webhook = graph_config.get("webhook") or {}
    webhook_url = webhook.get("notification_url", "")
    subscription_path = Path(webhook.get("subscription_state_path", "/nonexistent")).expanduser()
    webhook_configured = webhook_url.startswith("https://") and "REPLACE_" not in webhook_url
    subscription = load_json(subscription_path).get("subscription", {}) if subscription_path.exists() else {}
    subscription_expiry = subscription.get("expirationDateTime", "")
    edge_config_path = ROOT / "config" / "dio_edge.local.json"
    edge_config = load_json(edge_config_path) if edge_config_path.exists() else {}
    edge_url = str(edge_config.get("base_url", ""))
    edge_token_path = Path(edge_config.get("edge_token_path", "/nonexistent")).expanduser()
    edge_ready = edge_url.startswith("https://") and "REPLACE_" not in edge_url and edge_token_path.exists()
    onedrive_initialised = any((ROOT / "runs" / "microsoft_graph").glob("init-*.json"))
    lingua_chain = verify_lingua_chain(ROOT / "state" / "lingua" / "beast_crystal_chain.jsonl")
    engine_audit_path = ROOT / "state" / "production_engines" / "ENGINE_AUDIT_RECEIPT.json"
    engine_audit = load_json(engine_audit_path) if engine_audit_path.exists() else {}
    engine_summary = engine_audit.get("summary") or {}
    engine_rows = {row.get("product"): row for row in engine_audit.get("engines") or []}
    detached_engines = engine_summary.get("detached_or_cli_only") or []
    return [
        {
            "id": "graph",
            "name": "Microsoft Graph",
            "state": "connected" if graph_configured and cache_path.exists() else "setup_required",
            "detail": "OAuth token cache present" if graph_configured and cache_path.exists() else "Client ID and operator consent still required",
        },
        {
            "id": "graph_webhook",
            "name": "Graph webhook ingress",
            "state": "active" if subscription_path.exists() else ("endpoint_ready" if webhook_configured and port_open("127.0.0.1", 8787) else "setup_required"),
            "detail": f"Active through {subscription_expiry}" if subscription_path.exists() else ("Create the Graph subscription" if webhook_configured else "Public HTTPS callback still required"),
        },
        {
            "id": "edge_gateway",
            "name": "DIO edge gateway",
            "state": "connected" if edge_ready else "setup_required",
            "detail": "Cloudflare Worker and D1 durable ingress" if edge_ready else "Deploy Worker and install the local pull token",
        },
        {
            "id": "outlook_browser",
            "name": "Outlook browser fallback",
            "state": "online" if port_open("127.0.0.1", 3000) else "offline",
            "detail": "Local operator fallback on port 3000",
        },
        {
            "id": "onedrive",
            "name": "OneDrive job transport",
            "state": "connected" if onedrive_initialised else ("local_ready" if Path("/home/byron/KnowEdge_Microsoft_Mirror").exists() else "missing"),
            "detail": "Remote DIO product folders initialised" if onedrive_initialised else ("Graph remote initialisation pending" if not cache_path.exists() else "Graph transport can initialise remote DIO tree"),
        },
        {
            "id": "market_loop",
            "name": "Hivenance market loop",
            "state": "ready" if (ROOT / "campaigns/dio_market_loop/wave4/REGISTRY_IMPORT_RECEIPT.json").exists() else "missing",
            "detail": "Wave 4 hypotheses and NicheFoundry scores",
        },
        {
            "id": "market_command",
            "name": "DIO Market Command",
            "state": "online" if port_open("127.0.0.1", 8770) else ("ready" if (ROOT / "market_command" / "core.py").exists() else "missing"),
            "detail": "Cross-channel experiments, verified attribution and governed settlement on port 8770",
        },
        {
            "id": "commercial_triune",
            "name": "Commercial Triune",
            "state": "active" if (ROOT / "state" / "commerce" / "dio_commerce.sqlite").exists() else "ready",
            "detail": "Metatron belief, Michael next action, Loki dissent and harmonic transaction governance",
        },
        {
            "id": "nichefoundry_media",
            "name": "NicheFoundry media layer",
            "state": "ready" if (ROOT / "config" / "media_layers.json").exists() else "missing",
            "detail": "Shared faceless video, campaign visual, thumbnail, caption and lesson-production infrastructure",
        },
        {
            "id": "production_engine_attachment",
            "name": "Production engine attachment",
            "state": "needs_fusion" if detached_engines else ("audited" if engine_audit else "audit_missing"),
            "detail": (
                f"{engine_summary.get('audited', 0)} engines audited · detached: {', '.join(detached_engines)}"
                if engine_audit else "Run scripts/audit_product_engines.py"
            ),
        },
        {
            "id": "homs_engine_attachment",
            "name": "HOMS engine attachment",
            "state": (engine_rows.get("HOMS") or {}).get("verdict", "audit_missing"),
            "detail": (engine_rows.get("HOMS") or {}).get("next_attachment_step", "HyMark attachment audit has not run"),
        },
        {
            "id": "document_studio_attachment",
            "name": "Document Studio attachment",
            "state": (engine_rows.get("Document Studio / Lingua") or {}).get("verdict", "audit_missing"),
            "detail": (engine_rows.get("Document Studio / Lingua") or {}).get("next_attachment_step", "Document Studio attachment audit has not run"),
        },
        {
            "id": "sophia_presence",
            "name": "Sophia Gemini review lane",
            "state": "online" if port_open("127.0.0.1", 7070) else "offline",
            "detail": "Gemini reasoning with Mandos and grounded release validation" if port_open("127.0.0.1", 7070) else "Sophia Presence is not reachable on port 7070",
        },
        {
            "id": "beast_lingua",
            "name": "BEAST Lingua memory",
            "state": "active" if lingua_chain["valid"] and lingua_chain["block_count"] else ("invalid" if not lingua_chain["valid"] else "missing"),
            "detail": f"Valid local hash chain · {lingua_chain['block_count']} learning events" if lingua_chain["valid"] and lingua_chain["block_count"] else "Lingua learning chain requires attention",
        },
        {
            "id": "outbound",
            "name": "Outbound authority",
            "state": policy.get("outbound_mail", "off"),
            "detail": "One-time mail intent approval remains mandatory",
        },
    ]


def build_attention(
    jobs: list[dict[str, Any]],
    campaigns: list[dict[str, Any]],
    market_campaigns: list[dict[str, Any]],
    mail_intents: list[dict[str, Any]],
    systems: list[dict[str, Any]],
    sophia_jobs: list[dict[str, Any]],
    vamp_jobs: list[dict[str, Any]],
    document_studio_jobs: list[dict[str, Any]],
    product_workflows: list[dict[str, Any]],
    leads: list[dict[str, Any]],
    video_candidates: list[dict[str, Any]],
    lingua: dict[str, Any],
) -> list[dict[str, Any]]:
    attention = []
    tracked_intents = {
        job.get("mail_intent_id")
        for job in [*sophia_jobs, *vamp_jobs, *document_studio_jobs, *product_workflows]
        if job.get("mail_intent_id")
    }
    managed_job_ids = {job["job_id"] for job in product_workflows}
    for lead in leads:
        if lead["qualification"] == "pending":
            attention.append({"severity": "action", "kind": "lead", "title": f"{str(lead['product']).upper()} · {lead['lead_id']}", "detail": f"new request · {lead['offer']}", "entity_id": lead["lead_id"], "link": lead["path"]})
        elif lead["qualification"] == "qualified" and not lead.get("promotion_state"):
            attention.append({"severity": "action", "kind": "lead", "title": f"{str(lead['product']).upper()} · {lead['lead_id']}", "detail": "qualified lead has not been promoted into a product route", "entity_id": lead["lead_id"], "link": lead["path"]})
    for system in systems:
        if system["state"] in {"setup_required", "missing", "invalid"}:
            attention.append({"severity": "critical" if system["state"] == "invalid" else "action", "kind": "system", "title": system["name"], "detail": system["detail"], "entity_id": system["id"], "link": ""})
    for intent in mail_intents:
        if intent["mail_intent_id"] in tracked_intents:
            continue
        if intent["approval"] in {"pending", "approved"} and intent["send_state"] not in {"sent", "rejected"}:
            detail = "Outlook draft ready for manual review" if intent["provider_draft_ready"] else f"{intent['purpose']} · {intent['approval']}"
            attention.append({"severity": "action", "kind": "mail", "title": intent["subject"], "detail": detail, "entity_id": intent["mail_intent_id"], "link": intent["path"]})
    for job in jobs:
        if job["job_id"] in managed_job_ids:
            continue
        if job["status"] in {"needs_review", "failed", "blocked"} or job["approval"] == "pending":
            severity = "critical" if job["status"] == "failed" else "action"
            attention.append({"severity": severity, "kind": "job", "title": f"{job['product'].upper()} · {job['job_id']}", "detail": f"{job['status']} · approval {job['approval']}", "entity_id": job["job_id"], "link": job["job_path"]})
    for job in sophia_jobs:
        if job["action"] or job["outlook_draft_ready"] or job["state"] in {"blocked", "payment_hold"}:
            severity = "critical" if job["state"] in {"blocked", "payment_hold"} else "action"
            detail = "Outlook draft ready for manual review" if job["outlook_draft_ready"] else f"{job['state']} · payment {job['payment_state']} · approval {job['approval_state']}"
            attention.append({
                "severity": severity,
                "kind": "sophia",
                "title": f"SOPHIA · {job['job_id']}",
                "detail": detail,
                "entity_id": job["job_id"],
                "link": job["path"],
            })
    for job in vamp_jobs:
        if job["action"] or job["outlook_draft_ready"] or job["state"] in {"blocked", "payment_hold"}:
            severity = "critical" if job["state"] in {"blocked", "payment_hold"} else "action"
            detail = "Outlook draft ready for manual review" if job["outlook_draft_ready"] else f"{job['state']} · evidence {job['evidence_backed_pct'] or 0}% · approval {job['approval_state']}"
            attention.append({
                "severity": severity,
                "kind": "vamp",
                "title": f"VAMP · {job['job_id']}",
                "detail": detail,
                "entity_id": job["job_id"],
                "link": job["path"],
            })
    for job in document_studio_jobs:
        if job["action"] or job["outlook_draft_ready"] or job["state"] in {"blocked", "payment_hold"}:
            severity = "critical" if job["state"] in {"blocked", "payment_hold"} else "action"
            detail = "Outlook draft ready for manual review" if job["outlook_draft_ready"] else f"{job['state']} · {job['service']} · approval {job['approval_state']}"
            attention.append({
                "severity": severity,
                "kind": "document-studio",
                "title": f"DOCUMENT STUDIO · {job['job_id']}",
                "detail": detail,
                "entity_id": job["job_id"],
                "link": job["path"],
            })
    for job in product_workflows:
        if job["action"] or job["notification_state"] == "outlook_ready" or job["state"] == "blocked":
            severity = "critical" if job["state"] == "blocked" else "action"
            next_step = "review Outlook draft" if job["notification_state"] == "outlook_ready" else (job["action"] or "blocked").replace("-", " ")
            attention.append({
                "severity": severity,
                "kind": job["product"],
                "title": f"{job['product'].upper()} · {job['job_id']}",
                "detail": f"next: {next_step} · intake {job['intake_state']} · processing {job['processing_state']}",
                "entity_id": job["job_id"],
                "link": job["path"],
            })
    for campaign in campaigns:
        if campaign["approval"] in {"unknown", "pending"}:
            attention.append({"severity": "action", "kind": "campaign", "title": campaign["title"], "detail": f"{campaign['layer']} · editorial approval required", "entity_id": campaign["layer"], "link": campaign["campaign_pack"]})
    for campaign in market_campaigns:
        if campaign["settlement"] in {"pending", "revise"}:
            attention.append({"severity": "info" if campaign["settlement"] == "pending" else "action", "kind": "market", "title": campaign["product"], "detail": f"market settlement {campaign['settlement']} · foundry {campaign['foundry_decision']}", "entity_id": campaign["campaign_id"], "link": campaign["pack"]})
    for candidate in video_candidates:
        if candidate["status"] == "human_review_required":
            attention.append({
                "severity": "action",
                "kind": "video",
                "title": candidate["title"],
                "detail": "publishing preflight passed · full watch-through and asset approval required",
                "entity_id": candidate["episode_id"],
                "link": candidate["video"],
            })
    for semantic in lingua.get("objects") or []:
        review_lanes = [lane for lane in semantic["languages"] if lane["status"] == "human_review_required"]
        if review_lanes:
            flags = sum(int(lane["material_flags"] or 0) for lane in review_lanes)
            stale = sum(int(lane["stale_units"] or 0) for lane in review_lanes)
            detail = f"{len(review_lanes)} language lanes · {flags} material flags · BEAST guard learning active"
            if stale:
                detail += f" · {stale} stale units"
            attention.append({
                "severity": "action",
                "kind": "lingua",
                "title": f"LINGUA · {semantic['object_id']}",
                "detail": detail,
                "entity_id": semantic["object_id"],
                "link": semantic["path"],
            })
    order = {"critical": 0, "action": 1, "info": 2}
    return sorted(attention, key=lambda item: order[item["severity"]])[:30]


def synthetic_activity(jobs: list[dict[str, Any]], campaigns: list[dict[str, Any]], telemetry: list[dict[str, str]]) -> list[dict[str, Any]]:
    activity = []
    for row in telemetry[-5:]:
        activity.append({"event": "delivery.completed", "occurred_at": row.get("created_at"), "severity": "info", "entity_type": "business_loop", "entity_id": row.get("loop_id"), "data": {"product": row.get("product"), "revenue": row.get("revenue_per_job")}})
    for job in jobs[:8]:
        activity.append({"event": "job.review_state", "occurred_at": job.get("created_at"), "severity": "action" if job.get("approval") == "pending" else "info", "entity_type": "job", "entity_id": job.get("job_id"), "data": {"product": job.get("product"), "status": job.get("status")}})
    for campaign in campaigns[:4]:
        activity.append({"event": "campaign.prepared", "occurred_at": "", "severity": "info", "entity_type": "campaign", "entity_id": campaign.get("layer"), "data": {"status": campaign.get("status")}})
    return activity


def build_dashboard_state(
    runs_root: Path | None = None,
    deliverables_root: Path | None = None,
    campaign_root: Path | None = None,
    telemetry_path: Path | None = None,
) -> dict[str, Any]:
    runs = collect_runs(runs_root or ROOT / "runs", deliverables_root or ROOT / "deliverables")
    campaigns = collect_campaigns(campaign_root or ROOT / "campaigns" / "phase3")
    telemetry = collect_business_telemetry(telemetry_path or ROOT / "telemetry" / "business_loop.csv")
    orders = collect_orders(ROOT / "state" / "commerce")
    transactions = collect_transactions(ROOT / "state" / "transactions")
    prospect_registry = collect_prospect_registry(ROOT / "campaigns" / "dio_market_loop" / "wave4" / "REGISTRY_IMPORT_RECEIPT.json")
    market_campaigns = collect_market_campaigns(ROOT / "campaigns" / "dio_market_loop" / "wave4" / "campaigns")
    market_command = collect_market_command()
    mail_intents = collect_mail_intents(ROOT / "state" / "mail_intents")
    sophia_jobs = collect_sophia_jobs(ROOT / "state" / "sophia_jobs")
    vamp_jobs = collect_vamp_jobs(ROOT / "state" / "vamp_jobs")
    document_studio_jobs = collect_document_studio_jobs(ROOT / "state" / "document_studio_jobs")
    product_workflows = collect_product_workflows(ROOT / "state" / "product_jobs")
    leads = collect_leads(ROOT / "state" / "leads")
    video_candidates = collect_video_candidates(ROOT / "deliverables" / "dio_video_candidates" / "DIO_VIDEO_CANDIDATE_REGISTRY.json")
    product_portfolio = collect_product_portfolio(ROOT / "state" / "product_portfolio" / "DIO_META_PORTFOLIO_ATLAS_IMPORT.json")
    lingua = collect_lingua_state(ROOT / "state" / "lingua", ROOT / "deliverables" / "document_studio")
    incidents = collect_incidents(ROOT / "state" / "incidents")
    events = collect_events(ROOT / "telemetry" / "dio_events.jsonl")
    notifications = collect_notifications(ROOT / "state" / "notifications" / "feed.json")
    policy = load_control_policy(ROOT / "state" / "control_policy.json")
    jobs = latest_unique_jobs(runs)
    operational_jobs = [job for job in jobs if job["mode"] == "live"]
    systems = collect_systems(policy)
    attention = build_attention(operational_jobs, campaigns, market_campaigns, mail_intents, systems, sophia_jobs, vamp_jobs, document_studio_jobs, product_workflows, leads, video_candidates, lingua)
    for item in reversed(market_command.get("attention") or []):
        if item.get("kind") in {"content", "media_buy"}:
            attention.insert(0, {
                "severity": item.get("severity", "action"),
                "kind": f"market_{item.get('kind')}",
                "title": item.get("title", item.get("entity_id")),
                "detail": item.get("detail", "Market Command operator decision required"),
                "entity_id": item.get("entity_id"),
                "link": "http://127.0.0.1:8770/",
            })
    for incident in incidents:
        if incident.get("state") not in {"closed", "resolved"}:
            attention.insert(0, {
                "severity": incident.get("severity", "action"),
                "kind": "incident",
                "title": incident.get("summary", incident.get("incident_id")),
                "detail": incident.get("next_action", "Operator decision required"),
                "entity_id": incident.get("incident_id"),
                "link": incident.get("path"),
            })
    activity = events or synthetic_activity(jobs, campaigns, telemetry)
    metrics = {
        "leads": sum(lead["qualification"] == "qualified" for lead in leads) + sum(int(float(row.get("qualified_leads") or 0)) for row in telemetry),
        "orders": sum(order["payment_state"] == "paid" for order in orders),
        "revenue": sum(float(row.get("revenue_per_job") or 0) for row in telemetry),
        "active_jobs": (
            sum(job["status"] not in {"approved", "delivered", "complete", "closed"} for job in operational_jobs)
            + sum(job["state"] not in {"closed", "delivered"} for job in sophia_jobs)
            + sum(job["state"] not in {"closed", "delivered"} for job in vamp_jobs)
            + sum(job["state"] not in {"closed", "delivered"} for job in document_studio_jobs)
            + sum(job["state"] not in {"closed", "delivered", "blocked"} for job in product_workflows)
        ),
        "needs_you": sum(item["severity"] in {"critical", "action"} for item in attention),
        "failures": sum(job["status"] == "failed" for job in jobs),
    }
    return {
        "schema": "dio.control_deck.state.v1",
        "generated_at": utc_now(),
        "metrics": metrics,
        "attention": attention,
        "activity": activity[:50],
        "notifications": notifications,
        "control_policy": policy,
        "systems": systems,
        "runs": runs,
        "jobs": jobs,
        "campaigns": campaigns,
        "market_campaigns": market_campaigns,
        "market_command": market_command,
        "video_candidates": video_candidates,
        "product_portfolio": product_portfolio,
        "lingua": lingua,
        "incidents": incidents,
        "mail_intents": mail_intents,
        "sophia_jobs": sophia_jobs,
        "vamp_jobs": vamp_jobs,
        "document_studio_jobs": document_studio_jobs,
        "product_workflows": product_workflows,
        "leads": leads,
        "business_telemetry": telemetry,
        "orders": orders,
        "transactions": transactions,
        "prospect_registry": prospect_registry,
        "summaries": {
            "jobs_by_product": dict(Counter(job["product"] for job in jobs)),
            "jobs_by_status": dict(Counter(job["status"] for job in jobs)),
        },
    }


def render_dashboard(state: dict[str, Any]) -> str:
    embedded = json.dumps(state, ensure_ascii=True).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>DIO Control Deck</title>
  <script src="https://unpkg.com/lucide@0.468.0/dist/umd/lucide.min.js"></script>
  <style>
    :root{{--ink:#eef3f3;--muted:#91a0a4;--line:#2a3539;--paper:#090d0f;--surface:#111719;--nav:#070a0c;--nav2:#172126;--green:#70d69f;--amber:#e5b65d;--red:#ff7d73;--blue:#67c8ed;--cyan:#61d2c7;--gold:#e5b65d}}
    *{{box-sizing:border-box}} html,body{{margin:0;min-height:100%;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--ink);background:var(--paper);letter-spacing:0}}
    button,a{{font:inherit}} button{{cursor:pointer}} .shell{{min-height:100vh;display:grid;grid-template-columns:216px minmax(0,1fr)}}
    aside{{background:var(--nav);color:#dce7e6;padding:18px 12px;position:sticky;top:0;height:100vh;display:flex;flex-direction:column;gap:20px}}
    .brand{{padding:4px 10px 16px;border-bottom:1px solid #2c383d}} .brand strong{{font:700 22px Georgia,serif;color:var(--gold)}} .brand span{{display:block;font-size:10px;color:#91aaa8;margin-top:3px;text-transform:uppercase}}
    nav{{display:grid;gap:4px}} .nav-btn{{border:0;background:transparent;color:#b8c9c7;border-radius:6px;min-height:40px;padding:9px 10px;display:flex;align-items:center;gap:10px;text-align:left}}
    .nav-btn:hover,.nav-btn.active{{background:var(--nav2);color:#fff}} .nav-btn svg{{width:17px;height:17px}}
    .side-status{{margin-top:auto;padding:12px 10px;border-top:1px solid #34454b;font-size:12px;color:#9db0ae;display:grid;gap:8px}} .side-status b{{color:#dce7e6}}
    .workspace{{min-width:0}} header{{height:64px;background:#0d1316;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:18px;padding:0 24px;position:sticky;top:0;z-index:4}}
    header h1{{font-size:18px;margin:0}} .health{{display:flex;align-items:center;gap:8px;color:var(--green);font-size:13px;font-weight:750}} .health i{{width:8px;height:8px;border-radius:50%;background:currentColor}}
    main{{padding:20px 24px 48px;display:grid;gap:18px;max-width:1600px;margin:0 auto}}
    .authority{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:1px solid var(--line);background:var(--surface);border-radius:6px;overflow:hidden}}
    .authority-item{{padding:12px 14px;display:flex;align-items:center;justify-content:space-between;gap:12px;border-right:1px solid var(--line)}} .authority-item:nth-child(4n){{border-right:0}} .authority-item:nth-child(-n+4){{border-bottom:1px solid var(--line)}}
    .authority-copy{{min-width:0}} .authority-copy b{{display:block;font-size:13px}} .authority-copy span{{display:block;color:var(--muted);font-size:11px;margin-top:2px}}
    .switch{{border:1px solid var(--line);background:#151d20;color:var(--muted);border-radius:999px;padding:5px 9px;min-width:76px;font-size:11px;font-weight:800;text-transform:uppercase}} .switch.on{{background:#102b20;color:var(--green);border-color:#315d46}} .switch.danger{{background:#2b1717;color:var(--red);border-color:#683d39}}
    .metrics{{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));border:1px solid var(--line);background:var(--surface);border-radius:6px;overflow:hidden}}
    .metric{{padding:15px;border-right:1px solid var(--line);min-width:0}} .metric:last-child{{border-right:0}} .metric span{{font-size:11px;text-transform:uppercase;color:var(--muted);font-weight:750}} .metric strong{{display:block;font-size:24px;margin-top:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    .overview{{display:grid;grid-template-columns:minmax(0,1.08fr) minmax(340px,.92fr);gap:18px}} .panel{{background:var(--surface);border:1px solid var(--line);border-radius:6px;min-width:0}}
    .panel-head{{min-height:48px;padding:12px 15px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:12px}} .panel-head h2{{font-size:14px;margin:0}} .panel-head span{{font-size:11px;color:var(--muted)}}
    .queue,.activity{{display:grid}} .queue-item,.activity-item{{display:grid;grid-template-columns:10px minmax(0,1fr) auto;gap:11px;align-items:center;padding:12px 15px;border-bottom:1px solid #202a2e;text-decoration:none;color:inherit;min-height:62px}} .queue-item:last-child,.activity-item:last-child{{border-bottom:0}}
    .queue-item:hover{{background:#151e21}} .severity{{width:8px;height:8px;border-radius:50%}} .severity.critical{{background:var(--red)}} .severity.action{{background:var(--amber)}} .severity.info{{background:var(--green)}}
    .item-copy{{min-width:0}} .item-copy b{{display:block;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}} .item-copy span{{display:block;font-size:12px;color:var(--muted);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}} .kind{{font-size:10px;color:var(--muted);text-transform:uppercase;font-weight:800}}
    .tabs{{display:flex;gap:2px;border-bottom:1px solid var(--line);overflow-x:auto}} .tab{{border:0;background:transparent;padding:11px 14px;color:var(--muted);font-size:12px;font-weight:760;border-bottom:2px solid transparent;white-space:nowrap}} .tab.active{{color:var(--gold);border-bottom-color:var(--gold)}}
    .tab-panel{{display:none}} .tab-panel.active{{display:block}} .table-wrap{{overflow:auto;max-height:520px}} table{{border-collapse:collapse;width:100%;font-size:12px}} th,td{{text-align:left;padding:10px 12px;border-bottom:1px solid #202a2e;vertical-align:top}} th{{position:sticky;top:0;background:#151e22;color:#aab7ba;font-size:10px;text-transform:uppercase;z-index:1}} td code{{font-size:11px;color:#9bdef7}} a{{color:var(--blue);text-decoration:none}} a:hover{{text-decoration:underline}}
    .badge{{display:inline-flex;align-items:center;min-height:22px;border:1px solid var(--line);border-radius:999px;padding:3px 7px;font-size:10px;font-weight:800;text-transform:uppercase;white-space:nowrap}} .badge.good{{background:#102b20;color:var(--green);border-color:#315d46}} .badge.warn{{background:#2b2415;color:#f1c66f;border-color:#6d5930}} .badge.bad{{background:#2b1717;color:var(--red);border-color:#683d39}} .badge.muted{{background:#151d20;color:var(--muted)}}
    .lingua-summary{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));border-bottom:1px solid var(--line);background:#0d1417}} .lingua-stat{{padding:13px 15px;border-right:1px solid var(--line);min-width:0}} .lingua-stat:last-child{{border-right:0}} .lingua-stat span{{display:block;color:var(--muted);font-size:10px;font-weight:800;text-transform:uppercase}} .lingua-stat b{{display:block;margin-top:5px;font-size:17px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    .systems{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}} .system{{padding:16px;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}} .system b{{font-size:13px}} .system p{{font-size:12px;color:var(--muted);margin:7px 0 10px;line-height:1.4}}
    .small-action{{margin-top:7px;min-height:28px;padding:4px 8px;border:1px solid var(--blue);border-radius:4px;background:#11191c;color:var(--blue);font:inherit;font-size:10px;font-weight:800;cursor:pointer}} .small-action:hover{{background:#17262c}} .small-action.danger-action{{border-color:var(--red);color:var(--red)}} .small-action.danger-action:hover{{background:#2b1717}} .small-action:disabled{{opacity:.55;cursor:wait}} .empty{{padding:24px;color:var(--muted);font-size:13px}} .toast{{position:fixed;right:20px;bottom:20px;background:#192327;color:#fff;padding:12px 15px;border:1px solid var(--line);border-radius:6px;font-size:12px;box-shadow:0 16px 45px #0008;display:none;z-index:9}} .toast.show{{display:block}}
    dialog{{width:min(1180px,calc(100vw - 32px));max-height:calc(100vh - 32px);padding:0;border:1px solid var(--line);border-radius:6px;background:var(--surface);color:var(--ink);box-shadow:0 24px 80px #000b}} dialog::backdrop{{background:#030607dd}} .review-head{{position:sticky;top:0;z-index:3;display:flex;align-items:center;justify-content:space-between;gap:16px;padding:15px 18px;background:var(--surface);border-bottom:1px solid var(--line)}} .review-head h2{{font-size:16px;margin:0;color:var(--gold)}} .icon-action{{width:34px;height:34px;border:1px solid var(--line);border-radius:4px;background:#151d20;color:var(--ink);font-size:20px}} .review-meta{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;padding:16px 18px;border-bottom:1px solid var(--line);background:#0d1417}} .field{{display:grid;gap:5px}} .field label{{font-size:10px;color:var(--muted);font-weight:800;text-transform:uppercase}} .field input,.field textarea,.field select,.compact-select{{width:100%;border:1px solid #354247;border-radius:4px;background:#0b1113;color:var(--ink);padding:9px;font:inherit;font-size:12px}} .compact-select{{min-width:185px;margin-bottom:7px;padding:6px}} .review-units{{padding:0 18px}} .review-unit{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px;padding:17px 0;border-bottom:1px solid var(--line)}} .unit-title{{grid-column:1/-1;display:flex;align-items:center;justify-content:space-between;gap:12px}} .unit-title h3{{font-size:13px;margin:0}} .source-copy{{white-space:pre-wrap;font-size:12px;line-height:1.55;background:#0d1417;border-left:3px solid #63757b;padding:11px}} .target-copy textarea{{min-height:128px;resize:vertical;line-height:1.55}} .flag-list{{grid-column:1/-1;display:grid;gap:8px}} .flag-row{{display:grid;grid-template-columns:80px minmax(0,1fr) 180px minmax(160px,.7fr);gap:10px;align-items:center;padding:9px;background:#2a2315;border:1px solid #66562f;border-radius:4px;font-size:11px}} .unit-approval{{display:flex;align-items:center;gap:7px;font-size:11px;font-weight:750}} .review-actions{{position:sticky;bottom:0;display:flex;justify-content:flex-end;gap:9px;padding:13px 18px;background:var(--surface);border-top:1px solid var(--line)}} .primary-action{{min-height:36px;padding:7px 12px;border:1px solid var(--green);border-radius:4px;background:#1e7048;color:#fff;font-weight:800;font-size:12px}} .secondary-action{{min-height:36px;padding:7px 12px;border:1px solid var(--blue);border-radius:4px;background:#11191c;color:var(--blue);font-weight:800;font-size:12px}}
    @media(max-width:1050px){{.authority{{grid-template-columns:repeat(2,1fr)}}.authority-item:nth-child(2n){{border-right:0}}.authority-item:not(:nth-last-child(-n+2)){{border-bottom:1px solid var(--line)}}.metrics{{grid-template-columns:repeat(3,1fr)}}.metric:nth-child(3){{border-right:0}}.metric:nth-child(-n+3){{border-bottom:1px solid var(--line)}}.overview{{grid-template-columns:1fr}}.lingua-summary{{grid-template-columns:repeat(3,1fr)}}.lingua-stat{{border-bottom:1px solid var(--line)}}}}
    @media(max-width:760px){{.shell{{grid-template-columns:minmax(0,1fr)}}.workspace,main,main>*{{width:100%;max-width:100%;min-width:0}}aside{{height:auto;position:static;padding:10px;max-width:100vw;overflow:hidden}}.brand{{border:0;padding:4px 8px}}aside nav{{display:flex;overflow-x:auto;max-width:100%}}.nav-btn{{white-space:nowrap}}.side-status{{display:none}}header{{padding:0 14px}}main{{padding:14px}}.authority{{grid-template-columns:1fr}}.authority-item{{border-right:0;border-bottom:1px solid var(--line)}}.metrics{{grid-template-columns:repeat(2,1fr)}}.metric{{border-bottom:1px solid var(--line)}}.metric:nth-child(2n){{border-right:0}}.overview{{display:block}}.overview .panel+ .panel{{margin-top:14px}}.table-wrap{{width:100%;max-width:100%}}.lingua-summary{{grid-template-columns:repeat(2,1fr)}}.review-meta,.review-unit{{grid-template-columns:1fr}}.unit-title,.flag-list{{grid-column:1}}.flag-row{{grid-template-columns:1fr}}.review-actions{{flex-wrap:wrap}}}}
  </style>
</head>
<body>
<div class="shell">
  <aside>
    <div class="brand"><strong>DIO</strong><span>Control Deck</span></div>
    <nav aria-label="Control views">
      <button class="nav-btn active" data-jump="overview"><i data-lucide="layout-dashboard"></i>Overview</button>
      <button class="nav-btn" data-jump="attention"><i data-lucide="circle-alert"></i>Attention</button>
      <button class="nav-btn" data-tab-jump="workflows"><i data-lucide="list-checks"></i>Work Queue</button>
      <button class="nav-btn" data-tab-jump="sophia"><i data-lucide="graduation-cap"></i>Sophia</button>
      <button class="nav-btn" data-tab-jump="vamp"><i data-lucide="shield-check"></i>VAMP</button>
      <button class="nav-btn" data-tab-jump="document-studio"><i data-lucide="file-text"></i>Document Studio</button>
      <button class="nav-btn" data-tab-jump="lingua"><i data-lucide="languages"></i>Lingua QA</button>
      <button class="nav-btn" data-tab-jump="leads"><i data-lucide="contact-round"></i>Leads</button>
      <button class="nav-btn" data-tab-jump="transactions"><i data-lucide="workflow"></i>Transactions</button>
      <button class="nav-btn" data-tab-jump="mail"><i data-lucide="mail"></i>Mail</button>
      <button class="nav-btn" data-tab-jump="fulfilment"><i data-lucide="package-check"></i>Fulfilment</button>
      <button class="nav-btn" data-tab-jump="campaigns"><i data-lucide="megaphone"></i>Campaigns</button>
      <button class="nav-btn" data-tab-jump="market-command"><i data-lucide="chart-no-axes-combined"></i>Market Command</button>
      <button class="nav-btn" data-tab-jump="videos"><i data-lucide="video"></i>Video Releases</button>
      <button class="nav-btn" data-tab-jump="prospects"><i data-lucide="users"></i>Prospects</button>
      <button class="nav-btn" data-tab-jump="systems"><i data-lucide="activity"></i>Systems</button>
    </nav>
    <div class="side-status"><span>State refreshed <b id="sideTime">now</b></span><span>Local operator surface</span></div>
  </aside>
  <div class="workspace">
    <header><h1>DIO Operations</h1><div class="health"><i></i><span id="healthLabel">System state loaded</span></div></header>
    <main id="overview">
      <section class="authority" aria-label="Authority controls">
        <div class="authority-item"><div class="authority-copy"><b>Outbound mail</b><span>Approved intents only</span></div><button class="switch" data-policy="outbound_mail" title="Toggle outbound mail authority"></button></div>
        <div class="authority-item"><div class="authority-copy"><b>Automation</b><span>Intake and routing workers</span></div><button class="switch" data-policy="automation" title="Pause or resume automation"></button></div>
        <div class="authority-item"><div class="authority-copy"><b>Fulfilment release</b><span>Reviewed delivery boundary</span></div><button class="switch" data-policy="fulfilment_release" title="Hold or release fulfilment"></button></div>
        <div class="authority-item"><div class="authority-copy"><b>Lead intake</b><span>Capture approved prospects</span></div><button class="switch" data-policy="lead_capture" title="Hold or accept lead intake"></button></div>
        <div class="authority-item"><div class="authority-copy"><b>Data processing</b><span>Run product workloads</span></div><button class="switch" data-policy="data_processing" title="Hold or permit data processing"></button></div>
        <div class="authority-item"><div class="authority-copy"><b>Campaign release</b><span>Human publication gate</span></div><button class="switch" data-policy="campaign_release" title="Hold or permit campaign approval"></button></div>
        <div class="authority-item"><div class="authority-copy"><b>Invoice authority</b><span>Create job-specific checkout</span></div><button class="switch" data-policy="invoice_authority" title="Draft-only or issue checkout"></button></div>
        <div class="authority-item"><div class="authority-copy"><b>Payment mode</b><span>PayPal environment</span></div><button class="switch" data-policy="payment_mode" title="Switch sandbox or live payment environment"></button></div>
      </section>
      <section class="metrics" id="metrics"></section>
      <div class="overview">
        <section class="panel" id="attention"><div class="panel-head"><h2>Attention Queue</h2><span id="attentionCount"></span></div><div class="queue" id="attentionList"></div></section>
        <section class="panel"><div class="panel-head"><h2>Live Activity</h2><span>event-derived</span></div><div class="activity" id="activityList"></div></section>
      </div>
      <section class="panel">
        <div class="tabs" role="tablist">
          <button class="tab active" data-tab="workflows">Work Queue</button><button class="tab" data-tab="sophia">Sophia</button><button class="tab" data-tab="vamp">VAMP</button><button class="tab" data-tab="document-studio">Document Studio</button><button class="tab" data-tab="lingua">Lingua QA</button><button class="tab" data-tab="product-classes">Product Classes</button><button class="tab" data-tab="leads">Leads</button><button class="tab" data-tab="transactions">Transactions</button><button class="tab" data-tab="mail">Mail</button><button class="tab" data-tab="fulfilment">Fulfilment</button><button class="tab" data-tab="campaigns">Campaigns</button><button class="tab" data-tab="market-command">Market Command</button><button class="tab" data-tab="videos">Video Releases</button><button class="tab" data-tab="prospects">Prospects</button><button class="tab" data-tab="commerce">Commerce</button><button class="tab" data-tab="operations">Run History</button><button class="tab" data-tab="systems">Systems</button>
        </div>
        <div id="workflows" class="tab-panel active"><div class="table-wrap"><table><thead><tr><th>Product</th><th>Job</th><th>Intake</th><th>Processing</th><th>Output review</th><th>Notification</th><th>Recipient</th><th>Next action</th></tr></thead><tbody id="workflowRows"></tbody></table></div></div>
        <div id="operations" class="tab-panel"><div class="table-wrap"><table><thead><tr><th>Product</th><th>Job</th><th>Mode</th><th>Status</th><th>Approval</th><th>Risk</th><th>Run</th><th>Open</th></tr></thead><tbody id="jobsRows"></tbody></table></div></div>
        <div id="sophia" class="tab-panel"><div class="table-wrap"><table><thead><tr><th>Job</th><th>Mode</th><th>Payment</th><th>Review</th><th>Grounding</th><th>Approval</th><th>Delivery</th><th>Open</th></tr></thead><tbody id="sophiaRows"></tbody></table></div></div>
        <div id="vamp" class="tab-panel"><div class="table-wrap"><table><thead><tr><th>Job</th><th>Profile</th><th>Payment</th><th>Snapshot</th><th>Evidence</th><th>Approval</th><th>Delivery</th><th>Open</th></tr></thead><tbody id="vampRows"></tbody></table></div></div>
        <div id="document-studio" class="tab-panel"><div class="table-wrap"><table><thead><tr><th>Job</th><th>Service</th><th>Payment</th><th>Studio</th><th>Semantic</th><th>Approval</th><th>Delivery</th><th>Open</th></tr></thead><tbody id="documentStudioRows"></tbody></table></div></div>
        <div id="lingua" class="tab-panel"><div class="lingua-summary" id="linguaSummary"></div><div class="table-wrap"><table><thead><tr><th>Semantic object</th><th>Language lane</th><th>Source alignment</th><th>Deterministic integrity</th><th>Review signals</th><th>BEAST reuse</th><th>Authority</th><th>Open</th></tr></thead><tbody id="linguaRows"></tbody></table></div></div>
        <div id="product-classes" class="tab-panel"><div class="lingua-summary" id="productPortfolioSummary"></div><div class="panel-head"><h2>DIO Meta Portfolio</h2><span id="productPortfolioSource"></span></div><div class="table-wrap"><table><thead><tr><th>Product class</th><th>Suite</th><th>Family</th><th>Buyer / problem</th><th>Readiness</th><th>Maturity</th><th>Route</th><th>Open</th></tr></thead><tbody id="productClassRows"></tbody></table></div></div>
        <div id="leads" class="tab-panel"><div class="table-wrap"><table><thead><tr><th>Product</th><th>Reference</th><th>Contact</th><th>Offer</th><th>Qualification</th><th>Conversation</th><th>Promotion</th><th>Action</th></tr></thead><tbody id="leadRows"></tbody></table></div></div>
        <div id="transactions" class="tab-panel"><div class="panel-head"><h2>Commercial Transaction Spine</h2><span><button class="small-action" data-transaction-reconcile>Reconcile now</button></span></div><div class="table-wrap"><table><thead><tr><th>Transaction</th><th>Product / stage</th><th>Lineage</th><th>Payment</th><th>Metatron verdict</th><th>Loki</th><th>Harmonic flow</th><th>Next action</th><th>Open</th></tr></thead><tbody id="transactionRows"></tbody></table></div></div>
        <div id="mail" class="tab-panel"><div class="table-wrap"><table><thead><tr><th>Purpose</th><th>Subject</th><th>Recipient</th><th>Approval</th><th>Send state</th><th>Risk</th><th>Action</th></tr></thead><tbody id="mailRows"></tbody></table></div></div>
        <div id="fulfilment" class="tab-panel"><div class="table-wrap"><table><thead><tr><th>Product</th><th>Job</th><th>Deliverable</th><th>Approval</th><th>State</th></tr></thead><tbody id="fulfilmentRows"></tbody></table></div></div>
        <div id="campaigns" class="tab-panel"><div class="table-wrap"><table><thead><tr><th>Product</th><th>Campaign</th><th>Research evidence</th><th>Hivenance agents</th><th>Foundry</th><th>Settlement</th><th>Publication</th><th>Outreach</th><th>Open</th></tr></thead><tbody id="campaignRows"></tbody></table></div></div>
        <div id="market-command" class="tab-panel"><div class="lingua-summary" id="marketCommandSummary"></div><div class="panel-head"><h2>Creative Factory</h2><span><button class="small-action" data-factory-refresh>Refresh audience packages</button></span></div><div class="table-wrap"><table><thead><tr><th>Product / audience</th><th>Channel packages</th><th>Poster set</th><th>Media engine</th><th>Validation</th><th>Controls</th></tr></thead><tbody id="creativeFactoryRows"></tbody></table></div><div class="panel-head"><h2>Channel Adapters</h2><span><a href="http://127.0.0.1:8770/" target="_blank" rel="noopener">Open expanded command surface</a></span></div><div class="table-wrap"><table><thead><tr><th>Channel</th><th>Mode</th><th>Read state</th><th>Read authority</th><th>Missing setup</th><th>Write authority</th></tr></thead><tbody id="marketAdapterRows"></tbody></table></div><div class="panel-head"><h2>Governed Experiments</h2><span>proof → content → approval → channel → attribution → settlement</span></div><div class="table-wrap"><table><thead><tr><th>Campaign</th><th>Channel</th><th>State</th><th>Content authority</th><th>Spend cap</th><th>Qualified</th><th>Paid</th><th>Settlement</th><th>Control</th></tr></thead><tbody id="marketCommandRows"></tbody></table></div></div>
        <div id="videos" class="tab-panel"><div class="table-wrap"><table><thead><tr><th>Product</th><th>Film</th><th>Review</th><th>Preflight</th><th>YouTube</th><th>Action</th></tr></thead><tbody id="videoRows"></tbody></table></div></div>
        <div id="prospects" class="tab-panel"><div class="table-wrap"><table><thead><tr><th>Rank</th><th>Organisation</th><th>Product</th><th>Score</th><th>Public route</th><th>Outlook</th><th>Action</th></tr></thead><tbody id="prospectRows"></tbody></table></div></div>
        <div id="commerce" class="tab-panel"><div class="table-wrap"><table><thead><tr><th>Mode</th><th>Order</th><th>Product / job</th><th>Amount</th><th>Payment</th><th>Provider</th><th>Fulfilment</th><th>Open</th></tr></thead><tbody id="commerceRows"></tbody></table></div></div>
        <div id="systems" class="tab-panel"><div class="systems" id="systemsGrid"></div></div>
      </section>
    </main>
  </div>
</div>
<dialog id="linguaReviewDialog" aria-labelledby="linguaReviewTitle">
  <div class="review-head"><div><h2 id="linguaReviewTitle">Lingua semantic review</h2><small id="linguaReviewSubtitle"></small></div><button class="icon-action" id="closeLinguaReview" type="button" title="Close review">&times;</button></div>
  <div class="review-meta">
    <div class="field"><label for="linguaReviewer">Reviewer name</label><input id="linguaReviewer" autocomplete="name" placeholder="Proficient reviewer"></div>
    <div class="field"><label for="linguaReviewerRole">Reviewer role</label><input id="linguaReviewerRole" placeholder="Language practitioner, translator, subject specialist"></div>
  </div>
  <div class="review-units" id="linguaReviewUnits"></div>
  <div class="review-actions"><button class="secondary-action" id="saveLinguaReview" type="button">Save review</button><button class="primary-action" id="approveLinguaReview" type="button">Approve and crystallize</button></div>
</dialog>
<div class="toast" id="toast" role="status"></div>
<script>
const initialState={embedded}; let state=initialState;
const esc=(v)=>String(v??"").replace(/[&<>"']/g,c=>({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}}[c]));
const href=(p)=>p?((p.startsWith("http://")||p.startsWith("https://"))?p:(p.startsWith("/")?`file://${{p}}`:`../${{p}}`)):"";
const badge=(v)=>{{const s=String(v??"unknown");const c=s==="not_required"?"muted":/approved|delivered|complete|connected|online|ready|prioritize|sent|consumed|on|release|pass|active|valid/.test(s)?"good":/failed|blocked|critical|kill|missing|invalid|stale/.test(s)?"bad":/pending|review|paused|hold|setup|required|develop|revise|candidate/.test(s)?"warn":"muted";return `<span class="badge ${{c}}">${{esc(s)}}</span>`}};
const money=(v)=>new Intl.NumberFormat("en-ZA",{{style:"currency",currency:"ZAR",maximumFractionDigits:0}}).format(Number(v||0));
const orderMoney=(minor,currency)=>new Intl.NumberFormat("en-ZA",{{style:"currency",currency:currency||"USD"}}).format(Number(minor||0)/100);
function showToast(message){{const t=document.querySelector("#toast");t.textContent=message;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),2600)}}
function render(s){{state=s;document.querySelector("#sideTime").textContent=new Date(s.generated_at).toLocaleTimeString();
  const m=s.metrics;document.querySelector("#metrics").innerHTML=[["Qualified leads",m.leads],["Paid orders",m.orders],["Revenue",money(m.revenue)],["Active jobs",m.active_jobs],["Needs you",m.needs_you],["Failures",m.failures]].map(([k,v])=>`<div class="metric"><span>${{k}}</span><strong>${{v}}</strong></div>`).join("");
  document.querySelector("#attentionCount").textContent=`${{s.attention.length}} open`;
  document.querySelector("#attentionList").innerHTML=s.attention.length?s.attention.slice(0,12).map(a=>`<a class="queue-item" ${{a.link?`href="${{href(a.link)}}"`:""}}><i class="severity ${{esc(a.severity)}}"></i><span class="item-copy"><b>${{esc(a.title)}}</b><span>${{esc(a.detail)}}</span></span><span class="kind">${{esc(a.kind)}}</span></a>`).join(""):'<div class="empty">Nothing currently requires operator action.</div>';
  document.querySelector("#activityList").innerHTML=s.activity.length?s.activity.slice(0,12).map(a=>`<div class="activity-item"><i class="severity ${{esc(a.severity||"info")}}"></i><span class="item-copy"><b>${{esc(a.event)}}</b><span>${{esc(a.entity_type)}} · ${{esc(a.entity_id)}}</span></span><span class="kind">${{a.occurred_at?new Date(a.occurred_at).toLocaleTimeString([],{{hour:"2-digit",minute:"2-digit"}}):"recorded"}}</span></div>`).join(""):'<div class="empty">Events will appear when the mail and job workers begin.</div>';
  document.querySelector("#jobsRows").innerHTML=s.jobs.slice(0,80).map(j=>`<tr><td><b>${{esc(j.product)}}</b></td><td><code>${{esc(j.job_id)}}</code></td><td>${{badge(j.mode)}}</td><td>${{badge(j.status)}}</td><td>${{badge(j.approval)}}</td><td>${{esc(j.risk)}}</td><td>${{esc(j.run_name)}}</td><td>${{j.job_path?`<a href="${{href(j.job_path)}}">Open</a>`:"-"}}</td></tr>`).join("")||'<tr><td colspan="8">No jobs yet.</td></tr>';
  document.querySelector("#workflowRows").innerHTML=s.product_workflows.map(j=>`<tr><td><b>${{esc(j.product.toUpperCase())}}</b><br>${{badge(j.mode)}}</td><td><code>${{esc(j.job_id)}}</code><br><a href="${{href(j.path)}}">Workflow JSON</a>${{j.output_dir?` · <a href="${{href(j.output_dir)}}">Show pack</a>`:""}}${{j.mail_preview_path?`<br><a href="${{href(j.mail_preview_path)}}" target="_blank">Preview email</a>`:""}}${{j.notification_state==="outlook_ready"?` · <a href="https://outlook.live.com/mail/0/drafts" target="_blank" rel="noopener">Open Outlook drafts</a>`:""}}</td><td>${{badge(j.intake_state)}}</td><td>${{badge(j.processing_state)}}</td><td>${{badge(j.output_review_state)}}</td><td>${{badge(j.notification_state)}}</td><td>${{esc(j.recipient)}}${{j.controlled_fallback?"<br><small>controlled fallback</small>":""}}</td><td>${{j.action?`<button class="small-action" data-product-action="${{esc(j.action)}}" data-job-id="${{esc(j.job_id)}}">${{esc(j.action.replaceAll("-"," "))}}</button>`:j.notification_state==="outlook_ready"?"Review exact Outlook draft":"Complete"}}${{j.can_reject?`<br><button class="small-action danger-action" data-product-action="reject-intake" data-job-id="${{esc(j.job_id)}}">reject intake</button>`:""}}</td></tr>`).join("")||'<tr><td colspan="8">No active HOMS or Evidex workflows.</td></tr>';
  document.querySelector("#sophiaRows").innerHTML=s.sophia_jobs.map(j=>`<tr><td><code>${{esc(j.job_id)}}</code><br><small>${{esc(j.state)}}</small></td><td>${{badge(j.controlled?"controlled":"commercial")}}</td><td>${{badge(j.payment_state)}}</td><td>${{badge(j.review_state)}}</td><td>${{badge(j.grounding_passed?"passed":"pending")}}</td><td>${{badge(j.approval_state)}}</td><td>${{badge(j.outlook_draft_ready?"outlook ready":j.delivery_state)}}</td><td><a href="${{href(j.path)}}">Job JSON</a>${{j.output_dir?` · <a href="${{href(j.output_dir)}}">Show pack</a>`:""}}${{j.mail_preview_path?`<br><a href="${{href(j.mail_preview_path)}}" target="_blank">Preview email</a>`:""}}${{j.outlook_draft_ready?` · <a href="https://outlook.live.com/mail/0/drafts" target="_blank" rel="noopener">Open Outlook drafts</a>`:""}}${{j.action?`<br><button class="small-action" data-sophia-action="${{esc(j.action)}}" data-job-id="${{esc(j.job_id)}}">${{esc(j.action.replaceAll("-"," "))}}</button>`:""}}</td></tr>`).join("")||'<tr><td colspan="8">No Sophia commercial jobs yet.</td></tr>';
  document.querySelector("#vampRows").innerHTML=s.vamp_jobs.map(j=>`<tr><td><code>${{esc(j.job_id)}}</code><br><small>${{esc(j.state)}}</small></td><td>${{esc(j.profile_id)}}<br>${{badge(j.controlled?"controlled":"commercial")}}</td><td>${{badge(j.payment_state)}}</td><td>${{badge(j.snapshot_state)}}</td><td><b>${{j.evidence_backed_pct??"-"}}%</b><br><small>${{j.accepted_mappings??0}} accepted · ${{j.candidate_mappings??0}} review</small></td><td>${{badge(j.approval_state)}}</td><td>${{badge(j.outlook_draft_ready?"outlook ready":j.delivery_state)}}</td><td><a href="${{href(j.path)}}">Job JSON</a>${{j.output_dir?` · <a href="${{href(j.output_dir)}}">Show pack</a>`:""}}${{j.mail_preview_path?`<br><a href="${{href(j.mail_preview_path)}}" target="_blank">Preview email</a>`:""}}${{j.outlook_draft_ready?` · <a href="https://outlook.live.com/mail/0/drafts" target="_blank" rel="noopener">Open Outlook drafts</a>`:""}}${{j.action?`<br><button class="small-action" data-vamp-action="${{esc(j.action)}}" data-job-id="${{esc(j.job_id)}}">${{esc(j.action.replaceAll("-"," "))}}</button>`:""}}</td></tr>`).join("")||'<tr><td colspan="8">No VAMP commercial jobs yet.</td></tr>';
  document.querySelector("#documentStudioRows").innerHTML=(s.document_studio_jobs||[]).map(j=>`<tr><td><code>${{esc(j.job_id)}}</code><br><small>${{esc(j.state)}}</small></td><td>${{esc(j.service)}}<br><small>${{esc(j.source_language)}} -> ${{esc(j.target_language||j.source_language)}}</small><br>${{badge(j.controlled?"controlled":"commercial")}}</td><td>${{badge(j.payment_state)}}</td><td>${{badge(j.studio_state)}}<br><small>${{esc((j.release_readiness||"").replaceAll("_"," "))}}</small></td><td>${{j.semantic_object_id?`<code>${{esc(j.semantic_object_id)}}</code>`:badge("not registered")}}</td><td>${{badge(j.approval_state)}}</td><td>${{badge(j.outlook_draft_ready?"outlook ready":j.delivery_state)}}</td><td><a href="${{href(j.path)}}">Job JSON</a>${{j.output_dir?` · <a href="${{href(j.output_dir)}}">Show pack</a>`:""}}${{j.mail_preview_path?`<br><a href="${{href(j.mail_preview_path)}}" target="_blank">Preview email</a>`:""}}${{j.outlook_draft_ready?` · <a href="https://outlook.live.com/mail/0/drafts" target="_blank" rel="noopener">Open Outlook drafts</a>`:""}}${{j.action?`<br><button class="small-action" data-document-action="${{esc(j.action)}}" data-job-id="${{esc(j.job_id)}}">${{esc(j.action.replaceAll("-"," "))}}</button>`:""}}</td></tr>`).join("")||'<tr><td colspan="8">No Document Studio commercial jobs yet.</td></tr>';
  document.querySelector("#linguaSummary").innerHTML=[["Semantic objects",s.lingua.objects.length],["Products inherited",s.lingua.product_count],["Automatic learning",`${{s.lingua.beast_learning_events}} evidence events`],["Negative capability",`${{s.lingua.negative_capability.active||0}} active · ${{s.lingua.negative_capability.observing||0}} observing`],["Approved meaning",s.lingua.approved_semantic_credits],["Reuse economy",`${{s.lingua.beast_reuse_hits}} hits · ${{s.lingua.beast_provider_calls_avoided}} calls avoided`],["Memory Hull",`${{s.lingua.memory_residue}} sealed · ${{s.lingua.memory_residue_failed}} failed`],["PREC",`${{s.lingua.prec_lifecycles}} lifecycles`],["BEAST chain",`${{s.lingua.chain.valid?"valid":"invalid"}} · ${{s.lingua.chain.block_count}} blocks`]].map(([k,v])=>`<div class="lingua-stat"><span>${{esc(k)}}</span><b>${{esc(v)}}</b></div>`).join("");
  const linguaRows=s.lingua.objects.flatMap(o=>o.languages.length?o.languages.map(l=>`<tr><td><b>${{esc(o.object_id)}}</b><br><small>${{esc((o.origin||{{}}).product)}} · ${{esc((o.origin||{{}}).artifact_type)}} · v${{esc(o.source_version)}}</small><br><a href="${{href(o.path)}}">Semantic object</a></td><td><b>${{esc(l.language)}}</b><br>${{badge(l.status)}}</td><td><b>${{esc(l.anchor_coverage??"-")}}%</b><br><small>${{esc(l.unit_count)}}/${{esc(o.source_unit_count)}} units · ${{esc(l.stale_units)}} stale</small></td><td>Numerals ${{badge(l.numerals)}}<br>Tokens ${{badge(l.protected_tokens)}}</td><td><b>${{esc(l.material_flags)}} material flags</b><br><small>Learned automatically for conservative routing</small></td><td><b>${{esc(l.approved_units_reused)}} units · ${{esc(l.approved_terms_reused)}} terms</b><br><small>Only human-approved meaning is reusable</small></td><td>${{badge(l.semantic_authority)}}<br><small>Pack: ${{esc(l.release_readiness.replaceAll("_"," "))}}</small></td><td><button class="small-action" data-lingua-review data-object-id="${{esc(o.object_id)}}" data-language="${{esc(l.language)}}">${{l.semantic_authority==="approved_crystallized"?"Inspect approval":"Review and approve"}}</button><br>${{l.qa_path?`<a href="${{href(l.qa_path)}}">QA</a>`:"-"}}${{l.pack?` · <a href="${{href(l.pack)}}">Pack</a>`:""}}</td></tr>`):[`<tr><td><b>${{esc(o.object_id)}}</b><br><small>${{esc((o.origin||{{}}).product)}} · ${{esc((o.origin||{{}}).artifact_type)}} · v${{esc(o.source_version)}}</small><br><a href="${{href(o.path)}}">Semantic object</a></td><td>${{badge("source registered")}}</td><td><b>${{esc(o.source_unit_count)}} units</b><br><small>${{esc(o.source_language)}} canonical source</small></td><td>${{badge("awaiting language request")}}</td><td>No translation flags yet</td><td>Shared terminology eligible</td><td>${{badge("source authority only")}}</td><td>Choose a target language when this artifact enters production.</td></tr>`]);document.querySelector("#linguaRows").innerHTML=linguaRows.join("")||'<tr><td colspan="8">No Lingua semantic objects yet.</td></tr>';
  const portfolio=s.product_portfolio||{{state:"not_imported",summary:{{}},incarnations:[],suites:[]}},ps=portfolio.summary||{{}},audit=portfolio.readiness_audit||{{}},ra=audit.summary||{{}},activation=portfolio.activation_plan||{{summary:{{}}}},ap=activation.summary||{{}};document.querySelector("#productPortfolioSummary").innerHTML=[["Suites",ps.suites||0],["Product classes",ps.incarnations||0],["Processing-ready",audit.processing_ready_total||0],["Ready now",ra.launch_controlled_pilot||0],["To package",ap.products_to_package||0],["Near ready",ra.near_ready_profile_extension||0],["Not packaged",ra.not_ready||0]].map(([k,v])=>`<div class="lingua-stat"><span>${{esc(k)}}</span><b>${{esc(v)}}</b></div>`).join("");document.querySelector("#productPortfolioSource").innerHTML=portfolio.report_path?`<a href="${{href(portfolio.report_path)}}">Activation report</a>${{portfolio.readiness_audit?.report_path?` · <a href="${{href(portfolio.readiness_audit.report_path)}}">Readiness audit</a>`:""}}${{activation.doc_path?` · <a href="${{href(activation.doc_path)}}">Packaging plan</a>`:""}}`:badge(portfolio.state);document.querySelector("#productClassRows").innerHTML=(portfolio.incarnations||[]).map(p=>{{const r=p.readiness||{{label:"not audited",score:"-",confidence:"unknown",next_step:"Run product-class readiness audit."}},pc=p.processing_coverage||{{state:"not audited",summary:"Run processing audit.",organs:[]}},act=p.activation_plan||{{}},pkg=p.product_package||{{}},providers=[...new Set((pc.organs||[]).flatMap(o=>o.provided_by||[]))].slice(0,5).join(", "),wave=act.activation_wave?`<br>${{badge(act.activation_wave)}}<br><small>priority ${{esc(act.priority)}} · ${{esc(act.pilot_offer)}}</small>`:"",openLinks=[pkg.site_path?`<a href="${{href(pkg.site_path)}}">Product site</a>`:"",pkg.golden_proof_path?`<a href="${{href(pkg.golden_proof_path)}}">Golden proof</a>`:"",pkg.zip_path?`<a href="${{href(pkg.zip_path)}}">Package zip</a>`:"",p.candidate_path?`<a href="${{href(p.candidate_path)}}">Candidate JSON</a>`:""].filter(Boolean).join("<br>")||"-";return `<tr><td><b>${{esc(p.Incarnation)}}</b><br><code>${{esc(p.candidate_id||"unregistered")}}</code></td><td>${{esc(p.Suite)}}</td><td>${{esc(p["Primary family"])}}</td><td><small><b>${{esc(p["Buyer / market"])}}</b><br>${{esc(p["Problem solved"])}}</small></td><td>${{badge(r.label)}}<br>${{badge(pc.state)}}${{wave}}<br><small>score ${{esc(r.score)}} · ${{esc(r.confidence)}}<br>${{esc(providers||pc.summary)}}<br>${{esc(r.next_step)}}</small></td><td>${{badge(p.Maturity)}}<br><small>${{esc(p.Horizon)}} · reuse ${{esc(p["Reuse score"])}} · build ${{esc(p["Build burden"])}} · validation ${{esc(p["Validation burden"])}}</small></td><td>${{badge(p.state)}}<br><small>${{esc(p.Output)}}</small></td><td>${{openLinks}}</td></tr>`}}).join("")||'<tr><td colspan="8">Import the DIO Meta Portfolio Atlas to activate product classes.</td></tr>';
  document.querySelector("#leadRows").innerHTML=s.leads.map(l=>{{const promoted=Boolean(l.promotion_state),canPromote=l.qualification==="qualified"&&!promoted;const promoLinks=l.promotion_receipt?`<br><a href="${{href(l.promotion_receipt)}}">Promotion receipt</a>`:"";const missing=(l.missing_inputs||[]).length?`<br><small>Needs: ${{esc((l.missing_inputs||[]).join(", "))}}</small>`:"";let actions="";if(l.qualification==="pending")actions=`<button class="small-action" data-lead-action="qualify" data-lead-id="${{esc(l.lead_id)}}">qualify</button><br><button class="small-action danger-action" data-lead-action="reject" data-lead-id="${{esc(l.lead_id)}}">reject</button>`;else actions=`${{canPromote?`<button class="small-action" data-lead-action="promote-to-job" data-lead-id="${{esc(l.lead_id)}}">promote to job</button><br>`:""}}<button class="small-action danger-action" data-lead-action="close" data-lead-id="${{esc(l.lead_id)}}">close</button>`;return `<tr><td><b>${{esc(String(l.product||"").toUpperCase())}}</b></td><td><code>${{esc(l.lead_id)}}</code><br><a href="${{href(l.path)}}">Intake JSON</a>${{l.mail_preview_path?`<br><a href="${{href(l.mail_preview_path)}}" target="_blank">Preview acknowledgement</a>`:""}}${{l.mail_path?` · <a href="${{href(l.mail_path)}}">Mail intent</a>`:""}}</td><td>${{esc(l.name)}}<br><small>${{esc(l.email)}}${{l.organisation?` · ${{esc(l.organisation)}}`:""}}</small></td><td>${{esc(l.offer)}}</td><td>${{badge(l.qualification)}}</td><td>${{badge(l.conversation_id?"bound":l.acknowledgement_state)}}</td><td>${{badge(l.promotion_state||"not promoted")}}${{promoLinks}}${{missing}}</td><td>${{actions}}</td></tr>`}}).join("")||'<tr><td colspan="8">No public website leads yet.</td></tr>';
  document.querySelector("#transactionRows").innerHTML=(s.transactions||[]).map(t=>`<tr><td><code>${{esc(t.transaction_id)}}</code><br><small>${{esc(t.offer||"")}}</small></td><td><b>${{esc(String(t.product||"unknown").toUpperCase())}}</b><br>${{badge(t.stage)}}</td><td>${{t.lead_id?`Lead <code>${{esc(t.lead_id)}}</code><br>`:""}}${{t.job_id?`Job <code>${{esc(t.job_id)}}</code><br>`:""}}${{t.order_id?`Order <code>${{esc(t.order_id)}}</code>`:""}}</td><td>${{badge(t.payment_state||"not started")}}</td><td>${{badge(t.verdict)}}<br><small>Metatron transaction belief</small></td><td>${{badge(t.loki_status)}}<br><small>${{esc(t.loki_challenges)}} challenge(s)</small></td><td>${{badge(t.harmonic_mode)}}<br><small>discord ${{Math.round(Number(t.discord_score||0)*100)}}%</small></td><td><b>${{esc((t.selected_action||"none").replaceAll("_"," "))}}</b><br><small>${{esc((t.selected_authority||"").replaceAll("_"," "))}}</small></td><td><a href="${{href(t.path)}}">Transaction</a><br><a href="${{href(t.decision_path)}}">Decision</a></td></tr>`).join("")||'<tr><td colspan="9">No canonical transactions yet. Reconcile the commercial spine.</td></tr>';
  document.querySelector("#mailRows").innerHTML=s.mail_intents.map(i=>`<tr><td>${{esc(i.purpose)}}${{i.lead_id?`<br><code>${{esc(i.lead_id)}}</code>`:""}}${{i.campaign_id?`<br><code>${{esc(i.campaign_id)}}</code>`:""}}</td><td><b>${{esc(i.subject)}}</b><br><small>${{esc(i.body_preview)}}</small></td><td>${{esc(i.recipient)}}</td><td>${{badge(i.approval)}}</td><td>${{badge(i.provider_draft_ready&&i.send_state==="draft"?"outlook ready":i.send_state)}}<br><small>${{i.has_html?"HTML branded":"plain text"}} · ${{i.attachment_count}} attachment(s)</small></td><td>${{esc(i.risk)}}</td><td>${{i.preview_path?`<a href="${{href(i.preview_path)}}" target="_blank">Preview email</a><br>`:""}}<a href="${{href(i.path)}}">Intent JSON</a>${{i.provider_draft_ready?`<br><a href="https://outlook.live.com/mail/0/drafts" target="_blank" rel="noopener">Open Outlook drafts</a>`:""}}${{!i.provider_draft_ready&&!["sent","rejected"].includes(i.send_state)?`<br><button class="small-action" data-mail-action="outlook-draft" data-mail-id="${{esc(i.mail_intent_id)}}">create Outlook draft</button>`:""}}${{i.provider_draft_ready&&!["sent","rejected"].includes(i.send_state)?`<br><button class="small-action" data-mail-action="approve-send" data-mail-id="${{esc(i.mail_intent_id)}}" data-risk="${{esc(i.risk)}}">approve &amp; send</button>`:""}}${{!["sent","rejected"].includes(i.send_state)?`<br><button class="small-action danger-action" data-mail-action="reject" data-mail-id="${{esc(i.mail_intent_id)}}">reject</button>`:""}}</td></tr>`).join("")||'<tr><td colspan="7">No governed mail intents yet.</td></tr>';
  const fulfilment=[...s.product_workflows.filter(j=>j.output_dir).map(j=>({{product:j.product,job_id:j.job_id,dir:j.output_dir,approval:j.output_review_state,state:j.notification_state,mail:j.mail_preview_path,path:j.path}})),...s.sophia_jobs.filter(j=>j.output_dir).map(j=>({{product:"sophia",job_id:j.job_id,dir:j.output_dir,approval:j.approval_state,state:j.delivery_state,mail:j.mail_preview_path,path:j.path}})),...s.vamp_jobs.filter(j=>j.output_dir).map(j=>({{product:"vamp",job_id:j.job_id,dir:j.output_dir,approval:j.approval_state,state:j.delivery_state,mail:j.mail_preview_path,path:j.path}})),...(s.document_studio_jobs||[]).filter(j=>j.output_dir).map(j=>({{product:"document-studio",job_id:j.job_id,dir:j.output_dir,approval:j.approval_state,state:j.delivery_state,mail:j.mail_preview_path,path:j.path}})),...s.jobs.filter(j=>j.deliverable_dir).map(j=>({{product:j.product,job_id:j.job_id,dir:j.deliverable_dir,approval:j.approval,state:j.status,mail:"",path:j.job_path}}))];document.querySelector("#fulfilmentRows").innerHTML=fulfilment.slice(0,100).map(j=>`<tr><td>${{esc(j.product)}}</td><td><code>${{esc(j.job_id)}}</code><br><a href="${{href(j.path)}}">Job JSON</a></td><td><a href="${{href(j.dir)}}">Show pack</a>${{j.mail?`<br><a href="${{href(j.mail)}}" target="_blank">Preview delivery email</a>`:""}}</td><td>${{badge(j.approval)}}</td><td>${{badge(j.state)}}</td></tr>`).join("")||'<tr><td colspan="5">No fulfilment packs yet.</td></tr>';
  const market=s.market_campaigns.map(c=>`<tr><td><b>${{esc(c.product)}}</b>${{c.proof_state?`<br>${{badge(c.proof_state)}}<br><small>subject review: ${{esc(c.proof_review)}}</small>`:""}}</td><td><code>${{esc(c.campaign_id)}}</code><br>${{esc(c.mode)}}</td><td>${{badge("registry grounded")}}<br><small>${{esc(c.registry_observed_at||"date unavailable")}}</small><br>${{badge(c.live_search_state)}}${{c.live_search_state==="not_refreshed"?`<br><button class="small-action" data-market-action="refresh-research" data-campaign-id="${{esc(c.campaign_id)}}">Refresh research + agents</button>`:`<br><small>YouTube ${{esc(c.live_relevant_count)}}/${{esc(c.live_result_count)}} · web/blog ${{esc(c.live_web_relevant_count)}}/${{esc(c.live_web_result_count)}}<br>median ${{Number(c.live_median_views||0).toLocaleString()}} video views</small><br><button class="small-action" data-market-action="refresh-research" data-campaign-id="${{esc(c.campaign_id)}}">Refresh research + agents</button>`}}</td><td>${{badge(c.agent_decision)}}<br><small>${{esc(c.agent_regime)}}${{c.agent_family?` · ${{esc(c.agent_family.replaceAll("_"," "))}}`:""}}${{c.agent_harmony!==null&&c.agent_harmony!==undefined?` · ${{Math.round(Number(c.agent_harmony)*100)}}% harmony`:""}}</small></td><td>${{c.foundry_score??"-"}} · ${{badge(c.foundry_decision)}}${{c.live_top_score?`<br><small>live candidate ${{esc(c.live_top_score)}}</small>`:""}}</td><td>${{badge(c.settlement)}}</td><td>${{badge(c.release_state)}}<br>${{c.release_state!=="released"?`<button class="small-action" data-market-action="release-publication" data-campaign-id="${{esc(c.campaign_id)}}">release publication</button>`:`<button class="small-action danger-action" data-market-action="hold-publication" data-campaign-id="${{esc(c.campaign_id)}}">hold</button>`}}</td><td>${{badge(c.outreach)}}<br><small>permission gate retained</small></td><td><a href="${{href(c.pack)}}">Pack</a>${{c.proof_update?` · <a href="${{href(c.proof_update)}}">Golden proof</a>`:""}}${{c.proof_pointer?` · <a href="${{href(c.proof_pointer)}}">Proof folder</a>`:""}}${{c.live_signals?` · <a href="${{href(c.live_signals)}}">Live signals</a>`:""}}${{c.agent_receipt?` · <a href="${{href(c.agent_receipt)}}">Agent reasoning</a>`:""}}${{c.release_path?` · <a href="${{href(c.release_path)}}">Decision</a>`:""}}</td></tr>`).join("");
  const legacy=s.campaigns.map(c=>`<tr><td><b>${{esc(c.layer)}}</b></td><td>${{esc(c.title)}}</td><td>${{badge("local brief")}}</td><td>${{badge("legacy")}}</td><td>- · ${{badge(c.status)}}</td><td>${{badge(c.approval)}}</td><td>-</td><td>-</td><td><a href="${{href(c.campaign_pack)}}">Pack</a>${{["pending","unknown"].includes(c.approval)?`<br><button class="small-action" data-campaign-action="approve" data-layer="${{esc(c.layer)}}">approve release</button><br><button class="small-action danger-action" data-campaign-action="reject" data-layer="${{esc(c.layer)}}">reject</button>`:""}}</td></tr>`).join("");document.querySelector("#campaignRows").innerHTML=market+legacy||'<tr><td colspan="9">No campaigns yet.</td></tr>';
  const mc=s.market_command||{{campaigns:[],content_items:[],totals:{{}},policy:{{}},catalogs:{{channels:{{channels:[]}}}},adapter_readiness:{{}}}};document.querySelector("#marketCommandSummary").innerHTML=[["Experiments",mc.campaigns.length],["Awaiting campaign approval",mc.campaigns.filter(c=>c.approval_state==="pending").length],["Content awaiting approval",mc.content_items.filter(c=>c.approval_state==="pending").length],["Spend",orderMoney((mc.totals||{{}}).spend_minor||0,"ZAR")],["Verified revenue",orderMoney((mc.totals||{{}}).revenue_minor||0,"ZAR")],["Automatic spend",(mc.policy||{{}}).automatic_spend||"off"]].map(([k,v])=>`<div class="lingua-stat"><span>${{esc(k)}}</span><b>${{esc(v)}}</b></div>`).join("");const mcChannels=(((mc.catalogs||{{}}).channels||{{}}).channels||[]);document.querySelector("#marketAdapterRows").innerHTML=mcChannels.map(c=>{{const r=(mc.adapter_readiness||{{}})[c.id]||{{state:c.credential_state,missing:[],read_authority:"manual_import",write_authority:c.write_authority||"human_approval_required"}};return `<tr><td><b>${{esc(c.name)}}</b><br><code>${{esc(c.id)}}</code></td><td>${{esc(c.adapter_mode)}}</td><td>${{badge(r.state)}}</td><td>${{esc(r.read_authority||"manual import")}}</td><td>${{(r.missing||[]).length?`<small>${{esc(r.missing.join(", "))}}</small>`:badge("ready")}}</td><td>${{badge(r.write_authority||"human approval")}}</td></tr>`}}).join("")||'<tr><td colspan="6">No channel adapters registered.</td></tr>';const mcContent=Object.fromEntries(mc.content_items.map(c=>[c.campaign_id,c]));document.querySelector("#marketCommandRows").innerHTML=mc.campaigns.map(c=>{{const content=mcContent[c.campaign_id],contentState=content?content.approval_state:"missing";let controls="";if(content&&content.approval_state==="pending")controls+=`<button class="small-action" data-mc-action="approve-content" data-content-id="${{esc(content.content_id)}}">approve content</button><br>`;if(c.approval_state==="pending")controls+=`<button class="small-action" data-mc-action="approve-campaign" data-campaign-id="${{esc(c.campaign_id)}}">approve campaign</button><br>`;if(c.state==="approved")controls+=`<button class="small-action" data-mc-action="activate" data-campaign-id="${{esc(c.campaign_id)}}">activate</button><br>`;if(c.state==="active")controls+=`<button class="small-action" data-mc-action="settle" data-campaign-id="${{esc(c.campaign_id)}}">settle</button>`;return `<tr><td><b>${{esc(c.name)}}</b><br><code>${{esc(c.campaign_id)}}</code></td><td>${{esc(c.channel_id)}}</td><td>${{badge(c.state)}}<br><small>${{esc(c.publication_state)}}</small></td><td>${{badge(contentState)}}${{content&&content.semantic_object_id?`<br><small>${{esc(content.semantic_object_id)}}</small>`:""}}</td><td>${{orderMoney(c.budget_cap_minor,c.currency)}}</td><td>${{c.metrics.qualified_leads}}</td><td>${{c.metrics.paid_orders}}</td><td>${{c.settlement?badge(c.settlement.decision):badge("unsettled")}}</td><td>${{controls||"No action"}}</td></tr>`}}).join("")||'<tr><td colspan="9">Market Command has no experiments yet.</td></tr>';
  const factory=mc.creative_factory||{{families:[],summary:{{}}}};document.querySelector("#creativeFactoryRows").innerHTML=(factory.families||[]).map(f=>{{const channels=Object.keys(f.copy||{{}}),assets=f.assets||{{}},nf=f.nichefoundry||{{}},asset=assets.portrait_1080x1350||assets.square_1080||"",reel=assets.reel_1080x1920||"",request=nf.request||nf.request_path||"",pipeline=nf.media_pipeline_receipt||"",reelReceipt=nf.native_reel_receipt||"";const assetLinks=[["Show advert",asset],["Square",assets.square_1080],["Landscape",assets.landscape_1200x628],["Story",assets.vertical_1080x1920],["Thumbnail",assets.youtube_1280x720]].filter(row=>row[1]).map(row=>`<a href="${{href(row[1])}}" target="_blank">${{esc(row[0])}}</a>`).join(" · ");return `<tr><td><b>${{esc(f.product.name)}}</b><br><small>${{esc(f.audience.name)}}</small><br><code>${{esc(f.family_id)}}</code></td><td><b>${{channels.length}}</b> targeted packages<br><small>${{esc(channels.join(" · "))}}</small></td><td>${{assetLinks||badge("missing")}}<br><small>poster, social, story and thumbnail variants</small></td><td>${{badge(nf.media_pipeline_state||nf.native_reel_state||nf.reel_state||"not queued")}}${{reel?`<br><a href="${{href(reel)}}" target="_blank">Watch reel</a>`:""}}${{request?` · <a href="${{href(request)}}">Production request</a>`:""}}${{pipeline?`<br><a href="${{href(pipeline)}}">Media receipt</a>`:""}}${{reelReceipt?` · <a href="${{href(reelReceipt)}}">Reel receipt</a>`:""}}<br><small>premium episode: ${{esc(nf.premium_episode_state||nf.long_form_state||"not queued")}}</small></td><td>${{badge(f.validation?.state||"unknown")}}<br><small>publish held · spend disabled</small></td><td><button class="small-action" data-factory-media="${{esc(f.family_id)}}">Run media bridge</button><br><select class="compact-select" data-factory-channel="${{esc(f.family_id)}}">${{channels.map(c=>`<option value="${{esc(c)}}">${{esc(c.replaceAll("_"," "))}}</option>`).join("")}}</select><br><button class="small-action" data-factory-promote="${{esc(f.family_id)}}">Create governed draft</button></td></tr>`}}).join("")||'<tr><td colspan="6">Creative families have not been generated yet.</td></tr>';
  document.querySelector("#videoRows").innerHTML=s.video_candidates.map(v=>{{const reviewed=v.watch_approved&&v.voice_approved&&v.thumbnail_approved&&v.metadata_approved;const uploaded=Boolean(v.youtube&&v.youtube.video_id),published=v.youtube&&v.youtube.privacy_status==="public";let action;if(published)action=`<a class="small-action" href="${{esc(v.youtube.watch_url)}}" target="_blank" rel="noopener">Open public video</a><br><a href="${{esc(v.youtube.url)}}" target="_blank" rel="noopener">YouTube Studio</a>`;else if(uploaded)action=`<button class="small-action" data-video-action="publish-public" data-episode-id="${{esc(v.episode_id)}}">Publish publicly</button><br><a href="${{esc(v.youtube.url)}}" target="_blank" rel="noopener">Review in YouTube Studio</a>`;else if(!reviewed)action=`<button class="small-action" data-video-action="approve-review" data-episode-id="${{esc(v.episode_id)}}">Approve reviewed film</button>`;else action=`<button class="small-action" data-video-action="upload-private" data-episode-id="${{esc(v.episode_id)}}">Upload privately</button>`;return `<tr><td><b>${{esc(String(v.product_id||"").toUpperCase())}}</b><br><small>${{esc(v.channel_title)}}</small></td><td>${{esc(v.title)}}<br><a href="${{href(v.video)}}">Watch film</a> · <a href="${{href(v.thumbnail)}}">Thumbnail</a></td><td>${{badge(reviewed?"approved":"awaiting approval")}}<br><small>film · voice · thumbnail · metadata</small></td><td>${{badge(v.preflight_passed?"passed":"blocked")}}<br><a href="${{href(v.compliance_report)}}">QA report</a></td><td>${{badge(published?"public verified":uploaded?"private verified":v.private_upload_ready?"ready for private upload":"held")}}</td><td>${{action}}<br><small>${{published?"Live on the DIO workflows channel.":uploaded?"Final public release remains explicit.":reviewed?"Uploads to DIO workflows as private.":"Confirms your completed review."}}</small></td></tr>`}}).join("")||'<tr><td colspan="6">No final video candidates yet.</td></tr>';
  document.querySelector("#prospectRows").innerHTML=s.prospect_registry.top_targets.map(p=>{{const sent=p.mail_send_state==="sent";const draft=p.provider_draft_ready&&!sent;const enhanced=p.creative_state==="proof_card_ready";let action;if(sent)action=badge("sent");else if(draft&&!enhanced)action=`<button class="small-action" data-prospect-action="upgrade-draft" data-target-id="${{esc(p.target_id)}}" data-mail-id="${{esc(p.mail_intent_id)}}">Add proof card</button><br><a href="https://outlook.live.com/mail/0/drafts" target="_blank" rel="noopener">Open Outlook drafts</a>`;else if(draft)action=`${{p.email_preview?`<a class="small-action" href="${{href(p.email_preview)}}" target="_blank">Preview proof email</a><br>`:""}}<a href="https://outlook.live.com/mail/0/drafts" target="_blank" rel="noopener">Review exact Outlook draft</a><br><button class="small-action" data-prospect-action="send" data-target-id="${{esc(p.target_id)}}" data-mail-id="${{esc(p.mail_intent_id)}}">Send consent request</button>`;else if(p.email_eligible)action=`<button class="small-action" data-prospect-action="prepare-draft" data-target-id="${{esc(p.target_id)}}">Prepare consent-first draft</button>`;else action=`<a href="${{esc(p.source_url)}}" target="_blank" rel="noopener">Use public submission route</a>`;return `<tr><td>${{esc(p.rank)}}</td><td><b>${{esc(p.organisation)}}</b><br><code>${{esc(p.target_id)}}</code></td><td>${{esc(p.product_name||p.product_line_id)}}</td><td><b>${{esc(p.attack_score)}}</b></td><td>${{badge(p.route_state)}}<br><small>${{esc(p.public_contact_route||p.route_type)}}</small><br><a href="${{esc(p.source_url)}}" target="_blank" rel="noopener">Verify source</a></td><td>${{badge(sent?"sent":enhanced?"proof card ready":draft?"plain draft":"not started")}}<br>${{p.consent_mode?`<small>once-off consent request</small>`:""}}</td><td>${{action}}</td></tr>`}}).join("")||'<tr><td colspan="7">No active prospect registry.</td></tr>';
  document.querySelector("#commerceRows").innerHTML=s.orders.map(o=>`<tr><td>${{badge(o.environment)}}</td><td><code>${{esc(o.order_id)}}</code></td><td>${{esc(o.product_code)}}${{o.job_id?`<br><small>${{esc(o.job_id)}}</small>`:""}}</td><td><b>${{orderMoney(o.amount_minor,o.currency)}}</b></td><td>${{badge(o.payment_state)}}</td><td>${{esc(o.provider)}}</td><td>${{badge(o.fulfilment_released?"released":"held")}}</td><td><a href="${{href(o.path)}}">Order</a></td></tr>`).join("")||'<tr><td colspan="8">No local commerce orders yet.</td></tr>';
  document.querySelector("#systemsGrid").innerHTML=s.systems.map(x=>`<div class="system"><b>${{esc(x.name)}}</b><p>${{esc(x.detail)}}</p>${{badge(x.state)}}</div>`).join("");
  document.querySelectorAll("[data-policy]").forEach(btn=>{{const k=btn.dataset.policy,v=s.control_policy[k];btn.textContent=v;btn.className=`switch ${{["on","release","running","accept","process","issue","live"].includes(v)?"on":"danger"}}`}});
  const down=s.systems.filter(x=>["missing","invalid"].includes(x.state)).length;document.querySelector("#healthLabel").textContent=down?`${{down}} system failure${{down===1?"":"s"}}`:`${{s.metrics.needs_you}} actions waiting`;
}}
async function refresh(){{try{{const r=await fetch("/api/control/state",{{cache:"no-store"}});if(r.ok)render(await r.json())}}catch{{}}}}
let activeLinguaReview=null;
function openLinguaReview(objectId,language){{const semantic=state.lingua.objects.find(item=>item.object_id===objectId),lane=semantic&&semantic.languages.find(item=>item.language===language);if(!semantic||!lane)return;activeLinguaReview={{semantic,lane}};document.querySelector("#linguaReviewTitle").textContent=`${{language}} semantic review`;document.querySelector("#linguaReviewSubtitle").textContent=`${{objectId}} · source v${{semantic.source_version}} · ${{semantic.domain}}`;document.querySelector("#linguaReviewer").value=lane.reviewer||"";document.querySelector("#linguaReviewerRole").value=lane.reviewer_role||"";document.querySelector("#linguaReviewUnits").innerHTML=lane.units.map(unit=>`<section class="review-unit" data-unit-id="${{esc(unit.unit_id)}}" data-source-hash="${{esc(unit.source_hash)}}"><div class="unit-title"><h3>${{esc(unit.unit_id)}} · ${{esc(unit.unit_type.replaceAll("_"," "))}}</h3><label class="unit-approval"><input type="checkbox" data-unit-approved ${{unit.approved?"checked":""}}> Meaning approved</label></div><div><div class="field"><label>Source</label><div class="source-copy">${{esc(unit.source_text)}}</div></div></div><div class="target-copy"><div class="field"><label>Reviewed ${{esc(language)}} text</label><textarea data-target-text>${{esc(unit.target_text)}}</textarea></div></div><div class="flag-list">${{unit.flags.length?unit.flags.map(flag=>`<div class="flag-row" data-flag-index="${{flag.index}}"><b>${{esc(flag.severity)}}</b><span>${{esc(flag.issue)}}</span><select data-flag-resolution aria-label="Flag disposition"><option value="unresolved" ${{flag.resolution==="unresolved"?"selected":""}}>Unresolved</option><option value="accepted_as_is" ${{flag.resolution==="accepted_as_is"?"selected":""}}>Accepted as-is</option><option value="corrected" ${{flag.resolution==="corrected"?"selected":""}}>Corrected in target</option><option value="not_applicable" ${{flag.resolution==="not_applicable"?"selected":""}}>Not applicable</option></select><input data-flag-note value="${{esc(flag.note)}}" placeholder="Reviewer note"></div>`).join(""):'<small>No provider uncertainty flags on this unit. The reviewer still confirms meaning.</small>'}}</div></section>`).join("");const locked=lane.semantic_authority==="approved_crystallized";document.querySelectorAll("#linguaReviewDialog input,#linguaReviewDialog textarea,#linguaReviewDialog select").forEach(control=>control.disabled=locked);document.querySelector("#saveLinguaReview").disabled=locked;document.querySelector("#approveLinguaReview").disabled=locked;document.querySelector("#approveLinguaReview").textContent=locked?"Already crystallized":"Approve and crystallize";document.querySelector("#linguaReviewDialog").showModal()}}
function linguaReviewPayload(action){{if(!activeLinguaReview)throw new Error("No Lingua review is open.");const {{semantic,lane}}=activeLinguaReview;const units=[...document.querySelectorAll("#linguaReviewUnits .review-unit")].map(section=>({{unit_id:section.dataset.unitId,source_hash:section.dataset.sourceHash,target_text:section.querySelector("[data-target-text]").value,approved:section.querySelector("[data-unit-approved]").checked,flag_resolutions:[...section.querySelectorAll(".flag-row")].map(row=>({{index:Number(row.dataset.flagIndex),resolution:row.querySelector("[data-flag-resolution]").value,note:row.querySelector("[data-flag-note]").value}}))}}));return {{action,semantic_object_id:semantic.object_id,target_language:lane.language,reviewer:document.querySelector("#linguaReviewer").value,reviewer_role:document.querySelector("#linguaReviewerRole").value,units,terms:[],confirmed:action==="approve-language"}}}}
async function submitLinguaReview(action){{const button=document.querySelector(action==="approve-language"?"#approveLinguaReview":"#saveLinguaReview");if(action==="approve-language"&&!window.confirm("Approve every unit and crystallize this language as reusable semantic authority in BEAST?"))return;button.disabled=true;try{{const r=await fetch("/api/control/lingua/action",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(linguaReviewPayload(action))}}),payload=await r.json();if(!r.ok)throw new Error(payload.message||"Lingua review failed");showToast(action==="approve-language"?"Language authority crystallized":"Lingua review saved");document.querySelector("#linguaReviewDialog").close();activeLinguaReview=null;await refresh()}}catch(error){{showToast(error.message)}}finally{{button.disabled=false}}}}
document.querySelectorAll(".tab").forEach(btn=>btn.addEventListener("click",()=>{{document.querySelectorAll(".tab,.tab-panel").forEach(x=>x.classList.remove("active"));btn.classList.add("active");document.querySelector(`#${{btn.dataset.tab}}`).classList.add("active")}}));
document.querySelectorAll("[data-tab-jump]").forEach(btn=>btn.addEventListener("click",()=>{{document.querySelector(`.tab[data-tab="${{btn.dataset.tabJump}}"]`).click();document.querySelector(".tabs").scrollIntoView({{behavior:"smooth"}})}}));document.querySelectorAll("[data-jump]").forEach(btn=>btn.addEventListener("click",()=>document.querySelector(`#${{btn.dataset.jump}}`).scrollIntoView({{behavior:"smooth"}})));
document.querySelectorAll("[data-policy]").forEach(btn=>btn.addEventListener("click",async()=>{{const key=btn.dataset.policy;const values={{outbound_mail:["off","on"],automation:["paused","running"],fulfilment_release:["hold","release"],lead_capture:["hold","accept"],data_processing:["hold","process"],campaign_release:["hold","release"],invoice_authority:["draft_only","issue"],payment_mode:["sandbox","live"]}};const current=state.control_policy[key],next=values[key][current===values[key][0]?1:0];try{{const r=await fetch("/api/control/policy",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{[key]:next}})}});if(!r.ok)throw new Error();const payload=await r.json();state.control_policy=payload;render(state);showToast(`${{key.replaceAll("_"," ")}}: ${{next}}`)}}catch{{showToast("Start the Control Deck server to change authority policy.")}}}}));
document.querySelector("#sophiaRows").addEventListener("click",async event=>{{const btn=event.target.closest("[data-sophia-action]");if(!btn)return;const action=btn.dataset.sophiaAction,jobId=btn.dataset.jobId;if(action==="approve"&&!window.confirm(`Approve the grounded review pack for ${{jobId}}?`))return;btn.disabled=true;try{{const r=await fetch("/api/control/sophia/action",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{job_id:jobId,action,confirmed:action==="approve"}})}});const payload=await r.json();if(!r.ok)throw new Error(payload.message||"Action failed");showToast(`Sophia ${{action.replaceAll("-"," ")}} complete`);await refresh()}}catch(error){{showToast(error.message)}}finally{{btn.disabled=false}}}});
document.querySelector("#vampRows").addEventListener("click",async event=>{{const btn=event.target.closest("[data-vamp-action]");if(!btn)return;const action=btn.dataset.vampAction,jobId=btn.dataset.jobId;if(action==="approve"&&!window.confirm(`Approve the calibrated VAMP evidence snapshot for ${{jobId}}?`))return;btn.disabled=true;try{{const r=await fetch("/api/control/vamp/action",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{job_id:jobId,action,confirmed:action==="approve"}})}});const payload=await r.json();if(!r.ok)throw new Error(payload.message||"Action failed");showToast(`VAMP ${{action.replaceAll("-"," ")}} complete`);await refresh()}}catch(error){{showToast(error.message)}}finally{{btn.disabled=false}}}});
document.querySelector("#documentStudioRows").addEventListener("click",async event=>{{const btn=event.target.closest("[data-document-action]");if(!btn)return;const action=btn.dataset.documentAction,jobId=btn.dataset.jobId;if(action==="approve"&&!window.confirm(`Approve the Document Studio review pack for ${{jobId}}?`))return;btn.disabled=true;try{{const r=await fetch("/api/control/document-studio/action",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{job_id:jobId,action,confirmed:action==="approve"}})}});const payload=await r.json();if(!r.ok)throw new Error(payload.message||"Action failed");showToast(`Document Studio ${{action.replaceAll("-"," ")}} complete`);await refresh()}}catch(error){{showToast(error.message)}}finally{{btn.disabled=false}}}});
document.querySelector("#linguaRows").addEventListener("click",event=>{{const btn=event.target.closest("[data-lingua-review]");if(btn)openLinguaReview(btn.dataset.objectId,btn.dataset.language)}});document.querySelector("#closeLinguaReview").addEventListener("click",()=>document.querySelector("#linguaReviewDialog").close());document.querySelector("#saveLinguaReview").addEventListener("click",()=>submitLinguaReview("save-review"));document.querySelector("#approveLinguaReview").addEventListener("click",()=>submitLinguaReview("approve-language"));
document.querySelector("#workflowRows").addEventListener("click",async event=>{{const btn=event.target.closest("[data-product-action]");if(!btn)return;const action=btn.dataset.productAction,jobId=btn.dataset.jobId;const decision=["approve-intake","reject-intake","approve-output"].includes(action);if(decision&&!window.confirm(`${{action.replaceAll("-"," ")}} for ${{jobId}}?`))return;btn.disabled=true;try{{const r=await fetch("/api/control/product/action",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{job_id:jobId,action,confirmed:decision}})}});const payload=await r.json();if(!r.ok)throw new Error(payload.message||"Action failed");showToast(`${{action.replaceAll("-"," ")}} complete`);await refresh()}}catch(error){{showToast(error.message)}}finally{{btn.disabled=false}}}});
document.querySelector("#campaignRows").addEventListener("click",async event=>{{const btn=event.target.closest("[data-campaign-action]");if(!btn)return;const action=btn.dataset.campaignAction,layer=btn.dataset.layer;if(!window.confirm(`${{action}} campaign release for ${{layer}}?`))return;btn.disabled=true;try{{const r=await fetch("/api/control/campaign/action",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{layer,action,confirmed:true}})}});const payload=await r.json();if(!r.ok)throw new Error(payload.message||"Action failed");showToast(`campaign ${{action}} complete`);await refresh()}}catch(error){{showToast(error.message)}}finally{{btn.disabled=false}}}});
document.querySelector("#campaignRows").addEventListener("click",async event=>{{const btn=event.target.closest("[data-market-action]");if(!btn)return;const action=btn.dataset.marketAction,campaignId=btn.dataset.campaignId;const prompt=action==="refresh-research"?`Refresh web, blog and YouTube evidence, then rerun Hivenance agents for ${{campaignId}}?`:`${{action.replaceAll("-"," ")}} for ${{campaignId}}? Direct outreach remains blocked.`;if(!window.confirm(prompt))return;btn.disabled=true;try{{const r=await fetch("/api/control/market-campaign/action",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{campaign_id:campaignId,action,confirmed:true}})}});const payload=await r.json();if(!r.ok)throw new Error(payload.message||"Action failed");showToast(action==="refresh-research"?"Research and Hivenance reasoning refreshed":`market campaign ${{action.replaceAll("-"," ")}} complete`);await refresh()}}catch(error){{showToast(error.message)}}finally{{btn.disabled=false}}}});
document.querySelector("#marketCommandRows").addEventListener("click",async event=>{{const btn=event.target.closest("[data-mc-action]");if(!btn)return;const action=btn.dataset.mcAction,campaignId=btn.dataset.campaignId||"",contentId=btn.dataset.contentId||"";if(!window.confirm(`${{action.replaceAll("-"," ")}} ${{campaignId||contentId}}?`))return;btn.disabled=true;try{{const r=await fetch("/api/control/market-command/action",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{action,campaign_id:campaignId,content_id:contentId,confirmed:true}})}});const payload=await r.json();if(!r.ok)throw new Error(payload.message||"Action failed");showToast(`Market Command ${{action.replaceAll("-"," ")}} complete`);await refresh()}}catch(error){{showToast(error.message)}}finally{{btn.disabled=false}}}});
document.querySelector("[data-factory-refresh]").addEventListener("click",async event=>{{const btn=event.currentTarget;if(!window.confirm("Regenerate every audience and channel package from the current proof matrix? Existing approved experiments will not be changed."))return;btn.disabled=true;try{{const r=await fetch("/api/control/creative-factory/action",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{action:"refresh",confirmed:true}})}});const payload=await r.json();if(!r.ok)throw new Error(payload.message||"Factory refresh failed");showToast(`${{payload.result.summary.audiences}} audience families refreshed`);await refresh()}}catch(error){{showToast(error.message)}}finally{{btn.disabled=false}}}});
	document.querySelector("#creativeFactoryRows").addEventListener("click",async event=>{{const mediaBtn=event.target.closest("[data-factory-media]");if(mediaBtn){{const familyId=mediaBtn.dataset.factoryMedia;if(!window.confirm(`Run the native NicheFoundry media bridge for ${{familyId}}? This verifies scene images, music, ffmpeg, receipts and the held reel output.`))return;mediaBtn.disabled=true;try{{const r=await fetch("/api/control/creative-factory/action",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{action:"media-pipeline",family_id:familyId,confirmed:true}})}});const payload=await r.json();if(!r.ok)throw new Error(payload.message||"Media bridge failed");showToast(`${{payload.result.counts.ready}} media family ready · ${{payload.result.counts.blocked+payload.result.counts.failed}} blocked`);await refresh()}}catch(error){{showToast(error.message)}}finally{{mediaBtn.disabled=false}}return}}const btn=event.target.closest("[data-factory-promote]");if(!btn)return;const familyId=btn.dataset.factoryPromote,select=document.querySelector(`[data-factory-channel="${{CSS.escape(familyId)}}"]`),channelId=select.value;if(!window.confirm(`Create a held, zero-budget ${{channelId.replaceAll("_"," ")}} experiment for ${{familyId}}?`))return;btn.disabled=true;try{{const r=await fetch("/api/control/creative-factory/action",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{action:"promote",family_id:familyId,channel_id:channelId,confirmed:true}})}});const payload=await r.json();if(!r.ok)throw new Error(payload.message||"Draft promotion failed");showToast("Governed experiment draft created");await refresh()}}catch(error){{showToast(error.message)}}finally{{btn.disabled=false}}}});
document.querySelector("#videoRows").addEventListener("click",async event=>{{const btn=event.target.closest("[data-video-action]");if(!btn)return;const action=btn.dataset.videoAction,episodeId=btn.dataset.episodeId;const prompts={{"approve-review":"Confirm that you watched the complete film and approve its voice, thumbnail, and metadata?","upload-private":"Upload this approved film to the locked DIO workflows YouTube channel as PRIVATE?","publish-public":"Make this verified private video PUBLIC on the DIO workflows channel now?"}};if(!window.confirm(prompts[action]))return;btn.disabled=true;btn.textContent={{"approve-review":"Recording approval...","upload-private":"Uploading and verifying...","publish-public":"Publishing and verifying..."}}[action];try{{const r=await fetch("/api/control/video/action",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{episode_id:episodeId,action,confirmed:true}})}});const payload=await r.json();if(!r.ok)throw new Error(payload.message||"Action failed");showToast({{"approve-review":"Film review approved","upload-private":"Private YouTube upload verified","publish-public":"Public YouTube release verified"}}[action]);await refresh()}}catch(error){{showToast(error.message)}}finally{{btn.disabled=false}}}});
document.querySelector("#prospectRows").addEventListener("click",async event=>{{const btn=event.target.closest("[data-prospect-action]");if(!btn)return;const action=btn.dataset.prospectAction,targetId=btn.dataset.targetId,mailIntentId=btn.dataset.mailId;const prompts={{"prepare-draft":"Confirm that you reviewed the linked current public route. Create one consent-first Outlook proof-card draft?","upgrade-draft":"Replace the existing unsent plain draft with the consent-first HTML proof card?","send":"Confirm that you reviewed the exact Outlook draft and want to send this once-off consent request?"}};if(!window.confirm(prompts[action]))return;btn.disabled=true;try{{const r=await fetch("/api/control/prospect/action",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{target_id:targetId,mail_intent_id:mailIntentId,action,confirmed:true,route_confirmed:action==="prepare-draft"}})}});const payload=await r.json();if(!r.ok)throw new Error(payload.message||"Action failed");showToast({{"prepare-draft":"Consent-first Outlook draft ready","upgrade-draft":"Outlook proof card installed","send":"Consent request sent"}}[action]);await refresh()}}catch(error){{showToast(error.message)}}finally{{btn.disabled=false}}}});
document.querySelector("#leadRows").addEventListener("click",async event=>{{const btn=event.target.closest("[data-lead-action]");if(!btn)return;const action=btn.dataset.leadAction,leadId=btn.dataset.leadId;const prompt=action==="promote-to-job"?"Promote this qualified lead into the governed product route? If source files are missing, DIO will prepare a branded intake-materials mail draft.":`${{action}} ${{leadId}}?`;if(!window.confirm(prompt))return;btn.disabled=true;try{{const r=await fetch("/api/control/lead/action",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{lead_id:leadId,action,confirmed:true}})}});const payload=await r.json();if(!r.ok)throw new Error(payload.message||"Action failed");showToast(`lead ${{action.replaceAll("-"," ")}} complete`);await refresh()}}catch(error){{showToast(error.message)}}finally{{btn.disabled=false}}}});
document.querySelector("[data-transaction-reconcile]").addEventListener("click",async event=>{{const btn=event.currentTarget;if(!window.confirm("Reconcile leads, Outlook ingress, jobs, orders and governed mail into canonical transactions?"))return;btn.disabled=true;try{{const r=await fetch("/api/control/transaction/action",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{action:"reconcile",confirmed:true}})}});const payload=await r.json();if(!r.ok)throw new Error(payload.message||"Reconciliation failed");showToast(`${{payload.receipt.transactions}} commercial transaction(s) reconciled`);await refresh()}}catch(error){{showToast(error.message)}}finally{{btn.disabled=false}}}});
document.querySelector("#mailRows").addEventListener("click",async event=>{{const btn=event.target.closest("[data-mail-action]");if(!btn)return;const action=btn.dataset.mailAction,mailIntentId=btn.dataset.mailId;const sensitive=["sensitive","restricted"].includes(btn.dataset.risk);if(!window.confirm(`${{action.replaceAll("-"," ")}} ${{mailIntentId}}?${{sensitive?" Confirm that you verified the recipient and attachments.":""}}`))return;btn.disabled=true;try{{const r=await fetch("/api/control/mail/action",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{mail_intent_id:mailIntentId,action,confirmed:true,recipient_confirmed:sensitive}})}});const payload=await r.json();if(!r.ok)throw new Error(payload.message||"Action failed");showToast(`mail ${{action.replaceAll("-"," ")}} complete`);await refresh()}}catch(error){{showToast(error.message)}}finally{{btn.disabled=false}}}});
render(initialState);const requestedTab=window.location.hash.slice(1);const requestedButton=document.querySelector(`.tab[data-tab="${{CSS.escape(requestedTab)}}"]`);if(requestedButton){{requestedButton.click();requestAnimationFrame(()=>document.querySelector(".tabs").scrollIntoView({{block:"start"}}))}}if(window.lucide)window.lucide.createIcons();setInterval(refresh,5000);
</script>
</body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the DIO Control Deck.")
    parser.add_argument("--runs", default=str(ROOT / "runs"))
    parser.add_argument("--deliverables", default=str(ROOT / "deliverables"))
    parser.add_argument("--campaigns", default=str(ROOT / "campaigns" / "phase3"))
    parser.add_argument("--telemetry", default=str(ROOT / "telemetry" / "business_loop.csv"))
    parser.add_argument("--out", default=str(ROOT / "dashboard" / "index.html"))
    args = parser.parse_args()
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    state = build_dashboard_state(Path(args.runs).resolve(), Path(args.deliverables).resolve(), Path(args.campaigns).resolve(), Path(args.telemetry).resolve())
    write_json(out_path.parent / "state.json", state)
    out_path.write_text(render_dashboard(state), encoding="utf-8")
    print(f"Control Deck written to: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
