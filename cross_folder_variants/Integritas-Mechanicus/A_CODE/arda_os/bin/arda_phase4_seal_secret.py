#!/usr/bin/env python3
"""
Create a sealed Phase 4 secret bundle for Arda authority release.
"""

import argparse
import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.phase4_secret_release import Phase4SecretReleaseService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Seal an Arda Phase 4 secret bundle")
    parser.add_argument("--purpose", required=True, choices=["policy_signing", "attestation_signing", "loader_authority"])
    parser.add_argument("--manifest-id", required=True)
    parser.add_argument("--manifest-digest", required=True)
    parser.add_argument("--secret-value")
    parser.add_argument("--secret-file")
    parser.add_argument("--output", required=True)
    parser.add_argument("--key-id", default="phase4-default")
    args = parser.parse_args()

    if bool(args.secret_value) == bool(args.secret_file):
        print("ARDA_PHASE4_SEAL_SECRET: provide exactly one of --secret-value or --secret-file", file=sys.stderr)
        return 1

    seal_key = os.getenv(Phase4SecretReleaseService.SEAL_KEY_ENV)
    if not seal_key:
        print(
            f"ARDA_PHASE4_SEAL_SECRET: missing {Phase4SecretReleaseService.SEAL_KEY_ENV}",
            file=sys.stderr,
        )
        return 1

    if args.secret_file:
        with open(args.secret_file, "r", encoding="utf-8") as handle:
            secret_value = handle.read().strip()
    else:
        secret_value = args.secret_value.strip()

    bundle = Phase4SecretReleaseService.build_sealed_bundle(
        purpose=args.purpose,
        manifest_id=args.manifest_id,
        manifest_digest=args.manifest_digest,
        secret_value=secret_value,
        seal_key=seal_key,
        key_id=args.key_id,
    )

    output_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(bundle, handle, indent=2, sort_keys=True)
        handle.write("\n")

    payload = {
        "ok": True,
        "purpose": args.purpose,
        "manifest_id": args.manifest_id,
        "manifest_digest": args.manifest_digest,
        "output": output_path,
        "sealed_bundle_env": Phase4SecretReleaseService.SECRET_BUNDLE_ENV_MAP[args.purpose],
        "seal_key_env": Phase4SecretReleaseService.SEAL_KEY_ENV,
        "secret_fingerprint": bundle["secret_fingerprint"],
        "key_id": bundle["key_id"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
