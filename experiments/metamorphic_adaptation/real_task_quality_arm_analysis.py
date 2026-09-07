from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean


REAL_TASK_QUALITY_ARM_ANALYSIS_VERSION = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_ARM_ANALYSIS_V1"
REAL_TASK_QUALITY_ARM_ANALYSIS_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_ARM_ANALYSIS_READY"
REAL_TASK_QUALITY_ARM_ANALYSIS_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_ARM_ANALYSIS_REFUSED"


@dataclass(frozen=True)
class RealTaskQualityArmAnalysisReceipt:
    analysis_version: str
    status: str
    rubric_evaluation_status: str
    scores_loaded: int
    labels_loaded: int
    arms_analyzed: int
    tasks_analyzed: int
    arm_means_path: str
    task_means_path: str
    factor_effects_path: str
    baseline_arm: str
    baseline_arm_mean: float
    full_arm: str
    full_arm_mean: float
    full_minus_baseline_effect: float
    best_arm: str
    best_arm_mean: float
    real_task_quality_analysis_authorized: bool
    real_adaptive_evidence: bool
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    rubric_evaluation_sha256: str
    rubric_scores_sha256: str
    label_join_sha256: str
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _score_value(item: dict) -> float:
    if "total_score" in item:
        return float(item["total_score"])
    if "quality_score" in item:
        return float(item["quality_score"])
    return float(item.get("score", 0.0))


