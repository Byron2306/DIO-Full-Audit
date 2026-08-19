from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import (
    MarketSensoriumStore,
    TargetFeatures,
    canonical_json,
    clamp,
    digest_payload,
    recency_score,
    stable_id,
    utc_now,
)


RESOLVABLE_KINDS = {"PUBLIC_DOMAIN_SIGNAL", "MARKET_OPPORTUNITY"}
EXPLICIT_ORGANISATION_KEYS = (
    "organisation",
    "organization",
    "organisation_name",
    "organization_name",
    "company",
    "company_name",
    "institution",
    "institution_name",
    "employer",
    "employer_name",
    "agency",
    "agency_name",
    "buyer_organisation",
    "buyer_organization",
    "entity_name",
)

# Deliberately conservative. These are organisation-form markers, not arbitrary
# title-case spans. A headline hit remains a discovered target hypothesis, never
# a verified buyer unit, lead, consent state or demand claim.
ORG_MARKERS = (
    "University",
    "Foundation",
    "Group",
    "Holdings",
    "Council",
    "Board",
    "Trust",
    "Association",
    "Institute",
    "College",
    "School",
    "Authority",
    "Commission",
    "Society",
    "Federation",
    "Network",
    "Centre",
    "Center",
    "Bank",
    "Hospital",
    "Municipality",
    "Agency",
)

CAP_TOKEN = r"[A-Z][A-Za-z0-9&'’.-]*"
CONNECTOR_TOKEN = r"(?:of|the|and|for|South|Africa|African|National|Provincial|State|Global|International|North|West|East|Central|Cape)"
NAME_TOKEN = rf"(?:{CAP_TOKEN}|{CONNECTOR_TOKEN})"
PREFIX_PATTERNS = (
    re.compile(rf"\b((?:University|Department|Ministry|Council|Institute|College|School|Foundation|Trust|Authority|Commission|Board|Association|Federation|Society|Agency|Municipality|Hospital|Bank)\s+(?:of|for)\s+{NAME_TOKEN}(?:\s+{NAME_TOKEN}){{0,5}})\b"),
)
SUFFIX_PATTERN = re.compile(
    rf"\b(({NAME_TOKEN}(?:\s+{NAME_TOKEN}){{0,5}})\s+(?:{'|'.join(ORG_MARKERS)}))\b"
)


@dataclass(frozen=True)
class ResolvedIdentity:
    organisation: str
    evidence: str
    confidence: float
    source_ref: str


def _text(value: Any) -> str:
    return str(value or "").strip()


def _candidate_payload(row: Any) -> dict[str, Any]:
    try:
        return json.loads(row["payload_json"] or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}


def _record_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    record = payload.get("record")
    if isinstance(record, dict):
        return record
    return payload


def _first_explicit_organisation(record: dict[str, Any], payload: dict[str, Any]) -> str:
    for source in (record, payload):
        for key in EXPLICIT_ORGANISATION_KEYS:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                for nested_key in ("name", "title", "label"):
                    nested = value.get(nested_key)
                    if isinstance(nested, str) and nested.strip():
                        return nested.strip()
    return ""


