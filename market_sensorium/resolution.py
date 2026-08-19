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

# These are organisation-form markers, not arbitrary title-case spans.
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
    "Parliament",
)

# Acronyms can be strong subject-identity evidence even when the market relevance
# score is low. Generic/domain acronyms must not become organisation identities.
GENERIC_ACRONYMS = {
    "AI",
    "APA",
    "B2B",
    "B2C",
    "CAPS",
    "DIY",
    "ESL",
    "FAQ",
    "FET",
    "HR",
    "ICT",
    "NGO",
    "NGOS",
    "NST",
    "NSTECH",
    "PBL",
    "PDF",
    "PIP",
    "RSA",
    "SA",
    "SDG",
    "SDGS",
    "SEO",
    "SME",
    "SMME",
    "STEM",
    "TVET",
    "UK",
    "UN",
    "US",
    "USA",
    "ZA",
}

CAP_TOKEN = r"[A-Z][A-Za-z0-9&'’.-]*"
CONNECTOR_TOKEN = (
    r"(?:of|the|and|for|South|Africa|African|National|Provincial|State|"
    r"Global|International|North|West|East|Central|Cape)"
)
NAME_TOKEN = rf"(?:{CAP_TOKEN}|{CONNECTOR_TOKEN})"
PREFIX_PATTERNS = (
    re.compile(
        rf"\b((?:University|Department|Ministry|Council|Institute|College|School|"
        rf"Foundation|Trust|Authority|Commission|Board|Association|Federation|"
        rf"Society|Agency|Municipality|Hospital|Bank|Parliament)\s+(?:of|for)\s+"
        rf"{NAME_TOKEN}(?:\s+{NAME_TOKEN}){{0,5}})\b"
    ),
)
SUFFIX_PATTERN = re.compile(
    rf"\b(({NAME_TOKEN}(?:\s+{NAME_TOKEN}){{0,5}})\s+(?:{'|'.join(ORG_MARKERS)}))\b"
)
ACRONYM_PATTERN = re.compile(r"\b[A-Z][A-Z0-9&.-]{2,14}\b")


@dataclass(frozen=True)
class ResolvedIdentity:
    organisation: str
    evidence: str
    confidence: float
    source_ref: str
    entity_role: str = "SUBJECT_ORGANISATION"
    target_eligible: bool = True
    source_link: str = ""


@dataclass(frozen=True)
class SourceEntity:
    name: str
    entity_role: str
    evidence: str
    source_ref: str
    source_link: str = ""


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


def _normalise_name(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" \t\r\n-–—:;,.|")


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


def _publisher_suffix(title: str) -> str:
    value = _text(title)
    if " - " not in value:
        return ""
    return _normalise_name(value.rsplit(" - ", 1)[1])


def _organisation_acronym(value: str) -> str:
    tokens = re.findall(r"[A-Za-z]+", value)
    if not tokens:
        return ""
    initials = "".join(
        token[0].upper()
        for token in tokens
        if token.lower() not in {"of", "the", "and", "for", "in", "on", "to", "a", "an"}
    )
    return initials if 2 <= len(initials) <= 14 else ""


def _publisher_aliases(title: str, record: dict[str, Any]) -> set[str]:
    aliases: set[str] = set()
    suffix = _publisher_suffix(title)
    if suffix:
        aliases.add(suffix.casefold())
        suffix_acronym = _organisation_acronym(suffix)
        if suffix_acronym:
            aliases.add(suffix_acronym.casefold())
    for key in ("publisher", "source", "channel_title", "channel", "author", "feed_title"):
        value = record.get(key)
        names: list[str] = []
        if isinstance(value, str) and value.strip():
            names.append(value)
        elif isinstance(value, dict):
            for nested_key in ("name", "title", "label"):
                nested = value.get(nested_key)
                if isinstance(nested, str) and nested.strip():
                    names.append(nested)
        for name in names:
            normal = _normalise_name(name)
            if normal:
                aliases.add(normal.casefold())
                alias_acronym = _organisation_acronym(normal)
                if alias_acronym:
                    aliases.add(alias_acronym.casefold())
    return aliases


