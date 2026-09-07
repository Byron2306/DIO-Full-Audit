from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_VERSION = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_V1"
ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_READY"
ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_REFUSED"


@dataclass(frozen=True)
class EcosystemAdaptationEvidenceDigest:
    digest_version: str
    status: str
    organ_registry_status: str
    ecosystem_plan_status: str
    ecosystem_execution_status: str
    ecosystem_rubric_evaluation_status: str
    ecosystem_arm_analysis_status: str
    ecosystem_adaptive_verdict_status: str
    organs_registered: int
    planned_encounters: int
    ecosystem_outputs_produced: int
    ecosystem_scores_written: int
    arms_analyzed: int
    tasks_analyzed: int
    mean_ecosystem_quality_score: float
    mean_organ_coverage_score: float
    organ_gap_outputs: int
    full_coverage_outputs: int
    baseline_arm: str
    baseline_arm_mean: float
    full_arm: str
    full_arm_mean: float
    full_minus_baseline_effect: float
    minimum_mean_ecosystem_quality_score: float
    minimum_full_minus_baseline_effect: float
    ecosystem_quality_threshold_met: bool
    ecosystem_adaptive_effect_threshold_met: bool
    ecosystem_adaptive_evidence_verdict: str
    allowed_claim_tier: str
    real_ecosystem_adaptive_evidence: bool
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    organ_registry_sha256: str
    ecosystem_plan_sha256: str
    ecosystem_execution_sha256: str
    ecosystem_rubric_evaluation_sha256: str
    ecosystem_arm_analysis_sha256: str
    ecosystem_adaptive_verdict_sha256: str
    boundary: str


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_ecosystem_adaptation_evidence_digest(
    *,
    organ_registry_receipt_path: Path,
    ecosystem_plan_receipt_path: Path,
    ecosystem_execution_receipt_path: Path,
    ecosystem_rubric_evaluation_receipt_path: Path,
    ecosystem_arm_analysis_receipt_path: Path,
    ecosystem_adaptive_verdict_path: Path,
) -> EcosystemAdaptationEvidenceDigest:
    registry = _load(organ_registry_receipt_path)
    plan = _load(ecosystem_plan_receipt_path)
    execution = _load(ecosystem_execution_receipt_path)
    rubric = _load(ecosystem_rubric_evaluation_receipt_path)
    arm_analysis = _load(ecosystem_arm_analysis_receipt_path)
    verdict = _load(ecosystem_adaptive_verdict_path)

    registry_ready = (
        registry.get("status") == "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ORGAN_CAPABILITY_REGISTRY_READY"
        and registry.get("organs_registered") == 11
        and registry.get("real_ecosystem_execution_authorized") is True
        and registry.get("adaptive_claim_authorized") is False
    )
    plan_ready = (
        plan.get("status") == "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_ADAPTATION_PLAN_READY"
        and plan.get("tests_true_adaptive_surface") is True
        and plan.get("planned_encounters") == 25
        and plan.get("adaptive_claim_authorized") is False
    )
    execution_ready = (
        execution.get("status") == "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_EXECUTION_READY"
        and execution.get("executed") is True
        and execution.get("ecosystem_outputs_produced") == 25
        and execution.get("ecosystem_quality_scoring_authorized") is True
        and execution.get("adaptive_claim_authorized") is False
    )
    rubric_ready = (
        rubric.get("status") == "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATION_READY"
        and rubric.get("ecosystem_scores_written") == 25
        and rubric.get("ecosystem_arm_analysis_authorized") is True
        and rubric.get("adaptive_claim_authorized") is False
    )
    arm_analysis_ready = (
        arm_analysis.get("status") == "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_READY"
        and arm_analysis.get("arms_analyzed") == 5
        and arm_analysis.get("tasks_analyzed") == 5
        and arm_analysis.get("adaptive_claim_authorized") is False
    )
    verdict_ready = (
        verdict.get("status") == "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_READY"
        and verdict.get("arm_analysis_status") == "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_READY"
    )
    ready = registry_ready and plan_ready and execution_ready and rubric_ready and arm_analysis_ready and verdict_ready

    return EcosystemAdaptationEvidenceDigest(
        digest_version=ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_VERSION,
        status=ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_READY_TOKEN if ready else ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_REFUSED_TOKEN,
        organ_registry_status=str(registry.get("status")),
        ecosystem_plan_status=str(plan.get("status")),
        ecosystem_execution_status=str(execution.get("status")),
        ecosystem_rubric_evaluation_status=str(rubric.get("status")),
        ecosystem_arm_analysis_status=str(arm_analysis.get("status")),
        ecosystem_adaptive_verdict_status=str(verdict.get("status")),
        organs_registered=int(registry.get("organs_registered", 0)),
        planned_encounters=int(plan.get("planned_encounters", 0)),
        ecosystem_outputs_produced=int(execution.get("ecosystem_outputs_produced", 0)),
        ecosystem_scores_written=int(rubric.get("ecosystem_scores_written", 0)),
        arms_analyzed=int(arm_analysis.get("arms_analyzed", 0)),
        tasks_analyzed=int(arm_analysis.get("tasks_analyzed", 0)),
        mean_ecosystem_quality_score=float(verdict.get("mean_ecosystem_quality_score", rubric.get("mean_ecosystem_quality_score", 0.0))),
        mean_organ_coverage_score=float(verdict.get("mean_organ_coverage_score", rubric.get("mean_organ_coverage_score", 0.0))),
        organ_gap_outputs=int(rubric.get("organ_gap_outputs", execution.get("organ_gap_outputs", 0))),
        full_coverage_outputs=int(rubric.get("full_coverage_outputs", execution.get("full_coverage_outputs", 0))),
        baseline_arm=str(verdict.get("baseline_arm", arm_analysis.get("baseline_arm", "A_DIO_CORE_ONLY"))),
        baseline_arm_mean=float(verdict.get("baseline_arm_mean", arm_analysis.get("baseline_arm_mean", 0.0))),
        full_arm=str(verdict.get("full_arm", arm_analysis.get("full_arm", "E_FULL_ECOSYSTEM_ORCHESTRATION"))),
        full_arm_mean=float(verdict.get("full_arm_mean", arm_analysis.get("full_arm_mean", 0.0))),
        full_minus_baseline_effect=float(verdict.get("full_minus_baseline_effect", arm_analysis.get("full_minus_baseline_effect", 0.0))),
        minimum_mean_ecosystem_quality_score=float(verdict.get("minimum_mean_ecosystem_quality_score", 0.0)),
        minimum_full_minus_baseline_effect=float(verdict.get("minimum_full_minus_baseline_effect", 0.0)),
        ecosystem_quality_threshold_met=bool(verdict.get("ecosystem_quality_threshold_met")) if ready else False,
        ecosystem_adaptive_effect_threshold_met=bool(verdict.get("ecosystem_adaptive_effect_threshold_met")) if ready else False,
        ecosystem_adaptive_evidence_verdict=str(verdict.get("ecosystem_adaptive_evidence_verdict", "NO_VERDICT")),
        allowed_claim_tier=str(verdict.get("allowed_claim_tier", "T0_NO_CLAIM")) if ready else "T0_NO_CLAIM",
        real_ecosystem_adaptive_evidence=bool(verdict.get("real_ecosystem_adaptive_evidence")) if ready else False,
        adaptive_claim_authorized=bool(verdict.get("adaptive_claim_authorized")) if ready else False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        organ_registry_sha256=_sha256_path(organ_registry_receipt_path),
        ecosystem_plan_sha256=_sha256_path(ecosystem_plan_receipt_path),
        ecosystem_execution_sha256=_sha256_path(ecosystem_execution_receipt_path),
        ecosystem_rubric_evaluation_sha256=_sha256_path(ecosystem_rubric_evaluation_receipt_path),
        ecosystem_arm_analysis_sha256=_sha256_path(ecosystem_arm_analysis_receipt_path),
        ecosystem_adaptive_verdict_sha256=_sha256_path(ecosystem_adaptive_verdict_path),
        boundary=(
            "This ecosystem adaptation evidence digest binds the organ registry, ecosystem plan, explicit execution, "
            "blinded rubric evaluation, post-score arm analysis, and ecosystem adaptive evidence verdict. It authorizes "
            "only the bounded claim tier granted by the ecosystem adaptive evidence verdict. It never authorizes commercial "
            "validation, professional approval, publication, spend, fulfilment, world-first status, or authority expansion."
        ),
    )


def write_ecosystem_adaptation_evidence_digest(
    *,
    organ_registry_receipt_path: Path,
    ecosystem_plan_receipt_path: Path,
    ecosystem_execution_receipt_path: Path,
    ecosystem_rubric_evaluation_receipt_path: Path,
    ecosystem_arm_analysis_receipt_path: Path,
    ecosystem_adaptive_verdict_path: Path,
    output_path: Path,
) -> EcosystemAdaptationEvidenceDigest:
    digest = build_ecosystem_adaptation_evidence_digest(
        organ_registry_receipt_path=organ_registry_receipt_path,
        ecosystem_plan_receipt_path=ecosystem_plan_receipt_path,
        ecosystem_execution_receipt_path=ecosystem_execution_receipt_path,
        ecosystem_rubric_evaluation_receipt_path=ecosystem_rubric_evaluation_receipt_path,
        ecosystem_arm_analysis_receipt_path=ecosystem_arm_analysis_receipt_path,
        ecosystem_adaptive_verdict_path=ecosystem_adaptive_verdict_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(digest), indent=2, sort_keys=True) + "\n")
    return digest
