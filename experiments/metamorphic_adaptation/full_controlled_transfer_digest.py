from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


FULL_TRANSFER_DIGEST_VERSION = "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_DIGEST_V1"
FULL_TRANSFER_DIGEST_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_DIGEST_READY"
FULL_TRANSFER_DIGEST_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_DIGEST_REFUSED"


@dataclass(frozen=True)
class FullControlledTransferDigest:
    digest_version: str
    status: str
    plan_status: str
    scaffold_status: str
    execution_status: str
    compatibility_status: str
    blind_evaluation_status: str
    factorial_analysis_status: str
    claim_gate_status: str
    full_transfer_end_to_end_proven: bool
    full_native_run_passed: bool
    full_run_encounters_passed: int
    full_run_encounters_failed: int
    full_run_encounters_timed_out: int
    evaluated_blind_outputs: int
    arms_analyzed: int
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
    plan_sha256: str
    scaffold_sha256: str
    execution_sha256: str
    compatibility_sha256: str
    blind_evaluation_sha256: str
    factorial_analysis_sha256: str
    claim_gate_sha256: str
    boundary: str


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_full_controlled_transfer_digest(
    *,
    plan_path: Path,
    scaffold_receipt_path: Path,
    execution_receipt_path: Path,
    compatibility_verdict_path: Path,
    blind_evaluation_receipt_path: Path,
    factorial_analysis_receipt_path: Path,
    claim_gate_path: Path,
) -> FullControlledTransferDigest:
    plan = _load(plan_path)
    scaffold = _load(scaffold_receipt_path)
    execution = _load(execution_receipt_path)
    compatibility = _load(compatibility_verdict_path)
    blind = _load(blind_evaluation_receipt_path)
    factorial = _load(factorial_analysis_receipt_path)
    claim_gate = _load(claim_gate_path)

    passed = int(execution.get("full_run_encounters_passed", 0))
    failed = int(execution.get("full_run_encounters_failed", 0))
    timed_out = int(execution.get("full_run_encounters_timed_out", 0))
    evaluated = int(blind.get("evaluated_blind_outputs", 0))
    arms = int(factorial.get("arms_analyzed", 0))
    effect = float(factorial.get("full_minus_baseline_effect", 0.0))

    full_native_run_passed = (
        execution.get("status") == "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_EXECUTION_READY"
        and execution.get("executed") is True
        and execution.get("real_native_mode") is True
        and passed == 25
        and failed == 0
        and timed_out == 0
        and execution.get("adaptive_claim_authorized") is False
    )

    end_to_end = (
        plan.get("status") == "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_PLAN_READY"
        and scaffold.get("status") == "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_SCAFFOLD_READY"
        and full_native_run_passed
        and compatibility.get("status") == "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_COMPATIBILITY_VERDICT_READY"
        and compatibility.get("full_run_native_compatibility_proven") is True
        and blind.get("status") == "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_BLIND_EVALUATION_READY"
        and evaluated == 25
        and factorial.get("status") == "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_FACTORIAL_ANALYSIS_READY"
        and arms == 5
        and claim_gate.get("status") == "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_CLAIM_GATE_VERDICT_READY"
        and claim_gate.get("mechanics_proven") is True
        and claim_gate.get("allowed_claim_tier") == "T3_FULL_NATIVE_COMPATIBILITY_BLIND_FACTORIAL_PIPELINE_ONLY"
        and claim_gate.get("real_adaptive_evidence") is False
        and claim_gate.get("adaptive_claim_authorized") is False
    )

    return FullControlledTransferDigest(
        digest_version=FULL_TRANSFER_DIGEST_VERSION,
        status=FULL_TRANSFER_DIGEST_READY_TOKEN if end_to_end else FULL_TRANSFER_DIGEST_REFUSED_TOKEN,
        plan_status=str(plan.get("status")),
        scaffold_status=str(scaffold.get("status")),
        execution_status=str(execution.get("status")),
        compatibility_status=str(compatibility.get("status")),
        blind_evaluation_status=str(blind.get("status")),
        factorial_analysis_status=str(factorial.get("status")),
        claim_gate_status=str(claim_gate.get("status")),
        full_transfer_end_to_end_proven=end_to_end,
        full_native_run_passed=full_native_run_passed,
        full_run_encounters_passed=passed,
        full_run_encounters_failed=failed,
        full_run_encounters_timed_out=timed_out,
        evaluated_blind_outputs=evaluated,
        arms_analyzed=arms,
        full_minus_baseline_effect=effect,
        allowed_claim_tier=(
            "T3_FULL_NATIVE_COMPATIBILITY_BLIND_FACTORIAL_PIPELINE_ONLY"
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
        plan_sha256=_sha256_path(plan_path),
        scaffold_sha256=_sha256_path(scaffold_receipt_path),
        execution_sha256=_sha256_path(execution_receipt_path),
        compatibility_sha256=_sha256_path(compatibility_verdict_path),
        blind_evaluation_sha256=_sha256_path(blind_evaluation_receipt_path),
        factorial_analysis_sha256=_sha256_path(factorial_analysis_receipt_path),
        claim_gate_sha256=_sha256_path(claim_gate_path),
        boundary=(
            "This digest authorizes only the statement that the full 25-encounter real native "
            "controlled transfer smoke run, blind evaluation, factorial analysis, and claim gate "
            "completed compatibly. It does not authorize an adaptive-composition claim, retained-"
            "learning claim, real performance improvement claim, commercial validation claim, "
            "professional approval claim, publication, spend, fulfilment, world-first claim, or "
            "authority expansion."
        ),
    )


def write_full_controlled_transfer_digest(
    *,
    plan_path: Path,
    scaffold_receipt_path: Path,
    execution_receipt_path: Path,
    compatibility_verdict_path: Path,
    blind_evaluation_receipt_path: Path,
    factorial_analysis_receipt_path: Path,
    claim_gate_path: Path,
    output_path: Path,
) -> FullControlledTransferDigest:
    digest = build_full_controlled_transfer_digest(
        plan_path=plan_path,
        scaffold_receipt_path=scaffold_receipt_path,
        execution_receipt_path=execution_receipt_path,
        compatibility_verdict_path=compatibility_verdict_path,
        blind_evaluation_receipt_path=blind_evaluation_receipt_path,
        factorial_analysis_receipt_path=factorial_analysis_receipt_path,
        claim_gate_path=claim_gate_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(digest), indent=2, sort_keys=True) + "\n")
    return digest
