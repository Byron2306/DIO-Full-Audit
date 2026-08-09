#!/usr/bin/env python3
"""
Compile a Phase 5 policy bundle into a kernel projection plan.
"""

import argparse
import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.policy_compiler import (  # noqa: E402
    POLICY_BUNDLE_PATH,
    compile_projection_plan,
    load_and_verify_policy_bundle,
)
from backend.services.measured_policy_profiles import expand_projection_profile  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile Arda policy bundle into a projection plan")
    parser.add_argument("--bundle", default=POLICY_BUNDLE_PATH)
    parser.add_argument("--path", action="append", default=[], help="Executable path to allow in harmony projection")
    parser.add_argument("--profile", choices=["critical-host"], action="append", default=[])
    parser.add_argument(
        "--enforcement-mode",
        choices=["audit", "legacy_inode", "fsverity_strict"],
        default="audit",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    try:
        bundle = load_and_verify_policy_bundle(args.bundle)
        executable_paths = list(args.path)
        for profile in args.profile:
            executable_paths = expand_projection_profile(profile, base_paths=executable_paths)
        plan = compile_projection_plan(
            bundle,
            executable_paths=executable_paths,
            enforcement_mode=args.enforcement_mode,
        )
        output_path = os.path.abspath(args.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(plan, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except Exception as error:
        print(f"ARDA_COMPILE_PROJECTION: {error}", file=sys.stderr)
        return 1

    payload = {
        "cwd": os.getcwd(),
        "bundle_path": os.path.abspath(args.bundle),
        "output_path": output_path,
        "plan": plan,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
