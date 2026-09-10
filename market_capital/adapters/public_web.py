from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from .base import DiscoveryBatch, DiscoveryObservation, SourceAdapter

DEFAULT_SOURCE_ID = "SRC-FIRST-PARTY-PROGRAMME"
VALID_OPPORTUNITY_TYPES = {"INVESTOR", "GRANT", "DONOR", "SPONSOR", "PATRONAGE", "ACCELERATOR", "PRIZE"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _http_url(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return text
    return None


def normalize_public_page(page: dict[str, Any]) -> dict[str, Any]:
    url = _http_url(page.get("url"))
    if not url:
        raise ValueError("A public http/https source URL is required")
    facts = dict(page.get("facts") or {})
    policy_state = str(page.get("policy_state") or "READY").strip().upper()

    route: str | None = None
    route_state = "NO_PUBLIC_ROUTE"
    route_truth_class: str | None = None

    if policy_state == "POLICY_BLOCKED":
        route_state = "POLICY_BLOCKED"
    elif str(facts.get("route_freshness") or "").upper() == "STALE":
        route_state = "STALE_ROUTE"
    else:
        application_route = _http_url(facts.get("application_route"))
        public_contact_url = _http_url(facts.get("public_contact_url"))
        public_email = str(facts.get("public_email") or "").strip()
        if application_route:
            route = application_route
            route_state = "APPLICATION_ROUTE_VERIFIED"
            route_truth_class = "OBSERVED"
        elif public_contact_url:
            route = public_contact_url
            route_state = "PUBLIC_ROUTE_VERIFIED"
            route_truth_class = "OBSERVED"
        elif public_email and "@" in public_email and " " not in public_email:
            route = f"mailto:{public_email}"
            route_state = "PUBLIC_ROUTE_VERIFIED"
            route_truth_class = "OBSERVED"
        elif facts.get("route_requires_review"):
            route_state = "NEEDS_REVIEW"

    opportunity_type = str(facts.get("opportunity_type") or "").strip().upper()
    if opportunity_type and opportunity_type not in VALID_OPPORTUNITY_TYPES:
        opportunity_type = ""

    return {
        "source_url": url,
        "title": page.get("title"),
        "canonical_domain": urlparse(url).netloc.casefold(),
        "organisation_name": facts.get("organisation_name"),
        "person_name": facts.get("name"),
        "public_role": facts.get("role"),
        "opportunity_type": opportunity_type or None,
        "deadline": facts.get("deadline"),
        "amount": facts.get("amount"),
        "currency": facts.get("currency"),
        "themes": facts.get("themes") or [],
        "eligibility": facts.get("eligibility"),
        "public_contact_route": route,
        "route_state": route_state,
        "route_truth_class": route_truth_class,
        "truth_class": "PUBLIC_WEB_OBSERVATION",
        "contact_authority": False,
        "authority_created": False,
        "external_effects": False,
    }


class PublicWebAdapter(SourceAdapter):
    def discover(self, plan_slice: dict[str, Any]) -> DiscoveryBatch:
        source_id = str(plan_slice.get("source_id") or DEFAULT_SOURCE_ID).strip()
        pages = list(plan_slice.get("pages") or [])
        limit = max(0, int(plan_slice.get("limit") or len(pages)))
        observed_at = str(plan_slice.get("observed_at") or _now())
        observations: list[DiscoveryObservation] = []

        for index, page in enumerate(pages[:limit]):
            normalized = normalize_public_page(dict(page))
            facts = dict(page.get("facts") or {})
            if normalized.get("opportunity_type"):
                entity_type = "OPPORTUNITY"
                native_id = str(facts.get("opportunity_id") or normalized["source_url"])
            elif normalized.get("person_name") or normalized.get("public_role"):
                entity_type = "PERSON"
                native_id = str(facts.get("person_id") or normalized["source_url"])
            else:
                entity_type = "ORGANISATION"
                native_id = str(facts.get("organisation_id") or normalized["source_url"])
            observations.append(
                DiscoveryObservation(
                    source_id=source_id,
                    entity_type=entity_type,
                    source_record_id=native_id or f"public-page-{index}",
                    source_reference=normalized["source_url"],
                    observed_at=observed_at,
                    payload=normalized,
                    assertion_class="OBSERVED",
                )
            )
        return DiscoveryBatch(source_id, tuple(observations), None, "READY")
