from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


REAL_TASK_QUALITY_DIGEST_VERSION = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_DIGEST_V1"
REAL_TASK_QUALITY_DIGEST_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_DIGEST_READY"
REAL_TASK_QUALITY_DIGEST_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_DIGEST_REFUSED"


@dataclass(frozen=True)
class RealTaskQualityDigest:
    digest_version: str
    status: str
    bundle_status: str
    execution_status: str
    rubric_evaluation_status: str
    arm_analysis_status: str
    claim_gate_status: str
    real_task_quality_end_to_end_proven: bool
    quality_pipeline_exercised: bool
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
    allowed_claim_tier: str
    real_adaptive_evidence: bool
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
    claim_gate_sha256: str
    boundary: str


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_real_task_quality_digest(
    *,
    bundle_receipt_path: Path,
    execution_receipt_path: Path,
    rubric_evaluation_receipt_path: Path,
    arm_analysis_receipt_path: Path,
    claim_gate_path: Path,
) -> RealTaskQualityDigest:
    bundle = _load(bundle_receipt_path)
    execution = _load(execution_receipt_path)
    rubric = _load(rubric_evaluation_receipt_path)
    arm_analysis = _load(arm_analysis_receipt_path)
    claim_gate = _load(claim_gate_path)

    assignments_staged = int(bundle.get("task_assignments_staged", 0))
    task_outputs_produced = int(execution.get("task_outputs_produced", 0))
    rubric_scores_written = int(rubric.get("rubric_scores_written", 0))
    scores_loaded = int(arm_analysis.get("scores_loaded", 0))
    arms_analyzed = int(arm_analysis.get("arms_analyzed", 0))
    tasks_analyzed = int(arm_analysis.get("tasks_analyzed", 0))
    mean_quality_score = float(rubric.get("mean_quality_score", 0.0))
    full_minus_baseline_effect = float(arm_analysis.get("full_minus_baseline_effect", 0.0))

    bundle_ready = (
        bundle.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_BUNDLE_READY"
        and assignments_staged == 25
        and bundle.get("real_task_quality_scoring_authorized") is True
        and bundle.get("adaptive_claim_authorized") is False
    )
    execution_ready = (
        execution.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_EXECUTION_READY"
        and execution.get("executed") is True
        and task_outputs_produced == 25
        and execution.get("adaptive_claim_authorized") is False
    )
    rubric_ready = (
        rubric.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_RUBRIC_EVALUATION_READY"
        and rubric_scores_written == 25
        and rubric.get("real_adaptive_evidence") is False
        and rubric.get("adaptive_claim_authorized") is False
    )
    arm_analysis_ready = (
        arm_analysis.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_ARM_ANALYSIS_READY"
        and scores_loaded == 25
        and arms_analyzed == 5
        and tasks_analyzed == 5
        and arm_analysis.get("real_adaptive_evidence") is False
        and arm_analysis.get("adaptive_claim_authorized") is False
    )
    claim_gate_ready = (
        claim_gate.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_CLAIM_GATE_VERDICT_READY"
        and claim_gate.get("quality_pipeline_exercised") is True
        and claim_gate.get("mechanics_proven") is True
        and claim_gate.get("allowed_claim_tier") == "T4_REAL_TASK_QUALITY_PIPELINE_EXERCISED_NO_ADAPTIVE_CLAIM"
        and claim_gate.get("real_adaptive_evidence") is False
        and claim_gate.get("adaptive_claim_authorized") is False
    )

    end_to_end = (
        bundle_ready
        and execution_ready
        and rubric_ready
        and arm_analysis_ready
        and claim_gate_ready
    )

    return RealTaskQualityDigest(
        digest_version=REAL_TASK_QUALITY_DIGEST_VERSION,
        status=REAL_TASK_QUALITY_DIGEST_READY_TOKEN if end_to_end else REAL_TASK_QUALITY_DIGEST_REFUSED_TOKEN,
        bundle_status=str(bundle.get("status")),
        execution_status=str(execution.get("status")),
        rubric_evaluation_status=str(rubric.get("status")),
        arm_analysis_status=str(arm_analysis.get("status")),
        claim_gate_status=str(claim_gate.get("status")),
        real_task_quality_end_to_end_proven=end_to_end,
        quality_pipeline_exercised=bool(claim_gate.get("quality_pipeline_exercised")) if end_to_end else False,
        assignments_staged=assignments_staged,
        task_outputs_produced=task_outputs_produced,
        rubric_scores_written=rubric_scores_written,
        scores_loaded=scores_loaded,
        arms_analyzed=arms_analyzed,
        tasks_analyzed=tasks_analyzed,
        mean_quality_score=mean_quality_score,
        baseline_arm=str(arm_analysis.get("baseline_arm", "A_STATELESS_RESET")),
        baseline_arm_mean=float(arm_analysis.get("baseline_arm_mean", 0.0)),
        full_arm=str(arm_analysis.get("full_arm", "E_FULL_SEMANTIC_MARKET_BEAST")),
        full_arm_mean=float(arm_analysis.get("full_arm_mean", 0.0)),
        full_minus_baseline_effect=full_minus_baseline_effect,
        allowed_claim_tier=(
            "T4_REAL_TASK_QUALITY_PIPELINE_EXERCISED_NO_ADAPTIVE_CLAIM"
            if end_to_end
            else "T0_NO_CLAIM"
        ),
        real_adaptive_evidence=False,
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
        claim_gate_sha256=_sha256_path(claim_gate_path),
        boundary=(
            "This digest authorizes only the statement that the real task-quality bundle, "
            "blinded output generation, rubric evaluation, post-score arm analysis, and claim gate "
            "completed compatibly. It does not authorize an adaptive-composition claim, retained-"
            "learning claim, real performance improvement claim, commercial validation claim, "
            "professional approval claim, publication, spend, fulfilment, world-first claim, or "
            "authority expansion."
        ),
    )


def write_real_task_quality_digest(
    *,
    bundle_receipt_path: Path,
    execution_receipt_path: Path,
    rubric_evaluation_receipt_path: Path,
    arm_analysis_receipt_path: Path,
    claim_gate_path: Path,
    output_path: Path,
) -> RealTaskQualityDigest:
    digest = build_real_task_quality_digest(
        bundle_receipt_path=bundle_receipt_path,
        execution_receipt_path=execution_receipt_path,
        rubric_evaluation_receipt_path=rubric_evaluation_receipt_path,
        arm_analysis_receipt_path=arm_analysis_receipt_path,
        claim_gate_path=claim_gate_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(digest), indent=2, sort_keys=True) + "\n")
    return digest
