from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .base import DiscoveryBatch, DiscoveryObservation, SourceAdapter
from ..http_client import HttpClient

SOURCE_ID = "SRC-CROSSREF-FUNDERS"
DEFAULT_URL = "https://api.crossref.org/funders"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class CrossrefFundersAdapter(SourceAdapter):
    def __init__(self, http: HttpClient | Any | None = None):
        self.http = http or HttpClient()

    def discover(self, plan_slice: dict[str, Any]) -> DiscoveryBatch:
        limit = max(1, int(plan_slice.get("limit") or 25))
        payload = self.http.get_json(
            str(plan_slice.get("data_url") or DEFAULT_URL),
            params={"query": str(plan_slice.get("query") or ""), "rows": limit},
        )
        items = ((payload or {}).get("message") or {}).get("items") or []
        observed_at = _now()
        observations: list[DiscoveryObservation] = []
        for raw in items[:limit]:
            funder_id = str(raw.get("id") or "").strip()
            name = str(raw.get("name") or "").strip()
            if not funder_id or not name:
                continue
            reference = str(raw.get("uri") or f"https://api.crossref.org/funders/{funder_id}")
            normalized = {
                "organisation_id": f"crossref-funder:{funder_id}",
                "canonical_name": name,
                "funder_id": funder_id,
                "location": raw.get("location"),
                "alternate_names": raw.get("alt-names") or [],
                "replaces": raw.get("replaces") or [],
                "replaced_by": raw.get("replaced-by") or [],
                "truth_class": "FUNDER_IDENTITY_OBSERVATION",
                "funding_intent": "UNPROVED",
                "authority_created": False,
            }
            observations.append(DiscoveryObservation(SOURCE_ID, "ORGANISATION", funder_id, reference, observed_at, normalized))
        return DiscoveryBatch(SOURCE_ID, tuple(observations), None, "READY")
