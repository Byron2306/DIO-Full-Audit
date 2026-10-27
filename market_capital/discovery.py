from __future__ import annotations

from pathlib import Path
from typing import Any

from .registry import upsert_organisation, upsert_opportunity, upsert_person

REQUIRED_ADAPTER_FIELDS = {"source_type", "permitted_discovery_mode", "source_url", "last_seen"}


def normalise_source_adapter(adapter: dict[str, Any]) -> dict[str, Any]:
    data = {key: adapter.get(key) for key in REQUIRED_ADAPTER_FIELDS}
    missing = [key for key, value in data.items() if not str(value or "").strip()]
    if missing:
        raise ValueError(f"source adapter missing required fields: {', '.join(sorted(missing))}")
    data = {key: str(value).strip() for key, value in data.items()}
    data["authority_created"] = False
    data["external_effects"] = False
    return data


def _observed_source_patch(adapter: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_urls": [adapter["source_url"]],
        "source_last_seen": adapter["last_seen"],
        "source_type": adapter["source_type"],
        "discovery_mode": adapter["permitted_discovery_mode"],
    }


def ingest_public_observation(state_root: Path, observation: dict[str, Any]) -> dict[str, Any]:
    adapter = normalise_source_adapter(dict(observation.get("adapter") or {}))
    source_patch = _observed_source_patch(adapter)

    organisation_payload = dict(observation.get("organisation") or {})
    if not organisation_payload:
        raise ValueError("public observation must include an organisation")
    organisation_payload.update(source_patch)
    organisation_payload.setdefault("truth_class", "PUBLIC_SOURCE_OBSERVATION")
    organisation = upsert_organisation(state_root, organisation_payload)

    person = None
    person_payload = dict(observation.get("person") or {})
    if person_payload:
        if not str(person_payload.get("name") or "").strip():
            raise ValueError("public person candidate requires an observed name")
        person_payload.update(source_patch)
        person_payload.setdefault("organisation_id", organisation["organisation_id"])
        person_payload["truth_class"] = "IDENTITY_RESOLUTION_CANDIDATE"
        # Discovery may preserve an explicitly observed public route, but it does not invent one.
        person = upsert_person(state_root, person_payload)

    opportunity_payload = dict(observation.get("opportunity") or {})
    if not opportunity_payload:
        raise ValueError("public observation must include an opportunity")
    opportunity_payload.update(source_patch)
    opportunity_payload.setdefault("organisation_id", organisation["organisation_id"])
    if person:
        opportunity_payload.setdefault("person_id", person["person_id"])
    opportunity_payload["truth_class"] = "PUBLIC_SOURCE_OBSERVATION"
    opportunity = upsert_opportunity(state_root, opportunity_payload)

    return {
        "schema": "dio.market_capital.discovery_ingest.v1",
        "adapter": adapter,
        "organisation": organisation,
        "person": person,
        "opportunity": opportunity,
        "authority_created": False,
        "external_effects": False,
    }


def dedupe_observation_candidates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for record in records:
        opportunity = dict(record.get("opportunity") or {})
        adapter = dict(record.get("adapter") or {})
        key = (
            str(opportunity.get("opportunity_id") or opportunity.get("title") or "").strip().casefold(),
            str((record.get("organisation") or {}).get("name") or "").strip().casefold(),
            str(adapter.get("source_url") or "").strip().casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(record)
    return out
