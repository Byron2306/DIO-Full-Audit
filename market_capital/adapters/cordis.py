from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from .base import DiscoveryBatch, DiscoveryObservation, SourceAdapter
from ..http_client import HttpClient

SOURCE_ID = "SRC-CORDIS"
SPARQL_URL = "https://cordis.europa.eu/datalab/sparql"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:20].upper()
    return f"{prefix}-{digest}"


def _binding_value(binding: dict[str, Any], name: str) -> str | None:
    value = (binding.get(name) or {}).get("value")
    text = str(value or "").strip()
    return text or None


def _sparql_query(search_text: str, limit: int) -> str:
    # Query the public EURIO graph. Search text is optional because Atlas
    # source allocations are currently source-class bounded rather than
    # per-source keyword payloads.
    safe = str(search_text or "").replace("\\", "\\\\").replace('"', '\\"').strip()
    title_filter = (
        f'FILTER(CONTAINS(LCASE(STR(?title)), LCASE("{safe}")))'
        if safe
        else ""
    )
    return f"""PREFIX eurio: <http://data.europa.eu/s66#>
SELECT ?id ?title ?start ?end ?organisation_name
WHERE {{
  ?project a eurio:Project ;
           eurio:identifier ?id ;
           eurio:title ?title .
  OPTIONAL {{ ?project eurio:startDate ?start . }}
  OPTIONAL {{ ?project eurio:endDate ?end . }}
  OPTIONAL {{
    ?project eurio:hasInvolvedParty ?participant .
    ?participant eurio:isRoleOf ?organisation .
    ?organisation eurio:legalName ?organisation_name .
  }}
  {title_filter}
}}
ORDER BY DESC(?start)
LIMIT {max(1, int(limit))}
"""


def _legacy_projects(
    payload: dict[str, Any] | None,
    *,
    observed_at: str,
    limit: int,
) -> list[DiscoveryObservation]:
    observations: list[DiscoveryObservation] = []
    for raw in ((payload or {}).get("projects") or [])[:limit]:
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
            "left_id": "CORDIS-EU-FRAMEWORK",
            "right_id": f"CORDIS-PROJECT-{project_id}",
            "relationship_type": "HISTORICAL_FUNDED_PROJECT",
            "truth_class": "HISTORICAL_AWARD_OBSERVATION",
            "future_funding_intent": "UNPROVED",
            "authority_created": False,
            "external_effects": False,
        }
        observations.append(
            DiscoveryObservation(
                SOURCE_ID,
                "RELATIONSHIP",
                project_id,
                reference,
                observed_at,
                normalized,
            )
        )
    return observations


class CordisAdapter(SourceAdapter):
    """Read historical EU-funded project evidence from public CORDIS data."""

    def __init__(self, http: HttpClient | Any | None = None):
        self.http = http or HttpClient()

    def discover(self, plan_slice: dict[str, Any]) -> DiscoveryBatch:
        limit = max(1, int(plan_slice.get("limit") or 25))
        observed_at = _now()
        explicit_url = str(plan_slice.get("data_url") or "").strip()

        # Explicit data_url is retained for controlled imports/tests and older
        # CORDIS JSON exports. Production defaults to the public EURIO SPARQL
        # endpoint rather than the credentialed Data Extraction API.
        if explicit_url:
            payload = self.http.get_json(
                explicit_url,
                params={"q": str(plan_slice.get("query") or "")},
            )
            return DiscoveryBatch(
                SOURCE_ID,
                tuple(_legacy_projects(payload, observed_at=observed_at, limit=limit)),
                None,
                "READY",
            )

        query = _sparql_query(str(plan_slice.get("query") or ""), limit)
        payload = self.http.get_json(
            SPARQL_URL,
            params={"query": query, "format": "application/sparql-results+json"},
            headers={"Accept": "application/sparql-results+json"},
        )

        observations: list[DiscoveryObservation] = []
        for binding in (((payload or {}).get("results") or {}).get("bindings") or [])[:limit]:
            project_id = _binding_value(binding, "id")
            title = _binding_value(binding, "title")
            if not project_id or not title:
                continue
            organisation_name = _binding_value(binding, "organisation_name")
            right_id = (
                _stable("ORG-CORDIS", organisation_name.casefold())
                if organisation_name
                else f"CORDIS-PROJECT-{project_id}"
            )
            normalized = {
                "award_id": project_id,
                "title": title,
                "start_date": _binding_value(binding, "start"),
                "end_date": _binding_value(binding, "end"),
                "recipient_name": organisation_name,
                "left_id": "CORDIS-EU-FRAMEWORK",
                "right_id": right_id,
                "relationship_type": (
                    "HISTORICAL_FUNDED_PARTICIPATION"
                    if organisation_name
                    else "HISTORICAL_FUNDED_PROJECT"
                ),
                "truth_class": "HISTORICAL_AWARD_OBSERVATION",
                "future_funding_intent": "UNPROVED",
                "authority_created": False,
                "external_effects": False,
            }
            observations.append(
                DiscoveryObservation(
                    SOURCE_ID,
                    "RELATIONSHIP",
                    f"{project_id}:{right_id}",
                    f"https://cordis.europa.eu/project/id/{project_id}",
                    observed_at,
                    normalized,
                )
            )

        return DiscoveryBatch(SOURCE_ID, tuple(observations), None, "READY")
