from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def export_campaign_pack(root: Path, campaign: dict[str, Any], channel: dict[str, Any] | None = None) -> dict[str, Any]:
    export_root = root / "state" / "market_command" / "exports" / campaign["campaign_id"]
    export_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "dio.market_campaign_export.v2",
        "exported_at": utc_now(),
        "campaign": campaign,
        "channel": channel or {},
        "operator_contract": {
            "this_is_not_publication": True,
            "this_is_not_spend_authority": True,
            "human_must_publish_or_create_platform_campaign": True,
            "bind_external_campaign_id_after_creation": True,
            "import_or_sync_results_after_launch": True,
        },
    }
    (export_root / "CAMPAIGN_PACK.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    checklist = f"""# {campaign['name']}\n\nCampaign ID: `{campaign['campaign_id']}`\n\n## Operator checklist\n\n1. Verify proof asset: `{campaign.get('proof_asset') or 'NOT SET'}`\n2. Verify audience: {campaign.get('audience')}\n3. Verify budget cap: {campaign.get('currency')} {campaign.get('budget_cap_minor',0)/100:.2f}\n4. Create/publish manually or through an approved adapter.\n5. Record the platform campaign ID in DIO.\n6. Sync/import platform measurement.\n7. Bind qualified leads, orders and verified payments back to this campaign.\n8. Run DIO settlement.\n\nTracked URL: {campaign.get('tracked_url') or ''}\n"""
    (export_root / "OPERATOR_CHECKLIST.md").write_text(checklist, encoding="utf-8")
    creative = {
        "campaign_id": campaign["campaign_id"],
        "channel_id": campaign["channel_id"],
        "headline_or_hook": "",
        "body": campaign.get("creative_brief") or "",
        "landing_page": campaign.get("tracked_url") or campaign.get("landing_page") or "",
        "proof_asset": campaign.get("proof_asset") or "",
        "cta": "",
    }
    (export_root / "CREATIVE_BRIEF.json").write_text(json.dumps(creative, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(creative.keys()))
    writer.writeheader(); writer.writerow(creative)
    (export_root / "CREATIVE_BRIEF.csv").write_text(output.getvalue(), encoding="utf-8")
    return {"campaign_id": campaign["campaign_id"], "export_dir": str(export_root), "files": ["CAMPAIGN_PACK.json", "OPERATOR_CHECKLIST.md", "CREATIVE_BRIEF.json", "CREATIVE_BRIEF.csv"]}
