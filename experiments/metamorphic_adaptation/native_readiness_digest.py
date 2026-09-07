from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


READINESS_DIGEST_VERSION = "DIO_METAMORPHIC_ADAPTATION_NATIVE_READINESS_DIGEST_V1"
READINESS_DIGEST_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_NATIVE_READINESS_DIGEST_READY"


@dataclass(frozen=True)
class NativeReadinessDigest:
    digest_version: str
    status: str
    preflight_status: str
    execution_status: str
    compatibility_status: str
    compatible_fast: int
    compatible_long_running: int
    failed_contract: int
    failed_dependency: int
    failed_runtime: int
    ready_for_controlled_transfer_run: bool
    adaptive_claim_authorized: bool
    commercial_or_world_first_claim_authorized: bool
    preflight_sha256: str
    execution_receipt_sha256: str
    compatibility_sha256: str
    boundary: str


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_native_readiness_digest(
    *,
    preflight_receipt_path: Path,
    execution_receipt_path: Path,
    compatibility_summary_path: Path,
) -> NativeReadinessDigest:
    preflight = _load(preflight_receipt_path)
    execution = _load(execution_receipt_path)
    compatibility = _load(compatibility_summary_path)

    failures = (
        compatibility["failed_contract"]
        + compatibility["failed_dependency"]
        + compatibility["failed_runtime"]
    )

    ready_for_controlled_transfer_run = (
        preflight["status"] == "DIO_METAMORPHIC_ADAPTATION_NATIVE_PREFLIGHT_READY"
        and execution["status"] == "DIO_METAMORPHIC_ADAPTATION_NATIVE_EXECUTION_COMPLETED"
        and compatibility["status"] == "DIO_METAMORPHIC_ADAPTATION_NATIVE_COMPATIBILITY_CLASSIFIED"
        and execution["adaptive_claim_authorized"] is False
        and compatibility["adaptive_claim_authorized"] is False
        and failures == 0
        and compatibility["compatible_fast"] >= 1
    )

    return NativeReadinessDigest(
        digest_version=READINESS_DIGEST_VERSION,
        status=READINESS_DIGEST_READY_TOKEN,
        preflight_status=preflight["status"],
        execution_status=execution["status"],
        compatibility_status=compatibility["status"],
        compatible_fast=compatibility["compatible_fast"],
        compatible_long_running=compatibility["compatible_long_running"],
        failed_contract=compatibility["failed_contract"],
        failed_dependency=compatibility["failed_dependency"],
        failed_runtime=compatibility["failed_runtime"],
        ready_for_controlled_transfer_run=ready_for_controlled_transfer_run,
        adaptive_claim_authorized=False,
        commercial_or_world_first_claim_authorized=False,
        preflight_sha256=_sha256_path(preflight_receipt_path),
        execution_receipt_sha256=_sha256_path(execution_receipt_path),
        compatibility_sha256=_sha256_path(compatibility_summary_path),
        boundary=(
            "This digest authorizes only a controlled transfer run. It does not authorize "
            "an adaptive-composition claim, commercial validation claim, professional approval "
            "claim, world-first claim, publication, spend, fulfilment, or authority expansion."
        ),
    )


def write_native_readiness_digest(
    *,
    preflight_receipt_path: Path,
    execution_receipt_path: Path,
    compatibility_summary_path: Path,
    output_path: Path,
) -> NativeReadinessDigest:
    digest = build_native_readiness_digest(
        preflight_receipt_path=preflight_receipt_path,
        execution_receipt_path=execution_receipt_path,
        compatibility_summary_path=compatibility_summary_path,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(digest), indent=2, sort_keys=True) + "\n")
    return digest
