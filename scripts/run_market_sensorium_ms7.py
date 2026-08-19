#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_sensorium.core import MarketSensoriumStore  # noqa: E402
from market_sensorium.query_learning import learn_discovery_queries  # noqa: E402

STATE_ROOT = ROOT / "state" / "market_sensorium"
DB_PATH = STATE_ROOT / "market_sensorium.sqlite"
MS6_RECEIPT = STATE_ROOT / "MARKET_SENSORIUM_MS6_RECEIPT.json"
MS7_RECEIPT = STATE_ROOT / "MARKET_SENSORIUM_MS7_RECEIPT.json"
MS6_VERIFIED = "DIO_MARKET_SENSORIUM_MARKET_HABITAT_INTELLIGENCE_VERIFIED"


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _apply_ms7_gate(receipt: dict) -> dict:
    summary = receipt.get("summary") or {}
    learned = summary.get("learned_queries") or {}

    candidates = int(learned.get("candidate_queries_generated") or 0)
    selected = int(learned.get("selected_queries") or 0)
    domains = int(learned.get("selected_domains") or 0)
    source_bound = int(learned.get("source_bound_selected_queries") or 0)
    adaptive = int(learned.get("adaptive_selected_queries") or 0)
    novel = int(learned.get("novel_selected_queries") or 0)
    drivers = int(learned.get("source_driver_total") or 0)
    max_domains = int(learned.get("max_domains") or 0)
    kind_counts = learned.get("query_kind_counts") or {}
    diversity = sum(1 for value in kind_counts.values() if int(value or 0) > 0)
    bounded = bool(learned.get("bounded_exploration", False))
    semantic_confusion = any(
        bool(learned.get(key, False))
        for key in (
            "query_execution_performed",
            "query_is_market_truth",
            "selected_query_is_best_market_query",
            "search_hit_is_lead",
            "market_demand_claimed",
            "authority_created",
            "external_effects",
            "outreach_authority_created",
            "publication_authority_created",
            "membership_authority_created",
            "dm_authority_created",
            "spend_authority_created",
        )
    )

    if receipt.get("ms6_acceptance") != MS6_VERIFIED:
        gate = "PENDING_VERIFIED_MS6_RECEIPT"
    elif candidates <= 0 or selected <= 0 or domains <= 0:
        gate = "PENDING_LEARNED_DISCOVERY_QUERY_EVIDENCE"
    elif not bounded or max_domains <= 0 or selected > max_domains:
        gate = "REFUSE_UNBOUNDED_QUERY_EXPLORATION"
    elif source_bound < selected or drivers < selected:
        gate = "PENDING_SOURCE_BOUND_QUERY_CAUSALITY"
    elif adaptive <= 0:
        gate = "PENDING_EVIDENCE_ADAPTIVE_QUERY_SELECTION"
    elif novel <= 0:
        gate = "PENDING_QUERY_NOVELTY"
    elif diversity < 2:
        gate = "PENDING_QUERY_DRIVER_DIVERSITY"
    elif semantic_confusion:
        gate = "REFUSE_QUERY_TRUTH_OR_AUTHORITY_INFLATION"
    else:
        gate = "DIO_MARKET_SENSORIUM_LEARNED_DISCOVERY_QUERIES_VERIFIED"

    receipt["ms7_implementation"] = "DIO_MARKET_SENSORIUM_EVIDENCE_ADAPTIVE_QUERY_SYNTHESIS_IMPLEMENTED"
    receipt["ms7_acceptance"] = gate
    receipt["ms7_truth"] = {
        "candidate_queries_generated": candidates,
        "selected_queries": selected,
        "selected_domains": domains,
        "source_bound_selected_queries": source_bound,
        "adaptive_selected_queries": adaptive,
        "novel_selected_queries": novel,
        "source_driver_total": drivers,
        "query_kind_diversity": diversity,
        "query_kind_counts": kind_counts,
        "candidate_driver_counts": learned.get("candidate_driver_counts") or {},
        "bounded_exploration": bounded,
        "max_domains": max_domains,
        "query_execution_performed": False,
        "query_is_market_truth": False,
        "selected_query_is_best_market_query": False,
        "search_hit_is_lead": False,
        "market_demand_claimed": False,
        "authority_created": False,
    }
    return receipt


def main() -> int:
    prior = _read_json(MS6_RECEIPT)
    ms6_acceptance = str(prior.get("ms6_acceptance") or "")
    if ms6_acceptance != MS6_VERIFIED:
        payload = {
            "schema": "dio.market_sensorium.ms7_learned_query_runner.v1",
            "ms6_acceptance": ms6_acceptance or "UNAVAILABLE",
            "ms7_implementation": "DIO_MARKET_SENSORIUM_EVIDENCE_ADAPTIVE_QUERY_SYNTHESIS_IMPLEMENTED",
            "ms7_acceptance": "PENDING_VERIFIED_MS6_RECEIPT",
            "reason": "The persisted MS-6 receipt does not carry the verified Market Habitat Intelligence token.",
            "authority_created": False,
            "external_effects": False,
        }
        MS7_RECEIPT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 0

    with MarketSensoriumStore(DB_PATH) as store:
        learned = learn_discovery_queries(ROOT, store, max_domains=8)

    receipt = {
        "schema": "dio.market_sensorium.ms7_learned_query_runner.v1",
        "ms6_acceptance": ms6_acceptance,
        "ms6_source_ms5_acceptance": prior.get("ms5_acceptance"),
        "summary": {"learned_queries": learned},
        "authority_created": False,
        "external_effects": False,
    }
    receipt = _apply_ms7_gate(receipt)
    MS7_RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
