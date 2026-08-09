#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_command.catalog import load_json  # noqa: E402
from market_command.core import MarketStore, utc_now  # noqa: E402


DB = ROOT / "state" / "market_command" / "market_command.sqlite"
EVENTS = ROOT / "telemetry" / "dio_events.jsonl"
CONFIG = ROOT / "config" / "market_command.json"
HYPOTHESES = ROOT / "campaigns" / "dio_market_loop" / "wave4" / "campaigns"


def channel_for(hypothesis: dict[str, Any]) -> str:
    experiment = hypothesis.get("experiment") or {}
    mode = str(experiment.get("mode") or "").casefold()
    channel = str(experiment.get("channel") or "").casefold()
    if "bulletin" in channel or "submission" in mode:
        return "SA_MEDIA_BUY"
    if "youtube" in channel:
        return "YOUTUBE_ORGANIC"
    if "facebook" in channel:
        return "FACEBOOK_PAGE"
    if "reddit" in channel:
        return "REDDIT_ORGANIC"
    return "LINKEDIN_ORGANIC"


def get_existing(store: MarketStore, campaign_id: str) -> dict[str, Any] | None:
    try:
        return store.get_campaign(campaign_id)
    except ValueError:
        return None


def import_hypotheses() -> dict[str, Any]:
    store = MarketStore(DB, EVENTS, load_json(CONFIG))
    imported = []
    for path in sorted(HYPOTHESES.glob("*/HIVENANCE_HYPOTHESIS.json")):
        hypothesis = load_json(path)
        campaign_id = str(hypothesis["campaign_id"])
        product = hypothesis.get("product") or {}
        audience = hypothesis.get("audience") or {}
        experiment = hypothesis.get("experiment") or {}
        channel_id = channel_for(hypothesis)
        campaign = get_existing(store, campaign_id)
        if campaign is None:
            campaign = store.create_campaign({
                "campaign_id": campaign_id,
                "product_line_id": product.get("product_line_id") or product.get("product_layer") or "DIO",
                "offer_id": product.get("offer_id"),
                "name": f"{product.get('public_name') or product.get('product_line_id')} proof experiment",
                "audience": audience.get("public_segment") or "DIO prospective buyer",
                "channel_id": channel_id,
                "mode": experiment.get("mode") or "bounded_experiment",
                "objective": experiment.get("success_event") or "qualified_pilot_conversation",
                "landing_page": f"sites/{product.get('product_layer')}/index.html" if product.get("product_layer") else "",
                "proof_asset": experiment.get("proof_asset"),
                "creative_brief": hypothesis.get("hypothesis"),
                "budget_cap_minor": int(experiment.get("budget_cap_minor") or 0),
                "currency": experiment.get("currency") or "ZAR",
                "experiment_window_days": int(experiment.get("window_days") or 14),
                "personalised_outreach_allowed": bool(audience.get("personalisation_allowed") is True),
                "source_lineage": {
                    "system": "hivenance_phoenix",
                    "hypothesis_id": hypothesis.get("hypothesis_id"),
                    "observation_id": (hypothesis.get("source") or {}).get("observation_id"),
                    "path": str(path.relative_to(ROOT)),
                },
                "source_gates": hypothesis.get("gates") or {},
            })
            campaign_state = "created"
        else:
            campaign_state = "already_present"

        content_id = "CNT-" + campaign_id.removeprefix("CMP-")
        content = store.add_content(campaign_id, {
            "content_id": content_id,
            "channel_id": channel_id,
            "format": "proof_campaign",
            "hook": experiment.get("public_hook") or product.get("public_name"),
            "body": "\n\n".join(filter(None, [
                experiment.get("proof_summary"),
                hypothesis.get("hypothesis"),
                f"Call to action: {experiment.get('cta')}" if experiment.get("cta") else "",
            ])),
            "asset_path": experiment.get("proof_asset"),
            "source_language": "English",
            "artifact_type": "proof_story",
            "semantic_object_id": f"MARKET-{campaign_id}",
            "source_version": str(hypothesis.get("registered_at") or "1.0.0"),
            "cta": experiment.get("cta") or "",
        })
        imported.append({
            "campaign_id": campaign_id,
            "campaign_state": campaign_state,
            "channel_id": channel_id,
            "content_id": content["content_id"],
            "semantic_object_id": content.get("semantic_object_id"),
            "approval_state": campaign["approval_state"],
            "content_approval_state": content["approval_state"],
        })

    receipt = {
        "schema": "dio.market_command.hivenance_import.v1",
        "imported_at": utc_now(),
        "source": str(HYPOTHESES.relative_to(ROOT)),
        "campaign_count": len(imported),
        "automatic_spend": "off",
        "publication_authority": "human_approval_required",
        "campaigns": imported,
    }
    receipt_path = ROOT / "state" / "market_command" / "HIVENANCE_IMPORT_RECEIPT.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    print(json.dumps(import_hypotheses(), indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
