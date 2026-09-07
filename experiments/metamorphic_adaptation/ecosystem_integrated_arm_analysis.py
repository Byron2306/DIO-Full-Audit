from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean


ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_VERSION = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_V1"
ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_READY"
ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_REFUSED"

BASELINE_ARM = "A_DIO_CORE_ONLY"
FULL_ARM = "E_FULL_ECOSYSTEM_ORCHESTRATION"


@dataclass(frozen=True)
class EcosystemIntegratedArmAnalysisReceipt:
    analysis_version: str
    status: str
    rubric_evaluation_status: str
    scores_loaded: int
    labels_loaded: int
    arms_analyzed: int
    tasks_analyzed: int
    baseline_arm: str
    baseline_arm_mean: float
    full_arm: str
    full_arm_mean: float
    full_minus_baseline_effect: float
    best_arm: str
    best_arm_mean: float
    mean_ecosystem_quality_score: float
    mean_organ_coverage_score: float
    ecosystem_arm_analysis_authorized: bool
    real_adaptive_evidence: bool
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    arm_means_path: str
    task_means_path: str
    factor_effects_path: str
    rubric_evaluation_sha256: str
    ecosystem_scores_sha256: str
    label_join_sha256: str
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _score(item: dict) -> float:
    return float(item.get("ecosystem_quality_score", item.get("quality_score", 0.0)))


def _coverage(item: dict) -> float:
    return float(item.get("organ_coverage_score", 0.0))


def _mean(values: list[float]) -> float:
    return round(mean(values), 6) if values else 0.0


