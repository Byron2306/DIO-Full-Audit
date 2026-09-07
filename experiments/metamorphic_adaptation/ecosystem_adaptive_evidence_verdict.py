from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_VERSION = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_V1"
ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_READY"
ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_REFUSED"

MINIMUM_MEAN_ECOSYSTEM_QUALITY_SCORE = 0.6
MINIMUM_FULL_MINUS_BASELINE_EFFECT = 0.15


@dataclass(frozen=True)
class EcosystemAdaptiveEvidenceVerdict:
    verdict_version: str
    status: str
    arm_analysis_status: str
    arms_analyzed: int
    tasks_analyzed: int
    mean_ecosystem_quality_score: float
    mean_organ_coverage_score: float
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
    arm_analysis_sha256: str
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate_ecosystem_adaptive_evidence(
    *,
    arm_analysis_path: Path,
    minimum_mean_ecosystem_quality_score: float = MINIMUM_MEAN_ECOSYSTEM_QUALITY_SCORE,
    minimum_full_minus_baseline_effect: float = MINIMUM_FULL_MINUS_BASELINE_EFFECT,
) -> EcosystemAdaptiveEvidenceVerdict:
    analysis = _load_json(arm_analysis_path)

    ready = (
        analysis.get("status") == "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_READY"
        and analysis.get("ecosystem_arm_analysis_authorized") is True
        and analysis.get("adaptive_claim_authorized") is False
        and analysis.get("arms_analyzed") == 5
        and analysis.get("tasks_analyzed") == 5
    )

    mean_quality = float(analysis.get("mean_ecosystem_quality_score", 0.0))
    effect = float(analysis.get("full_minus_baseline_effect", 0.0))
    quality_threshold_met = ready and mean_quality >= minimum_mean_ecosystem_quality_score
    effect_threshold_met = ready and effect >= minimum_full_minus_baseline_effect
    real_evidence = bool(quality_threshold_met and effect_threshold_met)

    if not ready:
        verdict_text = "ECOSYSTEM_ADAPTIVE_EVIDENCE_REFUSED_SOURCE_NOT_READY"
        allowed_claim_tier = "T0_NO_CLAIM"
    elif real_evidence:
        verdict_text = "ECOSYSTEM_ADAPTIVE_EVIDENCE_THRESHOLD_MET"
        allowed_claim_tier = "T5_BOUNDED_ECOSYSTEM_ADAPTIVE_EVIDENCE_CLAIM"
    elif not quality_threshold_met:
        verdict_text = "NO_ECOSYSTEM_ADAPTIVE_EVIDENCE_QUALITY_THRESHOLD_NOT_MET"
        allowed_claim_tier = "T4_ECOSYSTEM_QUALITY_PIPELINE_EXERCISED_NO_ADAPTIVE_CLAIM"
    else:
        verdict_text = "NO_ECOSYSTEM_ADAPTIVE_EVIDENCE_EFFECT_THRESHOLD_NOT_MET"
        allowed_claim_tier = "T4_ECOSYSTEM_QUALITY_PIPELINE_EXERCISED_NO_ADAPTIVE_CLAIM"

    return EcosystemAdaptiveEvidenceVerdict(
        verdict_version=ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_VERSION,
        status=(
            ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_READY_TOKEN
            if ready
            else ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_REFUSED_TOKEN
        ),
        arm_analysis_status=str(analysis.get("status")),
        arms_analyzed=int(analysis.get("arms_analyzed", 0)),
        tasks_analyzed=int(analysis.get("tasks_analyzed", 0)),
        mean_ecosystem_quality_score=mean_quality,
        mean_organ_coverage_score=float(analysis.get("mean_organ_coverage_score", 0.0)),
        baseline_arm=str(analysis.get("baseline_arm", "A_DIO_CORE_ONLY")),
        baseline_arm_mean=float(analysis.get("baseline_arm_mean", 0.0)),
        full_arm=str(analysis.get("full_arm", "E_FULL_ECOSYSTEM_ORCHESTRATION")),
        full_arm_mean=float(analysis.get("full_arm_mean", 0.0)),
        full_minus_baseline_effect=effect,
        minimum_mean_ecosystem_quality_score=minimum_mean_ecosystem_quality_score,
        minimum_full_minus_baseline_effect=minimum_full_minus_baseline_effect,
        ecosystem_quality_threshold_met=quality_threshold_met,
        ecosystem_adaptive_effect_threshold_met=effect_threshold_met,
        ecosystem_adaptive_evidence_verdict=verdict_text,
        allowed_claim_tier=allowed_claim_tier,
        real_ecosystem_adaptive_evidence=real_evidence,
        adaptive_claim_authorized=real_evidence,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        arm_analysis_sha256=_sha256_path(arm_analysis_path),
        boundary=(
            "This ecosystem adaptive evidence verdict evaluates whether post-score label-rejoined ecosystem "
            "arm analysis meets predeclared mean-quality and full-minus-baseline thresholds. When both "
            "thresholds are met, it authorizes only a bounded ecosystem adaptive-evidence claim. It never "
            "authorizes commercial validation, professional approval, publication, spend, fulfilment, "
            "world-first status, or authority expansion."
        ),
    )


def write_ecosystem_adaptive_evidence_verdict(
    *,
    arm_analysis_path: Path,
    output_path: Path,
    minimum_mean_ecosystem_quality_score: float = MINIMUM_MEAN_ECOSYSTEM_QUALITY_SCORE,
    minimum_full_minus_baseline_effect: float = MINIMUM_FULL_MINUS_BASELINE_EFFECT,
) -> EcosystemAdaptiveEvidenceVerdict:
    verdict = evaluate_ecosystem_adaptive_evidence(
        arm_analysis_path=arm_analysis_path,
        minimum_mean_ecosystem_quality_score=minimum_mean_ecosystem_quality_score,
        minimum_full_minus_baseline_effect=minimum_full_minus_baseline_effect,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(verdict), indent=2, sort_keys=True) + "\n")
    return verdict
