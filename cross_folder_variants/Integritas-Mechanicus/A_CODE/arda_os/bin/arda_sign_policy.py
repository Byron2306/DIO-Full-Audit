#!/usr/bin/env python3
"""Explicitly sign an Arda policy document with the configured policy key."""

import argparse
import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.policy_engine import POLICY_PATH, _canonical_bytes, _sign, load_and_verify_policy  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Sign an Arda policy document")
    parser.add_argument("--policy", default=POLICY_PATH)
    parser.add_argument("--verify-after", action="store_true")
    args = parser.parse_args()

    with open(args.policy, "r", encoding="utf-8") as handle:
        policy = json.load(handle)

    policy["signature"] = _sign(_canonical_bytes(policy))
    with open(args.policy, "w", encoding="utf-8") as handle:
        json.dump(policy, handle, indent=2, sort_keys=True)
        handle.write("\n")

    verified = False
    if args.verify_after:
        load_and_verify_policy(args.policy)
        verified = True

    print(
        json.dumps(
            {
                "ok": True,
                "policy": os.path.abspath(args.policy),
                "policy_id": policy.get("policy_id"),
                "version": policy.get("version"),
                "signature": policy["signature"],
                "verified": verified,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
