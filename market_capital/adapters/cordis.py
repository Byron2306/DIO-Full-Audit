from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .base import DiscoveryBatch, DiscoveryObservation, SourceAdapter
from ..http_client import HttpClient

SOURCE_ID = "SRC-CORDIS"
DEFAULT_URL = "https://cordis.europa.eu/open-data/export.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class CordisAdapter(SourceAdapter):
    def __init__(self, http: HttpClient | Any | None = None):
        self.http = http or HttpClient()

    def discover(self, plan_slice: dict[str, Any]) -> DiscoveryBatch:
        limit = max(1, int(plan_slice.get("limit") or 25))
        url = str(plan_slice.get("data_url") or DEFAULT_URL)
        payload = self.http.get_json(url, params={"q": str(plan_slice.get("query") or "")})
        rows = (payload or {}).get("projects") or []
        observed_at = _now()
        observations: list[DiscoveryObservation] = []
        for raw in rows[:limit]:
            project_id = str(raw.get("id") or "").strip()
            if not project_id:
                continue
            reference = str(raw.get("url") or f"https://cordis.europa.eu/project/id/{project_id}")
            normalized = {
                "award_id": project_id,
                "title": raw.get("title"),
                "acronym": raw.get("acronym"),
                "objective": raw.get("objective"),
                "programme": raw.get("programme"),
                "start_date": raw.get("startDate"),
                "end_date": raw.get("endDate"),
                "total_cost": raw.get("totalCost"),
                "ec_max_contribution": raw.get("ecMaxContribution"),
                "participants": raw.get("participants") or [],
                "truth_class": "HISTORICAL_AWARD_OBSERVATION",
                "future_funding_intent": "UNPROVED",
                "authority_created": False,
            }
            observations.append(DiscoveryObservation(SOURCE_ID, "RELATIONSHIP", project_id, reference, observed_at, normalized))
        return DiscoveryBatch(SOURCE_ID, tuple(observations), None, "READY")
