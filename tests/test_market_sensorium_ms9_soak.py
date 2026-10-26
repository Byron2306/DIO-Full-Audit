from __future__ import annotations

from pathlib import Path

from market_sensorium.core import MarketSensoriumStore
from market_sensorium.soak import (
    MS9_VERIFIED,
    capture_immutable_baseline,
    evaluate_soak,
    verify_immutable_baseline,
)


def _snapshot(iteration: int, *, observations: int = 10, authority: bool = False) -> dict:
    return {
        "iteration": iteration,
        "refresh": {
            "public_read_cycle_complete": True,
            "mail_read_cycle_complete": True,
        },
        "learned_query_execution": {
            "learned_queries_executed": 8,
            "history_bound_after_execution": 8,
            "batch_digest": "sha256:same-stable-world-batch",
        },
        "commercial_time": {
            "acceptance": "DIO_MARKET_SENSORIUM_COMMERCIAL_TIME_OBSERVATION_ACTIVE",
            "coverage_state": "CONTINUOUS",
            "unsupported_no_reply_inferences": 0,
            "age_only_silence_inference_used": False,
            "followup_authority_created": False,
            "market_demand_claimed": False,
            "authority_created": False,
        },
        "event_counts": {
            "observations": observations,
            "rank_transitions": 5,
            "commercial_hypotheses": 20,
            "competitive_offer_events": 6,
            "habitat_intelligence_events": 12,
            "learned_query_events": 16,
        },
        "immutable_prefix": {"all_prefixes_intact": True},
        "semantic_violation_total": 0,
        "cockpit_truth_class_violations": 0,
        "cockpit_truth_separation_valid": True,
        "ms8_verified": True,
        "ms2_observation_active_or_verified": True,
        "refused_phases": [],
        "best_target_claimed": False,
        "market_demand_claimed": False,
        "willingness_to_pay_proved": False,
        "commercial_success_proved": False,
        "customer_claimed": False,
        "authority_created": authority,
        "external_effects": False,
    }


def test_ms9_allows_stable_world_when_read_only_loop_repeats_cleanly() -> None:
    result = evaluate_soak([_snapshot(1), _snapshot(2), _snapshot(3)])
    assert result["ms9_acceptance"] == MS9_VERIFIED
    assert result["cycles_observed"] == 3
    assert result["learned_query_execution_cycles"] == 3
    assert result["query_batch_changes"] == 0
    assert result["stable_world_allowed"] is True
    assert result["query_change_required"] is False
    assert result["rank_change_required"] is False
    assert result["authority_created"] is False


def test_ms9_refuses_authority_or_truth_drift() -> None:
    result = evaluate_soak([_snapshot(1), _snapshot(2, authority=True), _snapshot(3)])
    assert result["ms9_acceptance"] == "REFUSE_AUTONOMIC_SEMANTIC_OR_AUTHORITY_DRIFT"
    assert result["authority_or_truth_failure_cycles"] == [2]


def test_ms9_refuses_event_ledger_count_regression() -> None:
    result = evaluate_soak([
        _snapshot(1, observations=10),
        _snapshot(2, observations=12),
        _snapshot(3, observations=11),
    ])
    assert result["ms9_acceptance"] == "REFUSE_HISTORICAL_EVENT_LEDGER_MUTATION"
    assert result["event_count_regressions"] == [
        {"table": "observations", "before": 12, "after": 11}
    ]


def test_ms9_preexisting_observation_prefix_may_be_appended_but_not_rewritten(tmp_path: Path) -> None:
    db = tmp_path / "market_sensorium.sqlite"
    with MarketSensoriumStore(db) as store:
        first = store.append_observation(
            source_kind="TEST",
            source_ref="source:a",
            entity_kind="TARGET",
            entity_id="T1",
            payload={"fact": "a"},
            observed_at="2026-08-19T00:00:00+00:00",
        )
        baseline = capture_immutable_baseline(store)
        store.append_observation(
            source_kind="TEST",
            source_ref="source:b",
            entity_kind="TARGET",
            entity_id="T2",
            payload={"fact": "b"},
            observed_at="2026-08-19T00:01:00+00:00",
        )
        appended = verify_immutable_baseline(store, baseline)
        assert appended["all_prefixes_intact"] is True

        store.connection.execute(
            "UPDATE observations SET provenance_digest='sha256:tampered' WHERE observation_id=?",
            (first,),
        )
        store.connection.commit()
        tampered = verify_immutable_baseline(store, baseline)
        assert tampered["all_prefixes_intact"] is False
        assert tampered["ledgers"]["observations"]["intact"] is False
