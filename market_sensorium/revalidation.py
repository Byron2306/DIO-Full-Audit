from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from . import resolution as base
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

STRICT_RESOLVER_VERSION = "MS-1.2_REVALIDATED_SOURCE_AWARE"

# A bare all-caps token is not automatically an organisation. These are common
# content/course/event words observed in the real Sensorium corpus or likely to
# occur as headings. The stronger source-family rules below do most of the work;
# this set is a final semantic guard, not a buyer registry.
CONTENT_ACRONYM_DENY = {
    "ANALYSIS",
    "ARTICLE",
    "CHAPTER",
    "DEGREE",
    "ENGHL",
    "FINAL",
    "GRADE",
    "IMPACT",
    "LITERATURE",
    "NEWS",
    "REPORT",
    "RESEARCH",
    "REVIEW",
    "THESIS",
    "UPDATE",
    "VIDEO",
    "WEBINAR",
}

STRICT_ACRONYM = re.compile(r"^[A-Z]{2,7}$")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _payload(row: Any) -> dict[str, Any]:
    try:
        value = json.loads(row["payload_json"] or "{}")
        return value if isinstance(value, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _strict_identity_verdict(row: Any, identity: base.ResolvedIdentity | None) -> tuple[bool, str]:
    if identity is None or not identity.target_eligible:
        return False, "NO_TARGET_ELIGIBLE_IDENTITY"
    if identity.evidence != "HEADLINE_SUBJECT_ACRONYM":
        return True, "NON_ACRONYM_IDENTITY_EVIDENCE"

    token = _text(identity.organisation).upper()
    if not STRICT_ACRONYM.fullmatch(token):
        return False, "ACRONYM_SHAPE_REJECTED"
    if token in base.GENERIC_ACRONYMS or token in CONTENT_ACRONYM_DENY:
        return False, "GENERIC_OR_CONTENT_TOKEN_REJECTED"

    # YouTube titles are excellent topic/habitat evidence but too noisy for bare
    # acronym -> organisation promotion. A YouTube organisation still resolves if
    # it has explicit organisation metadata or an organisation-form name.
    source_kind = _text(row["source_kind"]).lower()
    if "youtube" in source_kind:
        return False, "YOUTUBE_BARE_ACRONYM_UNCORROBORATED"

    return True, "SOURCE_BOUND_SUBJECT_ACRONYM"


def _write_candidate_payload(store: MarketSensoriumStore, candidate_id: str, state: str, payload: dict[str, Any]) -> None:
    store.connection.execute(
        """
        UPDATE discovery_candidates
        SET state=?, payload_json=?, provenance_digest=?
        WHERE candidate_id=?
        """,
        (state, canonical_json(payload), digest_payload(payload), candidate_id),
    )


def _mark_target_invalidated(store: MarketSensoriumStore, target_id: str, reason: str) -> None:
    if not target_id:
        return
    row = store.connection.execute(
        "SELECT metadata_json FROM target_memory WHERE target_id=?", (target_id,)
    ).fetchone()
    if row is None:
        return
    try:
        metadata = json.loads(row["metadata_json"] or "{}")
    except json.JSONDecodeError:
        metadata = {}
    metadata.update(
        {
            "target_state": "INVALIDATED_ENTITY_RESOLUTION",
            "rankable": False,
            "invalidated_by": STRICT_RESOLVER_VERSION,
            "invalidation_reason": reason,
            "invalidated_at": utc_now(),
            "lead_created": False,
            "market_demand_claimed": False,
            "authority_created": False,
        }
    )
    store.connection.execute(
        """
        UPDATE target_memory
        SET current_rank=NULL, current_score=NULL,
            next_recommended_action='OBSERVE', updated_at=?, metadata_json=?
        WHERE target_id=?
        """,
        (utc_now(), canonical_json(metadata), target_id),
    )


def _invalidate_candidate(store: MarketSensoriumStore, row: Any, reason: str) -> str:
    payload = _payload(row)
    prior = payload.get("resolution") if isinstance(payload.get("resolution"), dict) else {}
    target_id = _text(prior.get("target_id"))
    history = payload.get("resolution_history")
    if not isinstance(history, list):
        history = []
    if prior:
        history.append(
            {
                **prior,
                "history_state": "INVALIDATED_ON_STRICT_REVALIDATION",
                "invalidated_at": utc_now(),
                "invalidated_by": STRICT_RESOLVER_VERSION,
                "invalidation_reason": reason,
            }
        )
    payload["resolution_history"] = history[-10:]
    payload.pop("resolution", None)
    payload["resolution_revalidation"] = {
        "state": "REJECTED_ENTITY_RESOLUTION",
        "resolver_version": STRICT_RESOLVER_VERSION,
        "reason": reason,
        "revalidated_at": utc_now(),
        "target_created": False,
        "lead_created": False,
        "market_demand_claimed": False,
        "authority_created": False,
    }
    payload["target_created"] = False
    _write_candidate_payload(store, row["candidate_id"], "REJECTED_ENTITY_RESOLUTION", payload)

    store.append_observation(
        source_kind="DISCOVERY_RESOLUTION_INVALIDATION",
        source_ref=_text(row["source_ref"]),
        entity_kind="TARGET_HYPOTHESIS_REVALIDATION",
        entity_id=target_id or _text(row["candidate_id"]),
        domain_id=_text(row["domain_id"]),
        morphology=_text(row["morphology"]),
        observed_at=utc_now(),
        payload={
            "candidate_id": row["candidate_id"],
            "prior_target_id": target_id or None,
            "prior_organisation": prior.get("organisation"),
            "reason": reason,
            "resolver_version": STRICT_RESOLVER_VERSION,
            "rankable_now": False,
            "lead_created": False,
            "market_demand_claimed": False,
            "authority_created": False,
        },
    )
    return target_id


def _annotate_strict_valid(store: MarketSensoriumStore, row: Any, identity: base.ResolvedIdentity, reason: str) -> None:
    payload = _payload(row)
    resolution = payload.get("resolution") if isinstance(payload.get("resolution"), dict) else {}
    resolution.update(
        {
            "strict_resolver_version": STRICT_RESOLVER_VERSION,
            "strict_revalidation_state": "VALID",
            "strict_revalidation_reason": reason,
            "strict_revalidated_at": utc_now(),
        }
    )
    payload["resolution"] = resolution
    payload["resolution_revalidation"] = {
        "state": "STRICT_VALID",
        "resolver_version": STRICT_RESOLVER_VERSION,
        "reason": reason,
        "revalidated_at": utc_now(),
        "lead_created": False,
        "market_demand_claimed": False,
        "authority_created": False,
    }
    _write_candidate_payload(store, row["candidate_id"], "RESOLVED_ORGANISATION", payload)


def _revalidate_resolved_rows(
    store: MarketSensoriumStore,
    *,
    root: Path | None,
) -> tuple[int, list[dict[str, str]]]:
    source_cache: dict[str, dict[str, Any]] = {}
    rows = store.connection.execute(
        "SELECT * FROM discovery_candidates WHERE state='RESOLVED_ORGANISATION' ORDER BY candidate_id"
    ).fetchall()
    invalidated: list[dict[str, str]] = []
    for row in rows:
        payload = _payload(row)
        prior = payload.get("resolution") if isinstance(payload.get("resolution"), dict) else {}
        identity = base.resolve_identity(row, root=root, source_cache=source_cache)
        allowed, reason = _strict_identity_verdict(row, identity)
        if allowed and identity is not None:
            prior_org = _text(prior.get("organisation"))
            if prior_org and prior_org.casefold() != identity.organisation.casefold():
                allowed = False
                reason = "IDENTITY_CHANGED_ON_REVALIDATION"
        if not allowed or identity is None:
            target_id = _invalidate_candidate(store, row, reason)
            invalidated.append(
                {
                    "candidate_id": _text(row["candidate_id"]),
                    "target_id": target_id,
                    "organisation": _text(prior.get("organisation")),
                    "reason": reason,
                }
            )
            continue
        _annotate_strict_valid(store, row, identity, reason)
    store.connection.commit()
    return len(rows), invalidated


def _features_from_current_valid_resolutions(
    store: MarketSensoriumStore,
    *,
    root: Path | None,
) -> tuple[list[TargetFeatures], Counter[str], int]:
    rows = store.connection.execute(
        "SELECT * FROM discovery_candidates WHERE state='RESOLVED_ORGANISATION' ORDER BY candidate_id"
    ).fetchall()
    source_cache: dict[str, dict[str, Any]] = {}
    groups: dict[tuple[str, str], list[tuple[Any, base.ResolvedIdentity, dict[str, Any]]]] = defaultdict(list)
    evidence_counts: Counter[str] = Counter()
    confusion = 0

    for row in rows:
        identity = base.resolve_identity(row, root=root, source_cache=source_cache)
        allowed, _ = _strict_identity_verdict(row, identity)
        if not allowed or identity is None:
            confusion += 1
            continue
        payload = _payload(row)
        prior = payload.get("resolution") if isinstance(payload.get("resolution"), dict) else {}
        if _text(prior.get("strict_resolver_version")) != STRICT_RESOLVER_VERSION:
            confusion += 1
            continue
        domain_id = _text(row["domain_id"])
        if not domain_id:
            confusion += 1
            continue
        record = base._match_raw_source_record(row, payload, root=root, cache=source_cache)
        groups[(domain_id, identity.organisation.casefold())].append((row, identity, record))
        evidence_counts[identity.evidence] += 1

    features: list[TargetFeatures] = []
    for (domain_id, _), resolved_rows in sorted(groups.items(), key=lambda item: item[0]):
        identities = [identity for _, identity, _ in resolved_rows]
        organisation = max((identity.organisation for identity in identities), key=len)
        target_id = stable_id("DISC-TGT", domain_id, organisation.casefold())
        scores = [clamp(float(row["score"] or 0.0)) for row, _, _ in resolved_rows]
        max_score = max(scores) if scores else 0.0
        latest_seen = max(_text(row["last_seen_at"]) for row, _, _ in resolved_rows)
        evidence_confidence = max(identity.confidence for identity in identities)
        records = [record for _, _, record in resolved_rows]
        route_quality = max((base._route_quality(record) for record in records), default=0.08)
        repeat_signal = min(5, len(resolved_rows))
        problem_strength = clamp(max_score + max(0, repeat_signal - 1) * 0.03)
        momentum = clamp(0.25 + repeat_signal * 0.11)
        features.append(
            TargetFeatures(
                target_id=target_id,
                organisation=organisation,
                domain_id=domain_id,
                domain_fit=clamp(max(0.55, max_score)),
                morphology_fit=clamp(max(0.52, max_score * 0.96)),
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
    return features, evidence_counts, confusion


def resolve_discovery_candidates_revalidated(
    store: MarketSensoriumStore,
    *,
    root: Path | None = None,
    limit: int = 500,
) -> tuple[list[TargetFeatures], dict[str, Any]]:
    """MS-1.2 resolver: resolve, revalidate, and exclude false target identities.

    Historical false resolutions are preserved as invalidation observations and
    resolution history. They are removed from the current rankable feature set.
    """
    if root is None:
        try:
            candidate_root = store.path.resolve().parents[2]
            root = candidate_root if (candidate_root / "campaigns").exists() else None
        except IndexError:
            root = None

    prechecked, invalidated_before = _revalidate_resolved_rows(store, root=root)

    # Resolve still-unresolved evidence with the source-aware MS-1.1 machinery.
    _, base_summary = base.resolve_discovery_candidates(store, root=root, limit=limit)

    postchecked, invalidated_after = _revalidate_resolved_rows(store, root=root)
    invalidated = invalidated_before + invalidated_after

    features, evidence_counts, confusion = _features_from_current_valid_resolutions(
        store, root=root
    )
    valid_target_ids = {feature.target_id for feature in features}
    invalid_target_ids = {
        item["target_id"] for item in invalidated if item.get("target_id") and item["target_id"] not in valid_target_ids
    }
    for target_id in sorted(invalid_target_ids):
        reason = next(
            (item["reason"] for item in invalidated if item.get("target_id") == target_id),
            "STRICT_REVALIDATION_FAILED",
        )
        _mark_target_invalidated(store, target_id, reason)

    store.connection.commit()
    unresolved_remaining = store.connection.execute(
        "SELECT COUNT(*) FROM discovery_candidates WHERE state='UNRESOLVED_ENTITY'"
    ).fetchone()[0]
    rejected_total = store.connection.execute(
        "SELECT COUNT(*) FROM discovery_candidates WHERE state='REJECTED_ENTITY_RESOLUTION'"
    ).fetchone()[0]
    resolved_total = store.connection.execute(
        "SELECT COUNT(*) FROM discovery_candidates WHERE state='RESOLVED_ORGANISATION'"
    ).fetchone()[0]

    return features, {
        "resolver_version": STRICT_RESOLVER_VERSION,
        "candidates_examined": int(base_summary.get("candidates_examined") or 0),
        "candidates_resolved": int(resolved_total),
        "unique_resolved_target_hypotheses": len(features),
        "targets_created": int(base_summary.get("targets_created") or 0),
        "targets_refreshed": int(base_summary.get("targets_refreshed") or 0),
        "unresolved_remaining": int(unresolved_remaining),
        "rejected_entity_resolutions": int(rejected_total),
        "revalidated_existing_candidates": int(prechecked),
        "revalidated_post_resolution_candidates": int(postchecked),
        "invalidated_this_cycle": len(invalidated),
        "invalidated_examples": invalidated[:20],
        "resolution_evidence_counts": dict(sorted(evidence_counts.items())),
        "source_role_observations": int(base_summary.get("source_role_observations") or 0),
        "identity_relevance_decoupled": True,
        "publisher_auto_promoted": False,
        "youtube_bare_acronym_auto_promoted": False,
        "strict_revalidation_complete": True,
        "entity_role_confusion": int(confusion),
        "buyer_units_verified": 0,
        "leads_created": 0,
        "market_demand_claimed": False,
        "authority_created": False,
        "external_effects": False,
    }
