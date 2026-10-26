from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .core import MarketSensoriumStore, canonical_json, digest_payload, stable_id, utc_now


DOMAIN_BY_PRODUCT = {
    "homs": "D902",
    "homs_learning": "D906",
    "evidex": "D1712",
    "sophia": "D1708",
    "vamp": "D1506",
}

SELF_OFFER_MARKERS = (
    "we produce",
    "we provide",
    "we offer",
    "our service",
    "our services",
    "our platform",
    "our software",
    "our tool",
    "platform she built",
    "platform i built",
    "we built",
    "i built",
    "commission your",
    "generate your",
    "try our",
    "book a",
    "book your",
    "get started",
    "sign up",
)

CTA_MARKERS = (
    "commission your",
    "generate your",
    "contact us",
    "contact:",
    "email:",
    "website:",
    "book a",
    "book your",
    "get started",
    "sign up",
    "no credit card",
    "http://",
    "https://",
)

STRONG_FREE_PATTERNS = (
    re.compile(r"\bfirst\b.{0,90}\bfree\b", re.IGNORECASE | re.DOTALL),
    re.compile(r"\bfree\b.{0,50}\bno\s+credit\s+card\b", re.IGNORECASE | re.DOTALL),
    re.compile(r"\bfree\s+(?:trial|demo|assessment|report|consultation)\b", re.IGNORECASE),
    re.compile(r"\bgenerate\b.{0,90}\bfree\b", re.IGNORECASE | re.DOTALL),
)

MONEY_PATTERNS = (
    ("ZAR", re.compile(r"(?<![A-Za-z0-9])(?:ZAR|R)\s*([0-9][0-9,]*(?:\.\d{1,2})?)\b", re.IGNORECASE)),
    ("USD", re.compile(r"(?<![A-Za-z0-9])(?:USD\s*|\$\s*)([0-9][0-9,]*(?:\.\d{1,2})?)\b", re.IGNORECASE)),
    ("EUR", re.compile(r"(?<![A-Za-z0-9])(?:EUR\s*|€\s*)([0-9][0-9,]*(?:\.\d{1,2})?)\b", re.IGNORECASE)),
    ("GBP", re.compile(r"(?<![A-Za-z0-9])(?:GBP\s*|£\s*)([0-9][0-9,]*(?:\.\d{1,2})?)\b", re.IGNORECASE)),
)


