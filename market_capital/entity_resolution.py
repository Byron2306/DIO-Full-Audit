from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def _domain(value: Any) -> str:
    text = _text(value)
    for prefix in ("https://", "http://", "www."):
        text = text.removeprefix(prefix)
    return text.split("/", 1)[0].split(":", 1)[0]


def _shared_identifier(existing: Any, incoming: Any) -> bool:
    if not isinstance(existing, dict) or not isinstance(incoming, dict):
        return False
    for namespace, value in existing.items():
        if namespace in incoming and str(value or "").strip() and str(value).strip() == str(incoming[namespace]).strip():
            return True
    return False


@dataclass(frozen=True)
class ResolutionDecision:
    state: str
    matched_entity_id: str | None
    basis: str
    confidence: float
    authority_created: bool = False


def resolve_organisation(existing: dict[str, Any], incoming: dict[str, Any]) -> ResolutionDecision:
    entity_id = str(existing.get("organisation_id") or "").strip() or None

    if _shared_identifier(existing.get("source_ids"), incoming.get("source_ids")):
        return ResolutionDecision("MATCH", entity_id, "SOURCE_NATIVE_IDENTIFIER", 1.0)

    existing_domain = _domain(existing.get("canonical_domain"))
    incoming_domain = _domain(incoming.get("canonical_domain"))
    if existing_domain and incoming_domain and existing_domain == incoming_domain:
        return ResolutionDecision("MATCH", entity_id, "OFFICIAL_DOMAIN", 0.99)

    if _shared_identifier(existing.get("registry_ids"), incoming.get("registry_ids")):
        return ResolutionDecision("MATCH", entity_id, "PUBLIC_REGISTRY_IDENTIFIER", 0.99)

    existing_name = _text(existing.get("canonical_name"))
    incoming_name = _text(incoming.get("canonical_name"))
    existing_jurisdiction = _text(existing.get("jurisdiction"))
    incoming_jurisdiction = _text(incoming.get("jurisdiction"))
    if (
        existing_name
        and incoming_name
        and existing_name == incoming_name
        and existing_jurisdiction
        and incoming_jurisdiction
        and existing_jurisdiction == incoming_jurisdiction
    ):
        return ResolutionDecision("MATCH", entity_id, "NORMALIZED_NAME_JURISDICTION", 0.95)

    if existing_name and incoming_name:
        similarity = SequenceMatcher(None, existing_name, incoming_name).ratio()
        if similarity >= 0.65:
            return ResolutionDecision("NEEDS_REVIEW", None, "FUZZY_NAME_PROPOSAL_ONLY", round(similarity, 4))

    return ResolutionDecision("NO_MATCH", None, "INSUFFICIENT_IDENTITY_EVIDENCE", 0.0)
