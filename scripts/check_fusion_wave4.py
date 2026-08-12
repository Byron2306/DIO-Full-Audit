#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
CORE_ROOT = HERE.parents[1]
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from authority.canonical import load_authority_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate DIO Fusion Wave 4 authority/execution readiness.")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--core", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    core = Path(args.core).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    blockers: list[dict[str, str]] = []

    wave3_path = workspace / "receipts" / "fusion-wave3-latest.json"
    try:
        wave3 = json.loads(wave3_path.read_text(encoding="utf-8"))
    except Exception as exc:
        blockers.append({"code": "FUSION_WAVE3_RECEIPT_INVALID", "message": str(exc)})
        wave3 = {}
    if wave3.get("state") != "FUSION_WAVE3_READY":
        blockers.append({
            "code": "FUSION_WAVE3_NOT_READY",
            "message": f"Expected FUSION_WAVE3_READY, got {wave3.get('state')!r}.",
        })

    required_files = [
        core / "authority" / "canonical.py",
        core / "config" / "dio_authority_plane.json",
        core / "schemas" / "dio_authority_plane.schema.json",
        core / "tests" / "test_authority_execution_plane.py",
    ]
    for path in required_files:
        if not path.is_file():
            blockers.append({"code": "AUTHORITY_PLANE_FILE_MISSING", "message": str(path)})

    try:
        config = load_authority_config(core / "config" / "dio_authority_plane.json")
    except Exception as exc:
        blockers.append({"code": "AUTHORITY_PLANE_CONFIG_INVALID", "message": str(exc)})
        config = {}

    if config:
        if config.get("kernel_authority") != "Valinor":
            blockers.append({"code": "KERNEL_AUTHORITY_DRIFT", "message": "Valinor is not the sole configured kernel authority."})
        if config.get("execution_identity_authority") != "ARDA":
            blockers.append({"code": "ARDA_ROLE_DRIFT", "message": "ARDA is not configured as execution identity authority."})
        laws = config.get("laws") or {}
        for law in (
            "evidence_is_not_authority",
            "framework_ready_is_not_authority",
            "legalis_allow_is_not_execution_authority",
            "valinor_authorization_is_not_external_execution",
            "arda_identity_is_not_kernel_authority",
            "capability_lease_is_not_self_authorizing",
            "execution_requires_durable_receipt",
        ):
            if laws.get(law) is not True:
                blockers.append({"code": "AUTHORITY_LAW_MISSING", "message": law})

    state = "FUSION_WAVE4_READY" if not blockers else "BLOCKED"
    receipt = {
        "state": state,
        "contracts": 5,
        "kernel_authority": "Valinor",
        "execution_identity_authority": "ARDA",
        "previous_receipt_state": wave3.get("state"),
        "blockers": blockers,
        "receipt": str(out),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if state == "FUSION_WAVE4_READY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
