from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


REAL_TASK_QUALITY_ADAPTIVE_CLAIM_GATE_VERSION = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_ADAPTIVE_CLAIM_GATE_V1"
REAL_TASK_QUALITY_ADAPTIVE_CLAIM_GATE_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_ADAPTIVE_CLAIM_GATE_READY"
REAL_TASK_QUALITY_ADAPTIVE_CLAIM_GATE_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_ADAPTIVE_CLAIM_GATE_REFUSED"


@dataclass(frozen=True)
class RealTaskQualityAdaptiveClaimGateReceipt:
    gate_version: str
    status: str
    factorial_analysis_status: str
    real_quality_scores_analyzed: bool
    scores_loaded: int
    labels_loaded: int
    arms_analyzed: int
    baseline_arm: str
    baseline_mean_score: float
    full_arm: str
    full_mean_score: float
    full_minus_baseline_effect: float
    positive_full_stack_quality_effect_observed: bool
    real_adaptive_evidence: bool
    allowed_claim_tier: str
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    factorial_analysis_sha256: str
    boundary: str


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _float_value(payload: dict, *names: str) -> float:
    for name in names:
        if name in payload:
            return float(payload[name])
    return 0.0


def evaluate_real_task_quality_adaptive_claim_gate(
    *,
    factorial_analysis_receipt_path: Path,
) -> RealTaskQualityAdaptiveClaimGateReceipt:
    analysis = _load(factorial_analysis_receipt_path)

    ready = (
        analysis.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_FACTORIAL_ANALYSIS_READY"
        and analysis.get("real_quality_scores_analyzed") is True
        and analysis.get("scores_loaded") == 25
        and analysis.get("labels_loaded") == 25
        and analysis.get("arms_analyzed") == 5
        and analysis.get("adaptive_claim_authorized") is False
        and analysis.get("commercial_or_world_first_claim_authorized") is False
    )

    positive_effect = bool(analysis.get("positive_full_stack_quality_effect_observed") is True)
    analysis_adaptive_evidence = bool(analysis.get("real_adaptive_evidence") is True)
    effect = _float_value(analysis, "full_minus_baseline_effect")
    real_quality_scores_analyzed = bool(analysis.get("real_quality_scores_analyzed") is True)

    real_adaptive_evidence = bool(
        ready
        and positive_effect
        and analysis_adaptive_evidence
        and effect > 0.0
    )

    if not ready:
        status = REAL_TASK_QUALITY_ADAPTIVE_CLAIM_GATE_REFUSED_TOKEN
        allowed_claim_tier = "T0_NO_CLAIM"
    elif real_adaptive_evidence:
        status = REAL_TASK_QUALITY_ADAPTIVE_CLAIM_GATE_READY_TOKEN
        allowed_claim_tier = "T5_REAL_TASK_QUALITY_DIFFERENTIAL_OBSERVED_REQUIRES_EXTERNAL_REPLICATION"
    else:
        status = REAL_TASK_QUALITY_ADAPTIVE_CLAIM_GATE_READY_TOKEN
        allowed_claim_tier = "T4_REAL_TASK_QUALITY_ANALYZED_NO_ADAPTIVE_CLAIM"

    return RealTaskQualityAdaptiveClaimGateReceipt(
        gate_version=REAL_TASK_QUALITY_ADAPTIVE_CLAIM_GATE_VERSION,
        status=status,
        factorial_analysis_status=str(analysis.get("status")),
        real_quality_scores_analyzed=real_quality_scores_analyzed if ready else False,
        scores_loaded=int(analysis.get("scores_loaded", 0)),
        labels_loaded=int(analysis.get("labels_loaded", 0)),
        arms_analyzed=int(analysis.get("arms_analyzed", 0)),
        baseline_arm=str(analysis.get("baseline_arm", "A_STATELESS_RESET")),
        baseline_mean_score=_float_value(analysis, "baseline_mean_score", "baseline_arm_mean"),
        full_arm=str(analysis.get("full_arm", "E_FULL_SEMANTIC_MARKET_BEAST")),
        full_mean_score=_float_value(analysis, "full_mean_score", "full_arm_mean"),
        full_minus_baseline_effect=effect,
        positive_full_stack_quality_effect_observed=positive_effect if ready else False,
        real_adaptive_evidence=real_adaptive_evidence,
        allowed_claim_tier=allowed_claim_tier,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        factorial_analysis_sha256=_sha256_path(factorial_analysis_receipt_path),
        boundary=(
            "This real task-quality adaptive claim gate reviews the real task-quality factorial "
            "analysis and may record whether a positive full-stack quality differential was observed. "
            "It does not authorize adaptive-composition claims, retained-learning claims, commercial "
            "validation, professional approval, publication, spend, fulfilment, world-first claims, or "
            "authority expansion. Positive differentials require external replication and separate human "
            "claim authorization before any public or commercial claim."
        ),
    )


def write_real_task_quality_adaptive_claim_gate(
    *,
    factorial_analysis_receipt_path: Path,
    output_path: Path,
) -> RealTaskQualityAdaptiveClaimGateReceipt:
    receipt = evaluate_real_task_quality_adaptive_claim_gate(
        factorial_analysis_receipt_path=factorial_analysis_receipt_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
