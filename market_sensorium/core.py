from __future__ import annotations

import csv
import hashlib
import json
import math
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "dio.market_sensorium.v1"

DEFAULT_WEIGHTS: dict[str, float] = {
    "domain_fit": 0.16,
    "morphology_fit": 0.16,
    "capability_fit": 0.12,
    "buyer_role_confidence": 0.10,
    "problem_signal_strength": 0.10,
    "signal_recency": 0.08,
    "organisation_fit": 0.07,
    "route_quality": 0.05,
    "market_momentum": 0.05,
    "prior_engagement": 0.04,
    "competitive_whitespace": 0.04,
    "seed_prior": 0.03,
}

SILENCE_STATES = (
    "NO_CONTACT",
    "WAITING",
    "SILENCE_OBSERVED",
    "WEAK_NEGATIVE_SIGNAL",
    "CHANNEL_OFFER_DECAY",
    "DORMANT",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_id(prefix: str, *parts: object) -> str:
    payload = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:18].upper()
    return f"{prefix}-{digest}"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_payload(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def age_days(timestamp: str | None, now: datetime | None = None) -> float | None:
    parsed = parse_iso(timestamp)
    if parsed is None:
        return None
    current = now or datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0.0, (current - parsed.astimezone(timezone.utc)).total_seconds() / 86400.0)


def recency_score(timestamp: str | None, half_life_days: float = 30.0, now: datetime | None = None) -> float:
    age = age_days(timestamp, now)
    if age is None:
        return 0.0
    half_life = max(1.0, float(half_life_days))
    return clamp(math.pow(0.5, age / half_life))


def silence_state(sent_at: str | None, reply_state: str | None, now: datetime | None = None) -> tuple[str, float, float | None]:
    reply = str(reply_state or "").strip().upper()
    if reply and reply not in {"NONE", "UNKNOWN", "NO_REPLY", "SILENT"}:
        return "REPLIED", 0.0, age_days(sent_at, now)
    age = age_days(sent_at, now)
    if age is None:
        return "NO_CONTACT", 0.0, None
    if age <= 3:
        return "WAITING", 0.0, age
    if age <= 7:
        return "SILENCE_OBSERVED", 0.02, age
    if age <= 14:
        return "WEAK_NEGATIVE_SIGNAL", 0.05, age
    if age <= 30:
        return "CHANNEL_OFFER_DECAY", 0.10, age
    return "DORMANT", 0.16, age


@dataclass(frozen=True)
class SeedCandidate:
    seed_id: str
    domain_id: str
    domain_name: str
    rank: int
    organisation: str
    organisation_kind: str
    geography: str
    website: str
    engagement_mode: str
    rationale: str
    provenance_kind: str = "CURATED_BASELINE_PRIOR"
    evidence_state: str = "SEED_PRIOR_REQUIRES_REFRESH"
    authority_created: bool = False


@dataclass(frozen=True)
class TargetFeatures:
    target_id: str
    organisation: str
    domain_id: str
    domain_fit: float = 0.0
    morphology_fit: float = 0.0
    capability_fit: float = 0.0
    buyer_role_confidence: float = 0.0
    problem_signal_strength: float = 0.0
    signal_recency: float = 0.0
    organisation_fit: float = 0.0
    route_quality: float = 0.0
    market_momentum: float = 0.0
    prior_engagement: float = 0.0
    competitive_whitespace: float = 0.0
    seed_prior: float = 0.0
    silence_penalty: float = 0.0
    rejection_penalty: float = 0.0
    authority_penalty: float = 0.0
    stale_signal_penalty: float = 0.0


@dataclass(frozen=True)
class RankReceipt:
    receipt_id: str
    target_id: str
    organisation: str
    domain_id: str
    previous_rank: int | None
    current_rank: int
    score: float
    previous_score: float | None
    rank_delta: int | None
    score_delta: float | None
    causes: tuple[str, ...]
    observed_at: str
    authority_created: bool = False
    execution_performed: bool = False


