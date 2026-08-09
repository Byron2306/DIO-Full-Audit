#!/usr/bin/env python3
"""
Single-process Phase 1 root probe.

This avoids a second interpreter exec after the loader is already armed.
The sequence is:
1. instantiate the enforcement service
2. report status
3. run the native denial self-test from the same Python process
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


ARDA_ROOT = Path(__file__).resolve().parents[1]
if str(ARDA_ROOT) not in sys.path:
    sys.path.insert(0, str(ARDA_ROOT))

from backend.services.os_enforcement_service import OsEnforcementService  # noqa: E402


def main():
    service = OsEnforcementService()
    try:
        status = service.get_status()
        required_maps = status.get("required_maps", {})
        required_map_entries = required_maps.get("maps", {})
        native_denial_test = service.run_native_denial_self_test()
        missing_required_maps = [
            map_name
            for map_name, map_info in required_map_entries.items()
            if map_info.get("required") and not map_info.get("present")
        ]
        proof_checks = {
            "authoritative": bool(status.get("is_authoritative")),
            "attach_verified": bool(status.get("attach_verified")),
            "required_map_contract_ready": bool(required_maps.get("all_required_present")),
            "native_denial_observed": bool(native_denial_test.get("ok")),
        }
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cwd": os.getcwd(),
            "status": status,
            "native_denial_test": native_denial_test,
            "phase2_map_contract_proof": {
                "ok": all(proof_checks.values()),
                "checks": proof_checks,
                "required_map_count": len(required_map_entries),
                "missing_required_maps": missing_required_maps,
                "expected_pin_paths": {
                    map_name: map_info.get("pin_path")
                    for map_name, map_info in required_map_entries.items()
                },
            },
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload["phase2_map_contract_proof"]["ok"] else 1
    finally:
        service.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
