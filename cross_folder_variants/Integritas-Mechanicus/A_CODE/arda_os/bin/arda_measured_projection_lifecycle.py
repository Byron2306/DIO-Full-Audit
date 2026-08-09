#!/usr/bin/env python3
"""
Operate the local Phase 3 measured-projection lifecycle without claiming live kernel activation.
"""

import argparse
import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.os_enforcement_service import OsEnforcementService  # noqa: E402


def _read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Arda Phase 3 measured projection lifecycle")
    subparsers = parser.add_subparsers(dest="command", required=True)

    stage_parser = subparsers.add_parser("stage", help="Preflight and stage a measured manifest locally")
    stage_parser.add_argument("--manifest", required=True)
    stage_parser.add_argument("--attestation")

    activate_parser = subparsers.add_parser("activate", help="Activate a previously staged manifest locally")
    activate_parser.add_argument("--manifest-id", required=True)

    deactivate_parser = subparsers.add_parser("deactivate", help="Deactivate a staged or active manifest locally")
    deactivate_parser.add_argument("--manifest-id", required=True)
    deactivate_parser.add_argument("--reason", required=True)

    remove_parser = subparsers.add_parser("remove", help="Mark a staged manifest removed locally")
    remove_parser.add_argument("--manifest-id", required=True)

    project_parser = subparsers.add_parser("project", help="Project a staged measured manifest into pinned Phase 3 maps")
    project_parser.add_argument("--manifest-id", required=True)

    unproject_parser = subparsers.add_parser("unproject", help="Remove a measured manifest from pinned Phase 3 maps")
    unproject_parser.add_argument("--manifest-id", required=True)

    args = parser.parse_args()

    # Lifecycle operations can operate through pinned maps. Re-arming the loader
    # here would reset state/policy maps and make a status command destructive.
    service = OsEnforcementService(arm=False)
    try:
        try:
            if args.command == "stage":
                manifest = _read_json(args.manifest)
                attestation = _read_json(args.attestation) if args.attestation else None
                result = service.stage_measured_manifest(manifest, attestation)
            elif args.command == "activate":
                result = service.activate_staged_measured_manifest(args.manifest_id)
            elif args.command == "deactivate":
                result = service.deactivate_staged_measured_manifest(args.manifest_id, args.reason)
            elif args.command == "project":
                result = service.project_staged_measured_manifest(args.manifest_id)
            elif args.command == "unproject":
                result = service.unproject_staged_measured_manifest(args.manifest_id)
            else:
                result = service.remove_staged_measured_manifest(args.manifest_id)
        except Exception as error:
            print(f"ARDA_MEASURED_LIFECYCLE: {error}", file=sys.stderr)
            return 1

        payload = {
            "cwd": os.getcwd(),
            "command": args.command,
            "status": service.get_status(),
            "result": result,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    finally:
        service.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
