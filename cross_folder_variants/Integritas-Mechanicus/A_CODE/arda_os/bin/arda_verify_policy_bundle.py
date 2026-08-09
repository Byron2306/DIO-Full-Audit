#!/usr/bin/env python3
"""
Verify and evaluate a compiled Arda policy bundle.
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
    evaluate_policy_bundle,
    load_and_verify_policy_bundle,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify and evaluate an Arda policy bundle")
    parser.add_argument("--bundle", default=POLICY_BUNDLE_PATH)
    parser.add_argument("--command", required=True)
    parser.add_argument("--principal", required=True)
    parser.add_argument("--lane", required=True)
    args = parser.parse_args()

    try:
        bundle = load_and_verify_policy_bundle(args.bundle)
        evaluation = evaluate_policy_bundle(
            bundle,
            command=args.command,
            principal=args.principal,
            lane=args.lane,
        )
    except Exception as error:
        print(f"ARDA_VERIFY_POLICY_BUNDLE: {error}", file=sys.stderr)
        return 1

    payload = {
        "cwd": os.getcwd(),
        "bundle_path": os.path.abspath(args.bundle),
        "request": {
            "command": args.command,
            "principal": args.principal,
            "lane": args.lane,
        },
        "evaluation": evaluation,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if evaluation["decision"] == "ALLOW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
