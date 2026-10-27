from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .base import DiscoveryBatch, DiscoveryObservation, SourceAdapter
from ..http_client import HttpClient

SOURCE_ID = "SRC-GRANTS-GOV"
SEARCH_URL = "https://api.grants.gov/v1/api/search2"
DETAIL_BASE = "https://www.grants.gov/search-results-detail/"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class GrantsGovAdapter(SourceAdapter):
    def __init__(self, http: HttpClient | Any | None = None):
        self.http = http or HttpClient()

    def discover(self, plan_slice: dict[str, Any]) -> DiscoveryBatch:
        limit = max(1, int(plan_slice.get("limit") or 25))
        query = str(plan_slice.get("query") or "").strip()
        body = {"keyword": query, "rows": limit, "startRecordNum": 0}
        payload = self.http.post_json(SEARCH_URL, json_body=body)
        hits = ((payload or {}).get("data") or {}).get("oppHits") or []
        observed_at = _now()
        observations: list[DiscoveryObservation] = []
        for raw in hits[:limit]:
            record_id = str(raw.get("id") or raw.get("number") or "").strip()
            if not record_id:
                continue
            source_reference = f"{DETAIL_BASE}{record_id}"
            normalized = {
                "opportunity_id": record_id,
                "opportunity_type": "GRANT",
                "title": raw.get("title"),
                "number": raw.get("number"),
                "agency_code": raw.get("agencyCode"),
                "agency_name": raw.get("agencyName"),
                "open_date": raw.get("openDate"),
                "close_date": raw.get("closeDate"),
                "status": raw.get("oppStatus"),
                "document_type": raw.get("docType"),
                "assistance_listing_numbers": raw.get("alnist") or [],
                "truth_class": "LIVE_OPPORTUNITY_OBSERVATION",
                "funding_outcome": "UNPROVED",
                "authority_created": False,
            }
            observations.append(DiscoveryObservation(SOURCE_ID, "OPPORTUNITY", record_id, source_reference, observed_at, normalized))
        return DiscoveryBatch(SOURCE_ID, tuple(observations), None, "READY")
