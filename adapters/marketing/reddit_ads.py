from __future__ import annotations

import os
from typing import Any

from adapters.marketing.base import Transport, stdlib_transport, env_required, AdapterError, safe_int, safe_minor


CHANNEL_ID = "REDDIT_ADS"


def readiness() -> dict[str, Any]:
    required = ["REDDIT_ADS_ACCESS_TOKEN", "REDDIT_AD_ACCOUNT_ID", "REDDIT_USER_AGENT"]
    missing = [x for x in required if not os.environ.get(x)]
    return {
        "channel_id": CHANNEL_ID,
        "state": "ready_read_only" if not missing else "credentials_required",
        "required": required,
        "missing": missing,
        "read_authority": "adsread",
        "write_authority": "blocked_by_dio_wave2",
    }


def sync(start_date: str, end_date: str, transport: Transport = stdlib_transport) -> list[dict[str, Any]]:
    env = env_required("REDDIT_ADS_ACCESS_TOKEN", "REDDIT_AD_ACCOUNT_ID", "REDDIT_USER_AGENT")
    base = os.environ.get("REDDIT_ADS_API_BASE", "https://ads-api.reddit.com/api/v3").rstrip("/")
    headers = {"Authorization": f"Bearer {env['REDDIT_ADS_ACCESS_TOKEN']}", "User-Agent": env["REDDIT_USER_AGENT"]}
    account = env["REDDIT_AD_ACCOUNT_ID"]
    # Reddit reporting is a POST endpoint, but it is read-only. No campaign mutation endpoints exist in this adapter.
    body = {
        "starts_at": start_date,
        "ends_at": end_date,
        "breakdowns": ["campaign_id"],
        "fields": ["IMPRESSIONS", "CLICKS", "SPEND"],
    }
    response = transport("POST", f"{base}/ad_accounts/{account}/reports", headers, None, body)
    payload = response.payload
    rows = payload.get("data") if isinstance(payload, dict) else None
    if rows is None:
        rows = payload.get("results", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        raise AdapterError("Unexpected Reddit report response shape")
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        # Reddit monetary reporting fields such as SPEND are documented in millionths of account currency.
        spend_minor = safe_minor(row.get("SPEND"), scale=100) if isinstance(row.get("SPEND"), float) else round(safe_int(row.get("SPEND")) / 10000)
        out.append({
            "channel_id": CHANNEL_ID,
            "external_campaign_id": str(row.get("campaign_id") or row.get("CAMPAIGN_ID") or ""),
            "window_start": start_date,
            "window_end": end_date,
            "currency": str(row.get("currency") or "USD"),
            "impressions": safe_int(row.get("IMPRESSIONS") or row.get("impressions")),
            "reach": safe_int(row.get("REACH") or row.get("reach")),
            "clicks": safe_int(row.get("CLICKS") or row.get("clicks")),
            "conversions": float(row.get("CONVERSIONS") or row.get("conversions") or 0),
            "spend_minor": max(0, int(spend_minor)),
            "conversion_value_minor": 0,
            "source_mode": "api",
            "evidence_grade": "platform_api",
            "raw": row,
        })
    return out
