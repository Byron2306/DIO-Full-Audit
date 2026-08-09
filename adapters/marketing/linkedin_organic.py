from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from adapters.marketing.base import AdapterError, Transport, safe_int, stdlib_transport


CHANNEL_ID = "LINKEDIN_ORGANIC"


def readiness() -> dict[str, Any]:
    required = ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_ORGANIZATION_URN", "LINKEDIN_VERSION"]
    missing = [name for name in required if not os.environ.get(name)]
    return {
        "channel_id": CHANNEL_ID,
        "state": "ready_read_only" if not missing else "manual_ready",
        "required": required,
        "missing": missing,
        "read_authority": "organization_social_analytics" if not missing else "operator_import",
        "write_authority": "human_publish_only",
        "detail": "LinkedIn API analytics require approved organization access. Founder publication remains manual and approval-bound.",
    }


def _epoch_ms(value: str, end: bool = False) -> int:
    suffix = "T23:59:59+00:00" if end else "T00:00:00+00:00"
    return int(datetime.fromisoformat(f"{value}{suffix}").astimezone(timezone.utc).timestamp() * 1000)


def sync(start_date: str, end_date: str, transport: Transport = stdlib_transport) -> list[dict[str, Any]]:
    status = readiness()
    if status["missing"]:
        raise RuntimeError("LinkedIn analytics adapter not ready: " + ", ".join(status["missing"]))
    base = os.environ.get("LINKEDIN_API_BASE", "https://api.linkedin.com/rest").rstrip("/")
    urn = os.environ["LINKEDIN_ORGANIZATION_URN"]
    headers = {
        "Authorization": f"Bearer {os.environ['LINKEDIN_ACCESS_TOKEN']}",
        "LinkedIn-Version": os.environ["LINKEDIN_VERSION"],
        "X-Restli-Protocol-Version": "2.0.0",
    }
    params = {
        "q": "organizationalEntity",
        "organizationalEntity": urn,
        "timeIntervals.timeGranularityType": "ALL",
        "timeIntervals.timeRange.start": _epoch_ms(start_date),
        "timeIntervals.timeRange.end": _epoch_ms(end_date, end=True),
    }
    response = transport("GET", f"{base}/organizationalEntityShareStatistics", headers, params, None)
    elements = (response.payload or {}).get("elements") if isinstance(response.payload, dict) else None
    if not isinstance(elements, list):
        raise AdapterError("Unexpected LinkedIn organization analytics response shape")
    total: dict[str, Any] = {}
    for element in elements:
        stats = element.get("totalShareStatistics") or {}
        for key, value in stats.items():
            if isinstance(value, (int, float)):
                total[key] = total.get(key, 0) + value
    impressions = safe_int(total.get("impressionCount"))
    unique = safe_int(total.get("uniqueImpressionsCount"))
    clicks = safe_int(total.get("clickCount"))
    return [{
        "channel_id": CHANNEL_ID,
        "external_campaign_id": urn,
        "window_start": start_date,
        "window_end": end_date,
        "currency": "ZAR",
        "impressions": impressions,
        "reach": unique,
        "views": 0,
        "clicks": clicks,
        "conversions": 0,
        "spend_minor": 0,
        "conversion_value_minor": 0,
        "source_mode": "api",
        "evidence_grade": "platform_api",
        "raw": total,
    }]
