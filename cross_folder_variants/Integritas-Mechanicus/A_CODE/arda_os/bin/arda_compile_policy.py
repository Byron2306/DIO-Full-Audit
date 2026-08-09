#!/usr/bin/env python3
"""
Compile a verified Arda policy document into a signed Phase 5 law bundle.
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
    POLICY_PATH,
    generate_policy_bundle,
    load_and_verify_policy_bundle,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile Arda policy into a signed law bundle")
    parser.add_argument("--policy", default=POLICY_PATH)
    parser.add_argument("--output", default=POLICY_BUNDLE_PATH)
    parser.add_argument(
        "--verify-after",
        action="store_true",
        help="Verify the compiled bundle after writing it",
    )
    args = parser.parse_args()

    try:
        bundle = generate_policy_bundle(args.policy, args.output)
        verified = load_and_verify_policy_bundle(args.output) if args.verify_after else None
    except Exception as error:
        print(f"ARDA_COMPILE_POLICY: {error}", file=sys.stderr)
        return 1

    payload = {
        "cwd": os.getcwd(),
        "policy_path": os.path.abspath(args.policy),
        "output_path": os.path.abspath(args.output),
        "bundle": bundle,
        "verified": verified is not None,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
