from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


FULL_TRANSFER_PLAN_VERSION = "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_PLAN_V1"
FULL_TRANSFER_PLAN_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_PLAN_READY"
FULL_TRANSFER_PLAN_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_PLAN_REFUSED"


@dataclass(frozen=True)
class FullControlledTransferPlan:
    plan_version: str
    status: str
    real_pilot_digest_status: str
    real_pilot_digest_sha256: str
    full_run_planning_authorized: bool
    execute_by_default: bool
    arms: tuple[str, ...]
    encounters_per_arm: int
    full_run_encounters: int
    requires_explicit_execute_flag: bool
    requires_blind_evaluation: bool
    requires_factorial_analysis: bool
    requires_claim_gate: bool
    allowed_claim_tier: str
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    expected_outputs: tuple[str, ...]
    boundary: str


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_full_controlled_transfer_plan(
    *,
    real_pilot_digest_path: Path,
    encounters_per_arm: int = 5,
) -> FullControlledTransferPlan:
    digest = _load(real_pilot_digest_path)

    authorized = (
        digest.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_DIGEST_READY"
        and digest.get("real_pilot_end_to_end_proven") is True
        and digest.get("ready_to_plan_full_controlled_transfer_run") is True
        and digest.get("adaptive_claim_authorized") is False
        and digest.get("commercial_or_world_first_claim_authorized") is False
        and digest.get("allowed_claim_tier") == "T2_REAL_PILOT_COMPATIBILITY_AND_BLIND_PIPELINE_ONLY"
    )

    arms = (
        "A_STATELESS_RESET",
        "B_COMPOSITION_ONLY_NO_RETAINED_LEARNING",
        "C_SEMANTIC_RETAINED",
        "D_MARKET_RETAINED",
        "E_FULL_SEMANTIC_MARKET_BEAST",
    )

    return FullControlledTransferPlan(
        plan_version=FULL_TRANSFER_PLAN_VERSION,
        status=FULL_TRANSFER_PLAN_READY_TOKEN if authorized else FULL_TRANSFER_PLAN_REFUSED_TOKEN,
        real_pilot_digest_status=str(digest.get("status")),
        real_pilot_digest_sha256=_sha256_path(real_pilot_digest_path),
        full_run_planning_authorized=authorized,
        execute_by_default=False,
        arms=arms,
        encounters_per_arm=encounters_per_arm if authorized else 0,
        full_run_encounters=len(arms) * encounters_per_arm if authorized else 0,
        requires_explicit_execute_flag=True,
        requires_blind_evaluation=True,
        requires_factorial_analysis=True,
        requires_claim_gate=True,
        allowed_claim_tier=(
            "T2_REAL_PILOT_COMPATIBILITY_AND_BLIND_PIPELINE_ONLY"
            if authorized
            else "T0_NO_CLAIM"
        ),
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        expected_outputs=(
            "full_controlled_transfer_plan.json",
            "full_controlled_transfer_scaffold_receipt.json",
            "full_controlled_transfer_encounter_receipts.jsonl",
            "full_controlled_transfer_execution_receipt.json",
            "full_controlled_transfer_execution_receipts.jsonl",
            "full_controlled_transfer_blind_evaluation_receipt.json",
            "full_controlled_transfer_factorial_analysis_receipt.json",
            "full_controlled_transfer_claim_gate.json",
        ),
        boundary=(
            "This plan authorizes only planning of the full 25-encounter real controlled "
            "transfer run. It does not execute by default and does not authorize adaptive-"
            "composition, retained-learning, real performance improvement, commercial validation, "
            "professional approval, publication, spend, fulfilment, world-first, or authority-expansion claims."
        ),
    )


def write_full_controlled_transfer_plan(
    *,
    real_pilot_digest_path: Path,
    output_path: Path,
    encounters_per_arm: int = 5,
) -> FullControlledTransferPlan:
    plan = build_full_controlled_transfer_plan(
        real_pilot_digest_path=real_pilot_digest_path,
        encounters_per_arm=encounters_per_arm,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(plan), indent=2, sort_keys=True) + "\n")
    return plan
