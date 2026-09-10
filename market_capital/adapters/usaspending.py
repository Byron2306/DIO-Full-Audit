from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .base import DiscoveryBatch, DiscoveryObservation, SourceAdapter
from ..http_client import HttpClient

SOURCE_ID = "SRC-USASPENDING"
SEARCH_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class USASpendingAdapter(SourceAdapter):
    def __init__(self, http: HttpClient | Any | None = None):
        self.http = http or HttpClient()

    def discover(self, plan_slice: dict[str, Any]) -> DiscoveryBatch:
        limit = max(1, int(plan_slice.get("limit") or 25))
        body = {
            "filters": {"keywords": [str(plan_slice.get("query") or "").strip()]},
            "fields": ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency", "Start Date", "End Date", "Description"],
            "limit": limit,
            "page": int(plan_slice.get("page") or 1),
        }
        payload = self.http.post_json(str(plan_slice.get("data_url") or SEARCH_URL), json_body=body)
        observed_at = _now()
        observations: list[DiscoveryObservation] = []
        for raw in ((payload or {}).get("results") or [])[:limit]:
            award_id = str(raw.get("Award ID") or "").strip()
            if not award_id:
                continue
            reference = f"https://www.usaspending.gov/award/{award_id}"
            normalized = {
                "award_id": award_id,
                "recipient_name": raw.get("Recipient Name"),
                "amount": raw.get("Award Amount"),
                "awarding_agency": raw.get("Awarding Agency"),
                "start_date": raw.get("Start Date"),
                "end_date": raw.get("End Date"),
                "description": raw.get("Description"),
                "truth_class": "HISTORICAL_AWARD_OBSERVATION",
                "future_funding_intent": "UNPROVED",
                "authority_created": False,
            }
            observations.append(DiscoveryObservation(SOURCE_ID, "RELATIONSHIP", award_id, reference, observed_at, normalized))
        meta = (payload or {}).get("page_metadata") or {}
        next_cursor = str(int(meta.get("page") or 1) + 1) if meta.get("hasNext") else None
        return DiscoveryBatch(SOURCE_ID, tuple(observations), next_cursor, "READY")
