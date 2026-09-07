from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


REAL_TASK_QUALITY_CLAIM_GATE_VERSION = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_CLAIM_GATE_V1"
REAL_TASK_QUALITY_CLAIM_GATE_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_CLAIM_GATE_VERDICT_READY"
REAL_TASK_QUALITY_CLAIM_GATE_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_CLAIM_GATE_REFUSED"


@dataclass(frozen=True)
class RealTaskQualityClaimGateReceipt:
    gate_version: str
    status: str
    bundle_status: str
    execution_status: str
    rubric_evaluation_status: str
    arm_analysis_status: str
    assignments_staged: int
    task_outputs_produced: int
    rubric_scores_written: int
    scores_loaded: int
    arms_analyzed: int
    tasks_analyzed: int
    mean_quality_score: float
    baseline_arm: str
    baseline_arm_mean: float
    full_arm: str
    full_arm_mean: float
    full_minus_baseline_effect: float
    quality_pipeline_exercised: bool
    mechanics_proven: bool
    real_adaptive_evidence: bool
    allowed_claim_tier: str
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    bundle_receipt_sha256: str
    execution_receipt_sha256: str
    rubric_evaluation_sha256: str
    arm_analysis_sha256: str
    boundary: str


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate_real_task_quality_claim_gate(
    *,
    bundle_receipt_path: Path,
    execution_receipt_path: Path,
    rubric_evaluation_receipt_path: Path,
    arm_analysis_receipt_path: Path,
) -> RealTaskQualityClaimGateReceipt:
    bundle = _load(bundle_receipt_path)
    execution = _load(execution_receipt_path)
    rubric = _load(rubric_evaluation_receipt_path)
    analysis = _load(arm_analysis_receipt_path)

    bundle_ready = (
        bundle.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_BUNDLE_READY"
        and bundle.get("task_assignments_staged") == 25
        and bundle.get("real_task_quality_scoring_authorized") is True
        and bundle.get("execute_by_default") is False
        and bundle.get("adaptive_claim_authorized") is False
        and bundle.get("commercial_or_world_first_claim_authorized") is False
    )

    execution_ready = (
        execution.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_EXECUTION_READY"
        and execution.get("executed") is True
        and execution.get("assignments_loaded") == 25
        and execution.get("task_outputs_produced") == 25
        and execution.get("real_task_quality_scoring_authorized") is True
        and execution.get("adaptive_claim_authorized") is False
        and execution.get("commercial_or_world_first_claim_authorized") is False
    )

    rubric_ready = (
        rubric.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_RUBRIC_EVALUATION_READY"
        and rubric.get("outputs_loaded") == 25
        and rubric.get("rubric_scores_written") == 25
        and rubric.get("real_task_quality_evaluation_authorized") is True
        and rubric.get("real_adaptive_evidence") is False
        and rubric.get("adaptive_claim_authorized") is False
        and rubric.get("commercial_or_world_first_claim_authorized") is False
    )

    analysis_ready = (
        analysis.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_ARM_ANALYSIS_READY"
        and analysis.get("scores_loaded") == 25
        and analysis.get("labels_loaded") == 25
        and analysis.get("arms_analyzed") == 5
        and analysis.get("tasks_analyzed") == 5
        and analysis.get("real_task_quality_analysis_authorized") is True
        and analysis.get("real_adaptive_evidence") is False
        and analysis.get("adaptive_claim_authorized") is False
        and analysis.get("commercial_or_world_first_claim_authorized") is False
    )

    quality_pipeline_exercised = bundle_ready and execution_ready and rubric_ready and analysis_ready
    mechanics_proven = quality_pipeline_exercised

    mean_quality_score = float(rubric.get("mean_quality_score", 0.0))
    baseline_arm_mean = float(analysis.get("baseline_arm_mean", 0.0))
    full_arm_mean = float(analysis.get("full_arm_mean", 0.0))
    full_minus_baseline_effect = float(analysis.get("full_minus_baseline_effect", 0.0))

    return RealTaskQualityClaimGateReceipt(
        gate_version=REAL_TASK_QUALITY_CLAIM_GATE_VERSION,
        status=REAL_TASK_QUALITY_CLAIM_GATE_READY_TOKEN if mechanics_proven else REAL_TASK_QUALITY_CLAIM_GATE_REFUSED_TOKEN,
        bundle_status=str(bundle.get("status")),
        execution_status=str(execution.get("status")),
        rubric_evaluation_status=str(rubric.get("status")),
        arm_analysis_status=str(analysis.get("status")),
        assignments_staged=int(bundle.get("task_assignments_staged", 0)),
        task_outputs_produced=int(execution.get("task_outputs_produced", 0)),
        rubric_scores_written=int(rubric.get("rubric_scores_written", 0)),
        scores_loaded=int(analysis.get("scores_loaded", 0)),
        arms_analyzed=int(analysis.get("arms_analyzed", 0)),
        tasks_analyzed=int(analysis.get("tasks_analyzed", 0)),
        mean_quality_score=mean_quality_score,
        baseline_arm=str(analysis.get("baseline_arm", "A_STATELESS_RESET")),
        baseline_arm_mean=baseline_arm_mean,
        full_arm=str(analysis.get("full_arm", "E_FULL_SEMANTIC_MARKET_BEAST")),
        full_arm_mean=full_arm_mean,
        full_minus_baseline_effect=full_minus_baseline_effect,
        quality_pipeline_exercised=quality_pipeline_exercised,
        mechanics_proven=mechanics_proven,
        real_adaptive_evidence=False,
        allowed_claim_tier=(
            "T4_REAL_TASK_QUALITY_PIPELINE_EXERCISED_NO_ADAPTIVE_CLAIM"
            if mechanics_proven
            else "T0_NO_CLAIM"
        ),
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        bundle_receipt_sha256=_sha256_path(bundle_receipt_path),
        execution_receipt_sha256=_sha256_path(execution_receipt_path),
        rubric_evaluation_sha256=_sha256_path(rubric_evaluation_receipt_path),
        arm_analysis_sha256=_sha256_path(arm_analysis_receipt_path),
        boundary=(
            "This real task-quality claim gate authorizes only the statement that the frozen task-quality "
            "bundle, blinded task output generation, rubric scoring, and post-score arm analysis pipeline "
            "were exercised. It does not authorize an adaptive-composition claim, retained-learning claim, "
            "real performance improvement claim, commercial validation claim, professional approval claim, "
            "publication, spend, fulfilment, world-first claim, or authority expansion."
        ),
    )


def write_real_task_quality_claim_gate(
    *,
    bundle_receipt_path: Path,
    execution_receipt_path: Path,
    rubric_evaluation_receipt_path: Path,
    arm_analysis_receipt_path: Path,
    output_path: Path,
) -> RealTaskQualityClaimGateReceipt:
    receipt = evaluate_real_task_quality_claim_gate(
        bundle_receipt_path=bundle_receipt_path,
        execution_receipt_path=execution_receipt_path,
        rubric_evaluation_receipt_path=rubric_evaluation_receipt_path,
        arm_analysis_receipt_path=arm_analysis_receipt_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
