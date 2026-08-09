from __future__ import annotations

import os
from typing import Any

from adapters.marketing.base import AdapterError, Transport, safe_int, stdlib_transport


CHANNEL_ID = "FACEBOOK_PAGE"


def readiness() -> dict[str, Any]:
    required = ["FACEBOOK_PAGE_ACCESS_TOKEN", "FACEBOOK_PAGE_ID", "META_GRAPH_VERSION"]
    missing = [name for name in required if not os.environ.get(name)]
    return {
        "channel_id": CHANNEL_ID,
        "state": "ready_read_only" if not missing else "manual_ready",
        "required": required,
        "missing": missing,
        "read_authority": "page_posts_and_insights" if not missing else "operator_import",
        "write_authority": "human_business_suite_publish",
        "detail": "API reporting activates when Page credentials are present. Publication remains an approved Meta Business Suite action.",
    }


def _metric(insights: dict[str, Any], name: str) -> int:
    for row in insights.get("data") or []:
        if row.get("name") != name:
            continue
        values = row.get("values") or []
        if values:
            return safe_int(values[-1].get("value"))
    return 0


def sync(start_date: str, end_date: str, transport: Transport = stdlib_transport) -> list[dict[str, Any]]:
    status = readiness()
    if status["missing"]:
        raise RuntimeError("Facebook Page API reporting not ready: " + ", ".join(status["missing"]))
    base = os.environ.get("META_GRAPH_BASE", "https://graph.facebook.com").rstrip("/")
    version = os.environ["META_GRAPH_VERSION"]
    page_id = os.environ["FACEBOOK_PAGE_ID"]
    token = os.environ["FACEBOOK_PAGE_ACCESS_TOKEN"]
    fields = "id,message,created_time,permalink_url,shares,comments.limit(0).summary(true),likes.limit(0).summary(true),insights.metric(post_impressions,post_impressions_unique,post_clicks)"
    response = transport("GET", f"{base}/{version}/{page_id}/published_posts", {}, {"fields": fields, "since": start_date, "until": end_date, "limit": 100, "access_token": token}, None)
    rows = (response.payload or {}).get("data") if isinstance(response.payload, dict) else None
    if not isinstance(rows, list):
        raise AdapterError("Unexpected Facebook Page response shape")
    out = []
    for row in rows:
        insights = row.get("insights") or {}
        comments = ((row.get("comments") or {}).get("summary") or {}).get("total_count")
        likes = ((row.get("likes") or {}).get("summary") or {}).get("total_count")
        out.append({
            "channel_id": CHANNEL_ID,
            "external_campaign_id": str(row.get("id") or ""),
            "window_start": start_date,
            "window_end": end_date,
            "currency": "ZAR",
            "impressions": _metric(insights, "post_impressions"),
            "reach": _metric(insights, "post_impressions_unique"),
            "views": 0,
            "clicks": _metric(insights, "post_clicks"),
            "conversions": 0,
            "spend_minor": 0,
            "conversion_value_minor": 0,
            "source_mode": "api",
            "evidence_grade": "platform_api",
            "raw": {**row, "comments_total": safe_int(comments), "likes_total": safe_int(likes)},
        })
    return out
