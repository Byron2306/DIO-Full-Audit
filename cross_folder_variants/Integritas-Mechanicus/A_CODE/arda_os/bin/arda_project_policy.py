#!/usr/bin/env python3
"""
Project Phase 2 pinned-state policy into Arda's canonical bpffs contract.

This tool is intended for authoritative contexts where the canonical loader path
 is already armed and `/sys/fs/bpf/arda` is present.
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
    parser = argparse.ArgumentParser(description="Project pinned harmony/state policy into Arda's bpffs contract")
    parser.add_argument("--path", action="append", default=[], help="Executable path to seed as harmonic")
    parser.add_argument(
        "--projection-plan",
        help="Path to a compiled Phase 5 projection plan JSON file",
    )
    parser.add_argument(
        "--no-default-seed",
        action="store_true",
        help="Do not seed Arda's conservative default lawful executable set",
    )
    parser.add_argument(
        "--seed-running-processes",
        action="store_true",
        help="Also seed currently running executable identities from /proc/*/exe",
    )
    parser.add_argument(
        "--max-running-processes",
        type=int,
        default=64,
        help="Maximum number of running processes to seed when --seed-running-processes is used",
    )
    parser.add_argument(
        "--enforcement-mode",
        choices=["audit", "legacy_inode", "fsverity_strict"],
        default="audit",
        help="Enforcement mode to project into arda_state_map",
    )
    parser.add_argument(
        "--verify-native-denial-after",
        action="store_true",
        help="Run Arda's native denial self-test after projection completes",
    )
    args = parser.parse_args()

    service = OsEnforcementService()
    try:
        try:
            harmonic_paths = list(args.path)
            projection_plan = _read_json(args.projection_plan) if args.projection_plan else None
            if projection_plan is not None:
                harmonic_paths = list(projection_plan.get("targets", {}).get("harmony_allow_paths", []))
                if "enforcement_mode" in projection_plan.get("targets", {}):
                    args.enforcement_mode = projection_plan["targets"]["enforcement_mode"]
            if not args.no_default_seed and projection_plan is None:
                for path in service.DEFAULT_PROJECTION_SEED_PATHS:
                    if path not in harmonic_paths:
                        harmonic_paths.append(path)
            result = service.project_pinned_policy(
                harmonic_paths=harmonic_paths,
                enforcement_mode=args.enforcement_mode,
                constitutional_state=projection_plan.get("targets", {}).get("constitutional_state") if projection_plan else None,
                seed_running_processes=args.seed_running_processes,
                max_running_processes=args.max_running_processes,
                verify_native_denial_after=args.verify_native_denial_after,
            )
        except Exception as error:
            print(f"ARDA_PROJECT: {error}", file=sys.stderr)
            return 1
        payload = {
            "cwd": os.getcwd(),
            "projection_plan_path": os.path.abspath(args.projection_plan) if args.projection_plan else None,
            "requested_paths": harmonic_paths,
            "used_default_seed_paths": not args.no_default_seed,
            "status": service.get_status(),
            "projection": result,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    finally:
        service.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
