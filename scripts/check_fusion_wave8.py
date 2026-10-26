from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check DIO Fusion Wave 8 Continuous Assurance readiness.")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--core", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    core = Path(args.core).resolve()
    out = Path(args.out).resolve()
    blockers: list[str] = []

    previous_path = workspace / "receipts" / "fusion-wave7-latest.json"
    if not previous_path.is_file():
        blockers.append(f"missing Wave 7 receipt: {previous_path}")
        previous = {}
    else:
        previous = _load(previous_path)
        if previous.get("state") != "FUSION_WAVE7_READY":
            blockers.append(f"Wave 7 state is not FUSION_WAVE7_READY: {previous.get('state')}")
        if previous.get("loki_mounted_sources") != 3:
            blockers.append("Wave 7 receipt does not prove all three mounted Loki/Mystique sources.")
        if previous.get("twin_layers") != 8:
            blockers.append("Wave 7 receipt does not prove all eight Twin layers.")

    required_paths = [
        core / "assurance" / "continuous.py",
        core / "assurance" / "watcher.py",
        core / "config" / "dio_continuous_assurance.json",
        core / "schemas" / "dio_continuous_assurance.schema.json",
    ]
    for path in required_paths:
        if not path.is_file():
            blockers.append(f"missing Continuous Assurance path: {path}")

    config_path = core / "config" / "dio_continuous_assurance.json"
    config = _load(config_path) if config_path.is_file() else {}
    watch_layers = config.get("watch_layers") or []
    authority = config.get("authority") or {}
    loki = config.get("loki") or {}
    notification = config.get("notification") or {}

    expected_layers = {
        "world_state", "evidence_state", "claim_state", "requirement_state",
        "authority_state", "capability_state", "action_state", "receipt_state",
    }
    if set(watch_layers) != expected_layers:
        blockers.append("Continuous Assurance watch-layer set does not match the eight canonical Twin layers.")
    if authority.get("continuous_assurance_has_authority") is not False:
        blockers.append("Continuous Assurance must have no authority.")
    if authority.get("continuous_assurance_can_execute") is not False:
        blockers.append("Continuous Assurance must not execute.")
    if authority.get("kernel_authority") != "Valinor":
        blockers.append("Valinor is not preserved as sole kernel authority.")
    if authority.get("execution_identity_authority") != "ARDA":
        blockers.append("ARDA is not preserved as execution identity authority.")
    if loki.get("rerun_on_material_drift") is not True:
        blockers.append("Loki is not configured to rerun on material canonical drift.")
    if any(loki.get(key) is not True for key in (
        "mirror_remains_synthetic",
        "mirror_may_not_become_evidence",
        "mirror_may_not_mint_authority",
        "mirror_may_not_execute",
    )):
        blockers.append("Loki synthetic containment law is incomplete.")
    if notification.get("automatic_external_notification") is not False:
        blockers.append("Continuous Assurance must not enable automatic external notification.")

    receipt = {
        "schema": "dio.fusion.wave8.receipt.v1",
        "state": "FUSION_WAVE8_READY" if not blockers else "BLOCKED",
        "depends_on": {
            "fusion_wave7_receipt": str(previous_path),
            "fusion_wave7_state": previous.get("state"),
        },
        "twin_layers_watched": len(watch_layers),
        "critical_categories": len(config.get("critical_categories") or []),
        "event_driven_watcher_contract": (core / "assurance" / "watcher.py").is_file(),
        "loki_rerun_on_material_drift": loki.get("rerun_on_material_drift") is True,
        "operator_attention_receipts": notification.get("emit_operator_attention_receipt") is True,
        "automatic_external_notifications": 0 if notification.get("automatic_external_notification") is False else 1,
        "continuous_assurance_authority": False,
        "continuous_assurance_execution": False,
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
