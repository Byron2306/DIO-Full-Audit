from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


FULL_TRANSFER_CLAIM_GATE_VERSION = "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_CLAIM_GATE_V1"
FULL_TRANSFER_CLAIM_GATE_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_CLAIM_GATE_VERDICT_READY"
FULL_TRANSFER_CLAIM_GATE_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_CLAIM_GATE_REFUSED"


@dataclass(frozen=True)
class FullControlledTransferClaimGateReceipt:
    gate_version: str
    status: str
    compatibility_status: str
    blind_evaluation_status: str
    factorial_analysis_status: str
    full_run_native_compatibility_proven: bool
    full_blind_evaluation_exercised: bool
    full_factorial_analysis_exercised: bool
    full_run_encounters_passed: int
    evaluated_blind_outputs: int
    arms_analyzed: int
    full_minus_baseline_effect: float
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
    compatibility_verdict_sha256: str
    blind_evaluation_sha256: str
    factorial_analysis_sha256: str
    boundary: str


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate_full_transfer_claim_gate(
    *,
    compatibility_verdict_path: Path,
    blind_evaluation_receipt_path: Path,
    factorial_analysis_receipt_path: Path,
) -> FullControlledTransferClaimGateReceipt:
    compatibility = _load(compatibility_verdict_path)
    blind = _load(blind_evaluation_receipt_path)
    factorial = _load(factorial_analysis_receipt_path)

    compatibility_ready = (
        compatibility.get("status") == "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_COMPATIBILITY_VERDICT_READY"
        and compatibility.get("full_run_native_compatibility_proven") is True
        and compatibility.get("ready_for_full_blind_evaluation") is True
        and compatibility.get("full_run_encounters_passed") == 25
        and compatibility.get("adaptive_claim_authorized") is False
    )

    blind_ready = (
        blind.get("status") == "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_BLIND_EVALUATION_READY"
        and blind.get("evaluated_blind_outputs") == 25
        and blind.get("full_run_native_compatibility_proven") is True
        and blind.get("real_adaptive_evidence") is False
        and blind.get("adaptive_claim_authorized") is False
    )

    factorial_ready = (
        factorial.get("status") == "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_FACTORIAL_ANALYSIS_READY"
        and factorial.get("scores_loaded") == 25
        and factorial.get("labels_loaded") == 25
        and factorial.get("arms_analyzed") == 5
        and factorial.get("real_adaptive_evidence") is False
        and factorial.get("adaptive_claim_authorized") is False
    )

    mechanics_proven = compatibility_ready and blind_ready and factorial_ready

    return FullControlledTransferClaimGateReceipt(
        gate_version=FULL_TRANSFER_CLAIM_GATE_VERSION,
        status=FULL_TRANSFER_CLAIM_GATE_READY_TOKEN if mechanics_proven else FULL_TRANSFER_CLAIM_GATE_REFUSED_TOKEN,
        compatibility_status=str(compatibility.get("status")),
        blind_evaluation_status=str(blind.get("status")),
        factorial_analysis_status=str(factorial.get("status")),
        full_run_native_compatibility_proven=bool(compatibility.get("full_run_native_compatibility_proven")),
        full_blind_evaluation_exercised=blind_ready,
        full_factorial_analysis_exercised=factorial_ready,
        full_run_encounters_passed=int(compatibility.get("full_run_encounters_passed", 0)),
        evaluated_blind_outputs=int(blind.get("evaluated_blind_outputs", 0)),
        arms_analyzed=int(factorial.get("arms_analyzed", 0)),
        full_minus_baseline_effect=float(factorial.get("full_minus_baseline_effect", 0.0)),
        mechanics_proven=mechanics_proven,
        real_adaptive_evidence=False,
        allowed_claim_tier=(
            "T3_FULL_NATIVE_COMPATIBILITY_BLIND_FACTORIAL_PIPELINE_ONLY"
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
        compatibility_verdict_sha256=_sha256_path(compatibility_verdict_path),
        blind_evaluation_sha256=_sha256_path(blind_evaluation_receipt_path),
        factorial_analysis_sha256=_sha256_path(factorial_analysis_receipt_path),
        boundary=(
            "This full controlled transfer claim gate authorizes only the statement that the "
            "full 25-encounter native compatibility, blind evaluation, and factorial analysis "
            "pipeline were exercised. It does not authorize an adaptive-composition claim, "
            "retained-learning claim, real performance improvement claim, commercial validation "
            "claim, professional approval claim, publication, spend, fulfilment, world-first "
            "claim, or authority expansion."
        ),
    )


def write_full_transfer_claim_gate(
    *,
    compatibility_verdict_path: Path,
    blind_evaluation_receipt_path: Path,
    factorial_analysis_receipt_path: Path,
    output_path: Path,
) -> FullControlledTransferClaimGateReceipt:
    receipt = evaluate_full_transfer_claim_gate(
        compatibility_verdict_path=compatibility_verdict_path,
        blind_evaluation_receipt_path=blind_evaluation_receipt_path,
        factorial_analysis_receipt_path=factorial_analysis_receipt_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