def _headline_clause(record: dict[str, Any], display_name: str) -> str:
    title = _text(record.get("title") or record.get("name") or display_name)
    # Google News and many public-search surfaces append the publisher after a
    # final " - ". That suffix is source identity, not automatically buyer identity.
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
    publisher_aliases = _publisher_aliases(_text(record.get("title") or display_name), record)
    cleaned: list[str] = []
    for candidate in candidates:
        name = _normalise_name(candidate)
        if not name or len(name) < 4:
            continue
        if name.casefold() in publisher_aliases:
            continue
        cleaned.append(name)
    if not cleaned:
        return ""
    cleaned.sort(key=lambda value: (-len(value.split()), -len(value), value.lower()))
    return cleaned[0]


def _headline_subject_acronym(record: dict[str, Any], display_name: str) -> str:
    """Extract a plausible subject-organisation acronym without using relevance.

    This intentionally ignores the candidate market score. Identity evidence and
    commercial relevance are separate truth dimensions.
    """
    raw_title = _text(record.get("title") or display_name)
    headline = _headline_clause(record, display_name)
    if not headline:
        return ""
    publisher_aliases = _publisher_aliases(raw_title, record)
    candidates: list[tuple[int, int, str]] = []
    for match in ACRONYM_PATTERN.finditer(headline):
        token = match.group(0).strip(".")
        if token in GENERIC_ACRONYMS:
            continue
        if token.casefold() in publisher_aliases:
            continue
        # Ignore acronym-looking URL/domain fragments.
        if "." in token and not token.endswith("."):
            continue
        position = match.start()
        # Leading/early subject acronyms are stronger than incidental later tokens.
        priority = (3 if position == 0 else 0) + (1 if position < 32 else 0)
        candidates.append((priority, position, token))
    if not candidates:
        return ""
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    return candidates[0][2]


