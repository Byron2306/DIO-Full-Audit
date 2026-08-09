#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "campaigns" / "phase3" / "evidex" / "commercial_ops" / "outlook_first"
LINKS_JS = ROOT / "sites" / "evidex" / "assets" / "commercial-links.js"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def outlook_subject() -> str:
    return "EVIDEX PILOT PACK REQUEST"


def outlook_body() -> str:
    return "\n".join(
        [
            "Hi Evidex,",
            "",
            "I want to test a non-sensitive or redacted evidence pack.",
            "",
            "Organization:",
            "Reporting context: donor report / grant evidence / audit / compliance / M&E",
            "Deadline:",
            "Files available: emails / invoices / photos / spreadsheets / notes",
            "What the pack should help prove:",
            "Upload link or delivery arrangement:",
            "",
            "I understand this is review-ready support, not automatic auditor/donor sign-off.",
        ]
    )


def outlook_mailto() -> str:
    return f"mailto:?subject={quote(outlook_subject())}&body={quote(outlook_body())}"


def dummy_outlook_items() -> dict[str, object]:
    marker = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return {
        "schema": "knowedge.outlook_triage_export.v1",
        "created_at": utc_now(),
        "items": [
            {
                "message_id": f"dummy-evidex-outlook-{marker}",
                "thread_ref": f"dummy-evidex-thread-{marker}",
                "source": "outlook_triage_dummy",
                "folder": "Inbox",
                "subject": "EVIDEX Pilot Pack Request - Thandi Community Trust",
                "sender": "M&E Coordinator <pilot.client@example.org>",
                "received_at": utc_now(),
                "sender_type": "external_client",
                "urgency": "high",
                "intent": "evidence_pack_request",
                "risk": "routine",
                "lane": "evidex",
                "risk_flags": "",
                "confidence": "0.91",
                "draft_status": "draft_ready",
                "approval_required": "true",
                "safe_send_rating": "caution",
                "recommended_action": "Route to Evidex pilot pack; request redacted sample folder and payment confirmation before final delivery.",
                "next_step": "Prepare grant evidence pack intake, invoice metadata, and source index request.",
                "attachment_names": "kpi-progress.csv; receipts-summary.xlsx; attendance-register.pdf; field-photos.zip",
                "body": (
                    "We need a review-ready evidence pack for a donor grant report. "
                    "The project has KPI progress, attendance registers, receipts, photos, and email approvals, "
                    "but the evidence is scattered. We need a source index, evidence table, narrative draft, "
                    "QA receipt, and a ZIP that our grant consultant can review. Reporting period is April to June. "
                    "Please tell us how to send a redacted pilot folder and invoice/payment link."
                ),
                "primary_draft_path": "",
                "safer_draft_path": "",
                "shorter_draft_path": "",
                "evidence_note_path": "",
            }
        ],
    }


