from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .base import DiscoveryBatch, DiscoveryObservation, SourceAdapter
from ..http_client import HttpClient

SOURCE_ID = "SRC-PROPUBLICA-NONPROFITS"
SEARCH_URL = "https://projects.propublica.org/nonprofits/api/v2/search.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ProPublicaNonprofitsAdapter(SourceAdapter):
    def __init__(self, http: HttpClient | Any | None = None):
        self.http = http or HttpClient()

    def discover(self, plan_slice: dict[str, Any]) -> DiscoveryBatch:
        limit = max(1, int(plan_slice.get("limit") or 25))
        payload = self.http.get_json(
            str(plan_slice.get("data_url") or SEARCH_URL),
            params={"q": str(plan_slice.get("query") or "").strip()},
        )
        observed_at = _now()
        observations: list[DiscoveryObservation] = []
        for raw in ((payload or {}).get("organizations") or [])[:limit]:
            ein = str(raw.get("ein") or "").strip()
            name = str(raw.get("name") or "").strip()
            if not ein or not name:
                continue
            reference = f"https://projects.propublica.org/nonprofits/organizations/{ein}"
            normalized = {
                "organisation_id": f"ein:{ein}",
                "canonical_name": name,
                "ein": ein,
                "formatted_ein": raw.get("strein"),
                "city": raw.get("city"),
                "state": raw.get("state"),
                "ntee_code": raw.get("ntee_code"),
                "subsection_code": raw.get("subseccd"),
                "truth_class": "NONPROFIT_IDENTITY_OBSERVATION",
                "donor_status": "UNPROVED",
                "funding_intent": "UNPROVED",
                "authority_created": False,
            }
            observations.append(DiscoveryObservation(SOURCE_ID, "ORGANISATION", ein, reference, observed_at, normalized))
        current = int((payload or {}).get("cur_page") or 0)
        pages = int((payload or {}).get("num_pages") or 0)
        next_cursor = str(current + 1) if current + 1 < pages else None
        return DiscoveryBatch(SOURCE_ID, tuple(observations), next_cursor, "READY")
