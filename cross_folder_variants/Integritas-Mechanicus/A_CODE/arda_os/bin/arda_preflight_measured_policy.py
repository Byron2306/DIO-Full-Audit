#!/usr/bin/env python3
"""
Preflight Arda Phase 3 measured-identity manifests without touching live kernel state.
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
    parser = argparse.ArgumentParser(description="Preflight a measured-identity manifest for Arda Phase 3")
    parser.add_argument("--manifest", required=True, help="Path to the measured manifest JSON file")
    parser.add_argument("--attestation", help="Optional path to attestation-result JSON")
    parser.add_argument(
        "--commit-generation",
        action="store_true",
        help="Commit the manifest generation to the local monotonic store if preflight succeeds",
    )
    parser.add_argument("--json", action="store_true", help="Accepted for consistency; output is always JSON")
    args = parser.parse_args()

    service = OsEnforcementService(arm=False)
    try:
        try:
            manifest = _read_json(args.manifest)
            attestation = _read_json(args.attestation) if args.attestation else None
            result = service.preflight_measured_manifest(
                manifest,
                attestation,
                commit_generation=args.commit_generation,
            )
        except Exception as error:
            print(f"ARDA_PREFLIGHT: {error}", file=sys.stderr)
            return 1

        payload = {
            "cwd": os.getcwd(),
            "manifest_path": os.path.abspath(args.manifest),
            "attestation_path": os.path.abspath(args.attestation) if args.attestation else None,
            "status": service.get_status(),
            "preflight": result,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if result.get("ok") else 1
    finally:
        service.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
