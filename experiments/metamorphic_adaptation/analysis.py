from __future__ import annotations

import math
import random
from collections import defaultdict
from statistics import mean
from typing import Any, Callable


ARMS = ("000", "100", "010", "001", "110", "101", "011", "111")
TERMINAL_TOKEN = "DIO_CROSS_ENCOUNTER_ADAPTIVE_COMPOSITION_OBSERVED"


def _require_arm_means(means: dict[str, float]) -> None:
    missing = set(ARMS).difference(means)
    if missing:
        raise ValueError(f"missing factorial arm means: {sorted(missing)}")


def three_way_interaction(means: dict[str, float]) -> float:
    _require_arm_means(means)
    return (
        float(means["111"])
        - float(means["110"])
        - float(means["101"])
        - float(means["011"])
        + float(means["100"])
        + float(means["010"])
        + float(means["001"])
        - float(means["000"])
    )


def _percentile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("cannot compute percentile of empty values")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _task_arm_values(records: list[dict[str, Any]]) -> dict[str, dict[str, list[float]]]:
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in records:
        task_id = str(row.get("task_id") or "")
        arm_id = str(row.get("arm_id") or "")
        value = row.get("quality_score")
        if not task_id or arm_id not in ARMS or not isinstance(value, (int, float)):
            raise ValueError("score records require task_id, valid arm_id and numeric quality_score")
        grouped[task_id][arm_id].append(float(value))
    for task_id, arm_rows in grouped.items():
        missing = set(ARMS).difference(arm_rows)
        if missing:
            raise ValueError(f"task {task_id} is missing factorial arms: {sorted(missing)}")
    if not grouped:
        raise ValueError("no score records supplied")
    return grouped


def _arm_means(records: list[dict[str, Any]]) -> dict[str, float]:
    values: dict[str, list[float]] = {arm: [] for arm in ARMS}
    for row in records:
        arm = str(row.get("arm_id") or "")
        if arm in values:
            values[arm].append(float(row["quality_score"]))
    if any(not rows for rows in values.values()):
        raise ValueError("all factorial arms require scores")
    return {arm: mean(rows) for arm, rows in values.items()}


def _bootstrap_statistic(
    records: list[dict[str, Any]],
    statistic: Callable[[dict[str, float]], float],
    *,
    iterations: int,
    seed: int,
) -> dict[str, float | int]:
    if iterations <= 0:
        raise ValueError("bootstrap iterations must be positive")
    grouped = _task_arm_values(records)
    task_ids = sorted(grouped)
    rng = random.Random(seed)
    draws: list[float] = []

    for _ in range(iterations):
        sampled_tasks = [rng.choice(task_ids) for _ in task_ids]
        sampled_arm_values: dict[str, list[float]] = {arm: [] for arm in ARMS}
        for task_id in sampled_tasks:
            for arm in ARMS:
                source = grouped[task_id][arm]
                # Preserve the task block, then resample its replicate/rater observations.
                sampled_arm_values[arm].extend(rng.choice(source) for _ in source)
        sampled_means = {arm: mean(values) for arm, values in sampled_arm_values.items()}
        draws.append(float(statistic(sampled_means)))

    observed_means = _arm_means(records)
    estimate = float(statistic(observed_means))
    return {
        "estimate": round(estimate, 6),
        "ci_low": round(_percentile(draws, 0.025), 6),
        "ci_high": round(_percentile(draws, 0.975), 6),
        "iterations": iterations,
        "seed": seed,
    }


def bootstrap_difference(
    records: list[dict[str, Any]],
    left: str,
    right: str,
    iterations: int = 2000,
    seed: int = 17092026,
) -> dict[str, float | int]:
    if left not in ARMS or right not in ARMS:
        raise ValueError("bootstrap difference requires valid factorial arms")
    return _bootstrap_statistic(
        records,
        lambda values: float(values[left]) - float(values[right]),
        iterations=iterations,
        seed=seed,
    )


def _bootstrap_interaction(
    records: list[dict[str, Any]],
    iterations: int = 2000,
    seed: int = 17092027,
) -> dict[str, float | int]:
    return _bootstrap_statistic(records, three_way_interaction, iterations=iterations, seed=seed)


def _factorial_main_effect(means: dict[str, float], factor_index: int) -> float:
    enabled = [arm for arm in ARMS if arm[factor_index] == "1"]
    disabled = [arm for arm in ARMS if arm[factor_index] == "0"]
    return mean(means[arm] for arm in enabled) - mean(means[arm] for arm in disabled)


def _rater_custody_met(scores: list[dict[str, Any]]) -> bool:
    raters: dict[tuple[str, str, int], set[str]] = defaultdict(set)
    for row in scores:
        key = (
            str(row.get("task_id") or ""),
            str(row.get("arm_id") or ""),
            int(row.get("replicate") or 0),
        )
        rater = str(row.get("rater_id") or "")
        if all(key) and rater:
            raters[key].add(rater)
    return bool(raters) and all(len(values) >= 2 for values in raters.values())


