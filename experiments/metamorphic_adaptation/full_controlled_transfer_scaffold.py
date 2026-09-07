from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


FULL_TRANSFER_SCAFFOLD_VERSION = "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_SCAFFOLD_V1"
FULL_TRANSFER_SCAFFOLD_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_SCAFFOLD_READY"
FULL_TRANSFER_SCAFFOLD_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_SCAFFOLD_REFUSED"


@dataclass(frozen=True)
class FullControlledTransferScaffoldReceipt:
    scaffold_version: str
    status: str
    plan_status: str
    full_run_planning_authorized: bool
    execute_by_default: bool
    arms_staged: int
    encounters_per_arm: int
    full_run_encounters_staged: int
    encounter_receipts_path: str
    blind_labels_path: str
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    professional_approval_claim_authorized: bool
    publication_authorized: bool
    spend_authorized: bool
    fulfilment_authorized: bool
    authority_expansion_authorized: bool
    plan_sha256: str
    boundary: str


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage_full_controlled_transfer_run(
    *,
    full_plan_path: Path,
    output_dir: Path,
) -> FullControlledTransferScaffoldReceipt:
    plan = _load(full_plan_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    encounters_path = output_dir / "full_controlled_transfer_encounter_receipts.jsonl"
    blind_labels_path = output_dir / "full_controlled_transfer_blind_labels.json"
    scaffold_receipt_path = output_dir / "full_controlled_transfer_scaffold_receipt.json"

    authorized = (
        plan.get("status") == "DIO_METAMORPHIC_ADAPTATION_FULL_CONTROLLED_TRANSFER_PLAN_READY"
        and plan.get("full_run_planning_authorized") is True
        and plan.get("execute_by_default") is False
        and plan.get("requires_explicit_execute_flag") is True
        and plan.get("adaptive_claim_authorized") is False
        and plan.get("commercial_or_world_first_claim_authorized") is False
    )

    if not authorized:
        receipt = FullControlledTransferScaffoldReceipt(
            scaffold_version=FULL_TRANSFER_SCAFFOLD_VERSION,
            status=FULL_TRANSFER_SCAFFOLD_REFUSED_TOKEN,
            plan_status=str(plan.get("status")),
            full_run_planning_authorized=False,
            execute_by_default=bool(plan.get("execute_by_default")),
            arms_staged=0,
            encounters_per_arm=0,
            full_run_encounters_staged=0,
            encounter_receipts_path=str(encounters_path),
            blind_labels_path=str(blind_labels_path),
            adaptive_claim_authorized=False,
            commercial_or_world_first_claim_authorized=False,
            professional_approval_claim_authorized=False,
            publication_authorized=False,
            spend_authorized=False,
            fulfilment_authorized=False,
            authority_expansion_authorized=False,
            plan_sha256=_sha256_path(full_plan_path),
            boundary=(
                "Full controlled transfer scaffold refused because the full run plan did not "
                "authorize planning. No adaptive, commercial, professional, publication, spend, "
                "fulfilment, world-first, or authority-expansion claim is authorized."
            ),
        )
        scaffold_receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    arms = tuple(plan.get("arms", ()))
    encounters_per_arm = int(plan.get("encounters_per_arm", 0))

    blind_labels = {}
    ordinal = 1

    with encounters_path.open("w") as fh:
        for arm in arms:
            for encounter_index in range(1, encounters_per_arm + 1):
                blind_id = f"FULL-TRANSFER-BLIND-{ordinal:04d}"
                encounter = {
                    "blind_id": blind_id,
                    "arm": arm,
                    "encounter_index": encounter_index,
                    "status": "FULL_CONTROLLED_TRANSFER_STAGED_NOT_EXECUTED",
                    "execute_by_default": False,
                    "executed": False,
                    "native_execution_allowed_only_with_explicit_flag": True,
                    "adaptive_claim_authorized": False,
                    "commercial_or_world_first_claim_authorized": False,
                    "professional_approval_claim_authorized": False,
                    "publication_authorized": False,
                    "spend_authorized": False,
                    "fulfilment_authorized": False,
                    "authority_expansion_authorized": False,
                }
                fh.write(json.dumps(encounter, sort_keys=True) + "\n")
                blind_labels[blind_id] = {
                    "arm": arm,
                    "encounter_index": encounter_index,
                }
                ordinal += 1

    blind_labels_path.write_text(json.dumps(blind_labels, indent=2, sort_keys=True) + "\n")

    receipt = FullControlledTransferScaffoldReceipt(
        scaffold_version=FULL_TRANSFER_SCAFFOLD_VERSION,
        status=FULL_TRANSFER_SCAFFOLD_READY_TOKEN,
        plan_status=str(plan.get("status")),
        full_run_planning_authorized=True,
        execute_by_default=False,
        arms_staged=len(arms),
        encounters_per_arm=encounters_per_arm,
        full_run_encounters_staged=len(arms) * encounters_per_arm,
        encounter_receipts_path=str(encounters_path),
        blind_labels_path=str(blind_labels_path),
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        plan_sha256=_sha256_path(full_plan_path),
        boundary=(
            "This scaffold stages the full 25-encounter real controlled transfer run only. "
            "It does not execute native commands by default and does not authorize adaptive-"
            "composition, retained-learning, real performance improvement, commercial validation, "
            "professional approval, publication, spend, fulfilment, world-first, or authority-expansion claims."
        ),
    )
    scaffold_receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
