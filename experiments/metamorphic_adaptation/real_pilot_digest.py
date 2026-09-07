from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


REAL_PILOT_DIGEST_VERSION = "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_DIGEST_V1"
REAL_PILOT_DIGEST_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_DIGEST_READY"
REAL_PILOT_DIGEST_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_DIGEST_REFUSED"


@dataclass(frozen=True)
class RealPilotDigest:
    digest_version: str
    status: str
    plan_status: str
    scaffold_status: str
    execution_status: str
    compatibility_status: str
    blind_evaluation_status: str
    claim_gate_status: str
    real_pilot_end_to_end_proven: bool
    real_native_pilot_passed: bool
    pilot_encounters_passed: int
    pilot_encounters_failed: int
    pilot_encounters_timed_out: int
    evaluated_blind_outputs: int
    allowed_claim_tier: str
    ready_to_plan_full_controlled_transfer_run: bool
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    real_plan_sha256: str
    scaffold_receipt_sha256: str
    execution_receipt_sha256: str
    compatibility_verdict_sha256: str
    blind_evaluation_sha256: str
    claim_gate_sha256: str
    boundary: str


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_real_pilot_digest(
    *,
    real_plan_path: Path,
    scaffold_receipt_path: Path,
    execution_receipt_path: Path,
    compatibility_verdict_path: Path,
    blind_evaluation_receipt_path: Path,
    claim_gate_path: Path,
) -> RealPilotDigest:
    plan = _load(real_plan_path)
    scaffold = _load(scaffold_receipt_path)
    execution = _load(execution_receipt_path)
    compatibility = _load(compatibility_verdict_path)
    blind = _load(blind_evaluation_receipt_path)
    claim_gate = _load(claim_gate_path)

    passed = int(execution.get("pilot_encounters_passed", 0))
    failed = int(execution.get("pilot_encounters_failed", 0))
    timed_out = int(execution.get("pilot_encounters_timed_out", 0))
    evaluated = int(blind.get("evaluated_blind_outputs", 0))

    real_native_pilot_passed = (
        execution.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_EXECUTION_READY"
        and execution.get("executed") is True
        and execution.get("real_native_mode") is True
        and passed == 5
        and failed == 0
        and timed_out == 0
        and execution.get("adaptive_claim_authorized") is False
    )

    end_to_end = (
        plan.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_CONTROLLED_TRANSFER_PILOT_PLAN_READY"
        and scaffold.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_SCAFFOLD_READY"
        and real_native_pilot_passed
        and compatibility.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_COMPATIBILITY_VERDICT_READY"
        and compatibility.get("real_pilot_native_compatibility_proven") is True
        and blind.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_BLIND_EVALUATION_READY"
        and evaluated == 5
        and claim_gate.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_CLAIM_GATE_VERDICT_READY"
        and claim_gate.get("mechanics_proven") is True
        and claim_gate.get("allowed_claim_tier") == "T2_REAL_PILOT_COMPATIBILITY_AND_BLIND_PIPELINE_ONLY"
        and claim_gate.get("adaptive_claim_authorized") is False
    )

    return RealPilotDigest(
        digest_version=REAL_PILOT_DIGEST_VERSION,
        status=REAL_PILOT_DIGEST_READY_TOKEN if end_to_end else REAL_PILOT_DIGEST_REFUSED_TOKEN,
        plan_status=str(plan.get("status")),
        scaffold_status=str(scaffold.get("status")),
        execution_status=str(execution.get("status")),
        compatibility_status=str(compatibility.get("status")),
        blind_evaluation_status=str(blind.get("status")),
        claim_gate_status=str(claim_gate.get("status")),
        real_pilot_end_to_end_proven=end_to_end,
        real_native_pilot_passed=real_native_pilot_passed,
        pilot_encounters_passed=passed,
        pilot_encounters_failed=failed,
        pilot_encounters_timed_out=timed_out,
        evaluated_blind_outputs=evaluated,
        allowed_claim_tier=(
            "T2_REAL_PILOT_COMPATIBILITY_AND_BLIND_PIPELINE_ONLY"
            if end_to_end
            else "T0_NO_CLAIM"
        ),
        ready_to_plan_full_controlled_transfer_run=end_to_end,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        real_plan_sha256=_sha256_path(real_plan_path),
        scaffold_receipt_sha256=_sha256_path(scaffold_receipt_path),
        execution_receipt_sha256=_sha256_path(execution_receipt_path),
        compatibility_verdict_sha256=_sha256_path(compatibility_verdict_path),
        blind_evaluation_sha256=_sha256_path(blind_evaluation_receipt_path),
        claim_gate_sha256=_sha256_path(claim_gate_path),
        boundary=(
            "This digest authorizes only the statement that the limited real native pilot "
            "and blind evaluation pipeline completed compatibly. It permits planning a full "
            "25-encounter controlled transfer run. It does not authorize an adaptive-composition "
            "claim, retained-learning claim, real performance improvement claim, commercial "
            "validation claim, professional approval claim, publication, spend, fulfilment, "
            "world-first claim, or authority expansion."
        ),
    )


def write_real_pilot_digest(
    *,
    real_plan_path: Path,
    scaffold_receipt_path: Path,
    execution_receipt_path: Path,
    compatibility_verdict_path: Path,
    blind_evaluation_receipt_path: Path,
    claim_gate_path: Path,
    output_path: Path,
) -> RealPilotDigest:
    digest = build_real_pilot_digest(
        real_plan_path=real_plan_path,
        scaffold_receipt_path=scaffold_receipt_path,
        execution_receipt_path=execution_receipt_path,
        compatibility_verdict_path=compatibility_verdict_path,
        blind_evaluation_receipt_path=blind_evaluation_receipt_path,
        claim_gate_path=claim_gate_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(digest), indent=2, sort_keys=True) + "\n")
    return digest
