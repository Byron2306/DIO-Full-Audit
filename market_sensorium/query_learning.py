from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .core import MarketSensoriumStore, canonical_json, digest_payload, stable_id, utc_now

QUERY_KINDS = (
    "BASELINE_GAP",
    "ENTITY_RESOLUTION",
    "HABITAT_CORROBORATION",
    "COMPETITIVE_OFFER",
    "HIVENANCE_RESEARCH_TEST",
    "BROADEN_DISCOVERY",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalise_query(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _domain_rows(path: Path) -> dict[str, dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        str(row.get("domain_id") or ""): row
        for row in rows
        if row.get("domain_type") == "DOMAIN"
        and row.get("atlas_status") != "UNKNOWN_DOMAIN_TEST_ONLY"
        and row.get("domain_id")
    }


def _history(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    return payload if payload else {"schema": "dio.market_sensorium.domain_query_history.v1", "domains": {}}


def _safe_rows(store: MarketSensoriumStore, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
    try:
        return store.connection.execute(sql, params).fetchall()
    except Exception:
        return []


def _schema(store: MarketSensoriumStore) -> None:
    store.connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS learned_query_events (
          query_id TEXT PRIMARY KEY,
          domain_id TEXT NOT NULL,
          domain_name TEXT NOT NULL,
          query_kind TEXT NOT NULL,
          query_text TEXT NOT NULL,
          rationale TEXT NOT NULL,
          evidence_refs_json TEXT NOT NULL,
          evidence_digest TEXT NOT NULL,
          source_driver_count INTEGER NOT NULL,
          novelty_score REAL NOT NULL,
          parent_query_id TEXT,
          created_at TEXT NOT NULL,
          selected INTEGER NOT NULL DEFAULT 0,
          execution_performed INTEGER NOT NULL DEFAULT 0,
          authority_created INTEGER NOT NULL DEFAULT 0,
          market_demand_claimed INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS learned_query_events_domain_idx
          ON learned_query_events(domain_id, created_at);

        CREATE TABLE IF NOT EXISTS learned_query_memory (
          domain_id TEXT PRIMARY KEY,
          selected_query_id TEXT NOT NULL,
          selected_query_text TEXT NOT NULL,
          query_kind TEXT NOT NULL,
          previous_query_text TEXT,
          evidence_digest TEXT NOT NULL,
          source_driver_count INTEGER NOT NULL,
          novelty_score REAL NOT NULL,
          updated_at TEXT NOT NULL,
          execution_authority TEXT NOT NULL DEFAULT 'NONE',
          authority_created INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    store.connection.commit()


def _evidence_by_domain(store: MarketSensoriumStore) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "unresolved": [],
        "habitats": [],
        "offers": [],
        "hivenance": [],
    })

    for row in _safe_rows(
        store,
        """
        SELECT candidate_id, domain_id, display_name, source_kind, source_ref, score, last_seen_at
        FROM discovery_candidates
        WHERE state='UNRESOLVED_ENTITY' AND domain_id IS NOT NULL
        ORDER BY score DESC, last_seen_at DESC
        """,
    ):
        evidence[str(row["domain_id"])]["unresolved"].append({
            "kind": "UNRESOLVED_DISCOVERY",
            "id": row["candidate_id"],
            "name": row["display_name"],
            "source_kind": row["source_kind"],
            "source_ref": row["source_ref"],
        })

    for row in _safe_rows(
        store,
        """
        SELECT habitat_key, domain_id, platform, habitat_kind, canonical_name, source_ref,
               seller_association_state, intelligence_score
        FROM market_habitat_memory_v2
        WHERE domain_id IS NOT NULL AND permission_ladder_state='PUBLIC_OBSERVABLE'
        ORDER BY intelligence_score DESC, last_seen_at DESC
        """,
    ):
        evidence[str(row["domain_id"])]["habitats"].append({
            "kind": "PUBLIC_HABITAT",
            "id": row["habitat_key"],
            "platform": row["platform"],
            "habitat_kind": row["habitat_kind"],
            "name": row["canonical_name"],
            "source_ref": row["source_ref"],
            "seller_association_state": row["seller_association_state"],
        })

    for row in _safe_rows(
        store,
        """
        SELECT event_id, domain_id, seller, headline, source_ref, price_state
        FROM competitive_offer_events
        WHERE domain_id IS NOT NULL
        ORDER BY observed_at DESC
        """,
    ):
        evidence[str(row["domain_id"])]["offers"].append({
            "kind": "COMPETITIVE_OFFER",
            "id": row["event_id"],
            "seller": row["seller"],
            "headline": row["headline"],
            "source_ref": row["source_ref"],
            "price_state": row["price_state"],
        })

    for row in _safe_rows(
        store,
        """
        SELECT hypothesis_id, domain_id, hypothesis_type, bounded_test_json, evidence_digest,
               research_priority_score
        FROM commercial_hypotheses
        WHERE domain_id IS NOT NULL AND hypothesis_state='ACTIVE_RESEARCH_HYPOTHESIS'
        ORDER BY research_priority_score DESC, observed_at DESC
        """,
    ):
        try:
            bounded = json.loads(row["bounded_test_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            bounded = {}
        evidence[str(row["domain_id"])]["hivenance"].append({
            "kind": "HIVENANCE_RESEARCH_TEST",
            "id": row["hypothesis_id"],
            "hypothesis_type": row["hypothesis_type"],
            "test_kind": bounded.get("test_kind"),
            "instruction": bounded.get("instruction"),
            "evidence_digest": row["evidence_digest"],
        })

    return evidence


def _query_candidates(
    *,
    domain_id: str,
    domain: dict[str, str],
    weak: bool,
    prior_query: str,
    evidence: dict[str, Any],
) -> list[dict[str, Any]]:
    name = _text(domain.get("domain_name"))
    family = _text(domain.get("domain_family")).replace("_", " ").lower()
    candidates: list[dict[str, Any]] = []

    def add(kind: str, query: str, rationale: str, refs: list[dict[str, Any]], priority: float) -> None:
        normalised = _normalise_query(query)
        prior_normalised = _normalise_query(prior_query)
        novelty = 0.0 if prior_normalised and normalised == prior_normalised else 1.0
        if prior_normalised and normalised != prior_normalised:
            old_tokens = set(prior_normalised.split())
            new_tokens = set(normalised.split())
            union = old_tokens | new_tokens
            novelty = 1.0 if not union else round(1.0 - len(old_tokens & new_tokens) / len(union), 6)
        candidates.append({
            "query_kind": kind,
            "query": query.strip(),
            "rationale": rationale,
            "evidence_refs": refs[:12],
            "priority": round(priority, 6),
            "novelty_score": novelty,
        })

    if weak:
        add(
            "BASELINE_GAP",
            f'"{name}" South Africa organisations workflow problems providers',
            "ATLAS baseline remains family-fallback-only, so discovery should seek concrete organisations and workflow problems rather than reinforce the seed prior.",
            [{"kind": "ATLAS_BASELINE_GAP", "domain_id": domain_id}],
            0.78,
        )

    unresolved = list(evidence.get("unresolved") or [])
    if unresolved:
        add(
            "ENTITY_RESOLUTION",
            f'"{name}" South Africa organisation association regulator provider services',
            "Unresolved public discoveries exist in this domain; the next query should improve entity-role evidence rather than increase ambiguous headline volume.",
            unresolved[:8],
            min(0.92, 0.66 + 0.02 * len(unresolved)),
        )

    habitats = list(evidence.get("habitats") or [])
    if habitats:
        platforms = sorted({str(item.get("platform") or "") for item in habitats if item.get("platform")})
        provider_habitats = [
            item for item in habitats
            if item.get("seller_association_state") == "PROVIDER_OR_SELLER_ACTIVITY_OBSERVED"
        ]
        suffix = " providers services" if provider_habitats else " associations channels publications"
        add(
            "HABITAT_CORROBORATION",
            f'"{name}" South Africa{suffix} {' '.join(platforms[:2])}'.strip(),
            "Public habitat evidence exists; seek independent recurring sources or providers instead of treating individual content URLs as durable habitats.",
            habitats[:8],
            min(0.90, 0.58 + 0.02 * len(habitats) + (0.08 if provider_habitats else 0.0)),
        )

    offers = list(evidence.get("offers") or [])
    if offers:
        sellers = sorted({str(item.get("seller") or "") for item in offers if item.get("seller")})
        add(
            "COMPETITIVE_OFFER",
            f'"{name}" South Africa software service pricing alternatives providers',
            "Competitive provider offers have been observed; search for additional provider-owned offer evidence and explicit asking-price language without treating listings as demand.",
            offers[:8],
            min(0.95, 0.70 + 0.03 * len(sellers)),
        )

    hivenance = list(evidence.get("hivenance") or [])
    if hivenance:
        types = {str(item.get("hypothesis_type") or "") for item in hivenance}
        test_kinds = {str(item.get("test_kind") or "") for item in hivenance}
        terms: list[str] = []
        if "BUYER" in types or "COMPARE_BUYER_ROLE_EVIDENCE" in test_kinds:
            terms.extend(["buyer unit", "procurement", "workflow owner"])
        if "COMPETITION" in types or "TRACK_RELATIVE_FIELD_PERSISTENCE" in test_kinds:
            terms.extend(["providers", "competitors"])
        if "PRODUCT" in types or "COMPARE_WORKFLOW_CAPABILITY_FIT" in test_kinds:
            terms.extend(["workflow problem", "service"])
        if "HABITAT" in types:
            terms.extend(["association", "community"])
        if not terms:
            terms = ["organisations", "services", "challenges"]
        unique_terms = list(dict.fromkeys(terms))[:5]
        add(
            "HIVENANCE_RESEARCH_TEST",
            f'"{name}" South Africa {' '.join(unique_terms)}',
            "Hivenance has active bounded research questions in this domain; convert those unresolved questions into a read-only discovery query rather than treating the selected hypothesis as truth.",
            hivenance[:8],
            min(0.96, 0.72 + 0.01 * len(hivenance)),
        )

    if not candidates:
        add(
            "BROADEN_DISCOVERY",
            f'"{name}" South Africa {family} organisations services challenges',
            "No stronger adaptive evidence driver is available, so retain a bounded broad discovery query.",
            [{"kind": "DOMAIN_REGISTRY", "domain_id": domain_id}],
            0.40,
        )
    return candidates


def learn_discovery_queries(
    root: Path,
    store: MarketSensoriumStore,
    *,
    max_domains: int = 8,
) -> dict[str, Any]:
    """Create bounded, source-bound next-search queries from settled Sensorium evidence.

    This is deterministic adaptive query synthesis. It does not execute a search and
    does not create outreach, publication, membership, DM, spend or commerce authority.
    """
    _schema(store)
    root = Path(root).resolve()
    domain_registry = root / "config" / "atlas" / "dio_atlas_universal_domain_registry.csv"
    history_path = root / "state" / "market_sensorium" / "domain_query_history.json"
    baseline_path = root / "state" / "market_sensorium" / "domain_baseline_candidates.csv"
    domains = _domain_rows(domain_registry)
    history = _history(history_path)
    prior = history.get("domains") or {}
    evidence_by_domain = _evidence_by_domain(store)

    weak_domains: set[str] = set()
    if baseline_path.is_file():
        try:
            with baseline_path.open("r", encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    if str(row.get("provenance_kind") or "") == "FAMILY_FALLBACK":
                        weak_domains.add(str(row.get("domain_id") or ""))
        except OSError:
            pass

    now = utc_now()
    selected_pool: list[dict[str, Any]] = []
    candidate_count = 0
    driver_counts: Counter[str] = Counter()

    for domain_id, domain in sorted(domains.items()):
        domain_evidence = evidence_by_domain.get(domain_id) or {}
        prior_query = _text((prior.get(domain_id) or {}).get("query"))
        candidates = _query_candidates(
            domain_id=domain_id,
            domain=domain,
            weak=domain_id in weak_domains,
            prior_query=prior_query,
            evidence=domain_evidence,
        )
        candidate_count += len(candidates)
        for candidate in candidates:
            driver_counts[candidate["query_kind"]] += 1
            refs = candidate["evidence_refs"]
            evidence_digest = digest_payload(refs)
            query_id = stable_id(
                "LQ",
                domain_id,
                candidate["query_kind"],
                candidate["query"],
                evidence_digest,
            )
            previous = store.connection.execute(
                "SELECT selected_query_id FROM learned_query_memory WHERE domain_id=?",
                (domain_id,),
            ).fetchone()
            parent_query_id = str(previous["selected_query_id"]) if previous else None
            source_drivers = {
                (str(item.get("kind") or ""), str(item.get("source_ref") or item.get("id") or item.get("domain_id") or ""))
                for item in refs
            }
            adaptive_bonus = 0.0 if candidate["query_kind"] == "BROADEN_DISCOVERY" else 0.12
            score = float(candidate["priority"]) + adaptive_bonus + min(0.08, len(source_drivers) * 0.01)
            if candidate["novelty_score"] <= 0:
                score -= 0.25
            item = {
                "query_id": query_id,
                "domain_id": domain_id,
                "domain_name": _text(domain.get("domain_name")),
                "domain_family": _text(domain.get("domain_family")),
                "query_kind": candidate["query_kind"],
                "query": candidate["query"],
                "rationale": candidate["rationale"],
                "evidence_refs": refs,
                "evidence_digest": evidence_digest,
                "source_driver_count": len(source_drivers),
                "novelty_score": candidate["novelty_score"],
                "parent_query_id": parent_query_id,
                "selection_score": round(score, 6),
                "previous_query": prior_query or None,
            }
            selected_pool.append(item)
            store.connection.execute(
                """
                INSERT OR IGNORE INTO learned_query_events (
                  query_id,domain_id,domain_name,query_kind,query_text,rationale,
                  evidence_refs_json,evidence_digest,source_driver_count,novelty_score,
                  parent_query_id,created_at,selected,execution_performed,
                  authority_created,market_demand_claimed
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,0,0,0)
                """,
                (
                    query_id,
                    domain_id,
                    item["domain_name"],
                    item["query_kind"],
                    item["query"],
                    item["rationale"],
                    canonical_json(refs),
                    evidence_digest,
                    item["source_driver_count"],
                    item["novelty_score"],
                    parent_query_id,
                    now,
                ),
            )

    # Select at most one query per domain, then cap exploration globally.
    best_by_domain: dict[str, dict[str, Any]] = {}
    for item in selected_pool:
        current = best_by_domain.get(item["domain_id"])
        key = (item["selection_score"], item["novelty_score"], item["query_kind"])
        current_key = (
            current["selection_score"], current["novelty_score"], current["query_kind"]
        ) if current else None
        if current is None or key > current_key:
            best_by_domain[item["domain_id"]] = item

    selected = sorted(
        best_by_domain.values(),
        key=lambda item: (-float(item["selection_score"]), -float(item["novelty_score"]), item["domain_id"]),
    )[: max(1, int(max_domains))]

    for item in selected:
        store.connection.execute("UPDATE learned_query_events SET selected=1 WHERE query_id=?", (item["query_id"],))
        store.connection.execute(
            """
            INSERT INTO learned_query_memory (
              domain_id,selected_query_id,selected_query_text,query_kind,
              previous_query_text,evidence_digest,source_driver_count,novelty_score,
              updated_at,execution_authority,authority_created
            ) VALUES (?,?,?,?,?,?,?,?,?,'NONE',0)
            ON CONFLICT(domain_id) DO UPDATE SET
              selected_query_id=excluded.selected_query_id,
              selected_query_text=excluded.selected_query_text,
              query_kind=excluded.query_kind,
              previous_query_text=excluded.previous_query_text,
              evidence_digest=excluded.evidence_digest,
              source_driver_count=excluded.source_driver_count,
              novelty_score=excluded.novelty_score,
              updated_at=excluded.updated_at,
              execution_authority='NONE',
              authority_created=0
            """,
            (
                item["domain_id"],
                item["query_id"],
                item["query"],
                item["query_kind"],
                item["previous_query"],
                item["evidence_digest"],
                item["source_driver_count"],
                item["novelty_score"],
                now,
            ),
        )

    store.connection.commit()
    plan = {
        "schema": "dio.market_sensorium.learned_discovery_query_plan.v1",
        "created_at": now,
        "region_code": "ZA",
        "relevance_language": "en",
        "published_after_days": 180,
        "max_results_per_source": 5,
        "domains": [
            {
                "domain_id": item["domain_id"],
                "domain_name": item["domain_name"],
                "domain_family": item["domain_family"],
                "query": item["query"],
                "query_origin": "MS7_LEARNED_DISCOVERY_QUERY",
                "learned_query_id": item["query_id"],
                "query_kind": item["query_kind"],
                "evidence_digest": item["evidence_digest"],
                "source_driver_count": item["source_driver_count"],
                "novelty_score": item["novelty_score"],
                "baseline_state": "WEAK_FAMILY_PRIOR" if item["domain_id"] in weak_domains else "EVIDENCE_ADAPTIVE",
            }
            for item in selected
        ],
        "query_execution_performed": False,
        "query_is_market_truth": False,
        "market_demand_claimed": False,
        "authority_created": False,
        "external_effects": False,
    }
    plan_path = root / "state" / "market_sensorium" / "LEARNED_DISCOVERY_QUERY_PLAN.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    source_bound = sum(1 for item in selected if item["evidence_refs"] and item["evidence_digest"])
    adaptive = sum(1 for item in selected if item["query_kind"] != "BROADEN_DISCOVERY")
    novel = sum(1 for item in selected if float(item["novelty_score"]) > 0)
    source_driver_total = sum(int(item["source_driver_count"]) for item in selected)
    return {
        "schema": "dio.market_sensorium.learned_discovery_queries.v1",
        "candidate_queries_generated": candidate_count,
        "selected_queries": len(selected),
        "selected_domains": len({item["domain_id"] for item in selected}),
        "source_bound_selected_queries": source_bound,
        "adaptive_selected_queries": adaptive,
        "novel_selected_queries": novel,
        "source_driver_total": source_driver_total,
        "query_kind_counts": dict(sorted(Counter(item["query_kind"] for item in selected).items())),
        "candidate_driver_counts": dict(sorted(driver_counts.items())),
        "max_domains": max(1, int(max_domains)),
        "bounded_exploration": len(selected) <= max(1, int(max_domains)),
        "plan_path": str(plan_path.relative_to(root)),
        "query_execution_performed": False,
        "query_is_market_truth": False,
        "selected_query_is_best_market_query": False,
        "search_hit_is_lead": False,
        "market_demand_claimed": False,
        "outreach_authority_created": False,
        "publication_authority_created": False,
        "membership_authority_created": False,
        "dm_authority_created": False,
        "spend_authority_created": False,
        "authority_created": False,
        "external_effects": False,
        "examples": [
            {
                "domain_id": item["domain_id"],
                "domain_name": item["domain_name"],
                "query_kind": item["query_kind"],
                "query": item["query"],
                "novelty_score": item["novelty_score"],
                "source_driver_count": item["source_driver_count"],
                "selection_score": item["selection_score"],
                "previous_query": item["previous_query"],
                "query_id": item["query_id"],
            }
            for item in selected[:8]
        ],
    }