class MarketSensoriumStore:
    """SQLite-backed temporal memory for market observations and ranking lineage.

    This store records observations and recommendations only. It has no send, spend,
    publish, join, DM, payment, or deployment authority.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self._migrate()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "MarketSensoriumStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _migrate(self) -> None:
        self.connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS observations (
                observation_id TEXT PRIMARY KEY,
                observed_at TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                source_ref TEXT NOT NULL,
                entity_kind TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                domain_id TEXT,
                morphology TEXT,
                payload_json TEXT NOT NULL,
                provenance_digest TEXT NOT NULL,
                authority_created INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS observations_entity_idx
              ON observations(entity_kind, entity_id, observed_at);

            CREATE TABLE IF NOT EXISTS target_memory (
                target_id TEXT PRIMARY KEY,
                organisation TEXT NOT NULL,
                domain_id TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                last_contact_at TEXT,
                reply_state TEXT,
                consent_state TEXT,
                conversation_id TEXT,
                email_sent_count INTEGER NOT NULL DEFAULT 0,
                proof_request_count INTEGER NOT NULL DEFAULT 0,
                meeting_count INTEGER NOT NULL DEFAULT 0,
                acceptance_count INTEGER NOT NULL DEFAULT 0,
                payment_count INTEGER NOT NULL DEFAULT 0,
                current_score REAL,
                current_rank INTEGER,
                previous_score REAL,
                previous_rank INTEGER,
                silence_state TEXT NOT NULL DEFAULT 'NO_CONTACT',
                silence_penalty REAL NOT NULL DEFAULT 0,
                next_recommended_action TEXT NOT NULL DEFAULT 'OBSERVE',
                updated_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS rank_receipts (
                receipt_id TEXT PRIMARY KEY,
                target_id TEXT NOT NULL,
                organisation TEXT NOT NULL,
                domain_id TEXT NOT NULL,
                previous_rank INTEGER,
                current_rank INTEGER NOT NULL,
                score REAL NOT NULL,
                previous_score REAL,
                rank_delta INTEGER,
                score_delta REAL,
                causes_json TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                authority_created INTEGER NOT NULL DEFAULT 0,
                execution_performed INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS habitat_memory (
                habitat_id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                canonical_name TEXT NOT NULL,
                source_ref TEXT NOT NULL,
                domain_id TEXT,
                access_state TEXT NOT NULL,
                terms_state TEXT NOT NULL,
                operator_membership_state TEXT NOT NULL DEFAULT 'UNKNOWN',
                posting_authority TEXT NOT NULL DEFAULT 'NONE',
                dm_authority TEXT NOT NULL DEFAULT 'NONE',
                current_rank INTEGER,
                current_score REAL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                recommended_action TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                authority_created INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS offer_observations (
                offer_observation_id TEXT PRIMARY KEY,
                source_kind TEXT NOT NULL,
                source_ref TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                seller TEXT,
                domain_id TEXT,
                morphology TEXT,
                headline TEXT,
                pitch_angle TEXT,
                audience TEXT,
                price_value REAL,
                price_currency TEXT,
                price_basis TEXT,
                payload_json TEXT NOT NULL,
                provenance_digest TEXT NOT NULL,
                authority_created INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS discovery_candidates (
                candidate_id TEXT PRIMARY KEY,
                source_kind TEXT NOT NULL,
                source_ref TEXT NOT NULL,
                candidate_kind TEXT NOT NULL,
                display_name TEXT NOT NULL,
                domain_id TEXT,
                morphology TEXT,
                score REAL NOT NULL DEFAULT 0,
                state TEXT NOT NULL DEFAULT 'UNRESOLVED_ENTITY',
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                provenance_digest TEXT NOT NULL,
                authority_created INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS discovery_candidates_domain_idx
              ON discovery_candidates(domain_id, score DESC, last_seen_at DESC);

            CREATE TABLE IF NOT EXISTS cycle_runs (
                cycle_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                mode TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                receipt_digest TEXT NOT NULL,
                authority_created INTEGER NOT NULL DEFAULT 0,
                external_effects INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        self.connection.commit()

    def append_observation(
        self,
        *,
        source_kind: str,
        source_ref: str,
        entity_kind: str,
        entity_id: str,
        payload: dict[str, Any],
        observed_at: str | None = None,
        domain_id: str = "",
        morphology: str = "",
    ) -> str:
        timestamp = observed_at or utc_now()
        observation_id = stable_id("OBS", source_kind, source_ref, entity_kind, entity_id, timestamp, digest_payload(payload))
        digest = digest_payload(payload)
        self.connection.execute(
            """
            INSERT OR IGNORE INTO observations (
              observation_id, observed_at, source_kind, source_ref, entity_kind,
              entity_id, domain_id, morphology, payload_json, provenance_digest,
              authority_created
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                observation_id,
                timestamp,
                source_kind,
                source_ref,
                entity_kind,
                entity_id,
                domain_id or None,
                morphology or None,
                canonical_json(payload),
                digest,
            ),
        )
        self.connection.commit()
        return observation_id

    def upsert_target(
        self,
        *,
        target_id: str,
        organisation: str,
        domain_id: str,
        seen_at: str | None = None,
        last_contact_at: str | None = None,
        reply_state: str | None = None,
        consent_state: str | None = None,
        conversation_id: str | None = None,
        email_sent_count: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        timestamp = seen_at or utc_now()
        existing = self.connection.execute(
            "SELECT * FROM target_memory WHERE target_id = ?", (target_id,)
        ).fetchone()
        if existing is None:
            silence, penalty, _ = silence_state(last_contact_at, reply_state)
            self.connection.execute(
                """
                INSERT INTO target_memory (
                  target_id, organisation, domain_id, first_seen_at, last_seen_at,
                  last_contact_at, reply_state, consent_state, conversation_id,
                  email_sent_count, silence_state, silence_penalty,
                  next_recommended_action, updated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target_id,
                    organisation,
                    domain_id,
                    timestamp,
                    timestamp,
                    last_contact_at,
                    reply_state,
                    consent_state,
                    conversation_id,
                    int(email_sent_count or 0),
                    silence,
                    penalty,
                    self._next_action(silence, reply_state, consent_state),
                    utc_now(),
                    canonical_json(metadata or {}),
                ),
            )
        else:
            contact = last_contact_at or existing["last_contact_at"]
            reply = reply_state if reply_state is not None else existing["reply_state"]
            consent = consent_state if consent_state is not None else existing["consent_state"]
            silence, penalty, _ = silence_state(contact, reply)
            merged_meta = json.loads(existing["metadata_json"] or "{}")
            merged_meta.update(metadata or {})
            count = int(email_sent_count if email_sent_count is not None else existing["email_sent_count"] or 0)
            self.connection.execute(
                """
                UPDATE target_memory
                SET organisation=?, domain_id=?, last_seen_at=?, last_contact_at=?,
                    reply_state=?, consent_state=?, conversation_id=?, email_sent_count=?,
                    silence_state=?, silence_penalty=?, next_recommended_action=?,
                    updated_at=?, metadata_json=?
                WHERE target_id=?
                """,
                (
                    organisation,
                    domain_id,
                    timestamp,
                    contact,
                    reply,
                    consent,
                    conversation_id or existing["conversation_id"],
                    count,
                    silence,
                    penalty,
                    self._next_action(silence, reply, consent),
                    utc_now(),
                    canonical_json(merged_meta),
                    target_id,
                ),
            )
        self.connection.commit()

    @staticmethod
    def _next_action(silence: str, reply_state: str | None, consent_state: str | None) -> str:
        reply = str(reply_state or "").upper()
        consent = str(consent_state or "").upper()
        if consent in {"NO", "REFUSED", "WITHDRAWN", "OPT_OUT"} or reply in {"NO", "REJECTED", "OPT_OUT"}:
            return "HOLD_OUTREACH_OBSERVE_ONLY"
        if consent in {"YES", "GRANTED", "CONSENTED"}:
            return "REVIEW_PERMITTED_NEXT_STEP"
        if silence in {"CHANNEL_OFFER_DECAY", "DORMANT"}:
            return "RESEARCH_OR_PIVOT_NO_FOLLOWUP_AUTHORITY"
        if silence == "WEAK_NEGATIVE_SIGNAL":
            return "OBSERVE_AND_REASSESS"
        if silence in {"WAITING", "SILENCE_OBSERVED"}:
            return "WAIT_AND_OBSERVE"
        return "OBSERVE"

    def rank(self, features: Iterable[TargetFeatures], observed_at: str | None = None) -> list[RankReceipt]:
        """Rank targets within each ATLAS domain and preserve rank lineage."""
        timestamp = observed_at or utc_now()
        grouped: dict[str, list[tuple[TargetFeatures, float, list[str]]]] = {}
        for item in features:
            score, causes = score_target(item)
            grouped.setdefault(item.domain_id, []).append((item, score, causes))
        receipts: list[RankReceipt] = []
        for domain_id in sorted(grouped):
            scored = grouped[domain_id]
            scored.sort(key=lambda row: (-row[1], row[0].organisation.lower(), row[0].target_id))
            for rank, (item, score, causes) in enumerate(scored, start=1):
                existing = self.connection.execute(
                    "SELECT * FROM target_memory WHERE target_id=?", (item.target_id,)
                ).fetchone()
                previous_rank = existing["current_rank"] if existing else None
                previous_score = existing["current_score"] if existing else None
                rank_delta = (int(previous_rank) - rank) if previous_rank is not None else None
                score_delta = round(score - float(previous_score), 6) if previous_score is not None else None
                receipt = RankReceipt(
                    receipt_id=stable_id("RANK", item.target_id, timestamp, score, rank),
                    target_id=item.target_id,
                    organisation=item.organisation,
                    domain_id=item.domain_id,
                    previous_rank=previous_rank,
                    current_rank=rank,
                    score=score,
                    previous_score=previous_score,
                    rank_delta=rank_delta,
                    score_delta=score_delta,
                    causes=tuple(causes),
                    observed_at=timestamp,
                )
                receipts.append(receipt)
                if existing is None:
                    self.upsert_target(
                        target_id=item.target_id,
                        organisation=item.organisation,
                        domain_id=item.domain_id,
                        seen_at=timestamp,
                        metadata={"rank_features": asdict(item)},
                    )
                self.connection.execute(
                    """
                    UPDATE target_memory
                    SET previous_score=current_score, previous_rank=current_rank,
                        current_score=?, current_rank=?, updated_at=?, metadata_json=?
                    WHERE target_id=?
                    """,
                    (
                        score,
                        rank,
                        utc_now(),
                        canonical_json({"rank_features": asdict(item), "rank_causes": causes}),
                        item.target_id,
                    ),
                )
                self.connection.execute(
                    """
                    INSERT OR REPLACE INTO rank_receipts (
                      receipt_id, target_id, organisation, domain_id, previous_rank,
                      current_rank, score, previous_score, rank_delta, score_delta,
                      causes_json, observed_at, authority_created, execution_performed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
                    """,
                    (
                        receipt.receipt_id,
                        receipt.target_id,
                        receipt.organisation,
                        receipt.domain_id,
                        receipt.previous_rank,
                        receipt.current_rank,
                        receipt.score,
                        receipt.previous_score,
                        receipt.rank_delta,
                        receipt.score_delta,
                        canonical_json(receipt.causes),
                        receipt.observed_at,
                    ),
                )
        self.connection.commit()
        return receipts

    def record_habitat(
        self,
        *,
        platform: str,
        canonical_name: str,
        source_ref: str,
        domain_id: str,
        access_state: str,
        terms_state: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        habitat_id = stable_id("HAB", platform, canonical_name, source_ref)
        requires_operator = access_state in {
            "LOGIN_REQUIRED",
            "MEMBERSHIP_REQUIRED",
            "INVITE_REQUIRED",
            "API_PERMISSION_REQUIRED",
            "BOT_INSTALL_REQUIRES_ADMIN",
        }
        if access_state == "REFUSE_AUTOMATION" or terms_state in {"TERMS_RESTRICTED", "REFUSE"}:
            action = "OBSERVE_ONLY_OR_REFUSE"
        elif requires_operator:
            action = "NEEDS_YOU"
        else:
            action = "PUBLIC_READ_ONLY"
        self.connection.execute(
            """
            INSERT INTO habitat_memory (
              habitat_id, platform, canonical_name, source_ref, domain_id,
              access_state, terms_state, first_seen_at, last_seen_at,
              recommended_action, payload_json, authority_created
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            ON CONFLICT(habitat_id) DO UPDATE SET
              domain_id=excluded.domain_id,
              access_state=excluded.access_state,
              terms_state=excluded.terms_state,
              last_seen_at=excluded.last_seen_at,
              recommended_action=excluded.recommended_action,
              payload_json=excluded.payload_json
            """,
            (
                habitat_id,
                platform,
                canonical_name,
                source_ref,
                domain_id,
                access_state,
                terms_state,
                now,
                now,
                action,
                canonical_json(payload or {}),
            ),
        )
        self.connection.commit()
        return {
            "habitat_id": habitat_id,
            "recommended_action": action,
            "authority_created": False,
            "posting_authority": "NONE",
            "dm_authority": "NONE",
        }

    def record_offer(
        self,
        *,
        source_kind: str,
        source_ref: str,
        observed_at: str,
        domain_id: str,
        seller: str = "",
        morphology: str = "",
        headline: str = "",
        pitch_angle: str = "",
        audience: str = "",
        price_value: float | None = None,
        price_currency: str = "",
        price_basis: str = "",
        payload: dict[str, Any] | None = None,
    ) -> str:
        body = payload or {}
        offer_id = stable_id("OFF", source_kind, source_ref, observed_at, seller, headline)
        self.connection.execute(
            """
            INSERT OR REPLACE INTO offer_observations (
              offer_observation_id, source_kind, source_ref, observed_at, seller,
              domain_id, morphology, headline, pitch_angle, audience, price_value,
              price_currency, price_basis, payload_json, provenance_digest,
              authority_created
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                offer_id,
                source_kind,
                source_ref,
                observed_at,
                seller or None,
                domain_id or None,
                morphology or None,
                headline or None,
                pitch_angle or None,
                audience or None,
                price_value,
                price_currency or None,
                price_basis or None,
                canonical_json(body),
                digest_payload(body),
            ),
        )
        self.connection.commit()
        return offer_id

    def record_discovery_candidate(
        self,
        *,
        source_kind: str,
        source_ref: str,
        candidate_kind: str,
        display_name: str,
        domain_id: str = "",
        morphology: str = "",
        score: float = 0.0,
        state: str = "UNRESOLVED_ENTITY",
        observed_at: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> str:
        """Remember a public-world discovery without promoting it to a lead/target.

        Discovery is knowledge only. A candidate remains unresolved until a separate
        resolver establishes organisation/buyer-unit identity and a governed ranking
        pass admits it.
        """
        body = payload or {}
        timestamp = observed_at or utc_now()
        candidate_id = stable_id(
            "DISC", source_kind, source_ref, candidate_kind, display_name, domain_id, morphology
        )
        digest = digest_payload(body)
        self.connection.execute(
            """
            INSERT INTO discovery_candidates (
              candidate_id, source_kind, source_ref, candidate_kind, display_name,
              domain_id, morphology, score, state, first_seen_at, last_seen_at,
              payload_json, provenance_digest, authority_created
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            ON CONFLICT(candidate_id) DO UPDATE SET
              score=excluded.score,
              state=excluded.state,
              last_seen_at=excluded.last_seen_at,
              payload_json=excluded.payload_json,
              provenance_digest=excluded.provenance_digest
            """,
            (
                candidate_id,
                source_kind,
                source_ref,
                candidate_kind,
                display_name,
                domain_id or None,
                morphology or None,
                clamp(score),
                state,
                timestamp,
                timestamp,
                canonical_json(body),
                digest,
            ),
        )
        self.connection.commit()
        return candidate_id

    def write_cycle_receipt(self, started_at: str, mode: str, summary: dict[str, Any]) -> dict[str, Any]:
        completed = utc_now()
        payload = {
            "schema": "dio.market_sensorium.cycle_receipt.v1",
            "started_at": started_at,
            "completed_at": completed,
            "mode": mode,
            "summary": summary,
            "authority_created": False,
            "external_effects": False,
        }
        payload["receipt_digest"] = digest_payload(payload)
        payload["cycle_id"] = stable_id("MSC", started_at, completed, payload["receipt_digest"])
        self.connection.execute(
            """
            INSERT OR REPLACE INTO cycle_runs (
              cycle_id, started_at, completed_at, mode, summary_json,
              receipt_digest, authority_created, external_effects
            ) VALUES (?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                payload["cycle_id"],
                started_at,
                completed,
                mode,
                canonical_json(summary),
                payload["receipt_digest"],
            ),
        )
        self.connection.commit()
        return payload

    def summary(self) -> dict[str, Any]:
        c = self.connection
        return {
            "targets": c.execute("SELECT COUNT(*) FROM target_memory").fetchone()[0],
            "observations": c.execute("SELECT COUNT(*) FROM observations").fetchone()[0],
            "habitats": c.execute("SELECT COUNT(*) FROM habitat_memory").fetchone()[0],
            "offers": c.execute("SELECT COUNT(*) FROM offer_observations").fetchone()[0],
            "discovery_candidates": c.execute("SELECT COUNT(*) FROM discovery_candidates").fetchone()[0],
            "unresolved_discoveries": c.execute("SELECT COUNT(*) FROM discovery_candidates WHERE state='UNRESOLVED_ENTITY'").fetchone()[0],
            "rank_receipts": c.execute("SELECT COUNT(*) FROM rank_receipts").fetchone()[0],
            "needs_you_habitats": c.execute("SELECT COUNT(*) FROM habitat_memory WHERE recommended_action='NEEDS_YOU'").fetchone()[0],
            "silent_targets": c.execute("SELECT COUNT(*) FROM target_memory WHERE silence_state IN ('WEAK_NEGATIVE_SIGNAL','CHANNEL_OFFER_DECAY','DORMANT')").fetchone()[0],
            "authority_created": False,
            "external_effects": False,
        }


def score_target(features: TargetFeatures, weights: dict[str, float] | None = None) -> tuple[float, list[str]]:
    active = weights or DEFAULT_WEIGHTS
    positive: list[tuple[str, float]] = []
    for name, weight in active.items():
        value = clamp(getattr(features, name, 0.0))
        positive.append((name, value * weight))
    penalties = {
        "silence_penalty": clamp(features.silence_penalty, 0.0, 0.35),
        "rejection_penalty": clamp(features.rejection_penalty, 0.0, 0.60),
        "authority_penalty": clamp(features.authority_penalty, 0.0, 0.60),
        "stale_signal_penalty": clamp(features.stale_signal_penalty, 0.0, 0.30),
    }
    raw = sum(value for _, value in positive) - sum(penalties.values())
    score = round(clamp(raw), 6)
    causes: list[str] = []
    for name, contribution in sorted(positive, key=lambda item: (-item[1], item[0]))[:5]:
        if contribution >= 0.015:
            causes.append(f"+{name}:{contribution:.3f}")
    for name, penalty in penalties.items():
        if penalty > 0:
            causes.append(f"-{name}:{penalty:.3f}")
    if not causes:
        causes.append("insufficient_evidence")
    return score, causes


def load_baseline_csv(path: Path) -> list[SeedCandidate]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result: list[SeedCandidate] = []
    for row in rows:
        result.append(
            SeedCandidate(
                seed_id=row["seed_id"],
                domain_id=row["domain_id"],
                domain_name=row["domain_name"],
                rank=int(row["rank"]),
                organisation=row["organisation"],
                organisation_kind=row["organisation_kind"],
                geography=row["geography"],
                website=row["website"],
                engagement_mode=row["engagement_mode"],
                rationale=row["rationale"],
                provenance_kind=row.get("provenance_kind") or "CURATED_BASELINE_PRIOR",
                evidence_state=row.get("evidence_state") or "SEED_PRIOR_REQUIRES_REFRESH",
                authority_created=str(row.get("authority_created") or "false").lower() == "true",
            )
        )
    return result
