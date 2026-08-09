#!/usr/bin/env python3
"""Offline-style verifier for ARDA Phase 4 evidence produced on another host."""

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


def _read_evidence_bundle(path: str) -> dict:
    bundle = _read_json(path)
    evidence_path = Path(path)
    sidecar_path = evidence_path.parent / "08_quote_verification.json"
    if "quote_verification" not in bundle and sidecar_path.is_file():
        try:
            bundle["quote_verification"] = _read_json(str(sidecar_path))
        except Exception:
            pass
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify ARDA Phase 4 evidence off-box")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--attestation-envelope", required=True)
    parser.add_argument("--evidence-bundle", required=True)
    parser.add_argument("--pcr-baseline")
    parser.add_argument("--require-sigstore", action="store_true")
    parser.add_argument("--require-verifier-nonce", action="store_true")
    parser.add_argument("--require-tpm-quote-verification", action="store_true")
    args = parser.parse_args()

    service = OsEnforcementService(arm=False)
    try:
        try:
            manifest = _read_json(args.manifest)
            envelope = _read_json(args.attestation_envelope)
            local_evidence = _read_evidence_bundle(args.evidence_bundle)
            pcr_baseline = _read_json(args.pcr_baseline) if args.pcr_baseline else None
            result = service.evaluate_phase4_attestation_gate(
                manifest,
                envelope,
                None,
                local_evidence,
                pcr_baseline,
                args.require_tpm_quote_verification,
                False,
                False,
                args.require_verifier_nonce,
                args.require_sigstore,
            )
        except Exception as error:
            print(f"ARDA_PHASE4_REMOTE_VERIFY: {error}", file=sys.stderr)
            return 1

        payload = {
            "cwd": os.getcwd(),
            "mode": "remote_verifier",
            "manifest_path": os.path.abspath(args.manifest),
            "attestation_envelope_path": os.path.abspath(args.attestation_envelope),
            "evidence_bundle_path": os.path.abspath(args.evidence_bundle),
            "pcr_baseline_path": os.path.abspath(args.pcr_baseline) if args.pcr_baseline else None,
            "require_sigstore": args.require_sigstore,
            "require_verifier_nonce": args.require_verifier_nonce,
            "require_tpm_quote_verification": args.require_tpm_quote_verification,
            "trust_summary": {
                "local_attestation_passed": result.get("local_attestation_passed"),
                "externally_verifiable_attestation": result.get("externally_verifiable_attestation"),
                "production_ready": result.get("production_ready"),
                "attestation_envelope": {
                    "algorithm": result.get("attestation_envelope_trust", {}).get("algorithm"),
                    "verification_mode": result.get("attestation_envelope_trust", {}).get("verification_mode"),
                    "externally_verifiable": result.get("attestation_envelope_trust", {}).get("externally_verifiable"),
                    "transparency_integrated": result.get("attestation_envelope_trust", {}).get("transparency_integrated"),
                    "trust_mode": result.get("attestation_envelope_trust", {}).get("trust_mode"),
                },
                "tpm_identity": result.get("local_evidence", {}).get("tpm_identity"),
            },
            "gate": result,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if result.get("ok") else 1
    finally:
        service.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
