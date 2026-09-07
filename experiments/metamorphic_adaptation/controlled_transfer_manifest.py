from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


CONTROLLED_TRANSFER_MANIFEST_VERSION = "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_TRANSFER_MANIFEST_V1"
CONTROLLED_TRANSFER_MANIFEST_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_TRANSFER_MANIFEST_READY"


@dataclass(frozen=True)
class ControlledTransferManifest:
    manifest_version: str
    status: str
    readiness_digest_status: str
    readiness_digest_sha256: str
    transfer_run_authorized: bool
    execute_by_default: bool
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    arms: tuple[str, ...]
    encounter_count: int
    frozen_input_required: bool
    blind_evaluation_required: bool
    factorial_analysis_required: bool
    output_artifacts: tuple[str, ...]
    boundary: str


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_controlled_transfer_manifest(
    *,
    readiness_digest_path: Path,
    encounter_count: int = 5,
) -> ControlledTransferManifest:
    readiness_digest = json.loads(readiness_digest_path.read_text())

    transfer_run_authorized = (
        readiness_digest["status"] == "DIO_METAMORPHIC_ADAPTATION_NATIVE_READINESS_DIGEST_READY"
        and readiness_digest["ready_for_controlled_transfer_run"] is True
        and readiness_digest["adaptive_claim_authorized"] is False
        and readiness_digest["commercial_or_world_first_claim_authorized"] is False
    )

    return ControlledTransferManifest(
        manifest_version=CONTROLLED_TRANSFER_MANIFEST_VERSION,
        status=CONTROLLED_TRANSFER_MANIFEST_READY_TOKEN,
        readiness_digest_status=readiness_digest["status"],
        readiness_digest_sha256=_sha256_path(readiness_digest_path),
        transfer_run_authorized=transfer_run_authorized,
        execute_by_default=False,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        arms=(
            "A_STATELESS_RESET",
            "B_COMPOSITION_ONLY_NO_RETAINED_LEARNING",
            "C_SEMANTIC_RETAINED",
            "D_MARKET_RETAINED",
            "E_FULL_SEMANTIC_MARKET_BEAST",
        ),
        encounter_count=encounter_count,
        frozen_input_required=True,
        blind_evaluation_required=True,
        factorial_analysis_required=True,
        output_artifacts=(
            "controlled_transfer_manifest.json",
            "encounter_receipts.jsonl",
            "blind_evaluation_receipt.json",
            "factorial_analysis_receipt.json",
            "transfer_claim_gate.json",
        ),
        boundary=(
            "This manifest authorizes staging of a controlled transfer run only. "
            "It does not execute the run by default and does not authorize any "
            "adaptive-composition, commercial, professional, publication, spend, "
            "fulfilment, world-first, or authority-expansion claim."
        ),
    )


def write_controlled_transfer_manifest(
    *,
    readiness_digest_path: Path,
    output_path: Path,
    encounter_count: int = 5,
) -> ControlledTransferManifest:
    manifest = build_controlled_transfer_manifest(
        readiness_digest_path=readiness_digest_path,
        encounter_count=encounter_count,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n")
    return manifest
