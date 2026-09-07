from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


REAL_PILOT_SCAFFOLD_VERSION = "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_SCAFFOLD_V1"
REAL_PILOT_SCAFFOLD_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_SCAFFOLD_READY"
REAL_PILOT_SCAFFOLD_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_REAL_PILOT_SCAFFOLD_REFUSED"


@dataclass(frozen=True)
class RealPilotScaffoldReceipt:
    scaffold_version: str
    status: str
    plan_status: str
    real_pilot_authorized: bool
    execute_by_default: bool
    pilot_encounters_staged: int
    arms_staged: int
    real_pilot_encounter_receipts_path: str
    real_pilot_blind_labels_path: str
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


def stage_real_pilot_encounters(
    *,
    real_plan_path: Path,
    output_dir: Path,
) -> RealPilotScaffoldReceipt:
    plan = _load(real_plan_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    encounters_path = output_dir / "real_pilot_encounter_receipts.jsonl"
    blind_labels_path = output_dir / "real_pilot_blind_labels.json"
    receipt_path = output_dir / "real_pilot_scaffold_receipt.json"

    authorized = (
        plan.get("status") == "DIO_METAMORPHIC_ADAPTATION_REAL_CONTROLLED_TRANSFER_PILOT_PLAN_READY"
        and plan.get("real_pilot_authorized") is True
        and plan.get("execute_by_default") is False
        and plan.get("adaptive_claim_authorized") is False
        and plan.get("commercial_or_world_first_claim_authorized") is False
    )

    if not authorized:
        receipt = RealPilotScaffoldReceipt(
            scaffold_version=REAL_PILOT_SCAFFOLD_VERSION,
            status=REAL_PILOT_SCAFFOLD_REFUSED_TOKEN,
            plan_status=str(plan.get("status")),
            real_pilot_authorized=False,
            execute_by_default=bool(plan.get("execute_by_default")),
            pilot_encounters_staged=0,
            arms_staged=0,
            real_pilot_encounter_receipts_path=str(encounters_path),
            real_pilot_blind_labels_path=str(blind_labels_path),
            adaptive_claim_authorized=False,
            commercial_or_world_first_claim_authorized=False,
            professional_approval_claim_authorized=False,
            publication_authorized=False,
            spend_authorized=False,
            fulfilment_authorized=False,
            authority_expansion_authorized=False,
            plan_sha256=_sha256_path(real_plan_path),
            boundary=(
                "Real pilot scaffold refused because the real controlled transfer plan did not "
                "authorize a limited pilot. No adaptive, commercial, professional, publication, "
                "spend, fulfilment, world-first, or authority-expansion claim is authorized."
            ),
        )
        receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    arms = tuple(plan.get("arms", ()))
    pilot_encounters = int(plan.get("pilot_encounters", 0))

    selected_arms = arms[:pilot_encounters]
    blind_labels = {}

    with encounters_path.open("w") as fh:
        for index, arm in enumerate(selected_arms, start=1):
            blind_id = f"REAL-PILOT-BLIND-{index:04d}"
            encounter = {
                "blind_id": blind_id,
                "arm": arm,
                "encounter_index": 1,
                "status": "REAL_PILOT_STAGED_NOT_EXECUTED",
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
                "encounter_index": 1,
            }

    blind_labels_path.write_text(json.dumps(blind_labels, indent=2, sort_keys=True) + "\n")

    receipt = RealPilotScaffoldReceipt(
        scaffold_version=REAL_PILOT_SCAFFOLD_VERSION,
        status=REAL_PILOT_SCAFFOLD_READY_TOKEN,
        plan_status=str(plan.get("status")),
        real_pilot_authorized=True,
        execute_by_default=False,
        pilot_encounters_staged=len(selected_arms),
        arms_staged=len(selected_arms),
        real_pilot_encounter_receipts_path=str(encounters_path),
        real_pilot_blind_labels_path=str(blind_labels_path),
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        professional_approval_claim_authorized=False,
        publication_authorized=False,
        spend_authorized=False,
        fulfilment_authorized=False,
        authority_expansion_authorized=False,
        plan_sha256=_sha256_path(real_plan_path),
        boundary=(
            "This scaffold stages one limited real native pilot encounter per arm. It does not "
            "execute native commands by default, does not authorize the full 25-encounter run, "
            "and does not authorize adaptive-composition, real performance, commercial validation, "
            "professional approval, publication, spend, fulfilment, world-first, or authority-expansion claims."
        ),
    )
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
