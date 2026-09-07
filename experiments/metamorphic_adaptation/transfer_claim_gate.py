from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


TRANSFER_CLAIM_GATE_VERSION = "DIO_METAMORPHIC_ADAPTATION_TRANSFER_CLAIM_GATE_V1"
TRANSFER_CLAIM_GATE_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_TRANSFER_CLAIM_GATE_FIXTURE_VERDICT_READY"
TRANSFER_CLAIM_GATE_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_TRANSFER_CLAIM_GATE_REFUSED"


@dataclass(frozen=True)
class TransferClaimGateReceipt:
    gate_version: str
    status: str
    execution_status: str
    blind_evaluation_status: str
    factorial_analysis_status: str
    fixture_mode: bool
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
    execution_receipt_sha256: str
    blind_evaluation_sha256: str
    factorial_analysis_sha256: str
    boundary: str


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate_transfer_claim_gate(
    *,
    execution_receipt_path: Path,
    blind_evaluation_receipt_path: Path,
    factorial_analysis_receipt_path: Path,
) -> TransferClaimGateReceipt:
    execution = _load(execution_receipt_path)
    blind = _load(blind_evaluation_receipt_path)
    factorial = _load(factorial_analysis_receipt_path)

    execution_status = execution.get("status")
    blind_status = blind.get("status")
    factorial_status = factorial.get("status")

    fixture_mode = (
        execution.get("fixture_mode") is True
        and blind.get("fixture_mode") is True
        and factorial.get("fixture_mode") is True
    )

    mechanics_proven = (
        execution_status == "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_TRANSFER_EXECUTION_FIXTURE_READY"
        and blind_status == "DIO_METAMORPHIC_ADAPTATION_BLIND_EVALUATION_FIXTURE_READY"
        and factorial_status == "DIO_METAMORPHIC_ADAPTATION_FACTORIAL_ANALYSIS_FIXTURE_READY"
        and execution.get("encounters_executed", 0) > 0
        and blind.get("evaluated_blind_outputs", 0) == execution.get("encounters_executed", -1)
        and factorial.get("blind_scores_loaded", 0) == blind.get("evaluated_blind_outputs", -1)
        and factorial.get("real_adaptive_evidence") is False
        and fixture_mode
    )

    status = (
        TRANSFER_CLAIM_GATE_READY_TOKEN
        if mechanics_proven
        else TRANSFER_CLAIM_GATE_REFUSED_TOKEN
    )

    allowed_claim_tier = (
        "T1_FIXTURE_MECHANICS_PROVEN_NO_ADAPTIVE_CLAIM"
        if mechanics_proven
        else "T0_NO_CLAIM"
    )

    return TransferClaimGateReceipt(
        gate_version=TRANSFER_CLAIM_GATE_VERSION,
        status=status,
        execution_status=str(execution_status),
        blind_evaluation_status=str(blind_status),
        factorial_analysis_status=str(factorial_status),
        fixture_mode=fixture_mode,
        mechanics_proven=mechanics_proven,
        real_adaptive_evidence=False,
        allowed_claim_tier=allowed_claim_tier,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        execution_receipt_sha256=_sha256_path(execution_receipt_path),
        blind_evaluation_sha256=_sha256_path(blind_evaluation_receipt_path),
        factorial_analysis_sha256=_sha256_path(factorial_analysis_receipt_path),
        boundary=(
            "This transfer claim gate authorizes only the statement that fixture-mode "
            "controlled-transfer mechanics were exercised. It does not authorize an "
            "adaptive-composition claim, real performance claim, commercial validation claim, "
            "professional approval claim, publication, spend, fulfilment, world-first claim, "
            "or authority expansion."
        ),
    )


def write_transfer_claim_gate(
    *,
    execution_receipt_path: Path,
    blind_evaluation_receipt_path: Path,
    factorial_analysis_receipt_path: Path,
    output_path: Path,
) -> TransferClaimGateReceipt:
    receipt = evaluate_transfer_claim_gate(
        execution_receipt_path=execution_receipt_path,
        blind_evaluation_receipt_path=blind_evaluation_receipt_path,
        factorial_analysis_receipt_path=factorial_analysis_receipt_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
