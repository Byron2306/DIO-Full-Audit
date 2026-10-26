from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


EXPECTED_WAVE_STATES = {
    1: "FUSION_WAVE1_READY",
    2: "FUSION_WAVE2_READY",
    3: "FUSION_WAVE3_READY",
    4: "FUSION_WAVE4_READY",
    5: "FUSION_WAVE5_READY",
    6: "FUSION_WAVE6_READY",
    7: "FUSION_WAVE7_READY",
    8: "FUSION_WAVE8_READY",
}

PRODUCT_IDS = {
    "dio_assurance",
    "dio_agent_authority",
    "dio_vendorproof",
    "dio_accreditation",
    "dio_tenderproof",
    "dio_grantproof",
    "dio_research_integrity",
    "dio_regops",
    "dio_capitalroom",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check DIO Fusion Wave 9 CapitalRoom / External Proof readiness.")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--core", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    core = Path(args.core).resolve()
    out = Path(args.out).resolve()
    blockers: list[str] = []

    if str(core) not in sys.path:
        sys.path.insert(0, str(core))
    from capitalroom import build_capitalroom, validate_manifest, write_capitalroom

    phase0_path = workspace / "state" / "system_snapshots" / "latest.json"
    incarnation_path = workspace / "receipts" / "incarnation-latest.json"
    if not phase0_path.is_file():
        blockers.append(f"missing Phase 0 snapshot: {phase0_path}")
        phase0 = {}
    else:
        phase0 = _load(phase0_path)
        if phase0.get("overall_state") != "READY":
            blockers.append(f"Phase 0 state is not READY: {phase0.get('overall_state')}")

    if not incarnation_path.is_file():
        blockers.append(f"missing Incarnation receipt: {incarnation_path}")
        incarnation = {}
    else:
        incarnation = _load(incarnation_path)
        if incarnation.get("state") != "READY_FOR_FUSION":
            blockers.append(f"Incarnation state is not READY_FOR_FUSION: {incarnation.get('state')}")

    wave_receipts: dict[int, dict] = {}
    wave_hashes: dict[str, str] = {}
    for wave, expected_state in EXPECTED_WAVE_STATES.items():
        path = workspace / "receipts" / f"fusion-wave{wave}-latest.json"
        if not path.is_file():
            blockers.append(f"missing Wave {wave} receipt: {path}")
            continue
        payload = _load(path)
        wave_receipts[wave] = payload
        wave_hashes[str(wave)] = _sha256(path)
        if payload.get("state") != expected_state:
            blockers.append(f"Wave {wave} state is not {expected_state}: {payload.get('state')}")
        if payload.get("blockers") not in ([], None):
            blockers.append(f"Wave {wave} receipt contains blockers.")

    wave8 = wave_receipts.get(8) or {}
    if wave8.get("state") != "FUSION_WAVE8_READY":
        blockers.append("Wave 8 is not locally accepted.")
    if wave8.get("continuous_assurance_authority") is not False:
        blockers.append("Wave 8 receipt does not preserve no-authority assurance.")
    if wave8.get("continuous_assurance_execution") is not False:
        blockers.append("Wave 8 receipt does not preserve no-execution assurance.")

    required_paths = [
        core / "capitalroom" / "proof_room.py",
        core / "config" / "dio_capitalroom.json",
        core / "schemas" / "dio_capitalroom.schema.json",
        core / "config" / "dio_product_portfolio.json",
        core / "config" / "dio_vertical_executors.json",
    ]
    for path in required_paths:
        if not path.is_file():
            blockers.append(f"missing CapitalRoom source path: {path}")

    config = _load(core / "config" / "dio_capitalroom.json") if (core / "config" / "dio_capitalroom.json").is_file() else {}
    portfolio = _load(core / "config" / "dio_product_portfolio.json") if (core / "config" / "dio_product_portfolio.json").is_file() else {}
    vertical = _load(core / "config" / "dio_vertical_executors.json") if (core / "config" / "dio_vertical_executors.json").is_file() else {}

    if set(config.get("product_ids") or []) != PRODUCT_IDS:
        blockers.append("CapitalRoom config does not expose the exact nine governed product IDs.")
    portfolio_ids = {str(item.get("id")) for item in portfolio.get("products") or []}
    if not PRODUCT_IDS.issubset(portfolio_ids):
        blockers.append("DIO product portfolio is missing one or more CapitalRoom proof products.")

    locked_count = sum(
        1
        for executor in vertical.get("executors") or []
        for capability in executor.get("capabilities") or []
        if capability.get("binding_state") == "locked"
    )
    bound_count = sum(
        1
        for executor in vertical.get("executors") or []
        for capability in executor.get("capabilities") or []
        if capability.get("binding_state") == "bound"
    )
    if locked_count != 8:
        blockers.append(f"Expected 8 explicitly locked Wave 5 capabilities, found {locked_count}.")
    if bound_count != 8:
        blockers.append(f"Expected 8 bound Wave 5 capabilities, found {bound_count}.")
    if (vertical.get("laws") or {}).get("automatic_external_actions") is not False:
        blockers.append("Vertical executor registry does not preserve automatic_external_actions=false.")

    authority = config.get("authority") or {}
    truth = config.get("truth_boundary") or {}
    publication = config.get("publication") or {}
    if authority.get("capitalroom_has_authority") is not False:
        blockers.append("CapitalRoom must have no authority.")
    if authority.get("capitalroom_can_execute") is not False:
        blockers.append("CapitalRoom must not execute.")
    if authority.get("external_release_authorized") is not False:
        blockers.append("CapitalRoom external release must remain unauthorized.")
    if authority.get("kernel_authority") != "Valinor":
        blockers.append("Valinor is not preserved as sole kernel authority.")
    if authority.get("execution_identity_authority") != "ARDA":
        blockers.append("ARDA is not preserved as execution identity authority.")
    if publication.get("external_release") != "locked":
        blockers.append("CapitalRoom external publication must remain locked.")
    if publication.get("redact_local_paths") is not True:
        blockers.append("CapitalRoom local-path redaction must be enabled.")
    if any(value is not False for value in truth.values()):
        blockers.append("CapitalRoom truth boundary contains an overclaim.")

    proof_room_dir = workspace / "capitalroom" / "latest"
    manifest: dict = {}
    room: dict = {}
    if not blockers and len(wave_receipts) == 8:
        try:
            room = build_capitalroom(
                phase0_snapshot=phase0,
                incarnation_receipt=incarnation,
                wave_receipts=wave_receipts,
                product_portfolio=portfolio,
                vertical_registry=vertical,
            )
            manifest = write_capitalroom(room, proof_room_dir)
            validate_manifest(proof_room_dir, manifest)
        except Exception as exc:
            blockers.append(f"CapitalRoom build/validation failed: {exc}")

    output_files = [
        "PROOF_ROOM.json",
        "ARCHITECTURE_PROOF.json",
        "OPERATIONAL_PROOF.json",
        "REFUSAL_PROOF.json",
        "PRODUCT_PROOF.json",
        "README.md",
        "MANIFEST.json",
    ]
    if not blockers:
        for name in output_files:
            if not (proof_room_dir / name).is_file():
                blockers.append(f"CapitalRoom proof-room output missing: {name}")

    receipt = {
        "schema": "dio.fusion.wave9.receipt.v1",
        "state": "FUSION_WAVE9_READY" if not blockers else "BLOCKED",
        "depends_on": {
            "fusion_wave8_receipt": str(workspace / "receipts" / "fusion-wave8-latest.json"),
            "fusion_wave8_state": wave8.get("state"),
        },
        "source_truth_snapshot_id": phase0.get("snapshot_id"),
        "incarnation_state": incarnation.get("state"),
        "fusion_wave_receipts_verified": len(wave_receipts),
        "fusion_wave_receipt_sha256": wave_hashes,
        "proof_sections": 4,
        "product_profiles": 9 if PRODUCT_IDS.issubset(portfolio_ids) else 0,
        "bound_capabilities_disclosed": bound_count,
        "locked_capabilities_exposed": locked_count,
        "proof_room_files": len(output_files) if not blockers else 0,
        "proof_room_id": room.get("room_id"),
        "proof_room_fingerprint": room.get("fingerprint"),
        "proof_room_manifest_fingerprint": manifest.get("fingerprint"),
        "proof_room_dir": str(proof_room_dir),
        "commercial_overclaim_guards": len(truth),
        "capitalroom_authority": False,
        "capitalroom_execution": False,
        "external_release_authorized": False,
        "kernel_authority": "Valinor",
        "execution_identity_authority": "ARDA",
        "blockers": blockers,
        "receipt": str(out),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if not blockers else 2


if __name__ == "__main__":
    sys.exit(main())
