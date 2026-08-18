from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from products.studio_native_closure import (
    ACCEPTANCE_TOKEN,
    StudioNativeClosureError,
    close_studio_case,
    verify_native_closure_proof,
)

CASES = {
    "site_studio": Path("config/studio_harvest/site_studio.json"),
    "professional_correspondence_studio": Path("config/studio_harvest/professional_correspondence_studio.json"),
}


def _identity(result: dict[str, Any]) -> tuple[Any, ...]:
    return (
        result["receipt"]["native_closure_fingerprint"],
        result["proof_manifest"]["proof_fingerprint"],
        tuple((row["path"], row["sha256"]) for row in result["proof_manifest"]["artifacts"]),
    )


def _tamper_probe(result: dict[str, Any], root: Path) -> bool:
    source = Path(result["output_dir"])
    probe = root / f"tamper-{result['manifest']['studio_id']}"
    if probe.exists():
        shutil.rmtree(probe)
    shutil.copytree(source, probe)
    first = result["proof_manifest"]["artifacts"][0]["path"]
    target = probe / first
    target.write_bytes(target.read_bytes() + b"\nTAMPER")
    try:
        verify_native_closure_proof(probe, result["proof_manifest"])
    except StudioNativeClosureError:
        return True
    finally:
        shutil.rmtree(probe, ignore_errors=True)
    return False


def run_gauntlet(*, output_dir: Path | None = None) -> dict[str, Any]:
    owned = tempfile.TemporaryDirectory(prefix="dio-studio-native-closure-") if output_dir is None else None
    out = Path(owned.name) if owned else Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    studios: dict[str, Any] = {}

    for studio_id, manifest_path in CASES.items():
        first = close_studio_case(manifest_path=manifest_path, output_dir=out / studio_id / "run-a")
        second = close_studio_case(manifest_path=manifest_path, output_dir=out / studio_id / "run-b")
        if _identity(first) != _identity(second):
            raise AssertionError(f"{studio_id} native capability closure is non-deterministic")
        verify_native_closure_proof(Path(first["output_dir"]), first["proof_manifest"])
        verify_native_closure_proof(Path(second["output_dir"]), second["proof_manifest"])
        if not _tamper_probe(first, out):
            raise AssertionError(f"{studio_id} closure tamper detection failed")
        ledger = first["ledger"]
        if ledger["organ_execution_truth"] != "NATIVE_MULTI_ORGAN_EXECUTION_PROVED":
            raise AssertionError(f"{studio_id} did not reach unqualified native multi-organ execution")
        if not ledger["all_declared_capabilities_executed"]:
            raise AssertionError(f"{studio_id} declared capability closure incomplete")
        if any(row["execution_state"] != "NATIVE_EXECUTED" or row["missing_capabilities"] for row in ledger["organs"]):
            raise AssertionError(f"{studio_id} contains non-native or missing organ capabilities")
        receipt = first["receipt"]
        if any(receipt[key] != "REFUSE" for key in ("external_publication", "external_send", "media_spend", "payment")):
            raise AssertionError(f"{studio_id} authority drift")
        if receipt["external_effects"] or receipt["authority_created"] or receipt["new_engine_created"]:
            raise AssertionError(f"{studio_id} closure created forbidden authority/effects/engine")
        studios[studio_id] = {
            "native_capability_closure": "PASS",
            "deterministic_native_closure": "PASS",
            "native_closure_tamper_detection": "PASS",
            "truthful_capability_accounting": "PASS",
            "authority_boundary": "PASS",
            "organ_execution_truth": ledger["organ_execution_truth"],
            "native_organ_count": ledger["native_organ_count"],
            "partial_organ_count": ledger["partial_organ_count"],
            "source_bound_only_count": ledger["source_bound_only_count"],
            "all_declared_capabilities_executed": True,
            "external_publication": "REFUSE",
            "external_send": "REFUSE",
            "media_spend": "REFUSE",
            "payment": "REFUSE",
            "human_gate": "NEEDS_YOU",
            "native_closure_fingerprint": receipt["native_closure_fingerprint"],
        }

    receipt = {
        "schema": "dio.studio_native_closure_gauntlet_receipt.v1",
        "studio_count": len(studios),
        "studios": studios,
        "unqualified_native_multi_organ_execution": "PASS",
        "external_effects": False,
        "new_engine_created": False,
        "acceptance_token": ACCEPTANCE_TOKEN,
    }
    (out / "STUDIO_NATIVE_CLOSURE_GAUNTLET_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if owned is not None:
        owned.cleanup()
    return receipt
