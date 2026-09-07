from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from experiments.metamorphic_adaptation.confirmatory_manifest import write_confirmatory_manifest
from experiments.metamorphic_adaptation.dry_run_validator import validate_native_dry_run
from experiments.metamorphic_adaptation.native_bindings import load_native_bindings


PREFLIGHT_VERSION = "DIO_METAMORPHIC_ADAPTATION_NATIVE_PREFLIGHT_V1"
PREFLIGHT_READY_TOKEN = "DIO_METAMORPHIC_ADAPTATION_NATIVE_PREFLIGHT_READY"


@dataclass(frozen=True)
class NativePreflightReceipt:
    preflight_version: str
    status: str
    manifest_path: str
    dry_run_report_path: str
    manifest_sha256: str
    dry_run_report_sha256: str
    full_native_execution_allowed: bool
    refusal_boundary: str


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_native_preflight_bundle(output_dir: Path) -> NativePreflightReceipt:
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / "confirmatory_manifest.json"
    dry_run_report_path = output_dir / "native_dry_run_report.json"
    receipt_path = output_dir / "native_preflight_receipt.json"

    run_output = output_dir / "run_output_custody"

    manifest = write_confirmatory_manifest(
        manifest_path,
        run_output=run_output,
    )

    bindings = load_native_bindings()
    dry_run_report = validate_native_dry_run(
        bindings=bindings,
        run_output=run_output,
        python_executable="python",
    )

    dry_run_report_path.write_text(
        json.dumps(asdict(dry_run_report), indent=2, sort_keys=True) + "\n"
    )

    receipt = NativePreflightReceipt(
        preflight_version=PREFLIGHT_VERSION,
        status=PREFLIGHT_READY_TOKEN,
        manifest_path=str(manifest_path),
        dry_run_report_path=str(dry_run_report_path),
        manifest_sha256=_sha256_path(manifest_path),
        dry_run_report_sha256=_sha256_path(dry_run_report_path),
        full_native_execution_allowed=False,
        refusal_boundary=(
            "This preflight proves only manifest, binding and dry-run custody readiness. "
            "It does not execute adaptation episodes, does not perform transfer evaluation, "
            "and does not authorize an adaptive-composition claim."
        ),
    )

    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n")

    # Keep manifest referenced so linters do not mistake the call for ceremonial code.
    assert manifest.dry_run_status == "NATIVE_DRY_RUN_VALIDATED"

    return receipt
