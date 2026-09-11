from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from .base import DiscoveryBatch, DiscoveryObservation, SourceAdapter
from ..http_client import HttpClient

SOURCE_ID = "SRC-360GIVING"
ORG_LIST_URL = "https://api.threesixtygiving.org/api/v1/org/"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _grant_observations(
    payload: dict[str, Any] | None,
    *,
    observed_at: str,
    limit: int,
) -> list[DiscoveryObservation]:
    observations: list[DiscoveryObservation] = []
    for wrapper in ((payload or {}).get("results") or [])[:limit]:
        raw = wrapper.get("data") or {}
        grant_id = str(raw.get("identifier") or "").strip()
        if not grant_id:
            continue
        funders = raw.get("fundingOrganization") or []
        recipients = raw.get("recipientOrganization") or []
        reference = str(wrapper.get("self") or ORG_LIST_URL)
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
            "relationship_type": "HISTORICAL_AWARD",
            "truth_class": "HISTORICAL_AWARD_OBSERVATION",
            "future_funding_intent": "UNPROVED",
            "authority_created": False,
            "external_effects": False,
        }
        observations.append(
            DiscoveryObservation(
                SOURCE_ID,
                "RELATIONSHIP",
                grant_id,
                reference,
                observed_at,
                normalized,
            )
        )
    return observations


class Giving360Adapter(SourceAdapter):
    """Read 360Giving funder/grant data without inferring future intent.

    360Giving exposes grants beneath organisation-specific routes. In global
    mode DIO first enumerates public organisations that are known funders, then
    follows their explicit grants_made URLs within the supplied observation
    budget.
    """

    def __init__(self, http: HttpClient | Any | None = None):
        self.http = http or HttpClient()

    def discover(self, plan_slice: dict[str, Any]) -> DiscoveryBatch:
        limit = max(1, int(plan_slice.get("limit") or 25))
        observed_at = _now()
        org_id = str(plan_slice.get("org_id") or "").strip()
        direction = str(plan_slice.get("direction") or "made").strip().lower()
        explicit_url = str(plan_slice.get("data_url") or "").strip()

        if explicit_url:
            payload = self.http.get_json(explicit_url, params={"limit": limit})
            observations = _grant_observations(payload, observed_at=observed_at, limit=limit)
            next_cursor = (payload or {}).get("next")
            return DiscoveryBatch(
                SOURCE_ID,
                tuple(observations),
                str(next_cursor) if next_cursor else None,
                "READY",
            )

        if org_id:
            route = "grants_received" if direction == "received" else "grants_made"
            url = f"{ORG_LIST_URL}{quote(org_id, safe='')}/{route}/"
            payload = self.http.get_json(url, params={"limit": limit})
            observations = _grant_observations(payload, observed_at=observed_at, limit=limit)
            next_cursor = (payload or {}).get("next")
            return DiscoveryBatch(
                SOURCE_ID,
                tuple(observations),
                str(next_cursor) if next_cursor else None,
                "READY",
            )

        # Global census mode: enumerate known funders, then follow only the
        # explicit grants_made routes returned by 360Giving.
        funder_probe_limit = min(100, max(10, limit))
        organisations = self.http.get_json(
            ORG_LIST_URL,
            params={"limit": funder_probe_limit},
        )
        funders = [
            row
            for row in ((organisations or {}).get("results") or [])
            if row.get("funder")
        ]

        observations: list[DiscoveryObservation] = []
        max_funders = min(5, len(funders))
        for funder in funders[:max_funders]:
            if len(observations) >= limit:
                break
            funder_id = str(funder.get("org_id") or "").strip()
            grants_url = str(funder.get("grants_made") or "").strip()
            if not grants_url and funder_id:
                grants_url = f"{ORG_LIST_URL}{quote(funder_id, safe='')}/grants_made/"
            if not grants_url:
                continue

            remaining = limit - len(observations)
            per_funder = max(1, min(remaining, max(1, limit // max(1, max_funders))))
            grants = self.http.get_json(grants_url, params={"limit": per_funder})
            observations.extend(
                _grant_observations(
                    grants,
                    observed_at=observed_at,
                    limit=remaining,
                )
            )

        # If the sampled funders have no grant rows, preserve only observed
        # funder identities rather than inventing award relationships.
        if not observations:
            for funder in funders[:limit]:
                funder_id = str(funder.get("org_id") or "").strip()
                name = str(funder.get("name") or "").strip()
                if not funder_id or not name:
                    continue
                observations.append(
                    DiscoveryObservation(
                        SOURCE_ID,
                        "ORGANISATION",
                        funder_id,
                        str(funder.get("self") or ORG_LIST_URL),
                        observed_at,
                        {
                            "organisation_id": funder_id,
                            "canonical_name": name,
                            "funder_status": "OBSERVED_IN_360GIVING",
                            "funding_intent": "UNPROVED",
                            "truth_class": "OPEN_FUNDER_IDENTITY",
                            "authority_created": False,
                            "external_effects": False,
                        },
                    )
                )

        return DiscoveryBatch(SOURCE_ID, tuple(observations[:limit]), None, "READY")
