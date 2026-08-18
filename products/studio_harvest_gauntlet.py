from __future__ import annotations

import copy
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from products.studio_harvest import (
    ACCEPTANCE_TOKEN,
    StudioHarvestError,
    build_studio_case,
    validate_studio_manifest,
    verify_studio_proof,
)

CASES = {
    "site_studio": Path("config/studio_harvest/site_studio.json"),
    "professional_correspondence_studio": Path("config/studio_harvest/professional_correspondence_studio.json"),
}


def _identity(result: dict[str, Any]) -> tuple[Any, ...]:
    return (
        result["receipt"]["studio_fingerprint"],
        result["proof_manifest"]["proof_fingerprint"],
        tuple((x["path"], x["sha256"]) for x in result["proof_manifest"]["artifacts"]),
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
        verify_studio_proof(probe, result["proof_manifest"])
    except StudioHarvestError:
        return True
    finally:
        shutil.rmtree(probe, ignore_errors=True)
    return False


def run_gauntlet(*, output_dir: Path | None = None) -> dict[str, Any]:
    owned = tempfile.TemporaryDirectory(prefix="dio-studio-harvest-") if output_dir is None else None
    out = Path(owned.name) if owned else Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    receipts: dict[str, Any] = {}
    last_result: dict[str, Any] | None = None
    for studio_id, manifest_path in CASES.items():
        first = build_studio_case(manifest_path=manifest_path, output_dir=out / studio_id / "run-a")
        second = build_studio_case(manifest_path=manifest_path, output_dir=out / studio_id / "run-b")
        last_result = first
        if _identity(first) != _identity(second):
            raise AssertionError(f"{studio_id} controlled composition is non-deterministic")
        verify_studio_proof(Path(first["output_dir"]), first["proof_manifest"])
        verify_studio_proof(Path(second["output_dir"]), second["proof_manifest"])
        if not _tamper_probe(first, out):
            raise AssertionError(f"{studio_id} tamper detection failed")
        if first["route"]["product"] != studio_id or first["route"]["intent"] != "intake_request":
            raise AssertionError(f"{studio_id} Vesper route mismatch")
        if any(row["binding_state"] != "SOURCE_BOUND" for row in first["bindings"]):
            raise AssertionError(f"{studio_id} source binding incomplete")
        authority = first["receipt"]
        if any(authority[key] != "REFUSE" for key in ("external_publication", "external_send", "media_spend", "payment")):
            raise AssertionError(f"{studio_id} authority drift")
        receipts[studio_id] = {
            "job_resolution": "PASS",
            "capability_binding": "PASS",
            "vesper_routing": "PASS",
            "controlled_artifact_generation": "PASS",
            "deterministic_generation": "PASS",
            "tamper_detection": "PASS",
            "authority_boundary": "PASS",
            "organ_execution_truth": first["receipt"]["organ_execution_truth"],
            "external_publication": "REFUSE",
            "external_send": "REFUSE",
            "media_spend": "REFUSE",
            "payment": "REFUSE",
            "human_gate": "NEEDS_YOU",
            "studio_fingerprint": first["receipt"]["studio_fingerprint"],
        }

    if last_result is None:
        raise AssertionError("Studio Harvest has no cases")
    unsafe = copy.deepcopy(last_result["manifest"])
    unsafe["authority"]["external_send"] = "ALLOW"
    try:
        validate_studio_manifest(unsafe)
    except StudioHarvestError:
        unsafe_promotion_refused = True
    else:
        unsafe_promotion_refused = False
    if not unsafe_promotion_refused:
        raise AssertionError("unsafe Studio Harvest promotion accepted")

    receipt = {
        "schema": "dio.studio_harvest_gauntlet_receipt.v1",
        "studio_count": len(receipts),
        "studios": receipts,
        "unsafe_promotion_refusal": "PASS",
        "new_engine_created": False,
        "phase16_integrity_verifier_reused": True,
        "acceptance_token": ACCEPTANCE_TOKEN,
    }
    (out / "STUDIO_HARVEST_GAUNTLET_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if owned is not None:
        owned.cleanup()
    return receipt
