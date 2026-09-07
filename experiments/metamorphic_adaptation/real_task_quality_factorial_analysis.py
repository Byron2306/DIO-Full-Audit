from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean


REAL_TASK_QUALITY_FACTORIAL_VERSION = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_FACTORIAL_ANALYSIS_V1"
REAL_TASK_QUALITY_FACTORIAL_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_FACTORIAL_ANALYSIS_READY"
REAL_TASK_QUALITY_FACTORIAL_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_FACTORIAL_ANALYSIS_REFUSED"

BASELINE_ARM = "A_STATELESS_RESET"
FULL_ARM = "E_FULL_SEMANTIC_MARKET_BEAST"
EXPECTED_ARMS = (
    "A_STATELESS_RESET",
    "B_COMPOSITION_ONLY_NO_RETAINED_LEARNING",
    "C_SEMANTIC_RETAINED",
    "D_MARKET_RETAINED",
    "E_FULL_SEMANTIC_MARKET_BEAST",
)


@dataclass(frozen=True)
class RealTaskQualityFactorialAnalysisReceipt:
    analysis_version: str
    status: str
    scoring_status: str
    scores_loaded: int
    labels_loaded: int
    arms_analyzed: int
    arm_quality_means_path: str
    task_family_quality_means_path: str
    quality_factor_effects_path: str
    baseline_arm: str
    baseline_mean_score: float
    full_arm: str
    full_mean_score: float
    full_minus_baseline_effect: float
    best_arm: str
    best_mean_score: float
    real_quality_scores_analyzed: bool
    positive_full_stack_quality_effect_observed: bool
    real_adaptive_evidence: bool
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    scoring_receipt_sha256: str
    blind_scores_sha256: str
    label_join_sha256: str
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mean(values: list[float]) -> float:
    return float(mean(values)) if values else 0.0


def _score_value(score: dict) -> float:
    if "total_score" in score:
        return float(score["total_score"])
    return float(score["score"])


def _refused_receipt(
    *,
    scoring: dict,
    scores: list[dict],
    labels: dict,
    scoring_receipt_path: Path,
    blind_scores_path: Path,
    label_join_path: Path,
    arm_means_path: Path,
    task_family_means_path: Path,
    factor_effects_path: Path,
) -> RealTaskQualityFactorialAnalysisReceipt:
    return RealTaskQualityFactorialAnalysisReceipt(
        analysis_version=REAL_TASK_QUALITY_FACTORIAL_VERSION,
        status=REAL_TASK_QUALITY_FACTORIAL_REFUSED_TOKEN,
        scoring_status=str(scoring.get("status")),
        scores_loaded=len(scores),
        labels_loaded=len(labels),
        arms_analyzed=0,
        arm_quality_means_path=str(arm_means_path),
        task_family_quality_means_path=str(task_family_means_path),
        quality_factor_effects_path=str(factor_effects_path),
        baseline_arm=BASELINE_ARM,
        baseline_mean_score=0.0,
        full_arm=FULL_ARM,
        full_mean_score=0.0,
        full_minus_baseline_effect=0.0,
        best_arm="",
        best_mean_score=0.0,
        real_quality_scores_analyzed=False,
        positive_full_stack_quality_effect_observed=False,
        real_adaptive_evidence=False,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        scoring_receipt_sha256=_sha256_path(scoring_receipt_path),
        blind_scores_sha256=_sha256_path(blind_scores_path),
        label_join_sha256=_sha256_path(label_join_path),
        boundary=(
            "Real task-quality factorial analysis refused because the blind scoring receipt, "
            "25 blind scores, or 25 label records were incomplete or contaminated. No adaptive, "
            "commercial, professional, publication, spend, fulfilment, world-first, or "
            "authority-expansion claim is authorized."
        ),
    )