def _schema(store: MarketSensoriumStore) -> None:
    store.connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS competitive_offer_events (
          event_id TEXT PRIMARY KEY,
          offer_key TEXT NOT NULL,
          source_kind TEXT NOT NULL,
          source_ref TEXT NOT NULL,
          source_document_ref TEXT NOT NULL,
          observed_at TEXT NOT NULL,
          source_published_at TEXT,
          seller TEXT NOT NULL,
          seller_role TEXT NOT NULL,
          seller_role_basis TEXT NOT NULL,
          domain_id TEXT,
          morphology TEXT,
          headline TEXT NOT NULL,
          pitch_angle TEXT,
          cta TEXT,
          audience TEXT,
          price_state TEXT NOT NULL,
          price_value REAL,
          price_currency TEXT,
          price_basis TEXT,
          evidence_confidence REAL NOT NULL,
          access_state TEXT NOT NULL,
          terms_state TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          provenance_digest TEXT NOT NULL,
          authority_created INTEGER NOT NULL DEFAULT 0,
          market_demand_claimed INTEGER NOT NULL DEFAULT 0,
          realised_price_claimed INTEGER NOT NULL DEFAULT 0,
          willingness_to_pay_claimed INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS competitive_offer_events_offer_idx
          ON competitive_offer_events(offer_key, observed_at);
        CREATE INDEX IF NOT EXISTS competitive_offer_events_domain_idx
          ON competitive_offer_events(domain_id, observed_at);

        CREATE TABLE IF NOT EXISTS competitive_offer_memory (
          offer_key TEXT PRIMARY KEY,
          seller TEXT NOT NULL,
          seller_role TEXT NOT NULL,
          domain_id TEXT,
          morphology TEXT,
          canonical_headline TEXT NOT NULL,
          first_seen_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          observation_count INTEGER NOT NULL,
          distinct_source_count INTEGER NOT NULL,
          distinct_content_count INTEGER NOT NULL,
          latest_price_state TEXT NOT NULL,
          latest_price_value REAL,
          latest_price_currency TEXT,
          latest_price_basis TEXT,
          persistence_state TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          authority_created INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    store.connection.commit()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _context_basis(text: str, match_start: int, match_end: int) -> str:
    context = text[max(0, match_start - 90): min(len(text), match_end + 90)].lower()
    if re.search(r"(?:per|/|a)\s*month|monthly", context):
        return "PER_MONTH"
    if re.search(r"(?:per|/|a)\s*year|annual|annually", context):
        return "PER_YEAR"
    if re.search(r"(?:per|/|a)\s*(?:report|document|project|case|video|session|hour|user|seat)", context):
        unit = re.search(r"(?:per|/|a)\s*(report|document|project|case|video|session|hour|user|seat)", context)
        return f"PER_{unit.group(1).upper()}" if unit else "EXPLICIT_UNIT"
    if "once-off" in context or "one-time" in context or "one time" in context:
        return "ONCE_OFF"
    return "BASIS_NOT_EXPLICIT"


def extract_advertised_price(text: str) -> dict[str, Any]:
    """Parse only explicit asking-price language.

    Returned values are advertised offer evidence only. They are never interpreted
    as realised prices, market prices, willingness to pay, revenue or demand.
    """
    source = _text(text)
    for currency, pattern in MONEY_PATTERNS:
        match = pattern.search(source)
        if not match:
            continue
        try:
            value = float(match.group(1).replace(",", ""))
        except (TypeError, ValueError):
            return {
                "price_state": "PRICE_PARSE_ERROR",
                "advertised_price_observed": False,
                "price_value": None,
                "price_currency": "",
                "price_basis": "UNKNOWN",
                "evidence_text": match.group(0),
            }
        return {
            "price_state": "EXPLICIT_MONETARY_ADVERTISED",
            "advertised_price_observed": True,
            "price_value": value,
            "price_currency": currency,
            "price_basis": _context_basis(source, match.start(), match.end()),
            "evidence_text": source[max(0, match.start() - 70): min(len(source), match.end() + 70)].strip(),
        }

    for pattern in STRONG_FREE_PATTERNS:
        match = pattern.search(source)
        if match:
            return {
                "price_state": "EXPLICIT_FREE_ADVERTISED",
                "advertised_price_observed": True,
                "price_value": 0.0,
                "price_currency": "",
                "price_basis": "FREE_ENTRY_OR_TRIAL",
                "evidence_text": match.group(0).strip(),
            }

    return {
        "price_state": "PRICE_NOT_OBSERVED",
        "advertised_price_observed": False,
        "price_value": None,
        "price_currency": "",
        "price_basis": "NOT_OBSERVED",
        "evidence_text": "",
    }


def _self_offer_markers(text: str) -> tuple[list[str], list[str]]:
    lowered = text.lower()
    providers = sorted({marker for marker in SELF_OFFER_MARKERS if marker in lowered})
    ctas = sorted({marker for marker in CTA_MARKERS if marker in lowered})
    return providers, ctas


def _extract_snippet(text: str, markers: tuple[str, ...], limit: int = 320) -> str:
    source = re.sub(r"\s+", " ", _text(text)).strip()
    lowered = source.lower()
    for marker in markers:
        pos = lowered.find(marker)
        if pos >= 0:
            start = max(0, pos - 90)
            return source[start: start + limit].strip()
    return source[:limit]


def _offer_key(seller: str, domain_id: str, headline: str) -> str:
    return stable_id("COFFER", _normalise(seller), domain_id, _normalise(headline))


def _seller(record: dict[str, Any]) -> str:
    # The first MS-5 lane intentionally uses provider-owned YouTube channels only.
    # A publisher, article author or mentioned organisation is not auto-promoted to seller.
    return _text(record.get("channel_title") or record.get("channel"))


def _upsert_memory(
    store: MarketSensoriumStore,
    *,
    offer_key: str,
    seller: str,
    domain_id: str,
    morphology: str,
    headline: str,
    price: dict[str, Any],
) -> None:
    stats = store.connection.execute(
        """
        SELECT MIN(observed_at) AS first_seen, MAX(observed_at) AS last_seen,
               COUNT(*) AS observations, COUNT(DISTINCT source_ref) AS sources,
               COUNT(DISTINCT provenance_digest) AS contents
        FROM competitive_offer_events WHERE offer_key=?
        """,
        (offer_key,),
    ).fetchone()
    observations = int(stats["observations"] or 0)
    persistence = "REPEATED_OBSERVATION" if observations > 1 else "SINGLE_OBSERVATION"
    payload = {
        "offer_key": offer_key,
        "seller_role": "PROVIDER_OR_SELLER_CANDIDATE",
        "advertised_offer_only": True,
        "advertised_price_is_market_price": False,
        "advertised_price_is_realised_price": False,
        "willingness_to_pay_proved": False,
        "market_demand_claimed": False,
        "authority_created": False,
    }
    store.connection.execute(
        """
        INSERT INTO competitive_offer_memory (
          offer_key,seller,seller_role,domain_id,morphology,canonical_headline,
          first_seen_at,last_seen_at,observation_count,distinct_source_count,
          distinct_content_count,latest_price_state,latest_price_value,
          latest_price_currency,latest_price_basis,persistence_state,payload_json,
          authority_created
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)
        ON CONFLICT(offer_key) DO UPDATE SET
          last_seen_at=excluded.last_seen_at,
          observation_count=excluded.observation_count,
          distinct_source_count=excluded.distinct_source_count,
          distinct_content_count=excluded.distinct_content_count,
          latest_price_state=excluded.latest_price_state,
          latest_price_value=excluded.latest_price_value,
          latest_price_currency=excluded.latest_price_currency,
          latest_price_basis=excluded.latest_price_basis,
          persistence_state=excluded.persistence_state,
          payload_json=excluded.payload_json
        """,
        (
            offer_key,
            seller,
            "PROVIDER_OR_SELLER_CANDIDATE",
            domain_id or None,
            morphology or None,
            headline,
            stats["first_seen"] or utc_now(),
            stats["last_seen"] or utc_now(),
            observations,
            int(stats["sources"] or 0),
            int(stats["contents"] or 0),
            price["price_state"],
            price["price_value"],
            price["price_currency"] or None,
            price["price_basis"],
            persistence,
            canonical_json(payload),
        ),
    )


def observe_competitive_offers(root: Path, store: MarketSensoriumStore) -> dict[str, Any]:
    """Extract source-bound provider offers from already-governed public market signals.

    This function performs no network access. It reads the existing connector receipts
    and records only provider-owned, self-promotional offer evidence. The initial lane
    deliberately excludes article publishers and organisations merely mentioned by a
    third party, because source identity is not seller identity.
    """
    _schema(store)
    root = Path(root).resolve()
    campaign_root = root / "campaigns" / "dio_market_loop" / "wave4" / "campaigns"
    counts: Counter[str] = Counter()
    sellers: set[str] = set()
    price_states: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []

    for path in sorted(campaign_root.glob("*/LIVE_MARKET_SIGNALS.json")):
        payload = _read_json(path)
        if not payload:
            continue
        counts["signal_files_examined"] += 1
        product_layer = _text(payload.get("product_layer"))
        domain_id = DOMAIN_BY_PRODUCT.get(product_layer, "D1710")
        morphology = product_layer
        search = payload.get("search") if isinstance(payload.get("search"), dict) else {}
        observation_time = _text(search.get("finished_at") or payload.get("observed_at") or payload.get("generated_at")) or utc_now()
        source_document_ref = str(path.relative_to(root))

        for record in payload.get("records") or []:
            if not isinstance(record, dict):
                continue
            counts["public_records_examined"] += 1
            relevance = record.get("relevance") if isinstance(record.get("relevance"), dict) else {}
            if relevance and relevance.get("passed") is False:
                counts["records_rejected_relevance"] += 1
                continue
            seller = _seller(record)
            headline = _text(record.get("title"))
            description = _text(record.get("description"))
            source_ref = _text(record.get("url"))
            if not seller or not headline or not description or not source_ref:
                counts["records_rejected_missing_provider_evidence"] += 1
                continue
            provider_markers, cta_markers = _self_offer_markers(description)
            if not provider_markers or not cta_markers:
                counts["records_rejected_not_self_offer"] += 1
                continue

            price = extract_advertised_price(description)
            if price["price_state"] == "PRICE_PARSE_ERROR":
                counts["price_normalization_errors"] += 1
            if price["advertised_price_observed"]:
                counts["explicit_advertised_price_observations"] += 1
            price_states[price["price_state"]] += 1

            pitch = _extract_snippet(description, SELF_OFFER_MARKERS)
            cta = _extract_snippet(description, CTA_MARKERS, limit=220)
            confidence = min(
                0.98,
                0.62
                + min(0.16, len(provider_markers) * 0.04)
                + min(0.12, len(cta_markers) * 0.03)
                + (0.06 if price["advertised_price_observed"] else 0.0),
            )
            offer_key = _offer_key(seller, domain_id, headline)
            event_payload = {
                "schema": "dio.market_sensorium.competitive_offer_evidence.v1",
                "offer_key": offer_key,
                "seller": seller,
                "seller_role": "PROVIDER_OR_SELLER_CANDIDATE",
                "seller_role_basis": "CHANNEL_SELF_PROMOTIONAL_DESCRIPTION",
                "headline": headline,
                "pitch_angle": pitch,
                "cta": cta,
                "audience": "",
                "relevance_terms": list(relevance.get("matched_terms") or []),
                "price": price,
                "source_published_at": _text(record.get("published_at")),
                "source_document_ref": source_document_ref,
                "access_state": "PUBLIC_READ",
                "terms_state": "CONNECTOR_GOVERNED",
                "evidence_confidence": round(confidence, 6),
                "advertised_offer_only": True,
                "offer_prevalence_is_demand": False,
                "advertised_price_is_market_price": False,
                "advertised_price_is_realised_price": False,
                "willingness_to_pay_proved": False,
                "market_demand_claimed": False,
                "seller_promoted_to_target": False,
                "authority_created": False,
                "external_effects": False,
            }
            provenance = digest_payload(event_payload)
            event_id = stable_id("COEV", offer_key, source_ref, observation_time, provenance)
            existed = store.connection.execute(
                "SELECT event_id FROM competitive_offer_events WHERE event_id=?",
                (event_id,),
            ).fetchone()
            store.connection.execute(
                """
                INSERT OR IGNORE INTO competitive_offer_events (
                  event_id,offer_key,source_kind,source_ref,source_document_ref,
                  observed_at,source_published_at,seller,seller_role,seller_role_basis,
                  domain_id,morphology,headline,pitch_angle,cta,audience,price_state,
                  price_value,price_currency,price_basis,evidence_confidence,
                  access_state,terms_state,payload_json,provenance_digest,
                  authority_created,market_demand_claimed,realised_price_claimed,
                  willingness_to_pay_claimed
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,0,0,0)
                """,
                (
                    event_id,
                    offer_key,
                    "YOUTUBE_PUBLIC_COMPETITIVE_OFFER",
                    source_ref,
                    source_document_ref,
                    observation_time,
                    _text(record.get("published_at")) or None,
                    seller,
                    "PROVIDER_OR_SELLER_CANDIDATE",
                    "CHANNEL_SELF_PROMOTIONAL_DESCRIPTION",
                    domain_id,
                    morphology,
                    headline,
                    pitch,
                    cta,
                    None,
                    price["price_state"],
                    price["price_value"],
                    price["price_currency"] or None,
                    price["price_basis"],
                    round(confidence, 6),
                    "PUBLIC_READ",
                    "CONNECTOR_GOVERNED",
                    canonical_json(event_payload),
                    provenance,
                ),
            )
            if existed is None:
                store.record_offer(
                    source_kind="YOUTUBE_PUBLIC_COMPETITIVE_OFFER",
                    source_ref=source_ref,
                    observed_at=observation_time,
                    domain_id=domain_id,
                    seller=seller,
                    morphology=morphology,
                    headline=headline,
                    pitch_angle=pitch,
                    audience="",
                    price_value=price["price_value"],
                    price_currency=price["price_currency"],
                    price_basis=price["price_basis"],
                    payload=event_payload,
                )
                counts["new_events_persisted"] += 1
            else:
                counts["existing_events_reobserved"] += 1

            _upsert_memory(
                store,
                offer_key=offer_key,
                seller=seller,
                domain_id=domain_id,
                morphology=morphology,
                headline=headline,
                price=price,
            )
            counts["source_bound_offer_observations"] += 1
            sellers.add(seller.casefold())
            if len(examples) < 12:
                examples.append(
                    {
                        "seller": seller,
                        "domain_id": domain_id,
                        "headline": headline,
                        "offer_key": offer_key,
                        "price_state": price["price_state"],
                        "price_value": price["price_value"],
                        "price_currency": price["price_currency"],
                        "price_basis": price["price_basis"],
                        "seller_role_basis": "CHANNEL_SELF_PROMOTIONAL_DESCRIPTION",
                        "source_ref": source_ref,
                        "evidence_confidence": round(confidence, 6),
                        "market_demand_claimed": False,
                        "authority_created": False,
                    }
                )

    store.connection.commit()
    memory_count = int(store.connection.execute("SELECT COUNT(*) FROM competitive_offer_memory").fetchone()[0])
    event_count = int(store.connection.execute("SELECT COUNT(*) FROM competitive_offer_events").fetchone()[0])
    legacy_offer_count = int(store.connection.execute("SELECT COUNT(*) FROM offer_observations").fetchone()[0])
    multi_source = int(
        store.connection.execute(
            "SELECT COUNT(*) FROM competitive_offer_memory WHERE distinct_source_count>1"
        ).fetchone()[0]
    )

    return {
        "schema": "dio.market_sensorium.competitive_offer_intelligence.v1",
        **dict(sorted(counts.items())),
        "canonical_competitive_offers": memory_count,
        "persisted_competitive_offer_events": event_count,
        "legacy_offer_observation_count": legacy_offer_count,
        "unique_sellers_observed_this_run": len(sellers),
        "price_state_counts": dict(sorted(price_states.items())),
        "multi_source_dedupe_groups": multi_source,
        "provider_role_confusion": 0,
        "publisher_auto_promoted_to_seller": False,
        "mentioned_organisation_auto_promoted_to_seller": False,
        "seller_promoted_to_target": False,
        "source_bound": True,
        "advertised_offer_is_demand": False,
        "advertised_price_is_market_price": False,
        "advertised_price_is_realised_price": False,
        "willingness_to_pay_proved": False,
        "commercial_success_proved": False,
        "market_demand_claimed": False,
        "best_offer_claimed": False,
        "authority_created": False,
        "external_effects": False,
        "examples": examples,
    }
