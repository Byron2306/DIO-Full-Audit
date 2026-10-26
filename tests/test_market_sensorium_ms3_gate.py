from __future__ import annotations

from scripts.run_market_sensorium_cycle import _apply_ms3_gate


def _receipt(**overrides):
    transitions = {
        "transitions_recorded": 2,
        "historical_transitions": 2,
        "rank_movement_transitions": 1,
        "evidence_bound_transitions": 2,
        "rank_movement_evidence_bound_transitions": 1,
        "unexplained_rank_movements": 0,
        "kind_SCORE_DRIVEN_RANK_MOVEMENT": 0,
        "history_preserved": True,
        "rank_learning_mutated_evidence": False,
        "evidence_source_bound": True,
        "persisted_transition_count": 2,
        "market_demand_claimed": False,
        "authority_created": False,
        **overrides,
    }
    return {"summary": {"store": {"rank_transitions": transitions}}}


def test_ms3_gate_verifies_explained_source_bound_live_movement() -> None:
    result = _apply_ms3_gate(_receipt())
    assert result["ms3_acceptance"] == "DIO_MARKET_SENSORIUM_DYNAMIC_RANK_MOVEMENT_VERIFIED"
    assert result["ms3_truth"]["authority_created"] is False
    assert result["ms3_truth"]["market_demand_claimed"] is False


def test_ms3_gate_waits_when_rank_is_stable() -> None:
    result = _apply_ms3_gate(_receipt(rank_movement_transitions=0, rank_movement_evidence_bound_transitions=0))
    assert result["ms3_acceptance"] == "PENDING_DYNAMIC_RANK_MOVEMENT"


def test_ms3_gate_refuses_unexplained_or_score_only_movement() -> None:
    unexplained = _apply_ms3_gate(_receipt(unexplained_rank_movements=1))
    assert unexplained["ms3_acceptance"] == "REFUSE_UNEXPLAINED_RANK_MOVEMENT"

    score_only = _apply_ms3_gate(_receipt(kind_SCORE_DRIVEN_RANK_MOVEMENT=1))
    assert score_only["ms3_acceptance"] == "REFUSE_SCORE_ONLY_RANK_MOVEMENT"


def test_ms3_gate_refuses_evidence_mutation_or_missing_source_binding() -> None:
    mutated = _apply_ms3_gate(_receipt(rank_learning_mutated_evidence=True))
    assert mutated["ms3_acceptance"] == "REFUSE_RANK_HISTORY_OR_EVIDENCE_MUTATION"

    unbound = _apply_ms3_gate(_receipt(rank_movement_evidence_bound_transitions=0))
    assert unbound["ms3_acceptance"] == "PENDING_SOURCE_BOUND_RANK_MOVEMENT_EVIDENCE"