def _source_hints(record: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for source in (record, payload):
        for key in (
            "source_hints",
            "source_urls",
            "links",
        ):
            raw = source.get(key)
            if isinstance(raw, str):
                values.append(raw)
            elif isinstance(raw, list):
                values.extend(str(item) for item in raw if item)
        for key in (
            "official_url",
            "organisation_url",
            "organization_url",
            "website",
            "homepage",
            "url",
            "link",
            "source_url",
            "canonical_url",
            "webpage_url",
        ):
            raw = source.get(key)
            if isinstance(raw, str) and raw.strip():
                values.append(raw.strip())
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = _text(value)
        if not value.startswith(("https://", "http://")) or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _preferred_source_link(record: dict[str, Any], payload: dict[str, Any]) -> str:
    hints = _source_hints(record, payload)
    if not hints:
        return ""
    # Prefer a concrete content item over a search endpoint when both are present.
    non_search = [
        value
        for value in hints
        if "/rss/search" not in value and "/search?" not in value
    ]
    return (non_search or hints)[0]


def _load_source_document(root: Path | None, source_ref: str, cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if root is None or not source_ref:
        return {}
    if source_ref in cache:
        return cache[source_ref]
    path = root / source_ref
    try:
        payload = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        payload = {}
    cache[source_ref] = payload
    return payload


def _match_raw_source_record(
    row: Any,
    payload: dict[str, Any],
    *,
    root: Path | None,
    cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Rehydrate compressed MARKET_OPPORTUNITY records from their source receipt."""
    current = _record_from_payload(payload)
    if _text(row["candidate_kind"]) != "MARKET_OPPORTUNITY":
        return current
    source_doc = _load_source_document(root, _text(row["source_ref"]), cache)
    if not source_doc:
        return current

    title = _text(current.get("title") or row["display_name"])
    opportunity_id = _text(current.get("opportunity_id") or payload.get("opportunity_id"))
    opportunity: dict[str, Any] = {}
    for item in source_doc.get("top_opportunities") or []:
        if not isinstance(item, dict):
            continue
        if opportunity_id and _text(item.get("opportunity_id")) == opportunity_id:
            opportunity = item
            break
        if title and _text(item.get("title")) == title:
            opportunity = item
            break

    hints = _source_hints(opportunity or current, payload)
    source_kind = _text(row["source_kind"]).lower()
    pools: list[dict[str, Any]] = []
    if "youtube" in source_kind:
        pools.extend(item for item in source_doc.get("records") or [] if isinstance(item, dict))
    elif "rss" in source_kind or "news" in source_kind:
        pools.extend(item for item in source_doc.get("news_or_blog_records") or [] if isinstance(item, dict))
    else:
        pools.extend(item for item in source_doc.get("records") or [] if isinstance(item, dict))
        pools.extend(item for item in source_doc.get("news_or_blog_records") or [] if isinstance(item, dict))

    def record_urls(item: dict[str, Any]) -> set[str]:
        return set(_source_hints(item, {}))

    hint_set = set(hints)
    for item in pools:
        if hint_set and record_urls(item) & hint_set:
            return {**current, **item, "_rehydrated_from": _text(row["source_ref"])}
    for item in pools:
        if title and _text(item.get("title")) == title:
            return {**current, **item, "_rehydrated_from": _text(row["source_ref"])}
    return {**current, **opportunity} if opportunity else current


def _source_entities(record: dict[str, Any], display_name: str, source_ref: str) -> list[SourceEntity]:
    """Return non-target source/provider entities so role boundaries stay explicit."""
    title = _text(record.get("title") or display_name)
    source_link = _preferred_source_link(record, {})
    entities: list[SourceEntity] = []
    suffix = _publisher_suffix(title)
    if suffix:
        entities.append(
            SourceEntity(
                name=suffix,
                entity_role="PUBLISHER_OR_PROVIDER",
                evidence="TITLE_PUBLISHER_SUFFIX",
                source_ref=source_ref,
                source_link=source_link,
            )
        )
    channel = _normalise_name(_text(record.get("channel_title") or record.get("channel")))
    if channel and channel.casefold() != suffix.casefold():
        entities.append(
            SourceEntity(
                name=channel,
                entity_role="MARKET_HABITAT_OR_PROVIDER",
                evidence="SOURCE_CHANNEL_FIELD",
                source_ref=source_ref,
                source_link=source_link,
            )
        )
    deduped: dict[tuple[str, str], SourceEntity] = {}
    for entity in entities:
        deduped[(entity.entity_role, entity.name.casefold())] = entity
    return list(deduped.values())


def resolve_identity(
    row: Any,
    *,
    root: Path | None = None,
    source_cache: dict[str, dict[str, Any]] | None = None,
) -> ResolvedIdentity | None:
    """Resolve a target-eligible subject organisation from source-bound evidence.

    Identity confidence is deliberately independent from candidate market relevance.
    Publishers/providers/channels are recorded separately and are not promoted merely
    because they are named in a public source.
    """
    if _text(row["candidate_kind"]) not in RESOLVABLE_KINDS:
        return None
    payload = _candidate_payload(row)
    cache = source_cache if source_cache is not None else {}
    record = _match_raw_source_record(row, payload, root=root, cache=cache)
    source_link = _preferred_source_link(record, payload)
    explicit = _normalise_name(_first_explicit_organisation(record, payload))
    if explicit:
        return ResolvedIdentity(
            organisation=explicit,
            evidence="EXPLICIT_SOURCE_ORGANISATION_FIELD",
            confidence=0.86,
            source_ref=_text(row["source_ref"]),
            entity_role="SUBJECT_ORGANISATION",
            target_eligible=True,
            source_link=source_link,
        )
    marker = _headline_organisation(record, _text(row["display_name"]))
    if marker:
        return ResolvedIdentity(
            organisation=marker,
            evidence="HEADLINE_ORGANISATION_FORM_MARKER",
            confidence=0.66,
            source_ref=_text(row["source_ref"]),
            entity_role="SUBJECT_ORGANISATION",
            target_eligible=True,
            source_link=source_link,
        )
    acronym = _headline_subject_acronym(record, _text(row["display_name"]))
    if acronym:
        return ResolvedIdentity(
            organisation=acronym,
            evidence="HEADLINE_SUBJECT_ACRONYM",
            confidence=0.62,
            source_ref=_text(row["source_ref"]),
            entity_role="SUBJECT_ORGANISATION",
            target_eligible=True,
            source_link=source_link,
        )
    return None


def _route_quality(record: dict[str, Any]) -> float:
    # Only an explicit organisation-owned route raises route quality. Article/video
    # source links remain provenance, not contactability evidence.
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
        "entity_role": identity.entity_role,
        "target_eligible": identity.target_eligible,
        "evidence": identity.evidence,
        "identity_confidence": identity.confidence,
        "source_link": identity.source_link,
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


def _record_source_roles(
    store: MarketSensoriumStore,
    row: Any,
    *,
    record: dict[str, Any],
) -> int:
    payload = _candidate_payload(row)
    source_ref = _text(row["source_ref"])
    count = 0
    for entity in _source_entities(record, _text(row["display_name"]), source_ref):
        entity_id = stable_id("SRC-ENT", entity.entity_role, entity.name.casefold(), source_ref)
        store.append_observation(
            source_kind="DISCOVERY_ENTITY_ROLE",
            source_ref=source_ref,
            entity_kind=entity.entity_role,
            entity_id=entity_id,
            domain_id=_text(row["domain_id"]),
            morphology=_text(row["morphology"]),
            observed_at=_text(row["last_seen_at"]) or None,
            payload={
                "name": entity.name,
                "entity_role": entity.entity_role,
                "evidence": entity.evidence,
                "source_link": entity.source_link or _preferred_source_link(record, payload),
                "target_promoted": False,
                "lead_created": False,
                "market_demand_claimed": False,
                "authority_created": False,
            },
        )
        count += 1
    return count


def resolve_discovery_candidates(
    store: MarketSensoriumStore,
    *,
    root: Path | None = None,
    limit: int = 500,
) -> tuple[list[TargetFeatures], dict[str, Any]]:
    """Resolve public discoveries into rankable subject-organisation hypotheses.

    Promotion here means only "rankable discovered target hypothesis". Identity
    confidence, market relevance, buyer-unit verification, lead status, contact
    permission, demand and authority remain separate truth dimensions.
    """
    if root is None:
        try:
            candidate_root = store.path.resolve().parents[2]
            root = candidate_root if (candidate_root / "campaigns").exists() else None
        except IndexError:
            root = None

    rows = store.connection.execute(
        """
        SELECT * FROM discovery_candidates
        WHERE state='UNRESOLVED_ENTITY'
        ORDER BY score DESC, last_seen_at DESC, candidate_id
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()

    groups: dict[tuple[str, str], list[tuple[Any, ResolvedIdentity, dict[str, Any]]]] = defaultdict(list)
    unresolved = 0
    evidence_counts: Counter[str] = Counter()
    source_role_observations = 0
    source_cache: dict[str, dict[str, Any]] = {}

    for row in rows:
        payload = _candidate_payload(row)
        record = _match_raw_source_record(row, payload, root=root, cache=source_cache)
        source_role_observations += _record_source_roles(store, row, record=record)

        identity = resolve_identity(row, root=root, source_cache=source_cache)
        if identity is None or not identity.target_eligible:
            unresolved += 1
            continue
        domain_id = _text(row["domain_id"])
        if not domain_id:
            unresolved += 1
            continue
        key = (domain_id, identity.organisation.casefold())
        groups[key].append((row, identity, record))
        evidence_counts[identity.evidence] += 1

    features: list[TargetFeatures] = []
    targets_created = 0
    targets_refreshed = 0
    candidates_resolved = 0
    for (domain_id, _), resolved_rows in sorted(groups.items(), key=lambda item: item[0]):
        identities = [identity for _, identity, _ in resolved_rows]
        organisation = max((identity.organisation for identity in identities), key=len)
        target_id = stable_id("DISC-TGT", domain_id, organisation.casefold())
        existing = store.connection.execute(
            "SELECT target_id FROM target_memory WHERE target_id=?", (target_id,)
        ).fetchone()
        if existing is None:
            targets_created += 1
        else:
            targets_refreshed += 1

        scores = [clamp(float(row["score"] or 0.0)) for row, _, _ in resolved_rows]
        max_score = max(scores) if scores else 0.0
        latest_seen = max(_text(row["last_seen_at"]) for row, _, _ in resolved_rows)
        evidence_confidence = max(identity.confidence for identity in identities)
        records = [record for _, _, record in resolved_rows]
        route_quality = max((_route_quality(record) for record in records), default=0.08)
        repeat_signal = min(5, len(resolved_rows))
        problem_strength = clamp(max_score + max(0, repeat_signal - 1) * 0.03)
        momentum = clamp(0.25 + repeat_signal * 0.11)
        # Commercial relevance remains based on the candidate score; identity
        # confidence never silently inflates domain/problem fit.
        domain_fit = clamp(max(0.55, max_score))
        morphology_fit = clamp(max(0.52, max_score * 0.96))
        buyer_unit_state = "UNRESOLVED_BUYER_UNIT"

        store.upsert_target(
            target_id=target_id,
            organisation=organisation,
            domain_id=domain_id,
            seen_at=latest_seen or None,
            metadata={
                "source": "market_sensorium_source_aware_resolution",
                "target_state": "DISCOVERED_ORGANISATION_BUYER_UNIT_PENDING",
                "buyer_unit_state": buyer_unit_state,
                "entity_role": "SUBJECT_ORGANISATION",
                "discovery_candidate_ids": [row["candidate_id"] for row, _, _ in resolved_rows],
                "resolution_evidence": sorted({identity.evidence for identity in identities}),
                "resolution_identity_confidence": evidence_confidence,
                "source_links": sorted({identity.source_link for identity in identities if identity.source_link}),
                "source_observation_count": len(resolved_rows),
                "lead_created": False,
                "market_demand_claimed": False,
                "authority_created": False,
            },
        )
        for row, identity, _ in resolved_rows:
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
                "entity_role": "SUBJECT_ORGANISATION",
                "candidate_ids": [row["candidate_id"] for row, _, _ in resolved_rows],
                "identity_evidence": sorted({identity.evidence for identity in identities}),
                "identity_confidence": evidence_confidence,
                "source_links": sorted({identity.source_link for identity in identities if identity.source_link}),
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
        "resolver_version": "MS-1.1_SOURCE_AWARE",
        "candidates_examined": len(rows),
        "candidates_resolved": candidates_resolved,
        "unique_resolved_target_hypotheses": len(features),
        "targets_created": targets_created,
        "targets_refreshed": targets_refreshed,
        "unresolved_in_examined_batch": unresolved,
        "unresolved_remaining": unresolved_remaining,
        "resolution_evidence_counts": dict(sorted(evidence_counts.items())),
        "source_role_observations": source_role_observations,
        "identity_relevance_decoupled": True,
        "publisher_auto_promoted": False,
        "buyer_units_verified": 0,
        "leads_created": 0,
        "market_demand_claimed": False,
        "authority_created": False,
        "external_effects": False,
    }
