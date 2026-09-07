from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_VERSION = "DIO_METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_V1"
METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_READY"
METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_REFUSED"


@dataclass(frozen=True)
class MetamorphicAdaptationEvidenceDigest:
    digest_version: str
    status: str
    full_transfer_digest_status: str
    real_task_quality_digest_status: str
    adaptive_evidence_verdict_status: str
    full_transfer_end_to_end_proven: bool
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
    allowed_claim_tier: str
    real_adaptive_evidence: bool
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    full_transfer_digest_sha256: str
    real_task_quality_digest_sha256: str
    adaptive_evidence_verdict_sha256: str
    boundary: str


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_metamorphic_adaptation_evidence_digest(
    *,
    full_transfer_digest_path: Path,
    real_task_quality_digest_path: Path,
    adaptive_evidence_verdict_path: Path,
) -> MetamorphicAdaptationEvidenceDigest:
    full_transfer = _load(full_transfer_digest_path)
    quality = _load(real_task_quality_digest_path)
    verdict = _load(adaptive_evidence_verdict_path)

    full_transfer_ready = (
        full_transfer.get("status") == "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_DIGEST_READY"
        and full_transfer.get("full_transfer_end_to_end_proven") is True
        and full_transfer.get("adaptive_claim_authorized") is False
    )
    quality_ready = (
        quality.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_DIGEST_READY"
        and quality.get("real_task_quality_end_to_end_proven") is True
        and quality.get("quality_pipeline_exercised") is True
        and quality.get("adaptive_claim_authorized") is False
    )
    verdict_ready = (
        verdict.get("status") == "DIO_METAMORPHIC_ADAPTATION_ADAPTIVE_EVIDENCE_VERDICT_READY"
        and verdict.get("real_task_quality_digest_status") == "DIO_METAMORPHIC_ADAPTATION_REAL_TASK_QUALITY_DIGEST_READY"
        and verdict.get("quality_pipeline_exercised") is True
    )

    ready = full_transfer_ready and quality_ready and verdict_ready

    real_adaptive_evidence = bool(verdict.get("real_adaptive_evidence")) if ready else False
    adaptive_claim_authorized = bool(verdict.get("adaptive_claim_authorized")) if ready else False
    allowed_claim_tier = str(verdict.get("allowed_claim_tier", "T0_NO_CLAIM")) if ready else "T0_NO_CLAIM"

    return MetamorphicAdaptationEvidenceDigest(
        digest_version=METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_VERSION,
        status=(
            METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_READY_TOKEN
            if ready
            else METAMORPHIC_ADAPTATION_EVIDENCE_DIGEST_REFUSED_TOKEN
        ),
        full_transfer_digest_status=str(full_transfer.get("status")),
        real_task_quality_digest_status=str(quality.get("status")),
        adaptive_evidence_verdict_status=str(verdict.get("status")),
        full_transfer_end_to_end_proven=bool(full_transfer.get("full_transfer_end_to_end_proven")),
        real_task_quality_end_to_end_proven=bool(quality.get("real_task_quality_end_to_end_proven")),
        quality_pipeline_exercised=bool(quality.get("quality_pipeline_exercised")),
        mean_quality_score=float(quality.get("mean_quality_score", 0.0)),
        baseline_arm=str(verdict.get("baseline_arm", quality.get("baseline_arm", "A_STATELESS_RESET"))),
        baseline_arm_mean=float(verdict.get("baseline_arm_mean", quality.get("baseline_arm_mean", 0.0))),
        full_arm=str(verdict.get("full_arm", quality.get("full_arm", "E_FULL_SEMANTIC_MARKET_BEAST"))),
        full_arm_mean=float(verdict.get("full_arm_mean", quality.get("full_arm_mean", 0.0))),
        full_minus_baseline_effect=float(verdict.get("full_minus_baseline_effect", quality.get("full_minus_baseline_effect", 0.0))),
        minimum_mean_quality_score=float(verdict.get("minimum_mean_quality_score", 0.0)),
        minimum_full_minus_baseline_effect=float(verdict.get("minimum_full_minus_baseline_effect", 0.0)),
        quality_threshold_met=bool(verdict.get("quality_threshold_met")),
        adaptive_effect_threshold_met=bool(verdict.get("adaptive_effect_threshold_met")),
        adaptive_evidence_verdict=str(verdict.get("adaptive_evidence_verdict", "NO_VERDICT")),
        allowed_claim_tier=allowed_claim_tier,
        real_adaptive_evidence=real_adaptive_evidence,
        adaptive_claim_authorized=adaptive_claim_authorized,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        full_transfer_digest_sha256=_sha256_path(full_transfer_digest_path),
        real_task_quality_digest_sha256=_sha256_path(real_task_quality_digest_path),
        adaptive_evidence_verdict_sha256=_sha256_path(adaptive_evidence_verdict_path),
        boundary=(
            "This metamorphic adaptation evidence digest binds the full controlled-transfer smoke digest, "
            "real task-quality digest, and adaptive evidence verdict. It authorizes only the claim tier "
            "granted by the adaptive evidence verdict. It never authorizes commercial validation, "
            "professional approval, publication, spend, fulfilment, world-first status, or authority expansion."
        ),
    )


def write_metamorphic_adaptation_evidence_digest(
    *,
    full_transfer_digest_path: Path,
    real_task_quality_digest_path: Path,
    adaptive_evidence_verdict_path: Path,
    output_path: Path,
) -> MetamorphicAdaptationEvidenceDigest:
    digest = build_metamorphic_adaptation_evidence_digest(
        full_transfer_digest_path=full_transfer_digest_path,
        real_task_quality_digest_path=real_task_quality_digest_path,
        adaptive_evidence_verdict_path=adaptive_evidence_verdict_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(digest), indent=2, sort_keys=True) + "\n")
    return digest
