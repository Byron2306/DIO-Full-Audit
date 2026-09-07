from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


COMPATIBILITY_VERSION = "DIO_METAMORPHIC_ADAPTATION_NATIVE_COMPATIBILITY_V1"
COMPATIBILITY_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_NATIVE_COMPATIBILITY_CLASSIFIED"


@dataclass(frozen=True)
class NativeCompatibilitySummary:
    compatibility_version: str
    status: str
    compatible_fast: int
    compatible_long_running: int
    failed_contract: int
    failed_dependency: int
    failed_runtime: int
    adaptive_claim_authorized: bool
    classification_boundary: str


def _classify_failure(result: dict) -> str:
    exit_code = result["exit_code"]
    refusal_reason = result.get("refusal_reason") or ""

    if exit_code == 0:
        return "compatible_fast"

    if exit_code == 124 or "timed out" in refusal_reason.lower():
        return "compatible_long_running"

    return "failed_runtime"


def classify_native_compatibility(receipt_path: Path) -> NativeCompatibilitySummary:
    receipt = json.loads(receipt_path.read_text())

    counts = {
        "compatible_fast": 0,
        "compatible_long_running": 0,
        "failed_contract": 0,
        "failed_dependency": 0,
        "failed_runtime": 0,
    }

    for result in receipt["command_results"]:
        counts[_classify_failure(result)] += 1

    return NativeCompatibilitySummary(
        compatibility_version=COMPATIBILITY_VERSION,
        status=COMPATIBILITY_READY_TOKEN,
        compatible_fast=counts["compatible_fast"],
        compatible_long_running=counts["compatible_long_running"],
        failed_contract=counts["failed_contract"],
        failed_dependency=counts["failed_dependency"],
        failed_runtime=counts["failed_runtime"],
        adaptive_claim_authorized=receipt["adaptive_claim_authorized"],
        classification_boundary=(
            "Native compatibility classification describes command readiness only. "
            "It does not evaluate transfer performance and does not authorize an "
            "adaptive-composition claim."
        ),
    )


def write_native_compatibility_summary(receipt_path: Path, output_path: Path) -> NativeCompatibilitySummary:
    summary = classify_native_compatibility(receipt_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(summary), indent=2, sort_keys=True) + "\n")
    return summary
