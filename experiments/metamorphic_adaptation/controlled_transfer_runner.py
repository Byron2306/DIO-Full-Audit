from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


CONTROLLED_TRANSFER_RUN_VERSION = "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_TRANSFER_RUNNER_V1"
CONTROLLED_TRANSFER_RUN_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_TRANSFER_RUN_SCAFFOLD_READY"
CONTROLLED_TRANSFER_RUN_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_TRANSFER_RUN_REFUSED"


@dataclass(frozen=True)
class ControlledTransferRunReceipt:
    run_version: str
    status: str
    transfer_run_authorized: bool
    execute_requested: bool
    executed: bool
    arms_staged: int
    encounters_staged: int
    encounter_receipts_path: str
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    boundary: str


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def stage_controlled_transfer_run(
    *,
    manifest_path: Path,
    output_dir: Path,
    execute: bool = False,
) -> ControlledTransferRunReceipt:
    manifest = _load(manifest_path)

    transfer_run_authorized = manifest.get("transfer_run_authorized") is True
    arms = tuple(manifest.get("arms", ()))
    encounter_count = int(manifest.get("encounter_count", 0))

    output_dir.mkdir(parents=True, exist_ok=True)
    encounter_receipts_path = output_dir / "encounter_receipts.jsonl"
    run_receipt_path = output_dir / "controlled_transfer_run_receipt.json"

    if not transfer_run_authorized:
        receipt = ControlledTransferRunReceipt(
            run_version=CONTROLLED_TRANSFER_RUN_VERSION,
            status=CONTROLLED_TRANSFER_RUN_REFUSED_TOKEN,
            transfer_run_authorized=False,
            execute_requested=execute,
            executed=False,
            arms_staged=0,
            encounters_staged=0,
            encounter_receipts_path=str(encounter_receipts_path),
            adaptive_claim_authorized=False,
            commercial_or_world_first_claim_authorized=False,
            boundary=(
                "Controlled transfer run refused because the manifest did not authorize staging. "
                "No adaptive, commercial, professional, publication, spend, fulfilment, world-first, "
                "or authority-expansion claim is authorized."
            ),
        )
        run_receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
        return receipt

    for arm in arms:
        (output_dir / arm).mkdir(parents=True, exist_ok=True)

    with encounter_receipts_path.open("w") as fh:
        for arm in arms:
            for encounter_index in range(1, encounter_count + 1):
                fh.write(json.dumps({
                    "arm": arm,
                    "encounter_index": encounter_index,
                    "status": "STAGED_NOT_EXECUTED",
                    "executed": False,
                    "adaptive_claim_authorized": False,
                    "commercial_or_world_first_claim_authorized": False,
                }, sort_keys=True) + "\n")

    receipt = ControlledTransferRunReceipt(
        run_version=CONTROLLED_TRANSFER_RUN_VERSION,
        status=CONTROLLED_TRANSFER_RUN_READY_TOKEN,
        transfer_run_authorized=True,
        execute_requested=execute,
        executed=False,
        arms_staged=len(arms),
        encounters_staged=len(arms) * encounter_count,
        encounter_receipts_path=str(encounter_receipts_path),
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        boundary=(
            "This scaffold stages controlled transfer encounters only. It does not execute "
            "adaptive evaluation, does not claim improvement, and does not authorize commercial, "
            "professional, publication, spend, fulfilment, world-first, or authority-expansion claims."
        ),
    )

    run_receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")
    return receipt
