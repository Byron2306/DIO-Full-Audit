from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


ADAPTIVE_EVIDENCE_VERDICT_VERSION = "DIO_METAMORPHIC_ADAPTATION_ADAPTIVE_EVIDENCE_VERDICT_V1"
ADAPTIVE_EVIDENCE_VERDICT_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ADAPTIVE_EVIDENCE_VERDICT_READY"
ADAPTIVE_EVIDENCE_VERDICT_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ADAPTIVE_EVIDENCE_VERDICT_REFUSED"

MINIMUM_MEAN_QUALITY_SCORE = 0.6
MINIMUM_FULL_MINUS_BASELINE_EFFECT = 0.15


@dataclass(frozen=True)
class AdaptiveEvidenceVerdictReceipt:
    verdict_version: str
    status: str
    real_task_quality_digest_status: str
    real_task_quality_end_to_end_proven: bool
    quality_pipeline_exercised: bool
    mean_quality_score: float
    baseline_arm: str
    baseline_arm_mean: float
    full_arm: str
    full_arm_mean: float
    full_minus_baseline_effect: float
    minimum_mean_quality_score: float
    minimum_full_minus_baseline_effect: float
    quality_threshold_met: bool
    adaptive_effect_threshold_met: bool
    adaptive_evidence_verdict: str
    real_adaptive_evidence: bool
    adaptive_claim_authorized: bool
    allowed_claim_tier: str
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    real_task_quality_digest_sha256: str
    boundary: str


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate_adaptive_evidence_verdict(
    *,
    real_task_quality_digest_path: Path,
    minimum_mean_quality_score: float = MINIMUM_MEAN_QUALITY_SCORE,
    minimum_full_minus_baseline_effect: float = MINIMUM_FULL_MINUS_BASELINE_EFFECT,
) -> AdaptiveEvidenceVerdictReceipt:
    digest = _load(real_task_quality_digest_path)

    digest_ready = (
        digest.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_DIGEST_READY"
        and digest.get("real_task_quality_end_to_end_proven") is True
        and digest.get("quality_pipeline_exercised") is True
        and digest.get("adaptive_claim_authorized") is False
        and digest.get("commercial_or_world_first_claim_authorized") is False
        and digest.get("real_adaptive_evidence") is False
    )

    mean_quality = float(digest.get("mean_quality_score", 0.0))
    effect = float(digest.get("full_minus_baseline_effect", 0.0))
    quality_threshold_met = mean_quality >= minimum_mean_quality_score
    adaptive_effect_threshold_met = effect >= minimum_full_minus_baseline_effect
    adaptive_evidence = digest_ready and quality_threshold_met and adaptive_effect_threshold_met

    if not digest_ready:
        verdict = "NO_ADAPTIVE_EVIDENCE_DIGEST_NOT_READY"
        status = ADAPTIVE_EVIDENCE_VERDICT_REFUSED_TOKEN
        tier = "T0_NO_CLAIM"
    elif adaptive_evidence:
        verdict = "ADAPTIVE_EVIDENCE_THRESHOLD_MET"
        status = ADAPTIVE_EVIDENCE_VERDICT_READY_TOKEN
        tier = "T5_CROSS_ENCOUNTER_ADAPTIVE_COMPOSITION_OBSERVED"
    else:
        verdict = "NO_ADAPTIVE_EVIDENCE_THRESHOLD_NOT_MET"
        status = ADAPTIVE_EVIDENCE_VERDICT_READY_TOKEN
        tier = "T4_REAL_TASK_QUALITY_PIPELINE_EXERCISED_NO_ADAPTIVE_CLAIM"

    return AdaptiveEvidenceVerdictReceipt(
        verdict_version=ADAPTIVE_EVIDENCE_VERDICT_VERSION,
        status=status,
        real_task_quality_digest_status=str(digest.get("status")),
        real_task_quality_end_to_end_proven=bool(digest.get("real_task_quality_end_to_end_proven")),
        quality_pipeline_exercised=bool(digest.get("quality_pipeline_exercised")),
        mean_quality_score=mean_quality,
        baseline_arm=str(digest.get("baseline_arm", "")),
        baseline_arm_mean=float(digest.get("baseline_arm_mean", 0.0)),
        full_arm=str(digest.get("full_arm", "")),
        full_arm_mean=float(digest.get("full_arm_mean", 0.0)),
        full_minus_baseline_effect=effect,
        minimum_mean_quality_score=minimum_mean_quality_score,
        minimum_full_minus_baseline_effect=minimum_full_minus_baseline_effect,
        quality_threshold_met=quality_threshold_met,
        adaptive_effect_threshold_met=adaptive_effect_threshold_met,
        adaptive_evidence_verdict=verdict,
        real_adaptive_evidence=adaptive_evidence,
        adaptive_claim_authorized=adaptive_evidence,
        allowed_claim_tier=tier,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        real_task_quality_digest_sha256=_sha256_path(real_task_quality_digest_path),
        boundary=(
            "This adaptive evidence verdict evaluates whether the real task-quality digest meets "
            "predeclared quality and full-minus-baseline effect thresholds. It authorizes only a "
            "bounded adaptive-evidence claim when both thresholds are met and the source digest is "
            "ready. It never authorizes commercial validation, professional approval, publication, "
            "spend, fulfilment, world-first status, or authority expansion."
        ),
    )


def write_adaptive_evidence_verdict(
    *,
    real_task_quality_digest_path: Path,
    output_path: Path,
    minimum_mean_quality_score: float = MINIMUM_MEAN_QUALITY_SCORE,
    minimum_full_minus_baseline_effect: float = MINIMUM_FULL_MINUS_BASELINE_EFFECT,
) -> AdaptiveEvidenceVerdictReceipt:
    receipt = evaluate_adaptive_evidence_verdict(
        real_task_quality_digest_path=real_task_quality_digest_path,
        minimum_mean_quality_score=minimum_mean_quality_score,
        minimum_full_minus_baseline_effect=minimum_full_minus_baseline_effect,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
