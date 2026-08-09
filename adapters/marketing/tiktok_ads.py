from __future__ import annotations

import json
import os
from typing import Any

from adapters.marketing.base import Transport, stdlib_transport, env_required, AdapterError, safe_int, safe_minor

CHANNEL_ID = "TIKTOK_ADS"


def readiness() -> dict[str, Any]:
    required = ["TIKTOK_ACCESS_TOKEN", "TIKTOK_ADVERTISER_ID"]
    missing = [x for x in required if not os.environ.get(x)]
    return {
        "channel_id": CHANNEL_ID,
        "state": "ready_read_only" if not missing else "credentials_required",
        "required": required,
        "missing": missing,
        "read_authority": "reporting",
        "write_authority": "blocked_by_dio_wave2",
    }


def sync(start_date: str, end_date: str, transport: Transport = stdlib_transport) -> list[dict[str, Any]]:
    env = env_required("TIKTOK_ACCESS_TOKEN", "TIKTOK_ADVERTISER_ID")
    base = os.environ.get("TIKTOK_API_BASE", "https://business-api.tiktok.com/open_api/v1.3").rstrip("/")
    headers = {"Access-Token": env["TIKTOK_ACCESS_TOKEN"]}
    params = {
        "advertiser_id": env["TIKTOK_ADVERTISER_ID"],
        "report_type": "BASIC",
        "data_level": "AUCTION_CAMPAIGN",
        "dimensions": json.dumps(["campaign_id"]),
        "metrics": json.dumps(["campaign_name", "spend", "impressions", "clicks", "conversion"]),
        "start_date": start_date,
        "end_date": end_date,
        "page_size": 1000,
    }
    response = transport("GET", f"{base}/report/integrated/get/", headers, params, None)
    payload = response.payload
    if not isinstance(payload, dict) or int(payload.get("code", 0)) != 0:
        raise AdapterError(f"TikTok reporting error: {payload}")
    data = payload.get("data") or {}
    rows = data.get("list") or []
    out = []
    for row in rows:
        dims = row.get("dimensions") or {}
        metrics = row.get("metrics") or {}
        out.append({
            "channel_id": CHANNEL_ID,
            "external_campaign_id": str(dims.get("campaign_id") or ""),
            "window_start": start_date,
            "window_end": end_date,
            "currency": os.environ.get("TIKTOK_ACCOUNT_CURRENCY", "ZAR"),
            "impressions": safe_int(metrics.get("impressions")),
            "reach": safe_int(metrics.get("reach")),
            "clicks": safe_int(metrics.get("clicks")),
            "conversions": float(metrics.get("conversion") or 0),
            "spend_minor": safe_minor(metrics.get("spend"), 100),
            "conversion_value_minor": safe_minor(metrics.get("total_purchase_value"), 100),
            "source_mode": "api",
            "evidence_grade": "platform_api",
            "raw": row,
        })
    return out
