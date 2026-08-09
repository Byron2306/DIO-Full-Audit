#!/usr/bin/env python3
"""
Capture fresh Phase 4 TPM/PCR evidence from the live host and optionally verify it.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.os_enforcement_service import OsEnforcementService  # noqa: E402
from backend.services.attestation_service import create_envelope  # noqa: E402

DEFAULT_MEASURED_MANIFEST_PATH = "/var/lib/arda/projection/measured-critical.json"
DEFAULT_ATTESTATION_ENVELOPE_PATH = "/var/lib/arda/attestation/latest/09_attestation_envelope.json"
DEFAULT_VERIFIER_URL = "http://127.0.0.1:8094/verify/phase4"
DEFAULT_VERIFIER_OUTPUT_PATH = "/var/lib/arda/verifier/latest-verdict.json"


def _read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _read_nonce(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _manifest_digest(manifest: dict) -> str:
    body = {
        "schema_version": manifest.get("schema_version"),
        "manifest_id": manifest.get("manifest_id"),
        "generation": manifest.get("generation"),
        "node_id": manifest.get("node_id"),
        "policy_generation": manifest.get("policy_generation"),
        "audience": manifest.get("audience"),
        "attestation_result_id": manifest.get("attestation_result_id"),
        "attestation_evidence_digest": manifest.get("attestation_evidence_digest"),
        "issued_at": manifest.get("issued_at"),
        "expires_at": manifest.get("expires_at"),
        "entries": manifest.get("entries"),
    }
    return "sha256:" + hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _resolve_active_bundle_path() -> str:
    preferred = os.environ.get("ARDA_ACTIVE_BUNDLE_PATH", "/etc/arda/policy/active_bundle.json")
    return preferred


def _resolve_default_refresh_targets(
    manifest_path: str | None,
    envelope_path: str | None,
    output_dir: str,
    service: OsEnforcementService | None = None,
) -> tuple[str | None, str | None]:
    if manifest_path and envelope_path:
        return manifest_path, envelope_path
    normalized_output_dir = os.path.abspath(output_dir)
    if normalized_output_dir != os.path.abspath("/var/lib/arda/attestation/latest"):
        return manifest_path, envelope_path
    resolved_manifest = manifest_path
    resolved_envelope = envelope_path
    if resolved_manifest is None:
        resolved_manifest = _resolve_active_manifest_path(service)
    if resolved_manifest is None and os.path.exists(DEFAULT_MEASURED_MANIFEST_PATH):
        resolved_manifest = DEFAULT_MEASURED_MANIFEST_PATH
    if resolved_envelope is None:
        resolved_envelope = DEFAULT_ATTESTATION_ENVELOPE_PATH
    return resolved_manifest, resolved_envelope


def _resolve_active_manifest_path(service: OsEnforcementService | None) -> str | None:
    if service is None:
        return None
    try:
        status = service.get_status()
    except Exception:
        return None
    active_records = (
        status.get("phase3_measured_identity", {})
        .get("required_maps", {})
        .get("active_records", [])
    )
    if not active_records:
        return None
    latest = max(active_records, key=lambda record: int(record.get("generation") or 0))
    manifest_id = str(latest.get("manifest_id") or "").strip()
    if not manifest_id:
        return None
    projection_dir = Path("/var/lib/arda/projection")
    candidates = [
        projection_dir / f"{manifest_id}.json",
        projection_dir / "measured-critical-v2.json",
        projection_dir / "measured-critical.json",
        projection_dir / "measured-root.json",
    ]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("manifest_id") == manifest_id:
            return str(candidate)
    return None


def _refresh_attestation_envelope(
    manifest_path: str,
    envelope_path: str,
    *,
    evidence_bundle_path: str | None = None,
) -> dict:
    manifest = _read_json(manifest_path)
    bundle_path = _resolve_active_bundle_path()
    bundle = _read_json(bundle_path)
    envelope = create_envelope(
        command="phase4_live_attestation",
        principal="root-host-phase4",
        token_id=manifest["manifest_id"],
        lane="gondor",
        policy_id=bundle["policy_id"],
        policy_version=bundle["policy_version"],
        verdict="ALLOW",
        artifact_digest=_manifest_digest(manifest),
        policy_verdict="ALLOW",
        evidence_bundle_path=evidence_bundle_path,
    )
    envelope_dir = os.path.dirname(os.path.abspath(envelope_path))
    if envelope_dir:
        os.makedirs(envelope_dir, exist_ok=True)
    with open(envelope_path, "w", encoding="utf-8") as handle:
        json.dump(envelope, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return {
        "path": os.path.abspath(envelope_path),
        "bundle_path": os.path.abspath(bundle_path),
        "manifest_id": manifest["manifest_id"],
        "signing_algorithm": envelope.get("signing_algorithm"),
        "trust_mode": envelope.get("trust_mode"),
    }


def _collect_harmonic_toolchain(service: OsEnforcementService) -> list[str]:
    tool_paths = []
    live_attestation = getattr(service, "_phase4_live_attestation", None)
    if live_attestation is not None:
        for tool in live_attestation.REQUIRED_TOOLS:
            resolved = shutil.which(tool)
            if resolved:
                tool_paths.append(resolved)
                real = os.path.realpath(resolved)
                if real not in tool_paths:
                    tool_paths.append(real)

    for path in (sys.executable, "/usr/bin/env", "/bin/bash"):
        if path and os.path.exists(path) and path not in tool_paths:
            tool_paths.append(path)
    return tool_paths


def _default_nonce() -> str:
    return hashlib.sha256(
        f"{os.getpid()}:{datetime.now(timezone.utc).isoformat()}".encode("utf-8")
    ).hexdigest()[:32]


def _write_json(path: str, payload: dict) -> None:
    target = Path(path)
    if target.parent:
        target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _post_to_verifier(
    verifier_url: str,
    *,
    manifest_path: str,
    attestation_envelope_path: str,
    evidence_bundle_path: str,
    pcr_baseline_path: str | None,
    require_verifier_nonce: bool,
    require_tpm_quote_verification: bool,
    allow_attested_only_boot: bool,
    allow_missing_boot_measurement_for_live_proof: bool,
) -> dict:
    request_payload = {
        "manifest_path": os.path.abspath(manifest_path),
        "attestation_envelope_path": os.path.abspath(attestation_envelope_path),
        "evidence_bundle_path": os.path.abspath(evidence_bundle_path),
        "pcr_baseline_path": os.path.abspath(pcr_baseline_path) if pcr_baseline_path else None,
        "require_verifier_nonce": require_verifier_nonce,
        "require_tpm_quote_verification": require_tpm_quote_verification,
        "allow_attested_only_boot": allow_attested_only_boot,
        "allow_missing_boot_measurement_for_live_proof": allow_missing_boot_measurement_for_live_proof,
    }
    body = json.dumps(request_payload).encode("utf-8")
    request = urllib.request.Request(
        verifier_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _signed_verdict_ready(payload: dict | None) -> bool:
    if not isinstance(payload, dict):
        return False
    signed_verdict = payload.get("signed_verdict")
    if not isinstance(signed_verdict, dict):
        return False
    verifier = payload.get("verifier") or {}
    return bool(verifier.get("signed_verdicts_enabled"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture live Arda Phase 4 TPM/PCR evidence")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--nonce")
    parser.add_argument("--nonce-file")
    parser.add_argument("--manifest")
    parser.add_argument("--attestation-envelope")
    parser.add_argument("--cloud-witness")
    parser.add_argument("--pcr-baseline")
    parser.add_argument("--verifier-url", default=os.environ.get("ARDA_VERIFIER_URL"))
    parser.add_argument("--verifier-output", default=os.environ.get("ARDA_VERIFIER_OUTPUT", DEFAULT_VERIFIER_OUTPUT_PATH))
    parser.add_argument(
        "--allow-unsigned-verifier-response",
        action="store_true",
        help="Accept a verifier response that does not contain a signed verdict",
    )
    parser.add_argument(
        "--verify-gate",
        action="store_true",
        help="After capture, run the Phase 4 gate against the fresh local evidence",
    )
    parser.add_argument(
        "--require-tpm-quote-verification",
        action="store_true",
        help="Require cryptographic verification of the captured TPM quote",
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
    parser.add_argument(
        "--skip-harmonize-toolchain",
        action="store_true",
        help="Do not seed the TPM toolchain as harmonic before capture",
    )
    args = parser.parse_args()

    if args.nonce and args.nonce_file:
        print(
            "ARDA_PHASE4_LIVE_ATTESTATION: use either --nonce or --nonce-file, not both",
            file=sys.stderr,
        )
        return 1

    if args.verify_gate and (not args.manifest or not args.attestation_envelope):
        print(
            "ARDA_PHASE4_LIVE_ATTESTATION: --verify-gate requires --manifest and --attestation-envelope",
            file=sys.stderr,
        )
        return 1

    os.environ.setdefault("ARDA_ENFORCEMENT_MODE", "audit")
    verifier_nonce = args.nonce or (_read_nonce(args.nonce_file) if args.nonce_file else None)
    if args.verifier_url and not verifier_nonce:
        verifier_nonce = _default_nonce()
    if verifier_nonce:
        os.environ["ARDA_VERIFIER_NONCE"] = verifier_nonce

    service = OsEnforcementService()
    try:
        try:
            harmonized_paths = []
            harmonize_result = None
            if not args.skip_harmonize_toolchain and service.is_authoritative:
                harmonized_paths = _collect_harmonic_toolchain(service)
                if harmonized_paths:
                    harmonize_result = service.project_pinned_policy(
                        harmonic_paths=harmonized_paths,
                        enforcement_mode=service.enforcement_mode,
                    )
            capture = service.capture_phase4_live_attestation(args.output_dir, nonce=verifier_nonce)
            refreshed_envelope = None
            manifest_path, envelope_path = _resolve_default_refresh_targets(
                args.manifest,
                args.attestation_envelope,
                args.output_dir,
                service,
            )
            if manifest_path and envelope_path:
                refreshed_envelope = _refresh_attestation_envelope(
                    manifest_path,
                    envelope_path,
                    evidence_bundle_path=capture["bundle_path"],
                )
            gate = None
            verifier_result = None
            if args.verify_gate:
                os.environ["ARDA_PHASE4_CAPTURE_DIR"] = capture["evidence_dir"]
                if not manifest_path or not envelope_path:
                    print(
                        "ARDA_PHASE4_LIVE_ATTESTATION: --verify-gate requires a manifest and attestation envelope path",
                        file=sys.stderr,
                    )
                    return 1
                manifest = _read_json(manifest_path)
                attestation_envelope = _read_json(envelope_path)
                cloud_witness = _read_json(args.cloud_witness) if args.cloud_witness else None
                pcr_baseline = _read_json(args.pcr_baseline) if args.pcr_baseline else None
                gate = service.evaluate_phase4_attestation_gate(
                    manifest,
                    attestation_envelope,
                    cloud_witness,
                    capture["bundle"],
                    pcr_baseline,
                    args.require_tpm_quote_verification,
                    args.allow_attested_only_boot,
                    args.allow_missing_boot_measurement_for_live_proof,
                    bool(verifier_nonce),
                    False,
                )
            if args.verifier_url:
                if not manifest_path or not envelope_path:
                    print(
                        "ARDA_PHASE4_LIVE_ATTESTATION: verifier upload requires a resolved manifest and attestation envelope path",
                        file=sys.stderr,
                    )
                    return 1
                try:
                    verifier_result = _post_to_verifier(
                        args.verifier_url,
                        manifest_path=manifest_path,
                        attestation_envelope_path=envelope_path,
                        evidence_bundle_path=capture["bundle_path"],
                        pcr_baseline_path=args.pcr_baseline,
                        require_verifier_nonce=bool(verifier_nonce),
                        require_tpm_quote_verification=args.require_tpm_quote_verification,
                        allow_attested_only_boot=args.allow_attested_only_boot,
                        allow_missing_boot_measurement_for_live_proof=args.allow_missing_boot_measurement_for_live_proof,
                    )
                except urllib.error.URLError as error:
                    print(f"ARDA_PHASE4_LIVE_ATTESTATION: verifier service unavailable: {error}", file=sys.stderr)
                    return 1
                except Exception as error:
                    print(f"ARDA_PHASE4_LIVE_ATTESTATION: verifier request failed: {error}", file=sys.stderr)
                    return 1
                if args.verifier_output:
                    _write_json(args.verifier_output, verifier_result)
                if not args.allow_unsigned_verifier_response and not _signed_verdict_ready(verifier_result):
                    print(
                        "ARDA_PHASE4_LIVE_ATTESTATION: verifier response missing signed verdict",
                        file=sys.stderr,
                    )
                    return 1
        except Exception as error:
            print(f"ARDA_PHASE4_LIVE_ATTESTATION: {error}", file=sys.stderr)
            return 1

        payload = {
            "cwd": os.getcwd(),
            "output_dir": os.path.abspath(args.output_dir),
            "manifest_path": os.path.abspath(manifest_path) if manifest_path else None,
            "attestation_envelope_path": os.path.abspath(envelope_path) if envelope_path else None,
            "cloud_witness_path": os.path.abspath(args.cloud_witness) if args.cloud_witness else None,
            "pcr_baseline_path": os.path.abspath(args.pcr_baseline) if args.pcr_baseline else None,
            "verify_gate": args.verify_gate,
            "nonce_file": os.path.abspath(args.nonce_file) if args.nonce_file else None,
            "nonce_generated": bool(args.verifier_url and not args.nonce and not args.nonce_file),
            "verifier_nonce_present": bool(verifier_nonce),
            "verifier_url": args.verifier_url,
            "verifier_output": os.path.abspath(args.verifier_output) if args.verifier_output else None,
            "require_tpm_quote_verification": args.require_tpm_quote_verification,
            "allow_attested_only_boot": args.allow_attested_only_boot,
            "allow_missing_boot_measurement_for_live_proof": args.allow_missing_boot_measurement_for_live_proof,
            "harmonized_toolchain_paths": harmonized_paths,
            "harmonize_result": harmonize_result,
            "refreshed_attestation_envelope": refreshed_envelope,
            "verifier_result": verifier_result,
            "status": service.get_status(),
            "capture": capture,
            "gate": gate,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if gate is None or gate.get("ok") else 1
    finally:
        os.environ.pop("ARDA_VERIFIER_NONCE", None)
        service.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
