from __future__ import annotations

import os
from typing import Any

CHANNEL_ID = "GOOGLE_ADS"


def readiness() -> dict[str, Any]:
    required = ["GOOGLE_ADS_CUSTOMER_ID", "GOOGLE_ADS_CREDENTIALS_FILE"]
    missing = [x for x in required if not os.environ.get(x)]
    library = True
    try:
        import google.ads.googleads  # type: ignore  # noqa: F401
    except Exception:
        library = False
    if not library:
        missing.append("python-package:google-ads")
    return {
        "channel_id": CHANNEL_ID,
        "state": "ready_read_only" if not missing else "credentials_required",
        "required": required + ["python-package:google-ads"],
        "missing": missing,
        "read_authority": "reporting",
        "write_authority": "blocked_by_dio_wave2",
    }


def sync(start_date: str, end_date: str, transport=None) -> list[dict[str, Any]]:
    status = readiness()
    if status["missing"]:
        raise RuntimeError("Google Ads adapter not ready: " + ", ".join(status["missing"]))
    from google.ads.googleads.client import GoogleAdsClient  # type: ignore
    client = GoogleAdsClient.load_from_storage(os.environ["GOOGLE_ADS_CREDENTIALS_FILE"])
    service = client.get_service("GoogleAdsService")
    customer_id = os.environ["GOOGLE_ADS_CUSTOMER_ID"].replace("-", "")
    query = f"""
        SELECT campaign.id, campaign.name,
               metrics.impressions, metrics.clicks, metrics.cost_micros,
               metrics.conversions, metrics.conversions_value
        FROM campaign
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
    """
    rows = service.search_stream(customer_id=customer_id, query=query)
    out = []
    for batch in rows:
        for row in batch.results:
            out.append({
                "channel_id": CHANNEL_ID,
                "external_campaign_id": str(row.campaign.id),
                "window_start": start_date,
                "window_end": end_date,
                "currency": os.environ.get("GOOGLE_ADS_ACCOUNT_CURRENCY", "ZAR"),
                "impressions": int(row.metrics.impressions or 0),
                "reach": 0,
                "clicks": int(row.metrics.clicks or 0),
                "conversions": float(row.metrics.conversions or 0),
                "spend_minor": max(0, round(int(row.metrics.cost_micros or 0) / 10000)),
                "conversion_value_minor": max(0, round(float(row.metrics.conversions_value or 0) * 100)),
                "source_mode": "api",
                "evidence_grade": "platform_api",
                "raw": {"campaign_name": row.campaign.name},
            })
    return out
