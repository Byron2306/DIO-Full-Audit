#!/usr/bin/env python3
"""Operator controls for Arda's BPF enforcement maps."""

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.os_enforcement_service import OsEnforcementService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Control Arda BPF enforcement posture")
    parser.add_argument("--enable", action="store_true", help="Enable emergency deny-all lockdown")
    parser.add_argument("--disable", action="store_true", help="Disable emergency deny-all lockdown")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.enable == args.disable:
        parser.error("choose exactly one of --enable or --disable")

    service = OsEnforcementService()
    ok = service.set_emergency_lockdown(args.enable)
    status = service.get_status()
    payload = {
        "ok": ok,
        "requested_lockdown": "deny_all" if args.enable else "disabled",
        "lockdown_mode": status.get("lockdown_mode"),
        "arm_mode": status.get("arm_mode"),
        "is_authoritative": status.get("is_authoritative"),
        "is_simulation": status.get("is_simulation"),
        "last_error": status.get("last_error"),
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("ARDA BPF LOCKDOWN")
        print(f"ok: {payload['ok']}")
        print(f"requested_lockdown: {payload['requested_lockdown']}")
        print(f"lockdown_mode: {payload['lockdown_mode']}")
        print(f"arm_mode: {payload['arm_mode']}")
        print(f"is_authoritative: {payload['is_authoritative']}")
        print(f"is_simulation: {payload['is_simulation']}")
        print(f"last_error: {payload['last_error'] or '(none)'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