def analyze_ecosystem_integrated_arms(
    *,
    rubric_evaluation_receipt_path: Path,
    ecosystem_scores_path: Path,
    label_join_path: Path,
    output_dir: Path,
) -> EcosystemIntegratedArmAnalysisReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)
    receipt = _load_json(rubric_evaluation_receipt_path)
    scores = _load_jsonl(ecosystem_scores_path)
    labels = _load_json(label_join_path)

    arm_means_path = output_dir / "ecosystem_integrated_arm_means.json"
    task_means_path = output_dir / "ecosystem_integrated_task_means.json"
    factor_effects_path = output_dir / "ecosystem_integrated_factor_effects.json"
    analysis_receipt_path = output_dir / "ecosystem_integrated_arm_analysis_receipt.json"

    ready = (
        receipt.get("status") == "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATION_READY"
        and receipt.get("ecosystem_arm_analysis_authorized") is True
        and receipt.get("adaptive_claim_authorized") is False
        and receipt.get("ecosystem_scores_written") == 25
        and len(scores) == 25
        and len(labels) == 25
        and all(item.get("status") == "ECOSYSTEM_INTEGRATED_RUBRIC_SCORE_RECORDED" for item in scores)
        and all(item.get("adaptive_claim_authorized") is False for item in scores)
        and all(str(item.get("blind_id")) in labels for item in scores)
    )

    if not ready:
        analysis = EcosystemIntegratedArmAnalysisReceipt(
            analysis_version=ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_VERSION,
            status=ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_REFUSED_TOKEN,
            rubric_evaluation_status=str(receipt.get("status")),
            scores_loaded=len(scores),
            labels_loaded=len(labels),
            arms_analyzed=0,
            tasks_analyzed=0,
            baseline_arm=BASELINE_ARM,
            baseline_arm_mean=0.0,
            full_arm=FULL_ARM,
            full_arm_mean=0.0,
            full_minus_baseline_effect=0.0,
            best_arm="NONE",
            best_arm_mean=0.0,
            mean_ecosystem_quality_score=0.0,
            mean_organ_coverage_score=0.0,
            ecosystem_arm_analysis_authorized=False,
            real_adaptive_evidence=False,
            adaptive_claim_authorized=False,
            commercial_or_world_first_claim_authorized=False,
            professional_approval_claim_authorized=False,
            publication_authorized=False,
            spend_authorized=False,
            fulfilment_authorized=False,
            authority_expansion_authorized=False,
            arm_means_path=str(arm_means_path),
            task_means_path=str(task_means_path),
            factor_effects_path=str(factor_effects_path),
            rubric_evaluation_sha256=_sha256_path(rubric_evaluation_receipt_path),
            ecosystem_scores_sha256=_sha256_path(ecosystem_scores_path),
            label_join_sha256=_sha256_path(label_join_path),
            boundary=(
                "Ecosystem integrated arm analysis refused because blinded scores, label join, or rubric "
                "evaluation receipt were not ready. No adaptive, commercial, professional, publication, "
                "spend, fulfilment, world-first, or authority-expansion claim is authorized."
            ),
        )
        analysis_receipt_path.write_text(json.dumps(asdict(analysis), indent=2, sort_keys=True) + "\n")
        return analysis

    by_arm: dict[str, list[float]] = defaultdict(list)
    coverage_by_arm: dict[str, list[float]] = defaultdict(list)
    by_task: dict[str, list[float]] = defaultdict(list)
    gaps_by_arm: dict[str, int] = defaultdict(int)

    for item in scores:
        blind_id = str(item["blind_id"])
        label = labels[blind_id]
        arm_id = str(label["arm_id"])
        task_id = str(label["task_id"])
        by_arm[arm_id].append(_score(item))
        coverage_by_arm[arm_id].append(_coverage(item))
        by_task[task_id].append(_score(item))
        if int(item.get("organ_gap_count", 0)) > 0:
            gaps_by_arm[arm_id] += 1

    arm_means = {
        arm_id: {
            "mean_ecosystem_quality_score": _mean(values),
            "mean_organ_coverage_score": _mean(coverage_by_arm[arm_id]),
            "encounters": len(values),
            "organ_gap_outputs": gaps_by_arm.get(arm_id, 0),
        }
        for arm_id, values in sorted(by_arm.items())
    }
    task_means = {
        task_id: {"mean_ecosystem_quality_score": _mean(values), "encounters": len(values)}
        for task_id, values in sorted(by_task.items())
    }

    baseline_mean = float(arm_means.get(BASELINE_ARM, {}).get("mean_ecosystem_quality_score", 0.0))
    full_mean = float(arm_means.get(FULL_ARM, {}).get("mean_ecosystem_quality_score", 0.0))
    effect = round(full_mean - baseline_mean, 6)
    best_arm, best_payload = max(
        arm_means.items(),
        key=lambda pair: (pair[1]["mean_ecosystem_quality_score"], pair[0]),
    )
    factor_effects = {
        "baseline_arm": BASELINE_ARM,
        "baseline_arm_mean": baseline_mean,
        "full_arm": FULL_ARM,
        "full_arm_mean": full_mean,
        "full_minus_baseline_effect": effect,
        "best_arm": best_arm,
        "best_arm_mean": float(best_payload["mean_ecosystem_quality_score"]),
        "claim_boundary": (
            "Arm analysis is descriptive only. It may reveal an ecosystem effect size for a later verdict gate, "
            "but does not itself authorize adaptive-performance claims."
        ),
    }

    arm_means_path.write_text(json.dumps(arm_means, indent=2, sort_keys=True) + "\n")
    task_means_path.write_text(json.dumps(task_means, indent=2, sort_keys=True) + "\n")
    factor_effects_path.write_text(json.dumps(factor_effects, indent=2, sort_keys=True) + "\n")

    all_scores = [_score(item) for item in scores]
    all_coverages = [_coverage(item) for item in scores]
    analysis = EcosystemIntegratedArmAnalysisReceipt(
        analysis_version=ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_VERSION,
        status=ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_READY_TOKEN,
        rubric_evaluation_status=str(receipt.get("status")),
        scores_loaded=len(scores),
        labels_loaded=len(labels),
        arms_analyzed=len(by_arm),
        tasks_analyzed=len(by_task),
        baseline_arm=BASELINE_ARM,
        baseline_arm_mean=baseline_mean,
        full_arm=FULL_ARM,
        full_arm_mean=full_mean,
        full_minus_baseline_effect=effect,
        best_arm=best_arm,
        best_arm_mean=float(best_payload["mean_ecosystem_quality_score"]),
        mean_ecosystem_quality_score=_mean(all_scores),
        mean_organ_coverage_score=_mean(all_coverages),
        ecosystem_arm_analysis_authorized=True,
        real_adaptive_evidence=False,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        arm_means_path=str(arm_means_path),
        task_means_path=str(task_means_path),
        factor_effects_path=str(factor_effects_path),
        rubric_evaluation_sha256=_sha256_path(rubric_evaluation_receipt_path),
        ecosystem_scores_sha256=_sha256_path(ecosystem_scores_path),
        label_join_sha256=_sha256_path(label_join_path),
        boundary=(
            "This analysis rejoins ecosystem arm labels only after blinded rubric scoring and summarizes "
            "quality by arm and task. It is descriptive analysis only, does not constitute adaptive "
            "performance evidence, does not claim improvement, and does not authorize commercial validation, "
            "professional approval, publication, spend, fulfilment, world-first, or authority expansion."
        ),
    )
    analysis_receipt_path.write_text(json.dumps(asdict(analysis), indent=2, sort_keys=True) + "\n")
    return analysis