def write_markdown(path: Path) -> None:
    lines = [
        "# Evidex Outlook-First Intake",
        "",
        f"Updated: {utc_now()}",
        "",
        "## Why This Matters",
        "",
        "The Google Form and Drive/paygate route can stay, but it must not be the first blocker. The Outlook bot already produces the exact kind of triage records AutoRelease can route.",
        "",
        "## Live Spine",
        "",
        "```text",
        "ad or direct message",
        "-> prospect replies with EVIDEX PILOT PACK REQUEST",
        "-> Outlook bot triages mailbox or exported messages",
        "-> triage_summary.csv / triage JSON",
        "-> scripts/route_intake.py",
        "-> Evidex job envelope",
        "-> review pack",
        "-> deterministic Evidex pack generation",
        "-> operator approval",
        "-> invoice/paygate or manual PAID.txt before final delivery",
        "```",
        "",
        "## Operator Rule",
        "",
        "Use Outlook for discovery, qualification, and packet creation. Use Google Form/Drive for structured upload when it is working. Use payment links only after a human has checked the lead is real and scoped.",
        "",
        "## Subject Marker",
        "",
        "```text",
        f"{outlook_subject()}",
        "```",
        "",
        "## Buyer Reply Template",
        "",
        "```text",
        outlook_body(),
        "```",
        "",
        "## Verification",
        "",
        "The dummy packet in this folder is designed to route as an Evidex job through the same adapter path used by Outlook triage output.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_ad(path: Path) -> None:
    copy = [
        "# Evidex Outlook-First Push Ad",
        "",
        f"Updated: {utc_now()}",
        "",
        "## Channel",
        "",
        "LinkedIn post, WhatsApp follow-up, direct email, or reply to an existing prospect thread.",
        "",
        "## Copy",
        "",
        "```text",
        "Your donor report probably is not missing effort.",
        "It is missing an evidence pipeline.",
        "",
        "Evidex turns scattered emails, spreadsheets, receipts, photos, and notes into a review-ready evidence pack:",
        "",
        "- evidence table",
        "- source index",
        "- narrative draft",
        "- QA receipt",
        "- delivery ZIP",
        "",
        "Start with one non-sensitive or redacted pilot folder.",
        "",
        f"Reply with: {outlook_subject()}",
        "",
        "This is review-ready support, not automatic auditor or donor sign-off.",
        "```",
        "",
        "## Internal Routing",
        "",
        "Replies can be pulled by the Outlook bot and routed by AutoRelease without waiting for Google Drive mirroring.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(copy) + "\n", encoding="utf-8")


def update_links_js(path: Path) -> None:
    existing: dict[str, object] = {}
    if path.exists():
        text = path.read_text(encoding="utf-8", errors="replace")
        prefix = "window.EVIDEX_COMMERCIAL_LINKS = "
        if text.strip().startswith(prefix):
            raw = text.strip()[len(prefix) :].rstrip(";")
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    existing = parsed
            except json.JSONDecodeError:
                existing = {}

    existing.update(
        {
            "outlook_first_enabled": True,
            "outlook_subject_marker": outlook_subject(),
            "outlook_mailto": outlook_mailto(),
            "outlook_intake_packet": "campaigns/phase3/evidex/commercial_ops/outlook_first/dummy_outlook_evidex_intake.json",
            "generated_at": utc_now(),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("window.EVIDEX_COMMERCIAL_LINKS = " + json.dumps(existing, indent=2) + ";\n", encoding="utf-8")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dummy_path = OUT_DIR / "dummy_outlook_evidex_intake.json"
    guide_path = OUT_DIR / "OUTLOOK_FIRST_INTAKE.md"
    ad_path = OUT_DIR / "OUTLOOK_FIRST_AD.md"
    receipt_path = OUT_DIR / "OUTLOOK_FIRST_RECEIPT.json"

    write_json(dummy_path, dummy_outlook_items())
    write_markdown(guide_path)
    write_ad(ad_path)
    update_links_js(LINKS_JS)

    receipt = {
        "schema": "knowedge.evidex_outlook_first_intake.v1",
        "created_at": utc_now(),
        "status": "outlook_first_intake_ready",
        "subject_marker": outlook_subject(),
        "adapter": "adapters/outlook_triage/README.md",
        "outlook_bot": "/home/byron/Desktop/KnowEdge_Outlook_Triage_DROP_IN_BUILD_WIX4_FIXED",
        "files": [
            str(guide_path.relative_to(ROOT)),
            str(ad_path.relative_to(ROOT)),
            str(dummy_path.relative_to(ROOT)),
            str(LINKS_JS.relative_to(ROOT)),
        ],
        "next_command": (
            "python3 scripts/run_phase1_pipeline.py "
            f"--input {dummy_path.relative_to(ROOT)} "
            "--run runs/evidex_outlook_first_dry_run "
            "--out deliverables/evidex_outlook_first_dry_run"
        ),
    }
    write_json(receipt_path, receipt)
    print(json.dumps({"status": receipt["status"], "dummy": str(dummy_path.relative_to(ROOT))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