def _unique_run_count(scores: list[dict[str, Any]]) -> int:
    return len(
        {
            (
                str(row.get("task_id") or ""),
                str(row.get("arm_id") or ""),
                int(row.get("replicate") or 0),
            )
            for row in scores
        }
    )


def _repair_difference(scores: list[dict[str, Any]], left: str = "111", right: str = "000") -> float | None:
    left_values = [float(row["repair_burden"]) for row in scores if row.get("arm_id") == left and isinstance(row.get("repair_burden"), (int, float))]
    right_values = [float(row["repair_burden"]) for row in scores if row.get("arm_id") == right and isinstance(row.get("repair_burden"), (int, float))]
    if not left_values or not right_values:
        return None
    return round(mean(left_values) - mean(right_values), 6)


def classify_evidence(
    experiment: dict[str, Any],
    scores: list[dict[str, Any]],
    lineage: dict[str, Any],
) -> dict[str, Any]:
    freeze_violations = list(experiment.get("freeze_violations") or [])
    authority_violations = list(experiment.get("authority_violations") or [])
    selection_replaced = bool(experiment.get("selection_replaced"))
    lineage_valid = bool(lineage.get("valid", True))

    invalidation_reasons: list[str] = []
    if freeze_violations:
        invalidation_reasons.append("FREEZE_VIOLATION")
    if authority_violations:
        invalidation_reasons.append("AUTHORITY_VIOLATION")
    if selection_replaced:
        invalidation_reasons.append("TASK_SELECTION_REPLACED")
    if not lineage_valid:
        invalidation_reasons.append("LINEAGE_INTEGRITY_FAILURE")

    means = _arm_means(scores)
    full_difference = bootstrap_difference(scores, "111", "000", iterations=1000, seed=17092026)
    interaction = _bootstrap_interaction(scores, iterations=1000, seed=17092027)
    arm_differences = {
        arm: bootstrap_difference(scores, arm, "000", iterations=500, seed=17093000 + index)
        for index, arm in enumerate(ARMS)
        if arm != "000"
    }
    component_effects = {
        "S": arm_differences["100"],
        "M": arm_differences["010"],
        "B": arm_differences["001"],
    }
    factorial_main_effects = {
        "S": round(_factorial_main_effect(means, 0), 6),
        "M": round(_factorial_main_effect(means, 1), 6),
        "B": round(_factorial_main_effect(means, 2), 6),
    }

    if invalidation_reasons:
        tier = "INVALID"
    else:
        any_retained_reliable = any(result["ci_low"] > 0 for result in arm_differences.values())
        any_component_reliable = any(result["ci_low"] > 0 for result in component_effects.values())
        full_reliable = full_difference["estimate"] > 0 and full_difference["ci_low"] > 0
        interaction_reliable = interaction["estimate"] > 0 and interaction["ci_low"] > 0

        if full_reliable and interaction_reliable:
            tier = "T4"
        elif full_reliable and int(experiment.get("held_out_task_count") or 0) >= 1:
            tier = "T3"
        elif any_component_reliable:
            tier = "T2"
        elif any_retained_reliable:
            tier = "T1"
        else:
            tier = "T0"

    actual_unique_runs = _unique_run_count(scores)
    confirmatory_run_custody = (
        bool(experiment.get("confirmatory"))
        and int(experiment.get("held_out_task_count") or 0) == 3
        and int(experiment.get("held_out_run_count") or 0) >= 120
        and actual_unique_runs >= 120
        and bool(experiment.get("scores_locked"))
        and _rater_custody_met(scores)
    )
    novel_useful = any(
        bool(row.get("novel")) and bool(row.get("useful"))
        for row in experiment.get("novel_compositions") or []
        if isinstance(row, dict)
    )
    lineage_complete = (
        lineage_valid
        and bool(lineage.get("complete"))
        and bool(lineage.get("adaptive_links"))
    )

    if tier == "T4" and novel_useful and lineage_complete and confirmatory_run_custody:
        tier = "T5"

    acceptance_token = TERMINAL_TOKEN if tier == "T5" else None
    return {
        "schema": "dio.metamorphic_adaptation.analysis_receipt.v1",
        "tier": tier,
        "acceptance_token": acceptance_token,
        "claim_boundary": (
            "Controlled evidence of cross-encounter adaptive composition only; "
            "not AGI, consciousness, universal generalisation, autonomous authority, "
            "market validation or scientific consensus."
        ),
        "arm_means": {arm: round(value, 6) for arm, value in means.items()},
        "full_minus_stateless": full_difference,
        "three_way_interaction": interaction,
        "component_effects": component_effects,
        "factorial_main_effects": factorial_main_effects,
        "repair_burden_full_minus_stateless": _repair_difference(scores),
        "confirmatory_run_custody": confirmatory_run_custody,
        "actual_unique_run_count": actual_unique_runs,
        "novel_useful_composition": novel_useful,
        "lineage_complete": lineage_complete,
        "invalidation_reasons": invalidation_reasons,
        "freeze_violations": freeze_violations,
        "authority_violations": authority_violations,
    }
