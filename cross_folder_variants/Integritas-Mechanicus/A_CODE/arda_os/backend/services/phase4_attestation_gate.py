import hashlib
import json
import base64
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from backend.services.attestation_service import get_envelope_trust_report, verify_envelope


class Phase4AttestationError(RuntimeError):
    """Raised when Phase 4 attestation truth is insufficient for release."""


def _parse_utc(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _canonical_json_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _normalize_pcr_map(values: Dict[str, Any]) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    for key, value in (values or {}).items():
        normalized[str(key)] = str(value).lower()
    return normalized


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


class Phase4AttestationGate:
    """
    Phase 4 release gate for measured projection.

    This gate does not replace kernel authority; it constrains when measured
    manifests should be considered releasable by userspace policy.
    """

    AUDIENCE = "arda-phase4-attestation-gate"
    ACCEPTED_BOOT_STATES = {"LAWFUL", "LAWFUL_PARTIAL", "LAWFUL_FULL"}
    ACCEPTED_PROOF_BOOT_STATES = {"LAWFUL", "LAWFUL_PARTIAL", "LAWFUL_FULL", "ATTESTED_ONLY"}

    def evaluate(
        self,
        manifest: Dict[str, Any],
        attestation_envelope: Dict[str, Any],
        cloud_witness: Optional[Dict[str, Any]] = None,
        local_evidence: Optional[Dict[str, Any]] = None,
        pcr_baseline: Optional[Dict[str, Any]] = None,
        require_tpm_quote_verification: bool = False,
        allow_attested_only_boot: bool = False,
        allow_missing_boot_measurement_for_live_proof: bool = False,
        require_verifier_nonce: bool = False,
        require_nonlocal_attestation_signature: bool = False,
        *,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        failures = []
        envelope_trust = get_envelope_trust_report(attestation_envelope)

        if not envelope_trust.get("verified"):
            failures.append("attestation_envelope_signature")
        if require_nonlocal_attestation_signature:
            signing_algorithm = str(attestation_envelope.get("signing_algorithm") or "")
            if "sigstore" not in signing_algorithm.lower():
                failures.append("attestation_envelope_nonlocal_signature_required")
            elif not envelope_trust.get("externally_verifiable"):
                failures.append("attestation_envelope_nonlocal_signature_unverifiable")

        payload = attestation_envelope.get("payload", {})
        boot_context = payload.get("boot_context", {})
        boot_measurement_missing = boot_context.get("source") == "measurement_failed" or boot_context.get("error")
        if boot_measurement_missing:
            failures.append("boot_measurement_missing")

        timestamp_text = payload.get("timestamp")
        try:
            envelope_time = _parse_utc(timestamp_text)
            if (current_time - envelope_time).total_seconds() > 600:
                failures.append("attestation_envelope_stale")
        except Exception:
            failures.append("attestation_envelope_timestamp")

        manifest_digest = "sha256:" + hashlib.sha256(
            _canonical_json_bytes(
                {
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
            )
        ).hexdigest()

        expected_artifact_digest = payload.get("artifact_digest")
        if expected_artifact_digest and expected_artifact_digest != manifest_digest:
            failures.append("manifest_digest_binding")

        if cloud_witness is not None:
            if cloud_witness.get("status") != "ATTESTED":
                failures.append("cloud_witness_status")
            claim = cloud_witness.get("claim", {})
            if claim.get("hash") != manifest_digest:
                failures.append("cloud_witness_manifest_binding")
            if not cloud_witness.get("cloud_proof"):
                failures.append("cloud_witness_proof")

        local_evidence_summary = None
        if local_evidence is not None:
            local_evidence_summary, local_failures = self._evaluate_local_evidence(
                local_evidence,
                pcr_baseline,
                require_tpm_quote_verification=require_tpm_quote_verification,
                allow_attested_only_boot=allow_attested_only_boot,
                require_verifier_nonce=require_verifier_nonce,
            )
            failures.extend(local_failures)
            if (
                allow_missing_boot_measurement_for_live_proof
                and boot_measurement_missing
                and local_evidence_summary.get("tpm_quote_verification", {}).get("ok")
            ):
                failures = [failure for failure in failures if failure != "boot_measurement_missing"]

        ok = not failures
        local_attestation_passed = ok
        externally_verifiable_attestation = bool(
            envelope_trust.get("externally_verifiable")
            and envelope_trust.get("verified")
        )
        production_ready = bool(
            ok
            and externally_verifiable_attestation
            and not (allow_attested_only_boot or allow_missing_boot_measurement_for_live_proof)
        )

        return {
            "ok": ok,
            "timestamp": current_time.isoformat(),
            "audience": self.AUDIENCE,
            "manifest_id": manifest.get("manifest_id"),
            "manifest_digest": manifest_digest,
            "attestation_timestamp": timestamp_text,
            "attestation_envelope_trust": envelope_trust,
            "cloud_witness_attached": cloud_witness is not None,
            "local_evidence_attached": local_evidence is not None,
            "local_evidence": local_evidence_summary,
            "proof_mode": {
                "allow_attested_only_boot": allow_attested_only_boot,
                "allow_missing_boot_measurement_for_live_proof": allow_missing_boot_measurement_for_live_proof,
                "require_verifier_nonce": require_verifier_nonce,
                "require_nonlocal_attestation_signature": require_nonlocal_attestation_signature,
                "active": bool(allow_attested_only_boot or allow_missing_boot_measurement_for_live_proof),
            },
            "local_attestation_passed": local_attestation_passed,
            "externally_verifiable_attestation": externally_verifiable_attestation,
            "production_ready": production_ready,
            "failures": failures,
        }

    def _evaluate_local_evidence(
        self,
        local_evidence: Dict[str, Any],
        pcr_baseline: Optional[Dict[str, Any]],
        *,
        require_tpm_quote_verification: bool = False,
        allow_attested_only_boot: bool = False,
        require_verifier_nonce: bool = False,
    ) -> Tuple[Dict[str, Any], list]:
        failures = []
        tpm_quote = local_evidence.get("tpm_pcr_quote", {})
        pcr_values = _normalize_pcr_map(tpm_quote.get("pcr_values", {}))
        required_pcrs = ("0", "1", "7", "11")
        software_state_binding = local_evidence.get("software_state_binding", {})
        tpm_identity = local_evidence.get("tpm_identity", {})

        accepted_boot_states = self.ACCEPTED_PROOF_BOOT_STATES if allow_attested_only_boot else self.ACCEPTED_BOOT_STATES
        if local_evidence.get("boot_state") not in accepted_boot_states:
            failures.append("local_evidence_boot_state")
        boot_measurement = local_evidence.get("boot_measurement", {})
        if not isinstance(boot_measurement, dict) or not boot_measurement:
            failures.append("local_evidence_boot_measurement_missing")
        elif boot_measurement.get("classification") != local_evidence.get("boot_state"):
            failures.append("local_evidence_boot_measurement_mismatch")
        if tpm_quote.get("pcr_selection") != "sha256:0,1,7,11":
            failures.append("local_evidence_pcr_selection")
        if not tpm_quote.get("silicon_signed"):
            failures.append("local_evidence_not_silicon_signed")
        if not tpm_quote.get("quote_blob_b64"):
            failures.append("local_evidence_quote_missing")
        if not tpm_quote.get("signature_blob_b64"):
            failures.append("local_evidence_signature_missing")
        if require_verifier_nonce and tpm_quote.get("nonce_source") != "verifier_supplied":
            failures.append("local_evidence_verifier_nonce_required")
        if software_state_binding.get("available") and not software_state_binding.get("bound"):
            failures.append("local_evidence_software_state_unbound")
        if not software_state_binding.get("available"):
            failures.append("local_evidence_software_state_missing")
        if pcr_values.get("11") in (None, "", "0" * 64):
            failures.append("local_evidence_pcr11_zero")

        missing_pcrs = [pcr for pcr in required_pcrs if pcr not in pcr_values]
        if missing_pcrs:
            failures.append("local_evidence_pcr_missing")

        file_hashes = local_evidence.get("file_hashes", {})
        quote_blob_hash = None
        signature_blob_hash = None
        try:
            quote_blob_hash = hashlib.sha256(
                base64.b64decode(tpm_quote.get("quote_blob_b64", ""), validate=True)
            ).hexdigest()
        except Exception:
            failures.append("local_evidence_quote_blob_invalid")
        try:
            signature_blob_hash = hashlib.sha256(
                base64.b64decode(tpm_quote.get("signature_blob_b64", ""), validate=True)
            ).hexdigest()
        except Exception:
            failures.append("local_evidence_signature_blob_invalid")

        if quote_blob_hash and file_hashes.get("04_tpm_quote.bin") != quote_blob_hash:
            failures.append("local_evidence_quote_hash_mismatch")
        if signature_blob_hash and file_hashes.get("04_tpm_quote_sig.bin") != signature_blob_hash:
            failures.append("local_evidence_signature_hash_mismatch")

        expected_chain_hash = None
        if file_hashes:
            expected_chain_hash = hashlib.sha256(
                "".join(value for _, value in sorted(file_hashes.items())).encode("utf-8")
            ).hexdigest()
            if local_evidence.get("chain_hash") != expected_chain_hash:
                failures.append("local_evidence_chain_hash_mismatch")

        quote_verification = self._verify_tpm_quote(local_evidence)
        if require_tpm_quote_verification and not quote_verification["ok"]:
            failures.append("local_evidence_tpm_quote_verification")

        manufacturer = str(tpm_identity.get("manufacturer") or "unknown")
        identity_chain_mode = str(tpm_identity.get("identity_chain_mode") or "unknown")
        ek_certificate_present = bool(tpm_identity.get("ek_certificate_present"))
        ak_certified_by_ek = bool(tpm_identity.get("ak_certified_by_ek"))
        manufacturer_rooted = ek_certificate_present and ak_certified_by_ek
        baseline_pcrs = {}
        pcr_mismatches = {}
        if pcr_baseline is not None:
            baseline_pcrs = _normalize_pcr_map(pcr_baseline.get("pcrs", {}))
            for pcr in required_pcrs:
                expected = baseline_pcrs.get(pcr)
                actual = pcr_values.get(pcr)
                if expected and actual and expected != actual:
                    pcr_mismatches[pcr] = {"expected": expected, "actual": actual}
            if pcr_mismatches:
                failures.append("local_evidence_pcr_mismatch")

        return {
            "boot_state": local_evidence.get("boot_state"),
            "boot_measurement": boot_measurement,
            "pcr_selection": tpm_quote.get("pcr_selection"),
            "silicon_signed": bool(tpm_quote.get("silicon_signed")),
            "present_pcrs": sorted(pcr_values.keys()),
            "baseline_present": pcr_baseline is not None,
            "baseline_pcrs": sorted(baseline_pcrs.keys()),
            "pcr_mismatches": pcr_mismatches,
            "quote_blob_hash": quote_blob_hash,
            "signature_blob_hash": signature_blob_hash,
            "chain_hash": local_evidence.get("chain_hash"),
            "expected_chain_hash": expected_chain_hash,
            "tpm_quote_verification": quote_verification,
            "software_state_binding": {
                "available": bool(software_state_binding.get("available")),
                "bound": bool(software_state_binding.get("bound")),
                "manifest_id": software_state_binding.get("manifest_id"),
                "generation": software_state_binding.get("generation"),
                "policy_generation": software_state_binding.get("policy_generation"),
            },
            "tpm_identity": {
                "present": bool(tpm_identity),
                "manufacturer": manufacturer,
                "identity_chain_mode": identity_chain_mode,
                "ek_certificate_present": ek_certificate_present,
                "ak_certified_by_ek": ak_certified_by_ek,
                "manufacturer_rooted": manufacturer_rooted,
                "trust_tier": (
                    "manufacturer-rooted"
                    if manufacturer_rooted
                    else "identity-present-uncertified"
                    if tpm_identity
                    else "missing"
                ),
            },
            "nonce_source": tpm_quote.get("nonce_source"),
        }, failures

    def _verify_tpm_quote(self, local_evidence: Dict[str, Any]) -> Dict[str, Any]:
        embedded_verification = local_evidence.get("quote_verification")
        if isinstance(embedded_verification, dict) and "ok" in embedded_verification:
            return {
                **embedded_verification,
                "source": "embedded_evidence",
            }

        tpm_quote = local_evidence.get("tpm_pcr_quote", {})
        nonce = tpm_quote.get("nonce")
        ak_public_b64 = tpm_quote.get("ak_public_b64")
        quote_blob_b64 = tpm_quote.get("quote_blob_b64")
        signature_blob_b64 = tpm_quote.get("signature_blob_b64")
        pcr_blob_b64 = tpm_quote.get("pcr_blob_b64")
        pcr_values = _normalize_pcr_map(tpm_quote.get("pcr_values", {}))

        if not nonce or not ak_public_b64 or not quote_blob_b64 or not signature_blob_b64 or not pcr_values:
            return {
                "ok": False,
                "tool": "tpm2_checkquote",
                "reason": "missing_quote_artifacts",
            }

        tool_path = shutil.which("tpm2_checkquote")
        if tool_path is None:
            return {
                "ok": False,
                "tool": "tpm2_checkquote",
                "reason": "tool_unavailable",
            }

        sidecar_artifacts = self._resolve_local_evidence_sidecars(local_evidence)
        if sidecar_artifacts.get("04_tpm_quote_pcrs.bin"):
            try:
                result = subprocess.run(
                    [
                        tool_path,
                        "-u",
                        sidecar_artifacts.get("03_ak_public.pem") or self._write_temp_artifact("ak_public.pem", base64.b64decode(ak_public_b64)),
                        "-m",
                        sidecar_artifacts.get("04_tpm_quote.bin") or self._write_temp_artifact("quote.bin", base64.b64decode(quote_blob_b64)),
                        "-s",
                        sidecar_artifacts.get("04_tpm_quote_sig.bin") or self._write_temp_artifact("quote.sig", base64.b64decode(signature_blob_b64)),
                        "-f",
                        sidecar_artifacts["04_tpm_quote_pcrs.bin"],
                        "-g",
                        "sha256",
                        "-q",
                        nonce,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError as error:
                return {
                    "ok": False,
                    "tool": "tpm2_checkquote",
                    "reason": "tool_execution_failed",
                    "stderr": str(error),
                    "sidecar_artifacts": sidecar_artifacts,
                }
            return {
                "ok": result.returncode == 0,
                "tool": "tpm2_checkquote",
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "sidecar_artifacts": sidecar_artifacts,
            }

        with tempfile.TemporaryDirectory(prefix="arda-phase4-quote-") as temp_dir:
            public_path = os.path.join(temp_dir, "ak_public.pem")
            message_path = os.path.join(temp_dir, "quote.bin")
            signature_path = os.path.join(temp_dir, "quote.sig")
            pcr_path = os.path.join(temp_dir, "quote.pcr")

            with open(public_path, "wb") as handle:
                handle.write(base64.b64decode(ak_public_b64))
            with open(message_path, "wb") as handle:
                handle.write(base64.b64decode(quote_blob_b64))
            with open(signature_path, "wb") as handle:
                handle.write(base64.b64decode(signature_blob_b64))
            if pcr_blob_b64:
                with open(pcr_path, "wb") as handle:
                    handle.write(base64.b64decode(pcr_blob_b64))
            else:
                pcr_lines = ["sha256:"]
                for pcr_index in ("0", "1", "7", "11"):
                    value = pcr_values.get(pcr_index)
                    if value is not None:
                        label = f"{pcr_index:>2}" if pcr_index != "11" else "11"
                        pcr_lines.append(f"  {label}: 0x{value.upper()}")
                with open(pcr_path, "w", encoding="utf-8") as handle:
                    handle.write("\n".join(pcr_lines) + "\n")

            try:
                result = subprocess.run(
                    [
                        tool_path,
                        "-u",
                        public_path,
                        "-m",
                        message_path,
                        "-s",
                        signature_path,
                        "-f",
                        pcr_path,
                        "-g",
                        "sha256",
                        "-q",
                        nonce,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError as error:
                return {
                    "ok": False,
                    "tool": "tpm2_checkquote",
                    "reason": "tool_execution_failed",
                    "stderr": str(error),
                    "sidecar_artifacts": sidecar_artifacts,
                }

        return {
            "ok": result.returncode == 0,
            "tool": "tpm2_checkquote",
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "sidecar_artifacts": sidecar_artifacts,
        }

    def _resolve_local_evidence_sidecars(self, local_evidence: Dict[str, Any]) -> Dict[str, str]:
        file_hashes = local_evidence.get("file_hashes", {})
        search_roots = []
        env_roots = os.getenv("ARDA_PHASE4_EVIDENCE_DIRS", "")
        if env_roots:
            search_roots.extend([root for root in env_roots.split(os.pathsep) if root])
        cwd = os.getcwd()
        search_roots.extend(
            [
                os.path.join(cwd, "evidence"),
                os.path.join(os.path.dirname(cwd), "evidence"),
                os.path.join(cwd, "coronation_kit", "evidence"),
            ]
        )
        capture_dir = os.getenv("ARDA_PHASE4_CAPTURE_DIR")
        if capture_dir:
            search_roots.insert(0, capture_dir)

        resolved: Dict[str, str] = {}
        for filename, expected_hash in file_hashes.items():
            if filename not in {
                "03_ak_public.pem",
                "04_tpm_quote.bin",
                "04_tpm_quote_sig.bin",
                "04_tpm_quote_pcrs.bin",
                "04_quote_nonce.txt",
            }:
                continue
            for root in search_roots:
                candidate = os.path.join(root, filename)
                if not os.path.exists(candidate):
                    continue
                try:
                    if _sha256_file(candidate) == expected_hash:
                        resolved[filename] = candidate
                        break
                except OSError:
                    # Skip unreadable sidecars and continue searching other roots.
                    continue
        return resolved

    def _write_temp_artifact(self, name: str, content: bytes) -> str:
        temp_dir = tempfile.mkdtemp(prefix="arda-phase4-inline-")
        path = os.path.join(temp_dir, name)
        with open(path, "wb") as handle:
            handle.write(content)
        return path
