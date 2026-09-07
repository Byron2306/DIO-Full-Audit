from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


REAL_TRANSFER_PLAN_VERSION = "DIO_METAMORPHIC_ADAPTATION_REAL_CONTROLLED_TRANSFER_PLAN_V1"
REAL_TRANSFER_PLAN_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_CONTROLLED_TRANSFER_PILOT_PLAN_READY"
REAL_TRANSFER_PLAN_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_CONTROLLED_TRANSFER_PILOT_PLAN_REFUSED"


@dataclass(frozen=True)
class RealControlledTransferPlan:
    plan_version: str
    status: str
    fixture_digest_status: str
    fixture_digest_sha256: str
    real_pilot_authorized: bool
    execute_by_default: bool
    pilot_encounters: int
    full_run_encounters_locked: int
    arms: tuple[str, ...]
    pilot_strategy: str
    required_inputs: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    boundary: str


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_real_controlled_transfer_plan(
    *,
    fixture_digest_path: Path,
) -> RealControlledTransferPlan:
    digest = _load(fixture_digest_path)

    authorized = (
        digest.get("status") == "DIO_METAMORPHIC_ADAPTATION_FIXTURE_EXPERIMENT_DIGEST_READY"
        and digest.get("end_to_end_fixture_mechanics_proven") is True
        and digest.get("ready_for_real_controlled_transfer_execution") is True
        and digest.get("adaptive_claim_authorized") is False
        and digest.get("commercial_or_world_first_claim_authorized") is False
    )

    return RealControlledTransferPlan(
        plan_version=REAL_TRANSFER_PLAN_VERSION,
        status=REAL_TRANSFER_PLAN_READY_TOKEN if authorized else REAL_TRANSFER_PLAN_REFUSED_TOKEN,
        fixture_digest_status=str(digest.get("status")),
        fixture_digest_sha256=_sha256_path(fixture_digest_path),
        real_pilot_authorized=authorized,
        execute_by_default=False,
        pilot_encounters=5 if authorized else 0,
        full_run_encounters_locked=25,
        arms=(
            "A_STATELESS_RESET",
            "B_COMPOSITION_ONLY_NO_RETAINED_LEARNING",
            "C_SEMANTIC_RETAINED",
            "D_MARKET_RETAINED",
            "E_FULL_SEMANTIC_MARKET_BEAST",
        ),
        pilot_strategy=(
            "Run one real native controlled-transfer encounter per arm before any full 25-encounter run."
            if authorized
            else "No real pilot may be planned until the fixture digest authorizes preparation."
        ),
        required_inputs=(
            "fixture_experiment_digest.json",
            "controlled_transfer_manifest.json",
            "native_bindings.v1.json",
            "frozen transfer prompt/task bundle",
            "state custody directory",
        ),
        expected_outputs=(
            "real_controlled_transfer_plan.json",
            "real_pilot_encounter_receipts.jsonl",
            "real_pilot_execution_receipt.json",
            "real_pilot_blind_labels.json",
            "real_pilot_claim_gate.json",
        ),
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        boundary=(
            "This plan authorizes preparation of a limited real native controlled-transfer pilot only. "
            "It does not execute by default, does not authorize the full 25-encounter run, and does not "
            "authorize adaptive-composition, real performance, commercial validation, professional approval, "
            "publication, spend, fulfilment, world-first, or authority-expansion claims."
        ),
    )


def write_real_controlled_transfer_plan(
    *,
    fixture_digest_path: Path,
    output_path: Path,
) -> RealControlledTransferPlan:
    plan = build_real_controlled_transfer_plan(fixture_digest_path=fixture_digest_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(plan), indent=2, sort_keys=True) + "\n")
    return plan
