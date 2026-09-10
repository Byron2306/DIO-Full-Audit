from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .base import DiscoveryBatch, DiscoveryObservation, SourceAdapter
from ..http_client import HttpClient

SOURCE_ID = "SRC-360GIVING"
DEFAULT_URL = "https://api.threesixtygiving.org/api/v1/grant/"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class Giving360Adapter(SourceAdapter):
    def __init__(self, http: HttpClient | Any | None = None):
        self.http = http or HttpClient()

    def discover(self, plan_slice: dict[str, Any]) -> DiscoveryBatch:
        limit = max(1, int(plan_slice.get("limit") or 25))
        params = {
            "org_id": str(plan_slice.get("org_id") or ""),
            "direction": str(plan_slice.get("direction") or "made"),
            "limit": limit,
        }
        payload = self.http.get_json(str(plan_slice.get("data_url") or DEFAULT_URL), params=params)
        observed_at = _now()
        observations: list[DiscoveryObservation] = []
        for wrapper in ((payload or {}).get("results") or [])[:limit]:
            raw = wrapper.get("data") or {}
            grant_id = str(raw.get("identifier") or "").strip()
            if not grant_id:
                continue
            funders = raw.get("fundingOrganization") or []
            recipients = raw.get("recipientOrganization") or []
            reference = str(wrapper.get("self") or DEFAULT_URL)
            normalized = {
                "award_id": grant_id,
                "title": raw.get("title"),
                "description": raw.get("description"),
                "currency": raw.get("currency"),
                "amount": raw.get("amountAwarded"),
                "award_date": raw.get("awardDate"),
                "funder_id": (funders[0] or {}).get("id") if funders else None,
                "funder_name": (funders[0] or {}).get("name") if funders else None,
                "recipient_id": (recipients[0] or {}).get("id") if recipients else None,
                "recipient_name": (recipients[0] or {}).get("name") if recipients else None,
                "truth_class": "HISTORICAL_AWARD_OBSERVATION",
                "future_funding_intent": "UNPROVED",
                "authority_created": False,
            }
            observations.append(DiscoveryObservation(SOURCE_ID, "RELATIONSHIP", grant_id, reference, observed_at, normalized))
        next_cursor = (payload or {}).get("next")
        return DiscoveryBatch(SOURCE_ID, tuple(observations), str(next_cursor) if next_cursor else None, "READY")
