from __future__ import annotations

from scripts.run_market_sensorium_ms7 import _apply_ms7_gate


def _receipt(**overrides):
    learned = {
        "candidate_queries_generated": 12,
        "selected_queries": 4,
        "selected_domains": 4,
        "source_bound_selected_queries": 4,
        "adaptive_selected_queries": 3,
        "novel_selected_queries": 4,
        "source_driver_total": 9,
        "query_kind_counts": {"ENTITY_RESOLUTION": 2, "HABITAT_CORROBORATION": 1, "BROADEN_DISCOVERY": 1},
        "candidate_driver_counts": {"ENTITY_RESOLUTION": 4, "HABITAT_CORROBORATION": 4, "BROADEN_DISCOVERY": 4},
        "max_domains": 8,
        "bounded_exploration": True,
        "query_execution_performed": False,
        "query_is_market_truth": False,
        "selected_query_is_best_market_query": False,
        "search_hit_is_lead": False,
        "market_demand_claimed": False,
        "authority_created": False,
        "external_effects": False,
    }
    learned.update(overrides)
    return {
        "ms6_acceptance": "DIO_MARKET_SENSORIUM_MARKET_HABITAT_INTELLIGENCE_VERIFIED",
        "summary": {"learned_queries": learned},
    }


def test_ms7_gate_verifies_bounded_source_bound_adaptive_queries() -> None:
    receipt = _apply_ms7_gate(_receipt())
    assert receipt["ms7_acceptance"] == "DIO_MARKET_SENSORIUM_LEARNED_DISCOVERY_QUERIES_VERIFIED"
    truth = receipt["ms7_truth"]
    assert truth["query_execution_performed"] is False
    assert truth["query_is_market_truth"] is False
    assert truth["search_hit_is_lead"] is False
    assert truth["market_demand_claimed"] is False
    assert truth["authority_created"] is False


def test_ms7_gate_refuses_unbounded_exploration() -> None:
    receipt = _apply_ms7_gate(_receipt(selected_queries=9, max_domains=8, bounded_exploration=False))
    assert receipt["ms7_acceptance"] == "REFUSE_UNBOUNDED_QUERY_EXPLORATION"


def test_ms7_gate_requires_source_bound_causality() -> None:
    receipt = _apply_ms7_gate(_receipt(source_bound_selected_queries=3))
    assert receipt["ms7_acceptance"] == "PENDING_SOURCE_BOUND_QUERY_CAUSALITY"


def test_ms7_gate_requires_adaptive_and_novel_querying() -> None:
    receipt = _apply_ms7_gate(_receipt(adaptive_selected_queries=0))
    assert receipt["ms7_acceptance"] == "PENDING_EVIDENCE_ADAPTIVE_QUERY_SELECTION"
    receipt = _apply_ms7_gate(_receipt(novel_selected_queries=0))
    assert receipt["ms7_acceptance"] == "PENDING_QUERY_NOVELTY"


def test_ms7_gate_refuses_truth_or_authority_inflation() -> None:
    receipt = _apply_ms7_gate(_receipt(query_execution_performed=True))
    assert receipt["ms7_acceptance"] == "REFUSE_QUERY_TRUTH_OR_AUTHORITY_INFLATION"
    receipt = _apply_ms7_gate(_receipt(search_hit_is_lead=True))
    assert receipt["ms7_acceptance"] == "REFUSE_QUERY_TRUTH_OR_AUTHORITY_INFLATION"


def test_ms7_gate_waits_for_verified_ms6() -> None:
    receipt = _receipt()
    receipt["ms6_acceptance"] = "PENDING_MARKET_HABITAT_EVIDENCE"
    receipt = _apply_ms7_gate(receipt)
    assert receipt["ms7_acceptance"] == "PENDING_VERIFIED_MS6_RECEIPT"
