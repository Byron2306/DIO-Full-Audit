from __future__ import annotations

from typing import Any

from adapters.marketing.registry import sync as adapter_sync, readiness
from market_command.intelligence import IntelligenceStore


def sync_channel(store: IntelligenceStore, channel_id: str, start_date: str, end_date: str, external_links: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    status = readiness(channel_id)
    if status.get("state") != "ready_read_only":
        store.set_channel_health(channel_id, status.get("state", "not_ready"), status.get("read_authority", "unknown"), "Missing: " + ", ".join(status.get("missing") or []), status)
        raise ValueError(f"Channel {channel_id} not ready: {', '.join(status.get('missing') or [])}")
    try:
        rows = adapter_sync(channel_id, start_date, end_date)
    except Exception as exc:
        store.set_channel_health(channel_id, "error", status.get("read_authority", "unknown"), str(exc), status)
        raise
    links = external_links if external_links is not None else store.list_external_links()
    lookup = {(x["channel_id"], str(x["external_campaign_id"])): x["campaign_id"] for x in links}
    recorded = []
    for row in rows:
        row["campaign_id"] = lookup.get((channel_id, str(row.get("external_campaign_id") or "")))
        recorded.append(store.record_snapshot(row))
    store.set_channel_health(channel_id, "healthy", status.get("read_authority", "unknown"), f"Recorded {len(recorded)} platform snapshots", {"window_start": start_date, "window_end": end_date})
    return {"channel_id": channel_id, "window_start": start_date, "window_end": end_date, "recorded": len(recorded), "snapshots": recorded}