def analyze_real_task_quality_scores(
    *,
    scoring_receipt_path: Path,
    blind_scores_path: Path,
    label_join_path: Path,
    output_dir: Path,
) -> RealTaskQualityFactorialAnalysisReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)

    scoring = _load_json(scoring_receipt_path)
    scores = _load_jsonl(blind_scores_path)
    labels = _load_json(label_join_path)

    arm_means_path = output_dir / "real_task_quality_arm_means.json"
    task_family_means_path = output_dir / "real_task_quality_task_family_means.json"
    factor_effects_path = output_dir / "real_task_quality_factor_effects.json"
    receipt_path = output_dir / "real_task_quality_factorial_analysis_receipt.json"

    ready = (
        scoring.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_BLIND_RUBRIC_SCORING_READY"
        and scoring.get("real_quality_scores_available") is True
        and scoring.get("outputs_scored") == 25
        and scoring.get("real_adaptive_evidence") is False
        and scoring.get("adaptive_claim_authorized") is False
        and len(scores) == 25
        and len(labels) == 25
        and all(score.get("blind_id") in labels for score in scores)
        and all("arm" not in score for score in scores)
    )

    if not ready:
        receipt = _refused_receipt(
            scoring=scoring,
            scores=scores,
            labels=labels,
            scoring_receipt_path=scoring_receipt_path,
            blind_scores_path=blind_scores_path,
            label_join_path=label_join_path,
            arm_means_path=arm_means_path,
            task_family_means_path=task_family_means_path,
            factor_effects_path=factor_effects_path,
        )
        receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    by_arm: dict[str, list[float]] = {arm: [] for arm in EXPECTED_ARMS}
    by_family: dict[str, list[float]] = {}

    for score in scores:
        blind_id = score["blind_id"]
        label = labels[blind_id]
        arm = label["arm"]
        family = label.get("task_family", score.get("task_family", "unknown"))
        numeric_score = _score_value(score)
        by_arm.setdefault(arm, []).append(numeric_score)
        by_family.setdefault(family, []).append(numeric_score)

    arm_means = {
        arm: {"n": len(values), "mean_score": _mean(values), "scores": values}
        for arm, values in sorted(by_arm.items())
    }
    task_family_means = {
        family: {"n": len(values), "mean_score": _mean(values), "scores": values}
        for family, values in sorted(by_family.items())
    }

    baseline_mean = float(arm_means.get(BASELINE_ARM, {}).get("mean_score", 0.0))
    full_mean = float(arm_means.get(FULL_ARM, {}).get("mean_score", 0.0))
    effect = full_mean - baseline_mean
    best_arm, best_payload = max(arm_means.items(), key=lambda item: (item[1]["mean_score"], item[0]))
    complete_arm_counts = all(arm_means.get(arm, {}).get("n") == 5 for arm in EXPECTED_ARMS)
    positive_effect = bool(complete_arm_counts and effect > 0.0 and best_arm == FULL_ARM)

    factor_effects = {
        "baseline_arm": BASELINE_ARM,
        "full_arm": FULL_ARM,
        "baseline_mean_score": baseline_mean,
        "full_mean_score": full_mean,
        "full_minus_baseline_effect": effect,
        "best_arm": best_arm,
        "best_mean_score": float(best_payload["mean_score"]),
        "complete_arm_counts": complete_arm_counts,
        "real_quality_scores_analyzed": True,
        "positive_full_stack_quality_effect_observed": positive_effect,
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
        "claim_boundary": (
            "A positive quality differential is an observation for claim-gate review only. "
            "This analysis does not authorize adaptive-performance claims by itself."
        ),
    }

    arm_means_path.write_text(json.dumps(arm_means, indent=2, sort_keys=True) + "\n")
    task_family_means_path.write_text(json.dumps(task_family_means, indent=2, sort_keys=True) + "\n")
    factor_effects_path.write_text(json.dumps(factor_effects, indent=2, sort_keys=True) + "\n")

    receipt = RealTaskQualityFactorialAnalysisReceipt(
        analysis_version=REAL_TASK_QUALITY_FACTORIAL_VERSION,
        status=REAL_TASK_QUALITY_FACTORIAL_READY_TOKEN,
        scoring_status=str(scoring.get("status")),
        scores_loaded=len(scores),
        labels_loaded=len(labels),
        arms_analyzed=len([arm for arm in EXPECTED_ARMS if arm_means.get(arm, {}).get("n", 0) > 0]),
        arm_quality_means_path=str(arm_means_path),
        task_family_quality_means_path=str(task_family_means_path),
        quality_factor_effects_path=str(factor_effects_path),
        baseline_arm=BASELINE_ARM,
        baseline_mean_score=baseline_mean,
        full_arm=FULL_ARM,
        full_mean_score=full_mean,
        full_minus_baseline_effect=effect,
        best_arm=best_arm,
        best_mean_score=float(best_payload["mean_score"]),
        real_quality_scores_analyzed=True,
        positive_full_stack_quality_effect_observed=positive_effect,
        real_adaptive_evidence=False,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        scoring_receipt_sha256=_sha256_path(scoring_receipt_path),
        blind_scores_sha256=_sha256_path(blind_scores_path),
        label_join_sha256=_sha256_path(label_join_path),
        boundary=(
            "This gate rejoins labels after blind scoring and computes arm means, task-family means, "
            "and the full-minus-baseline quality effect for claim-gate review. It does not by itself "
            "authorize an adaptive-performance claim, retained-learning claim, commercial validation, "
            "professional approval, publication, spend, fulfilment, world-first claim, or authority expansion."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
