from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


ECOSYSTEM_EVIDENCE_REHYDRATION_VERSION = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_EVIDENCE_REHYDRATION_GATE_V1"
ECOSYSTEM_EVIDENCE_REHYDRATION_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_EVIDENCE_REHYDRATION_READY"
ECOSYSTEM_EVIDENCE_REHYDRATION_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_EVIDENCE_REHYDRATION_REFUSED"

ECOSYSTEM_VERDICT_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_READY"
T5_ECOSYSTEM_CLAIM_TIER = "T5_BOUNDED_ECOSYSTEM_ADAPTIVE_EVIDENCE_CLAIM"


@dataclass(frozen=True)
class EcosystemEvidenceRehydrationReceipt:
    gate_version: str
    status: str
    ecosystem_verdict_status: str
    source_bound: bool
    allowed_claim_tier: str
    baseline_arm: str
    baseline_arm_mean: float
    full_arm: str
    full_arm_mean: float
    full_minus_baseline_effect: float
    real_ecosystem_adaptive_evidence: bool
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    ecosystem_verdict_sha256: str
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rehydrate_ecosystem_adaptive_evidence(
    *,
    ecosystem_verdict_path: Path,
    output_path: Path,
) -> EcosystemEvidenceRehydrationReceipt:
    verdict = _load_json(ecosystem_verdict_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    source_bound = ecosystem_verdict_path.exists() and ecosystem_verdict_path.is_file()
    verdict_status = str(verdict.get("status"))
    claim_tier = str(verdict.get("allowed_claim_tier"))
    real_evidence = verdict.get("real_ecosystem_adaptive_evidence") is True
    upstream_authorized = verdict.get("adaptive_claim_authorized") is True

    ready = (
        source_bound
        and verdict_status == ECOSYSTEM_VERDICT_READY_TOKEN
        and claim_tier == T5_ECOSYSTEM_CLAIM_TIER
        and real_evidence
        and upstream_authorized
        and verdict.get("commercial_or_world_first_claim_authorized") is False
        and verdict.get("authority_expansion_authorized") is False
    )

    receipt = EcosystemEvidenceRehydrationReceipt(
        gate_version=ECOSYSTEM_EVIDENCE_REHYDRATION_VERSION,
        status=(
            ECOSYSTEM_EVIDENCE_REHYDRATION_READY_TOKEN
            if ready
            else ECOSYSTEM_EVIDENCE_REHYDRATION_REFUSED_TOKEN
        ),
        ecosystem_verdict_status=verdict_status,
        source_bound=source_bound,
        allowed_claim_tier=claim_tier,
        baseline_arm=str(verdict.get("baseline_arm", "")),
        baseline_arm_mean=float(verdict.get("baseline_arm_mean", 0.0)),
        full_arm=str(verdict.get("full_arm", "")),
        full_arm_mean=float(verdict.get("full_arm_mean", 0.0)),
        full_minus_baseline_effect=float(verdict.get("full_minus_baseline_effect", 0.0)),
        real_ecosystem_adaptive_evidence=real_evidence if ready else False,
        adaptive_claim_authorized=upstream_authorized if ready else False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        ecosystem_verdict_sha256=_sha256_path(ecosystem_verdict_path),
        boundary=(
            "This source-bound rehydration gate preserves the ecosystem adaptive evidence verdict "
            "from the Debian receipt pack and distinguishes it from Termux-local synthetic quality "
            "scoring. It may carry forward only the bounded T5 ecosystem adaptive evidence claim recorded "
            "by the upstream verdict. It does not authorize commercial validation, professional approval, "
            "publication, spend, fulfilment, world-first claims, or authority expansion."
            if ready
            else "Ecosystem adaptive evidence rehydration refused because the source-bound verdict did not "
            "carry a ready T5 bounded ecosystem adaptive evidence claim. It does not authorize commercial, "
            "professional, publication, spend, fulfilment, world-first, or authority-expansion claims."
        ),
    )

    output_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
