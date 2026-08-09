from __future__ import annotations

import os
from typing import Any

from adapters.marketing.base import AdapterError, Transport, safe_int, stdlib_transport


CHANNEL_ID = "INSTAGRAM_ORGANIC"


def readiness() -> dict[str, Any]:
    required = ["META_ACCESS_TOKEN", "INSTAGRAM_BUSINESS_ACCOUNT_ID", "META_GRAPH_VERSION"]
    missing = [name for name in required if not os.environ.get(name)]
    return {
        "channel_id": CHANNEL_ID,
        "state": "ready_read_only" if not missing else "manual_ready",
        "required": required,
        "missing": missing,
        "read_authority": "instagram_media_insights" if not missing else "operator_import",
        "write_authority": "human_business_suite_publish",
        "detail": "Organic Instagram reporting can be read through the connected professional account; publishing remains approval-bound.",
    }


def _metric(insights: dict[str, Any], *names: str) -> int:
    for row in insights.get("data") or []:
        if row.get("name") not in names:
            continue
        values = row.get("values") or []
        if values:
            return safe_int(values[-1].get("value"))
    return 0


def sync(start_date: str, end_date: str, transport: Transport = stdlib_transport) -> list[dict[str, Any]]:
    status = readiness()
    if status["missing"]:
        raise RuntimeError("Instagram organic adapter not ready: " + ", ".join(status["missing"]))
    base = os.environ.get("META_GRAPH_BASE", "https://graph.facebook.com").rstrip("/")
    account = os.environ["INSTAGRAM_BUSINESS_ACCOUNT_ID"]
    version = os.environ["META_GRAPH_VERSION"]
    token = os.environ["META_ACCESS_TOKEN"]
    fields = "id,caption,media_type,timestamp,permalink,like_count,comments_count,insights.metric(impressions,reach,plays,video_views)"
    response = transport("GET", f"{base}/{version}/{account}/media", {}, {"fields": fields, "since": start_date, "until": end_date, "limit": 100, "access_token": token}, None)
    rows = (response.payload or {}).get("data") if isinstance(response.payload, dict) else None
    if not isinstance(rows, list):
        raise AdapterError("Unexpected Instagram media response shape")
    out = []
    for row in rows:
        insights = row.get("insights") or {}
        out.append({
            "channel_id": CHANNEL_ID,
            "external_campaign_id": str(row.get("id") or ""),
            "window_start": start_date,
            "window_end": end_date,
            "currency": "ZAR",
            "impressions": _metric(insights, "impressions"),
            "reach": _metric(insights, "reach"),
            "views": _metric(insights, "plays", "video_views"),
            "clicks": 0,
            "conversions": 0,
            "spend_minor": 0,
            "conversion_value_minor": 0,
            "source_mode": "api",
            "evidence_grade": "platform_api",
            "raw": row,
        })
    return out
