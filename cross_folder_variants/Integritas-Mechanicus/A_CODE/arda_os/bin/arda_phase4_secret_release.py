#!/usr/bin/env python3
"""
Release high-authority Phase 4 material only after attestation gate success.
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
    parser = argparse.ArgumentParser(description="Release Arda Phase 4 secret material")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--attestation-envelope", required=True)
    parser.add_argument("--purpose", required=True, choices=["policy_signing", "attestation_signing", "loader_authority"])
    parser.add_argument("--requester", required=True)
    parser.add_argument("--cloud-witness")
    parser.add_argument("--local-evidence")
    parser.add_argument("--pcr-baseline")
    parser.add_argument(
        "--require-tpm-quote-verification",
        action="store_true",
        help="Require cryptographic verification of the TPM quote via tpm2_checkquote",
    )
    parser.add_argument(
        "--allow-attested-only-boot",
        action="store_true",
        help="Allow ATTESTED_ONLY live proof bundles during Phase 4 proof runs",
    )
    parser.add_argument(
        "--allow-missing-boot-measurement-for-live-proof",
        action="store_true",
        help="Allow missing software boot measurement if verified live TPM proof is present",
    )
    args = parser.parse_args()

    service = OsEnforcementService()
    try:
        try:
            manifest = _read_json(args.manifest)
            attestation_envelope = _read_json(args.attestation_envelope)
            cloud_witness = _read_json(args.cloud_witness) if args.cloud_witness else None
            local_evidence = _read_json(args.local_evidence) if args.local_evidence else None
            pcr_baseline = _read_json(args.pcr_baseline) if args.pcr_baseline else None
            gate = service.evaluate_phase4_attestation_gate(
                manifest,
                attestation_envelope,
                cloud_witness,
                local_evidence,
                pcr_baseline,
                args.require_tpm_quote_verification,
                args.allow_attested_only_boot,
                args.allow_missing_boot_measurement_for_live_proof,
            )
            result = service.release_phase4_secret(
                args.purpose,
                gate,
                requester=args.requester,
            )
        except Exception as error:
            print(f"ARDA_PHASE4_SECRET_RELEASE: {error}", file=sys.stderr)
            return 1

        payload = {
            "cwd": os.getcwd(),
            "manifest_path": os.path.abspath(args.manifest),
            "attestation_envelope_path": os.path.abspath(args.attestation_envelope),
            "cloud_witness_path": os.path.abspath(args.cloud_witness) if args.cloud_witness else None,
            "local_evidence_path": os.path.abspath(args.local_evidence) if args.local_evidence else None,
            "pcr_baseline_path": os.path.abspath(args.pcr_baseline) if args.pcr_baseline else None,
            "require_tpm_quote_verification": args.require_tpm_quote_verification,
            "allow_attested_only_boot": args.allow_attested_only_boot,
            "allow_missing_boot_measurement_for_live_proof": args.allow_missing_boot_measurement_for_live_proof,
            "purpose": args.purpose,
            "requester": args.requester,
            "status": service.get_status(),
            "gate": gate,
            "release": result,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    finally:
        service.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
