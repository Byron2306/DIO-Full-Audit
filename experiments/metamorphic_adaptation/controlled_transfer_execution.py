from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


CONTROLLED_TRANSFER_EXECUTION_VERSION = "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_TRANSFER_EXECUTION_V1"
CONTROLLED_TRANSFER_EXECUTION_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_TRANSFER_EXECUTION_FIXTURE_READY"
CONTROLLED_TRANSFER_EXECUTION_REFUSED_TOKEN = "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_TRANSFER_EXECUTION_REFUSED"


@dataclass(frozen=True)
class ControlledTransferExecutionReceipt:
    execution_version: str
    status: str
    run_scaffold_status: str
    execute_requested: bool
    fixture_mode: bool
    encounters_loaded: int
    encounters_executed: int
    executed_receipts_path: str
    blind_labels_path: str
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    boundary: str


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _score_proxy(*, arm: str, encounter_index: int) -> float:
    # Deterministic fixture score. It proves the harness can receipt and compare
    # outputs, but it is not evidence of real adaptive performance.
    arm_weight = {
        "A_STATELESS_RESET": 0.10,
        "B_COMPOSITION_ONLY_NO_RETAINED_LEARNING": 0.20,
        "C_SEMANTIC_RETAINED": 0.30,
        "D_MARKET_RETAINED": 0.30,
        "E_FULL_SEMANTIC_MARKET_BEAST": 0.40,
    }.get(arm, 0.0)
    return round(arm_weight + (encounter_index * 0.01), 4)


def execute_controlled_transfer_fixture(
    *,
    run_receipt_path: Path,
    encounter_receipts_path: Path,
    output_dir: Path,
    execute: bool = False,
) -> ControlledTransferExecutionReceipt:
    run_receipt = _load_json(run_receipt_path)
    run_status = run_receipt.get("status")

    output_dir.mkdir(parents=True, exist_ok=True)
    executed_receipts_path = output_dir / "executed_encounter_receipts.jsonl"
    blind_labels_path = output_dir / "blind_labels.json"

    staged_lines = [
        json.loads(line)
        for line in encounter_receipts_path.read_text().splitlines()
        if line.strip()
    ]

    if run_status != "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_TRANSFER_RUN_SCAFFOLD_READY":
        receipt = ControlledTransferExecutionReceipt(
            execution_version=CONTROLLED_TRANSFER_EXECUTION_VERSION,
            status=CONTROLLED_TRANSFER_EXECUTION_REFUSED_TOKEN,
            run_scaffold_status=str(run_status),
            execute_requested=execute,
            fixture_mode=True,
            encounters_loaded=len(staged_lines),
            encounters_executed=0,
            executed_receipts_path=str(executed_receipts_path),
            blind_labels_path=str(blind_labels_path),
            adaptive_claim_authorized=False,
            commercial_or_world_first_claim_authorized=False,
            boundary=(
                "Controlled transfer execution refused because the staged run receipt "
                "was not scaffold-ready. No adaptive, commercial, professional, publication, "
                "spend, fulfilment, world-first, or authority-expansion claim is authorized."
            ),
        )
        (output_dir / "controlled_transfer_execution_receipt.json").write_text(
            json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n"
        )
        return receipt

    blind_labels = {}
    with executed_receipts_path.open("w") as fh:
        for ordinal, staged in enumerate(staged_lines, start=1):
            arm = staged["arm"]
            encounter_index = int(staged["encounter_index"])
            blind_id = f"BLIND-{ordinal:04d}"

            input_material = json.dumps(
                {
                    "arm": arm,
                    "encounter_index": encounter_index,
                    "fixture": "controlled_transfer_execution_v1",
                },
                sort_keys=True,
            )
            output_material = json.dumps(
                {
                    "blind_id": blind_id,
                    "fixture_output": f"{arm}:{encounter_index}",
                    "score_proxy": _score_proxy(arm=arm, encounter_index=encounter_index),
                },
                sort_keys=True,
            )

            blind_labels[blind_id] = {
                "arm": arm,
                "encounter_index": encounter_index,
            }

            fh.write(json.dumps({
                "blind_id": blind_id,
                "arm": arm,
                "encounter_index": encounter_index,
                "status": "EXECUTED_FIXTURE",
                "executed": True,
                "fixture_mode": True,
                "input_sha256": _sha256_text(input_material),
                "output_sha256": _sha256_text(output_material),
                "score_proxy": _score_proxy(arm=arm, encounter_index=encounter_index),
                "adaptive_claim_authorized": False,
                "commercial_or_world_first_claim_authorized": False,
            }, sort_keys=True) + "\n")

    blind_labels_path.write_text(json.dumps(blind_labels, indent=2, sort_keys=True) + "\n")

    receipt = ControlledTransferExecutionReceipt(
        execution_version=CONTROLLED_TRANSFER_EXECUTION_VERSION,
        status=CONTROLLED_TRANSFER_EXECUTION_READY_TOKEN,
        run_scaffold_status=str(run_status),
        execute_requested=execute,
        fixture_mode=True,
        encounters_loaded=len(staged_lines),
        encounters_executed=len(staged_lines),
        executed_receipts_path=str(executed_receipts_path),
        blind_labels_path=str(blind_labels_path),
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        boundary=(
            "This fixture execution proves controlled transfer execution mechanics only. "
            "It does not constitute real adaptive performance evidence, does not claim "
            "improvement, and does not authorize commercial, professional, publication, "
            "spend, fulfilment, world-first, or authority-expansion claims."
        ),
    )

    (output_dir / "controlled_transfer_execution_receipt.json").write_text(
        json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n"
    )
    return receipt
