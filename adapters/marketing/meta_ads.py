from __future__ import annotations

import os
from typing import Any

from adapters.marketing.base import Transport, stdlib_transport, env_required, AdapterError, safe_int, safe_minor

CHANNEL_ID = "META_ADS"


def readiness() -> dict[str, Any]:
    required = ["META_ACCESS_TOKEN", "META_AD_ACCOUNT_ID", "META_GRAPH_VERSION"]
    missing = [x for x in required if not os.environ.get(x)]
    return {
        "channel_id": CHANNEL_ID,
        "state": "ready_read_only" if not missing else "credentials_required",
        "required": required,
        "missing": missing,
        "read_authority": "ads_read/insights",
        "write_authority": "blocked_by_dio_wave2",
        "detail": "Graph API version is explicit rather than hard-coded so platform version changes cannot silently mutate DIO behavior.",
    }


def sync(start_date: str, end_date: str, transport: Transport = stdlib_transport) -> list[dict[str, Any]]:
    env = env_required("META_ACCESS_TOKEN", "META_AD_ACCOUNT_ID", "META_GRAPH_VERSION")
    account = env["META_AD_ACCOUNT_ID"]
    if not account.startswith("act_"):
        account = "act_" + account
    base = os.environ.get("META_GRAPH_BASE", "https://graph.facebook.com").rstrip("/")
    params = {
        "access_token": env["META_ACCESS_TOKEN"],
        "level": "campaign",
        "fields": "campaign_id,campaign_name,impressions,reach,clicks,spend,actions,action_values",
        "time_range": '{"since":"%s","until":"%s"}' % (start_date, end_date),
        "limit": 500,
    }
    response = transport("GET", f"{base}/{env['META_GRAPH_VERSION']}/{account}/insights", {}, params, None)
    payload = response.payload
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise AdapterError("Unexpected Meta insights response shape")
    out = []
    for row in rows:
        actions = row.get("actions") or []
        conversions = 0.0
        for item in actions:
            if str(item.get("action_type") or "").lower() in {"purchase", "lead", "offsite_conversion.fb_pixel_purchase"}:
                try:
                    conversions += float(item.get("value") or 0)
                except (TypeError, ValueError):
                    pass
        values = row.get("action_values") or []
        conversion_value = 0.0
        for item in values:
            if str(item.get("action_type") or "").lower() in {"purchase", "offsite_conversion.fb_pixel_purchase"}:
                try:
                    conversion_value += float(item.get("value") or 0)
                except (TypeError, ValueError):
                    pass
        out.append({
            "channel_id": CHANNEL_ID,
            "external_campaign_id": str(row.get("campaign_id") or ""),
            "window_start": start_date,
            "window_end": end_date,
            "currency": os.environ.get("META_ACCOUNT_CURRENCY", "ZAR"),
            "impressions": safe_int(row.get("impressions")),
            "reach": safe_int(row.get("reach")),
            "clicks": safe_int(row.get("clicks")),
            "conversions": conversions,
            "spend_minor": safe_minor(row.get("spend"), 100),
            "conversion_value_minor": safe_minor(conversion_value, 100),
            "source_mode": "api",
            "evidence_grade": "platform_api",
            "raw": row,
        })
    return out
