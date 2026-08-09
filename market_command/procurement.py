from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_media_brief(root: Path, campaign: dict[str, Any], vendor: dict[str, Any], placement: str = "") -> dict[str, Any]:
    out = root / "state" / "market_command" / "procurement" / campaign["campaign_id"] / vendor["id"]
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "dio.media_procurement_brief.v1",
        "created_at": utc_now(),
        "campaign_id": campaign["campaign_id"],
        "vendor_id": vendor["id"],
        "vendor_name": vendor["name"],
        "product_line_id": campaign["product_line_id"],
        "audience": campaign["audience"],
        "objective": campaign["objective"],
        "placement_interest": placement,
        "proof_asset": campaign.get("proof_asset"),
        "tracked_url": campaign.get("tracked_url"),
        "maximum_budget_minor": campaign.get("budget_cap_minor", 0),
        "currency": campaign.get("currency", "ZAR"),
        "quote_requirements": [
            "placement/inventory description",
            "net price and taxes/fees",
            "campaign dates and delivery assumptions",
            "audience/targeting options",
            "creative specifications and deadlines",
            "measurement fields supplied after delivery",
            "click/UTM support where applicable",
            "cancellation/credit terms",
            "invoice and payment terms"
        ],
        "dio_measurement_contract": {
            "required": ["impressions_or_delivery", "clicks_if_available", "spend", "publication_evidence"],
            "preferred": ["reach", "engagement", "lead_count", "audience_breakdown"],
            "commercial_truth": "DIO independently binds downstream qualified leads, orders and verified payments."
        },
        "authority": {
            "brief_is_not_booking": True,
            "quote_requires_operator_review": True,
            "spend_requires_market_command_release": True
        }
    }
    (out / "MEDIA_BUY_BRIEF.json").write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    budget_minor = int(campaign.get("budget_cap_minor") or 0)
    budget_line = (
        f"{campaign.get('currency','ZAR')} {budget_minor / 100:.2f}"
        if budget_minor > 0
        else "No spend authorised yet. Please state your minimum viable controlled-pilot budget."
    )
    md = f"""# DIO Media Buy Brief\n\n**Campaign:** {campaign['name']} (`{campaign['campaign_id']}`)  \n**Vendor:** {vendor['name']}  \n**Product:** {campaign['product_line_id']}  \n**Audience:** {campaign['audience']}  \n**Objective:** {campaign['objective']}  \n**Placement interest:** {placement or 'Please recommend inventory against the objective'}  \n**Experiment budget position:** {budget_line}\n\n## Please quote\n\n- Your minimum viable controlled-pilot scope and budget\n- Placement / inventory and expected delivery\n- Agency fee, media spend and third-party costs as separate lines\n- Net price including all fees/taxes\n- Dates, creative specifications and material deadlines\n- Audience and targeting options\n- Measurement fields included in the post-campaign report\n- UTM/click tracking support where applicable\n- Cancellation/credit terms\n- Invoice and payment terms\n\n## Measurement contract\n\nDIO will bind the publisher/agency report to its own downstream lead, order and payment events. Platform-reported conversions do not replace DIO commercial settlement.\n\n## Authority boundary\n\nThis brief is a request for information/quotation. It is **not** a booking or spend authorization.\n"""
    (out / "MEDIA_BUY_BRIEF.md").write_text(md, encoding="utf-8")
    return {"campaign_id": campaign["campaign_id"], "vendor_id": vendor["id"], "output_dir": str(out), "files": ["MEDIA_BUY_BRIEF.json", "MEDIA_BUY_BRIEF.md"]}