def _publisher_names(record: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for key in ("publisher", "source", "channel_title", "channel", "author"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            names.add(_normalise_name(value))
        elif isinstance(value, dict):
            for nested_key in ("name", "title", "label"):
                nested = value.get(nested_key)
                if isinstance(nested, str) and nested.strip():
                    names.add(_normalise_name(nested))
    return {name for name in names if name}


def _normalise_name(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip(" \t\r\n-–—:;,.|")
    return cleaned


def _headline_clause(record: dict[str, Any], display_name: str) -> str:
    title = _text(record.get("title") or record.get("name") or display_name)
    # Google News commonly appends the publisher after a final " - ". Do not
    # accidentally promote the publisher simply because it appears in the title.
    if " - " in title:
        title = title.rsplit(" - ", 1)[0]
    return title.strip()


def _headline_organisation(record: dict[str, Any], display_name: str) -> str:
    headline = _headline_clause(record, display_name)
    if not headline:
        return ""
    candidates: list[str] = []
    for pattern in PREFIX_PATTERNS:
        candidates.extend(match.group(1) for match in pattern.finditer(headline))
    candidates.extend(match.group(1) for match in SUFFIX_PATTERN.finditer(headline))
    publishers = _publisher_names(record)
    cleaned: list[str] = []
    for candidate in candidates:
        name = _normalise_name(candidate)
        if not name or len(name) < 4:
            continue
        if _normalise_name(name) in publishers:
            continue
        cleaned.append(name)
    if not cleaned:
        return ""
    cleaned.sort(key=lambda value: (-len(value.split()), -len(value), value.lower()))
    return cleaned[0]


def resolve_identity(row: Any) -> ResolvedIdentity | None:
    """Resolve an organisation conservatively from source-bound public evidence.

    The resolver intentionally does not infer an organisation from a publisher or
    URL host alone. Explicit organisation metadata is strongest. A headline may be
    used only when it contains a recognisable organisation-form marker.
    """
    if _text(row["candidate_kind"]) not in RESOLVABLE_KINDS:
        return None
    payload = _candidate_payload(row)
    record = _record_from_payload(payload)
    explicit = _normalise_name(_first_explicit_organisation(record, payload))
    if explicit:
        return ResolvedIdentity(
            organisation=explicit,
            evidence="EXPLICIT_SOURCE_ORGANISATION_FIELD",
            confidence=0.86,
            source_ref=_text(row["source_ref"]),
        )
    score = clamp(float(row["score"] or 0.0))
    if score < 0.50:
        return None
    heuristic = _headline_organisation(record, _text(row["display_name"]))
    if heuristic:
        return ResolvedIdentity(
            organisation=heuristic,
            evidence="HEADLINE_ORGANISATION_FORM_MARKER",
            confidence=0.62,
            source_ref=_text(row["source_ref"]),
        )
    return None


def _route_quality(record: dict[str, Any]) -> float:
    for key in ("official_url", "organisation_url", "organization_url", "website", "homepage"):
        value = _text(record.get(key))
        if value.startswith("http://") or value.startswith("https://"):
            return 0.35
    return 0.08


def _mark_candidate_resolved(
    store: MarketSensoriumStore,
    row: Any,
    *,
    target_id: str,
    identity: ResolvedIdentity,
    buyer_unit_state: str,
) -> None:
    payload = _candidate_payload(row)
    payload["resolution"] = {
        "state": "RESOLVED_ORGANISATION_BUYER_UNIT_PENDING",
        "target_id": target_id,
        "organisation": identity.organisation,
        "evidence": identity.evidence,
        "identity_confidence": identity.confidence,
        "buyer_unit_state": buyer_unit_state,
        "resolved_at": utc_now(),
        "lead_created": False,
        "market_demand_claimed": False,
        "authority_created": False,
    }
    payload["target_created"] = True
    store.connection.execute(
        """
        UPDATE discovery_candidates
        SET state='RESOLVED_ORGANISATION', payload_json=?, provenance_digest=?
        WHERE candidate_id=?
        """,
        (canonical_json(payload), digest_payload(payload), row["candidate_id"]),
    )


def resolve_discovery_candidates(
    store: MarketSensoriumStore,
    *,
    limit: int = 500,
) -> tuple[list[TargetFeatures], dict[str, Any]]:
    """Resolve strong public discoveries into rankable organisation hypotheses.

    Promotion here means only "rankable discovered target hypothesis". It does not
    mean lead, buyer-unit verification, contact permission, demand or authority.
    """
    rows = store.connection.execute(
        """
        SELECT * FROM discovery_candidates
        WHERE state='UNRESOLVED_ENTITY'
        ORDER BY score DESC, last_seen_at DESC, candidate_id
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()

    groups: dict[tuple[str, str], list[tuple[Any, ResolvedIdentity]]] = defaultdict(list)
    unresolved = 0
    evidence_counts: Counter[str] = Counter()
    for row in rows:
        identity = resolve_identity(row)
        if identity is None:
            unresolved += 1
            continue
        domain_id = _text(row["domain_id"])
        if not domain_id:
            unresolved += 1
            continue
        key = (domain_id, identity.organisation.casefold())
        groups[key].append((row, identity))
        evidence_counts[identity.evidence] += 1

    features: list[TargetFeatures] = []
    targets_created = 0
    targets_refreshed = 0
    candidates_resolved = 0
    for (domain_id, _), resolved_rows in sorted(groups.items(), key=lambda item: item[0]):
        identities = [identity for _, identity in resolved_rows]
        organisation = max((identity.organisation for identity in identities), key=len)
        target_id = stable_id("DISC-TGT", domain_id, organisation.casefold())
        existing = store.connection.execute(
            "SELECT target_id FROM target_memory WHERE target_id=?", (target_id,)
        ).fetchone()
        if existing is None:
            targets_created += 1
        else:
            targets_refreshed += 1

        scores = [clamp(float(row["score"] or 0.0)) for row, _ in resolved_rows]
        max_score = max(scores) if scores else 0.0
        latest_seen = max(_text(row["last_seen_at"]) for row, _ in resolved_rows)
        evidence_confidence = max(identity.confidence for identity in identities)
        records = [_record_from_payload(_candidate_payload(row)) for row, _ in resolved_rows]
        route_quality = max((_route_quality(record) for record in records), default=0.08)
        repeat_signal = min(5, len(resolved_rows))
        problem_strength = clamp(max_score + max(0, repeat_signal - 1) * 0.03)
        momentum = clamp(0.25 + repeat_signal * 0.11)
        domain_fit = clamp(max(0.55, max_score))
        morphology_fit = clamp(max(0.52, max_score * 0.96))
        buyer_unit_state = "UNRESOLVED_BUYER_UNIT"

        store.upsert_target(
            target_id=target_id,
            organisation=organisation,
            domain_id=domain_id,
            seen_at=latest_seen or None,
            metadata={
                "source": "market_sensorium_discovery_resolution",
                "target_state": "DISCOVERED_ORGANISATION_BUYER_UNIT_PENDING",
                "buyer_unit_state": buyer_unit_state,
                "discovery_candidate_ids": [row["candidate_id"] for row, _ in resolved_rows],
                "resolution_evidence": sorted({identity.evidence for identity in identities}),
                "resolution_identity_confidence": evidence_confidence,
                "source_observation_count": len(resolved_rows),
                "lead_created": False,
                "market_demand_claimed": False,
                "authority_created": False,
            },
        )
        for row, identity in resolved_rows:
            _mark_candidate_resolved(
                store,
                row,
                target_id=target_id,
                identity=identity,
                buyer_unit_state=buyer_unit_state,
            )
            candidates_resolved += 1
        store.append_observation(
            source_kind="DISCOVERY_ENTITY_RESOLUTION",
            source_ref="market_sensorium/resolution.py",
            entity_kind="TARGET_HYPOTHESIS",
            entity_id=target_id,
            domain_id=domain_id,
            morphology=_text(resolved_rows[0][0]["morphology"]),
            observed_at=latest_seen or None,
            payload={
                "organisation": organisation,
                "candidate_ids": [row["candidate_id"] for row, _ in resolved_rows],
                "identity_evidence": sorted({identity.evidence for identity in identities}),
                "identity_confidence": evidence_confidence,
                "buyer_unit_state": buyer_unit_state,
                "target_truth_class": "RANKABLE_DISCOVERED_TARGET_HYPOTHESIS",
                "lead_created": False,
                "market_demand_claimed": False,
                "authority_created": False,
                "external_effects": False,
            },
        )
        features.append(
            TargetFeatures(
                target_id=target_id,
                organisation=organisation,
                domain_id=domain_id,
                domain_fit=domain_fit,
                morphology_fit=morphology_fit,
                capability_fit=0.56,
                buyer_role_confidence=clamp(evidence_confidence - 0.10),
                problem_signal_strength=problem_strength,
                signal_recency=recency_score(latest_seen, 30),
                organisation_fit=0.72,
                route_quality=route_quality,
                market_momentum=momentum,
                prior_engagement=0.0,
                competitive_whitespace=0.34,
                seed_prior=0.0,
                authority_penalty=0.08,
                stale_signal_penalty=max(0.0, 0.10 - recency_score(latest_seen, 120) * 0.10),
            )
        )

    store.connection.commit()
    unresolved_remaining = store.connection.execute(
        "SELECT COUNT(*) FROM discovery_candidates WHERE state='UNRESOLVED_ENTITY'"
    ).fetchone()[0]
    return features, {
        "candidates_examined": len(rows),
        "candidates_resolved": candidates_resolved,
        "unique_resolved_target_hypotheses": len(features),
        "targets_created": targets_created,
        "targets_refreshed": targets_refreshed,
        "unresolved_in_examined_batch": unresolved,
        "unresolved_remaining": unresolved_remaining,
        "resolution_evidence_counts": dict(sorted(evidence_counts.items())),
        "buyer_units_verified": 0,
        "leads_created": 0,
        "market_demand_claimed": False,
        "authority_created": False,
        "external_effects": False,
    }
