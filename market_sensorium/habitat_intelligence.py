from __future__ import annotations

import json
from collections import Counter
from typing import Any

from .core import MarketSensoriumStore, canonical_json, digest_payload, stable_id


PUBLIC_ACCESS_STATES = {"PUBLIC_READ", "PUBLIC_OBSERVABLE", "PUBLIC"}
OPERATOR_ACCESS_STATES = {
    "LOGIN_REQUIRED",
    "MEMBERSHIP_REQUIRED",
    "INVITE_REQUIRED",
    "API_PERMISSION_REQUIRED",
    "BOT_INSTALL_REQUIRES_ADMIN",
}
REFUSED_ACCESS_STATES = {"REFUSE_AUTOMATION"}
REFUSED_TERMS_STATES = {"TERMS_RESTRICTED", "REFUSE"}


def _obj(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _schema(store: MarketSensoriumStore) -> None:
    store.connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS habitat_intelligence_events (
          event_id TEXT PRIMARY KEY,
          habitat_key TEXT NOT NULL,
          source_habitat_id TEXT NOT NULL,
          platform TEXT NOT NULL,
          habitat_kind TEXT NOT NULL,
          canonical_name TEXT NOT NULL,
          source_ref TEXT NOT NULL,
          domain_id TEXT,
          observed_at TEXT NOT NULL,
          access_state TEXT NOT NULL,
          permission_ladder_state TEXT NOT NULL,
          operator_membership_state TEXT NOT NULL,
          posting_authority TEXT NOT NULL,
          dm_authority TEXT NOT NULL,
          read_authority TEXT NOT NULL,
          participant_inference_allowed INTEGER NOT NULL DEFAULT 0,
          seller_association_state TEXT NOT NULL,
          source_bound INTEGER NOT NULL DEFAULT 1,
          payload_json TEXT NOT NULL,
          provenance_digest TEXT NOT NULL,
          authority_created INTEGER NOT NULL DEFAULT 0,
          external_effects INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS habitat_intelligence_events_key_idx
          ON habitat_intelligence_events(habitat_key, observed_at);

        CREATE TABLE IF NOT EXISTS market_habitat_memory_v2 (
          habitat_key TEXT PRIMARY KEY,
          platform TEXT NOT NULL,
          habitat_kind TEXT NOT NULL,
          canonical_name TEXT NOT NULL,
          source_ref TEXT NOT NULL,
          domain_id TEXT,
          first_seen_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          observation_count INTEGER NOT NULL,
          access_state TEXT NOT NULL,
          permission_ladder_state TEXT NOT NULL,
          operator_membership_state TEXT NOT NULL,
          posting_authority TEXT NOT NULL,
          dm_authority TEXT NOT NULL,
          read_authority TEXT NOT NULL,
          seller_association_state TEXT NOT NULL,
          intelligence_score REAL NOT NULL,
          recommended_action TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          authority_created INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    store.connection.commit()


def _kind(platform: str) -> str:
    p = platform.strip().lower()
    if p == "youtube":
        return "YOUTUBE_CHANNEL_HABITAT"
    if p in {"news_or_blog", "news", "blog", "rss"}:
        return "NEWS_OR_BLOG_HABITAT"
    if p in {"facebook", "facebook_group", "facebook_page"}:
        return "FACEBOOK_HABITAT"
    if p in {"linkedin", "linkedin_group", "linkedin_page"}:
        return "LINKEDIN_HABITAT"
    if p in {"reddit", "subreddit"}:
        return "REDDIT_HABITAT"
    if p in {"discord", "discord_server"}:
        return "DISCORD_HABITAT"
    if p in {"forum", "community"}:
        return "COMMUNITY_OR_FORUM_HABITAT"
    if p in {"conference", "event"}:
        return "EVENT_HABITAT"
    if p in {"procurement", "funding_portal", "job_board"}:
        return "MARKET_PORTAL_HABITAT"
    return "PUBLIC_INFORMATION_HABITAT"


def _permission(access_state: str, terms_state: str) -> tuple[str, str, str, str, str, str]:
    access = access_state.upper()
    terms = terms_state.upper()
    if access in REFUSED_ACCESS_STATES or terms in REFUSED_TERMS_STATES:
        return (
            "REFUSED_OR_TERMS_RESTRICTED",
            "UNKNOWN",
            "NONE",
            "NONE",
            "NONE",
            "REFUSE_AUTOMATION_OR_OBSERVE_MANUALLY",
        )
    if access in OPERATOR_ACCESS_STATES:
        stage = "MEMBER_REQUIRED" if access in {"LOGIN_REQUIRED", "MEMBERSHIP_REQUIRED", "INVITE_REQUIRED"} else "NEEDS_YOU"
        return (stage, "UNKNOWN", "NONE", "NONE", "NONE", "NEEDS_YOU")
    if access in PUBLIC_ACCESS_STATES:
        return (
            "PUBLIC_OBSERVABLE",
            "NOT_REQUIRED_FOR_PUBLIC_READ",
            "NONE",
            "NONE",
            "PUBLIC_READ_ONLY",
            "OBSERVE_PUBLIC_ONLY",
        )
    return ("DISCOVERED", "UNKNOWN", "NONE", "NONE", "NONE", "OBSERVE_ACCESS_STATE")


def _seller_association(store: MarketSensoriumStore, source_ref: str, canonical_name: str) -> str:
    try:
        row = store.connection.execute(
            """
            SELECT COUNT(*) AS n
            FROM competitive_offer_events
            WHERE source_ref=? OR lower(seller)=lower(?)
            """,
            (source_ref, canonical_name),
        ).fetchone()
    except Exception:
        return "NO_SELLER_ASSOCIATION_OBSERVED"
    return "PROVIDER_OR_SELLER_ACTIVITY_OBSERVED" if int(row["n"] or 0) > 0 else "NO_SELLER_ASSOCIATION_OBSERVED"


def _score(*, platform: str, permission_state: str, seller_state: str, source_ref: str) -> float:
    score = 0.25
    if permission_state == "PUBLIC_OBSERVABLE":
        score += 0.30
    if platform.strip().lower() in {"youtube", "news_or_blog", "rss", "blog"}:
        score += 0.15
    if seller_state == "PROVIDER_OR_SELLER_ACTIVITY_OBSERVED":
        score += 0.12
    if source_ref.startswith(("https://", "http://")):
        score += 0.08
    return round(min(1.0, score), 6)


def observe_market_habitats(store: MarketSensoriumStore) -> dict[str, Any]:
    """Promote remembered habitat observations into governed habitat intelligence.

    This is an observation/classification pass only. Public visibility never grants
    membership, posting, DM, outreach, scraping, participant inference, or commerce
    authority.
    """
    _schema(store)
    rows = store.connection.execute(
        "SELECT * FROM habitat_memory ORDER BY last_seen_at DESC, habitat_id"
    ).fetchall()
    counts: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    access_counts: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []

    for row in rows:
        platform = str(row["platform"] or "")
        name = str(row["canonical_name"] or "")
        source_ref = str(row["source_ref"] or "")
        domain_id = str(row["domain_id"] or "")
        access_state = str(row["access_state"] or "DISCOVERED")
        terms_state = str(row["terms_state"] or "UNKNOWN")
        observed_at = str(row["last_seen_at"] or row["first_seen_at"] or "")
        kind = _kind(platform)
        permission, membership, posting, dm, read, action = _permission(access_state, terms_state)
        seller_state = _seller_association(store, source_ref, name)
        intelligence_score = _score(
            platform=platform,
            permission_state=permission,
            seller_state=seller_state,
            source_ref=source_ref,
        )
        habitat_key = stable_id("MHAB", platform.lower(), source_ref or name.lower(), domain_id)
        payload = {
            "schema": "dio.market_sensorium.habitat_intelligence.v1",
            "source_habitat_id": row["habitat_id"],
            "platform": platform,
            "habitat_kind": kind,
            "canonical_name": name,
            "source_ref": source_ref,
            "domain_id": domain_id,
            "access_state": access_state,
            "terms_state": terms_state,
            "permission_ladder_state": permission,
            "operator_membership_state": membership,
            "posting_authority": posting,
            "dm_authority": dm,
            "read_authority": read,
            "seller_association_state": seller_state,
            "intelligence_score": intelligence_score,
            "recommended_action": action,
            "public_visibility_is_consent": False,
            "public_visibility_is_membership": False,
            "public_visibility_is_posting_authority": False,
            "public_visibility_is_dm_authority": False,
            "participant_inference_allowed": False,
            "member_scraping_allowed": False,
            "habitat_is_demand": False,
            "habitat_is_buyer": False,
            "market_demand_claimed": False,
            "authority_created": False,
            "external_effects": False,
        }
        provenance = digest_payload(payload)
        event_id = stable_id("MHABEV", habitat_key, observed_at, provenance)
        store.connection.execute(
            """
            INSERT OR IGNORE INTO habitat_intelligence_events (
              event_id,habitat_key,source_habitat_id,platform,habitat_kind,
              canonical_name,source_ref,domain_id,observed_at,access_state,
              permission_ladder_state,operator_membership_state,posting_authority,
              dm_authority,read_authority,participant_inference_allowed,
              seller_association_state,source_bound,payload_json,provenance_digest,
              authority_created,external_effects
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,0,0)
            """,
            (
                event_id,
                habitat_key,
                row["habitat_id"],
                platform,
                kind,
                name,
                source_ref,
                domain_id or None,
                observed_at,
                access_state,
                permission,
                membership,
                posting,
                dm,
                read,
                0,
                seller_state,
                canonical_json(payload),
                provenance,
            ),
        )
        stats = store.connection.execute(
            """
            SELECT MIN(observed_at) AS first_seen, MAX(observed_at) AS last_seen,
                   COUNT(*) AS observations
            FROM habitat_intelligence_events WHERE habitat_key=?
            """,
            (habitat_key,),
        ).fetchone()
        store.connection.execute(
            """
            INSERT INTO market_habitat_memory_v2 (
              habitat_key,platform,habitat_kind,canonical_name,source_ref,domain_id,
              first_seen_at,last_seen_at,observation_count,access_state,
              permission_ladder_state,operator_membership_state,posting_authority,
              dm_authority,read_authority,seller_association_state,intelligence_score,
              recommended_action,payload_json,authority_created
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)
            ON CONFLICT(habitat_key) DO UPDATE SET
              last_seen_at=excluded.last_seen_at,
              observation_count=excluded.observation_count,
              access_state=excluded.access_state,
              permission_ladder_state=excluded.permission_ladder_state,
              operator_membership_state=excluded.operator_membership_state,
              posting_authority=excluded.posting_authority,
              dm_authority=excluded.dm_authority,
              read_authority=excluded.read_authority,
              seller_association_state=excluded.seller_association_state,
              intelligence_score=excluded.intelligence_score,
              recommended_action=excluded.recommended_action,
              payload_json=excluded.payload_json
            """,
            (
                habitat_key,
                platform,
                kind,
                name,
                source_ref,
                domain_id or None,
                stats["first_seen"] or observed_at,
                stats["last_seen"] or observed_at,
                int(stats["observations"] or 0),
                access_state,
                permission,
                membership,
                posting,
                dm,
                read,
                seller_state,
                intelligence_score,
                action,
                canonical_json(payload),
            ),
        )
        counts["habitat_observations_examined"] += 1
        if source_ref:
            counts["source_bound_habitats"] += 1
        if permission == "PUBLIC_OBSERVABLE":
            counts["public_observable_habitats"] += 1
        if action == "NEEDS_YOU":
            counts["needs_you_habitats"] += 1
        if permission == "REFUSED_OR_TERMS_RESTRICTED":
            counts["refused_or_terms_restricted_habitats"] += 1
        if seller_state == "PROVIDER_OR_SELLER_ACTIVITY_OBSERVED":
            counts["provider_associated_habitats"] += 1
        kind_counts[kind] += 1
        access_counts[permission] += 1
        if len(examples) < 12:
            examples.append(
                {
                    "name": name,
                    "platform": platform,
                    "kind": kind,
                    "domain_id": domain_id,
                    "permission": permission,
                    "read": read,
                    "membership": membership,
                    "post": posting,
                    "dm": dm,
                    "seller_association": seller_state,
                    "score": intelligence_score,
                    "recommended_action": action,
                }
            )

    store.connection.commit()
    persisted = int(store.connection.execute("SELECT COUNT(*) FROM market_habitat_memory_v2").fetchone()[0])
    events = int(store.connection.execute("SELECT COUNT(*) FROM habitat_intelligence_events").fetchone()[0])
    return {
        "schema": "dio.market_sensorium.market_habitat_intelligence.v1",
        **dict(sorted(counts.items())),
        "canonical_habitats": persisted,
        "persisted_habitat_intelligence_events": events,
        "habitat_kind_counts": dict(sorted(kind_counts.items())),
        "permission_state_counts": dict(sorted(access_counts.items())),
        "habitat_type_diversity": sum(1 for v in kind_counts.values() if v > 0),
        "public_visibility_is_consent": False,
        "public_visibility_is_membership": False,
        "public_visibility_is_posting_authority": False,
        "public_visibility_is_dm_authority": False,
        "participant_inference_allowed": False,
        "member_scraping_allowed": False,
        "seller_association_is_target_identity": False,
        "habitat_is_demand": False,
        "market_demand_claimed": False,
        "outreach_authority_created": False,
        "posting_authority_created": False,
        "dm_authority_created": False,
        "membership_authority_created": False,
        "authority_created": False,
        "external_effects": False,
        "examples": examples,
    }
