from __future__ import annotations

import pytest

from experiments.metamorphic_adaptation.atlas import (
    AtlasSelectionError,
    build_eligibility_pool,
    commit_seed,
    composition_fingerprint,
    select_tasks,
    verify_seed,
)


def _task(task_id: str, capabilities: list[str], **overrides: object) -> dict:
    row = {
        "id": task_id,
        "required_capabilities": capabilities,
        "dedicated_runner": False,
        "dedicated_template": False,
        "adaptation_overlap": False,
        "requires_external_effects": False,
        "scorable_artifact": True,
        "source_inputs_replayable": True,
    }
    row.update(overrides)
    return row


def _pool() -> list[dict]:
    tasks = [
        _task("t1", ["a", "b"]),
        _task("t2", ["a", "c"]),
        _task("t3", ["b", "c"]),
        _task("t4", ["a", "d"]),
        _task("t5", ["b", "d"]),
        _task("t6", ["c", "d"]),
    ]
    named = [
        {"id": "p1", "capabilities": ["a", "b"]},
        {"id": "p2", "capabilities": ["a", "c"]},
        {"id": "p3", "capabilities": ["b", "c"]},
        {"id": "p4", "capabilities": ["a", "d"]},
    ]
    eligible, excluded = build_eligibility_pool(tasks, named)
    assert excluded == []
    return eligible


def test_composition_fingerprint_is_order_insensitive_and_stable() -> None:
    assert composition_fingerprint(["cap.b", "cap.a"]) == composition_fingerprint(["cap.a", "cap.b"])
    assert composition_fingerprint(["cap.a", "cap.b"]).startswith("sha256:")


@pytest.mark.parametrize(
    ("task", "reason"),
    [
        (_task("runner", ["a", "b"], dedicated_runner=True), "dedicated_runner"),
        (_task("template", ["a", "b"], dedicated_template=True), "dedicated_template"),
        (_task("one-cap", ["a"]), "fewer_than_two_capabilities"),
        (_task("adaptation", ["a", "b"], adaptation_overlap=True), "adaptation_overlap"),
        (_task("external", ["a", "b"], requires_external_effects=True), "external_effect_required"),
        (_task("unscorable", ["a", "b"], scorable_artifact=False), "unscorable_artifact"),
        (_task("unreplayable", ["a", "b"], source_inputs_replayable=False), "unreplayable_inputs"),
    ],
)
def test_ineligible_candidates_are_excluded_with_frozen_reason(task: dict, reason: str) -> None:
    eligible, excluded = build_eligibility_pool([task], [])
    assert eligible == []
    assert excluded == [{"id": task["id"], "reason": reason}]


def test_named_composition_is_eligible_but_not_novel() -> None:
    eligible, excluded = build_eligibility_pool(
        [_task("candidate", ["a", "b"])],
        [{"id": "existing", "capabilities": ["b", "a"]}],
    )
    assert excluded == []
    assert eligible[0]["novel_composition"] is False


def test_commit_reveal_verifies_exact_seed() -> None:
    seed = b"sealed-until-after-adaptation"
    commitment = commit_seed(seed)
    assert commitment.startswith("sha256:")
    assert verify_seed(seed, commitment) is True
    assert verify_seed(b"different", commitment) is False


def test_same_seed_and_pool_produce_identical_selection() -> None:
    pool = _pool()
    first = select_tasks(pool, b"seed-alpha", count=3)
    second = select_tasks(pool, b"seed-alpha", count=3)
    assert first == second
    assert first["selection_replaced"] is False


def test_different_seed_changes_shuffle_order() -> None:
    pool = _pool()
    first = select_tasks(pool, b"seed-alpha", count=3)
    second = select_tasks(pool, b"seed-beta", count=3)
    assert first["shuffle_order"] != second["shuffle_order"]


def test_selector_enforces_predeclared_novelty_rule_without_operator_replacement() -> None:
    pool = [
        {**_task("old1", ["a", "b"]), "composition_fingerprint": composition_fingerprint(["a", "b"]), "novel_composition": False},
        {**_task("old2", ["a", "c"]), "composition_fingerprint": composition_fingerprint(["a", "c"]), "novel_composition": False},
        {**_task("old3", ["b", "c"]), "composition_fingerprint": composition_fingerprint(["b", "c"]), "novel_composition": False},
        {**_task("novel", ["a", "d"]), "composition_fingerprint": composition_fingerprint(["a", "d"]), "novel_composition": True},
    ]

    receipt = select_tasks(pool, b"find-novel", count=3)
    selected = [row["id"] for row in receipt["selected"]]
    assert "novel" in selected
    assert receipt["selection_replaced"] is False
    assert receipt["novelty_rule"] == "at_least_one_selected_task_must_have_novel_composition"


def test_selector_refuses_pool_without_novel_candidate() -> None:
    pool = [
        {**_task(f"old{i}", ["a", str(i)]), "composition_fingerprint": composition_fingerprint(["a", str(i)]), "novel_composition": False}
        for i in range(5)
    ]
    with pytest.raises(AtlasSelectionError, match="novel"):
        select_tasks(pool, b"seed", count=3)


def test_selector_refuses_too_small_pool() -> None:
    with pytest.raises(AtlasSelectionError, match="at least 3"):
        select_tasks(
            [{**_task("only", ["a", "b"]), "composition_fingerprint": composition_fingerprint(["a", "b"]), "novel_composition": True}],
            b"seed",
            count=3,
        )
