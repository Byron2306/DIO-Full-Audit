from __future__ import annotations

from market_sensorium.soak import evaluate_soak


def _snapshot(iteration: int) -> dict:
    return {
        "iteration": iteration,
        "refresh": {
            "public_read_cycle_complete": True,
            "mail_read_cycle_complete": True,
        },
        "learned_query_execution": {
            "learned_queries_executed": 8,
            "history_bound_after_execution": 8,
            "batch_digest": f"sha256:batch-{iteration}",
        },
        "commercial_time": {
            "coverage_state": "CONTINUOUS",
            "unsupported_no_reply_inferences": 0,
            "age_only_silence_inference_used": False,
            "followup_authority_created": False,
            "market_demand_claimed": False,
            "authority_created": False,
        },
        "event_counts": {
            "observations": 100 + iteration,
            "rank_transitions": 20 + iteration,
            "competitive_offer_events": 6,
            "habitat_intelligence_events": 20,
            "learned_query_events": 30 + iteration,
            "commercial_hypotheses": 100,
            "commercial_hypothesis_sets": 18,
        },
        "immutable_prefix": {
            "all_prefixes_intact": True,
            "all_historical_semantics_intact": True,
        },
        "semantic_violation_total": 0,
        "cockpit_truth_class_violations": 0,
        "cockpit_truth_separation_valid": True,
        "ms8_verified": True,
        "ms2_observation_active_or_verified": True,
        "refused_phases": [],
        "authority_created": False,
        "external_effects": False,
        "best_target_claimed": False,
        "market_demand_claimed": False,
        "willingness_to_pay_proved": False,
        "commercial_success_proved": False,
        "customer_claimed": False,
    }


def test_ms9_remains_pending_without_complete_read_refresh_soak() -> None:
    rows = [_snapshot(1), _snapshot(2), _snapshot(3)]
    rows[1]["refresh"]["public_read_cycle_complete"] = False
    result = evaluate_soak(rows)
    assert result["ms9_acceptance"] == "PENDING_COMPLETE_READ_ONLY_REFRESH_SOAK"


def test_ms9_refuses_unsupported_silence_inference() -> None:
    rows = [_snapshot(1), _snapshot(2), _snapshot(3)]
    rows[2]["commercial_time"]["unsupported_no_reply_inferences"] = 1
    result = evaluate_soak(rows)
    assert result["ms9_acceptance"] == "REFUSE_AUTONOMIC_SEMANTIC_OR_AUTHORITY_DRIFT"
    assert result["unsupported_silence_cycles"] == [3]


def test_ms9_remains_pending_when_learned_queries_are_not_actually_executed() -> None:
    rows = [_snapshot(1), _snapshot(2), _snapshot(3)]
    for row in rows:
        row["learned_query_execution"]["learned_queries_executed"] = 0
        row["learned_query_execution"]["history_bound_after_execution"] = 0
    result = evaluate_soak(rows)
    assert result["ms9_acceptance"] == "PENDING_LEARNED_QUERY_EXECUTION_ACROSS_SOAK"