def analyze_real_task_quality_by_arm(
    *,
    rubric_evaluation_receipt_path: Path,
    rubric_scores_path: Path,
    label_join_path: Path,
    output_dir: Path,
) -> RealTaskQualityArmAnalysisReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)

    receipt = _load_json(rubric_evaluation_receipt_path)
    scores = _load_jsonl(rubric_scores_path)
    labels = _load_json(label_join_path)

    arm_means_path = output_dir / "real_task_quality_arm_means.json"
    task_means_path = output_dir / "real_task_quality_task_means.json"
    factor_effects_path = output_dir / "real_task_quality_factor_effects.json"
    analysis_receipt_path = output_dir / "real_task_quality_arm_analysis_receipt.json"

    ready = (
        receipt.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_RUBRIC_EVALUATION_READY"
        and receipt.get("rubric_scores_written") == 25
        and receipt.get("real_task_quality_evaluation_authorized") is True
        and receipt.get("real_adaptive_evidence") is False
        and receipt.get("adaptive_claim_authorized") is False
        and len(scores) == 25
        and len(labels) == 25
        and all(item.get("blind_id") in labels for item in scores)
    )

    if not ready:
        result = RealTaskQualityArmAnalysisReceipt(
            analysis_version=REAL_TASK_QUALITY_ARM_ANALYSIS_VERSION,
            status=REAL_TASK_QUALITY_ARM_ANALYSIS_REFUSED_TOKEN,
            rubric_evaluation_status=str(receipt.get("status")),
            scores_loaded=len(scores),
            labels_loaded=len(labels),
            arms_analyzed=0,
            tasks_analyzed=0,
            arm_means_path=str(arm_means_path),
            task_means_path=str(task_means_path),
            factor_effects_path=str(factor_effects_path),
            baseline_arm="A_STATELESS_RESET",
            baseline_arm_mean=0.0,
            full_arm="E_FULL_SEMANTIC_MARKET_BEAST",
            full_arm_mean=0.0,
            full_minus_baseline_effect=0.0,
            best_arm="",
            best_arm_mean=0.0,
            real_task_quality_analysis_authorized=False,
            real_adaptive_evidence=False,
            adaptive_claim_authorized=False,
            commercial_or_world_first_claim_authorized=False,
            professional_approval_claim_authorized=False,
            publication_authorized=False,
            spend_authorized=False,
            fulfilment_authorized=False,
            authority_expansion_authorized=False,
            rubric_evaluation_sha256=_sha256_path(rubric_evaluation_receipt_path),
            rubric_scores_sha256=_sha256_path(rubric_scores_path),
            label_join_sha256=_sha256_path(label_join_path),
            boundary=(
                "Real task-quality arm analysis refused because rubric evaluation was not ready "
                "or the 25 score/label records were incomplete. No adaptive, commercial, professional, "
                "publication, spend, fulfilment, world-first, or authority-expansion claim is authorized."
            ),
        )
        analysis_receipt_path.write_text(json.dumps(asdict(result), indent=2, sort_keys=True) + "\n")
        return result

    by_arm: dict[str, list[float]] = {}
    by_task: dict[str, list[float]] = {}

    for item in scores:
        blind_id = item["blind_id"]
        label = labels[blind_id]
        arm = label["arm"]
        task_id = label["task_id"]
        score = _score_value(item)
        by_arm.setdefault(arm, []).append(score)
        by_task.setdefault(task_id, []).append(score)

    arm_means = {
        arm: {"n": len(values), "mean": mean(values), "scores": values}
        for arm, values in sorted(by_arm.items())
    }
    task_means = {
        task_id: {"n": len(values), "mean": mean(values), "scores": values}
        for task_id, values in sorted(by_task.items())
    }

    baseline_arm = "A_STATELESS_RESET"
    full_arm = "E_FULL_SEMANTIC_MARKET_BEAST"
    baseline_mean = float(arm_means.get(baseline_arm, {}).get("mean", 0.0))
    full_mean = float(arm_means.get(full_arm, {}).get("mean", 0.0))
    effect = full_mean - baseline_mean
    best_arm, best_payload = max(arm_means.items(), key=lambda item: (item[1]["mean"], item[0]))

    factor_effects = {
        "baseline_arm": baseline_arm,
        "baseline_arm_mean": baseline_mean,
        "full_arm": full_arm,
        "full_arm_mean": full_mean,
        "full_minus_baseline_effect": effect,
        "best_arm": best_arm,
        "best_arm_mean": float(best_payload["mean"]),
        "real_adaptive_evidence": False,
        "adaptive_claim_authorized": False,
        "claim_boundary": (
            "Arm-level task-quality differences are descriptive only at this gate. Adaptive evidence "
            "requires a later predeclared threshold gate and guardrail review."
        ),
    }

    arm_means_path.write_text(json.dumps(arm_means, indent=2, sort_keys=True) + "\n")
    task_means_path.write_text(json.dumps(task_means, indent=2, sort_keys=True) + "\n")
    factor_effects_path.write_text(json.dumps(factor_effects, indent=2, sort_keys=True) + "\n")

    result = RealTaskQualityArmAnalysisReceipt(
        analysis_version=REAL_TASK_QUALITY_ARM_ANALYSIS_VERSION,
        status=REAL_TASK_QUALITY_ARM_ANALYSIS_READY_TOKEN,
        rubric_evaluation_status=str(receipt.get("status")),
        scores_loaded=len(scores),
        labels_loaded=len(labels),
        arms_analyzed=len(arm_means),
        tasks_analyzed=len(task_means),
        arm_means_path=str(arm_means_path),
        task_means_path=str(task_means_path),
        factor_effects_path=str(factor_effects_path),
        baseline_arm=baseline_arm,
        baseline_arm_mean=baseline_mean,
        full_arm=full_arm,
        full_arm_mean=full_mean,
        full_minus_baseline_effect=effect,
        best_arm=best_arm,
        best_arm_mean=float(best_payload["mean"]),
        real_task_quality_analysis_authorized=True,
        real_adaptive_evidence=False,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        rubric_evaluation_sha256=_sha256_path(rubric_evaluation_receipt_path),
        rubric_scores_sha256=_sha256_path(rubric_scores_path),
        label_join_sha256=_sha256_path(label_join_path),
        boundary=(
            "This analysis rejoins labels only after blinded rubric scoring and summarizes real "
            "task-quality scores by arm and task. It is descriptive analysis only, does not constitute "
            "adaptive performance evidence, does not claim improvement, and does not authorize commercial "
            "validation, professional approval, publication, spend, fulfilment, world-first, or authority expansion."
        ),
    )
    analysis_receipt_path.write_text(json.dumps(asdict(result), indent=2, sort_keys=True) + "\n")
    return result
