from __future__ import annotations

from experiments.metamorphic_adaptation.analysis import (
    TERMINAL_TOKEN,
    bootstrap_difference,
    classify_evidence,
    three_way_interaction,
)


ARMS = ("000", "100", "010", "001", "110", "101", "011", "111")


def _scores(task_means: dict[str, dict[str, float]], replicates: int = 5, raters: int = 2) -> list[dict]:
    rows: list[dict] = []
    for task_id, means in task_means.items():
        for arm_id in ARMS:
            for replicate in range(1, replicates + 1):
                for rater in range(1, raters + 1):
                    rows.append(
                        {
                            "task_id": task_id,
                            "arm_id": arm_id,
                            "replicate": replicate,
                            "rater_id": f"human-{rater}",
                            "quality_score": float(means[arm_id]),
                            "repair_burden": 10.0 if arm_id != "111" else 5.0,
                        }
                    )
    return rows


def _experiment(**overrides: object) -> dict:
    row = {
        "confirmatory": True,
        "held_out_task_count": 3,
        "held_out_run_count": 120,
        "scores_locked": True,
        "freeze_violations": [],
        "authority_violations": [],
        "selection_replaced": False,
        "novel_compositions": [],
    }
    row.update(overrides)
    return row


def _lineage(complete: bool = False) -> dict:
    return {
        "valid": True,
        "complete": complete,
        "adaptive_links": [
            {
                "source_event_id": "evt-a",
                "consumer_event_id": "evt-b",
                "state_class": "S",
                "state_item": "audience",
            }
        ] if complete else [],
    }


def test_three_way_interaction_uses_exact_preregistered_contrast() -> None:
    y = {
        "000": 10.0,
        "100": 12.0,
        "010": 13.0,
        "001": 14.0,
        "110": 17.0,
        "101": 18.0,
        "011": 19.0,
        "111": 30.0,
    }
    expected = y["111"] - y["110"] - y["101"] - y["011"] + y["100"] + y["010"] + y["001"] - y["000"]
    assert three_way_interaction(y) == expected


def test_bootstrap_difference_reports_positive_fixed_effect_with_ci_excluding_zero() -> None:
    means = {
        task: {arm: (80.0 if arm == "111" else 50.0) for arm in ARMS}
        for task in ("t1", "t2", "t3")
    }
    result = bootstrap_difference(_scores(means), "111", "000", iterations=200, seed=7)
    assert result["estimate"] == 30.0
    assert result["ci_low"] == 30.0
    assert result["ci_high"] == 30.0


def test_t0_when_no_retained_state_arm_improves() -> None:
    means = {task: {arm: 60.0 for arm in ARMS} for task in ("t1", "t2", "t3")}
    result = classify_evidence(_experiment(), _scores(means), _lineage())
    assert result["tier"] == "T0"
    assert result["acceptance_token"] is None


def test_t1_when_lower_order_retained_combination_improves_without_full_transfer() -> None:
    means = {
        task: {arm: (70.0 if arm == "110" else 60.0) for arm in ARMS}
        for task in ("t1", "t2", "t3")
    }
    result = classify_evidence(_experiment(), _scores(means), _lineage())
    assert result["tier"] == "T1"
    assert result["acceptance_token"] is None


def test_t2_identifies_reliable_single_component_effect() -> None:
    means = {
        task: {arm: (70.0 if arm == "100" else 60.0) for arm in ARMS}
        for task in ("t1", "t2", "t3")
    }
    result = classify_evidence(_experiment(), _scores(means), _lineage())
    assert result["tier"] == "T2"
    assert result["component_effects"]["S"]["estimate"] == 10.0
    assert result["acceptance_token"] is None


def test_t3_when_full_arm_transfers_but_three_way_interaction_is_not_reliable() -> None:
    additive = {
        "000": 50.0,
        "100": 55.0,
        "010": 55.0,
        "001": 55.0,
        "110": 60.0,
        "101": 60.0,
        "011": 60.0,
        "111": 65.0,
    }
    means = {task: dict(additive) for task in ("t1", "t2", "t3")}
    result = classify_evidence(_experiment(), _scores(means), _lineage())
    assert result["tier"] == "T3"
    assert result["full_minus_stateless"]["ci_low"] > 0
    assert result["three_way_interaction"]["estimate"] == 0.0
    assert result["acceptance_token"] is None


def test_t4_requires_positive_full_effect_and_positive_three_way_interaction() -> None:
    means = {
        task: {arm: (90.0 if arm == "111" else 50.0) for arm in ARMS}
        for task in ("t1", "t2", "t3")
    }
    result = classify_evidence(_experiment(), _scores(means), _lineage())
    assert result["tier"] == "T4"
    assert result["full_minus_stateless"]["ci_low"] > 0
    assert result["three_way_interaction"]["ci_low"] > 0
    assert result["acceptance_token"] is None


def test_t5_requires_novel_useful_composition_complete_lineage_and_confirmatory_custody() -> None:
    means = {
        task: {arm: (90.0 if arm == "111" else 50.0) for arm in ARMS}
        for task in ("t1", "t2", "t3")
    }
    experiment = _experiment(
        novel_compositions=[{"task_id": "t2", "novel": True, "useful": True}],
    )
    result = classify_evidence(experiment, _scores(means), _lineage(complete=True))
    assert result["tier"] == "T5"
    assert result["acceptance_token"] == TERMINAL_TOKEN == "DIO_CROSS_ENCOUNTER_ADAPTIVE_COMPOSITION_OBSERVED"


def test_t5_is_refused_by_authority_or_freeze_violation() -> None:
    means = {
        task: {arm: (90.0 if arm == "111" else 50.0) for arm in ARMS}
        for task in ("t1", "t2", "t3")
    }
    base = {
        "novel_compositions": [{"task_id": "t2", "novel": True, "useful": True}],
    }
    authority = classify_evidence(
        _experiment(**base, authority_violations=[{"effect": "send", "before": "REFUSE", "after": "ALLOW"}]),
        _scores(means),
        _lineage(complete=True),
    )
    freeze = classify_evidence(
        _experiment(**base, freeze_violations=[{"path": "prompt.txt", "state": "CHANGED"}]),
        _scores(means),
        _lineage(complete=True),
    )
    assert authority["tier"] == "INVALID"
    assert freeze["tier"] == "INVALID"
    assert authority["acceptance_token"] is None
    assert freeze["acceptance_token"] is None


def test_t5_is_refused_without_two_raters_per_run_or_without_120_runs() -> None:
    means = {
        task: {arm: (90.0 if arm == "111" else 50.0) for arm in ARMS}
        for task in ("t1", "t2", "t3")
    }
    exp = _experiment(novel_compositions=[{"task_id": "t1", "novel": True, "useful": True}])
    one_rater = classify_evidence(exp, _scores(means, raters=1), _lineage(complete=True))
    short_run = classify_evidence({**exp, "held_out_run_count": 119}, _scores(means), _lineage(complete=True))
    assert one_rater["tier"] == "T4"
    assert short_run["tier"] == "T4"
    assert one_rater["acceptance_token"] is None
    assert short_run["acceptance_token"] is None
