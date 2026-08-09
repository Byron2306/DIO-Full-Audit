#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_command.catalog import load_json  # noqa: E402
from market_command.core import MarketStore, utc_now  # noqa: E402
from market_command.intelligence import IntelligenceStore  # noqa: E402


DB = ROOT / "state" / "market_command" / "market_command.sqlite"
EVENTS = ROOT / "telemetry" / "dio_events.jsonl"


def bind_owned_videos() -> dict:
    market = MarketStore(DB, EVENTS, load_json(ROOT / "config" / "market_command.json"))
    intelligence = IntelligenceStore(DB, EVENTS)
    campaigns = market.list_campaigns()
    product_campaigns: dict[str, list[str]] = {}
    for campaign in campaigns:
        prefix = str(campaign["product_line_id"]).split("_", 1)[0].casefold()
        product_campaigns.setdefault(prefix, []).append(campaign["campaign_id"])
    bindings = []
    for summary in intelligence.state().get("snapshots") or []:
        snapshot = intelligence.get_snapshot(summary["snapshot_id"])
        if snapshot.get("channel_id") != "YOUTUBE_ORGANIC":
            continue
        raw = snapshot.get("raw") or {}
        title = str(raw.get("title") or "").strip()
        prefix = title.split(None, 1)[0].rstrip(":").casefold() if title else ""
        candidates = product_campaigns.get(prefix) or []
        if len(candidates) != 1:
            continue
        link = intelligence.bind_external_campaign({
            "campaign_id": candidates[0],
            "channel_id": "YOUTUBE_ORGANIC",
            "external_campaign_id": snapshot["external_campaign_id"],
            "external_account_id": "UCc916iuoPLseg05t5J5leaQ",
            "metadata": {"binding_method": "owned_video_title_product_prefix", "title": title},
        })
        bindings.append({
            "campaign_id": link["campaign_id"],
            "video_id": link["external_campaign_id"],
            "title": title,
            "snapshot_id": snapshot["snapshot_id"],
        })
    receipt = {
        "schema": "dio.market_command.owned_video_binding.v1",
        "bound_at": utc_now(),
        "binding_count": len(bindings),
        "bindings": bindings,
    }
    path = ROOT / "state" / "market_command" / "OWNED_VIDEO_BINDING_RECEIPT.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    print(json.dumps(bind_owned_videos(), indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
