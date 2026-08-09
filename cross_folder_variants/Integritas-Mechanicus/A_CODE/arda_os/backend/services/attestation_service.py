"""
Arda DSSE Attestation Service
==============================
Produces DSSE-style signed attestation envelopes with REAL signing.

Two signing modes:
1. sigstore (default if OIDC is available): Signs via Fulcio + posts to public Rekor.
   This gives you a real, externally-witnessed transparency receipt.
2. HMAC-SHA3-256 fallback: Used when sigstore OIDC flow cannot complete
   (e.g., non-interactive environments). Honestly labelled as "HS3-256".

DSSE binds a message to its type via:
    PAE(type, message) = len(type) || ":" || type || " " || len(message) || ":" || message

Boot context is a REAL measurement from the Windows substrate (Secure Boot + TPM).
"""

import hashlib
import hmac as hmac_mod
import json
import logging
import os
import base64
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger("ARDA_ATTEST")

DSSE_TYPE_URI = "application/vnd.arda.attestation.v1+json"

_ATTEST_SECRET = os.getenv(
    "ARDA_ATTESTATION_SECRET", "ARDA-ATTEST-SECRET-REPLACE-IN-PRODUCTION"
).encode()
DEFAULT_AK_CONTEXT_PATH = os.getenv("ARDA_TPM_AK_CONTEXT", "/var/lib/arda/attestation/latest/ak/ak.ctx")
DEFAULT_AK_PUBLIC_PATH = os.getenv("ARDA_TPM_AK_PUBLIC", "/var/lib/arda/attestation/latest/03_ak_public.pem")
DEFAULT_PHASE4_EVIDENCE_BUNDLE_PATH = os.getenv(
    "ARDA_PHASE4_EVIDENCE_BUNDLE",
    "/var/lib/arda/attestation/latest/07_sovereign_attestation.json",
)


def _pae(type_uri: str, body: bytes) -> bytes:
    """Pre-Authentication Encoding per DSSE spec."""
    t = type_uri.encode("utf-8")
    return (
        str(len(t)).encode() + b":" + t
        + b" "
        + str(len(body)).encode() + b":" + body
    )


def _canonical_body(obj: Dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _get_boot_context() -> dict:
    """Gets REAL boot measurements from the substrate."""
    try:
        from backend.services.boot_measurement import measure_boot_state
        return measure_boot_state()
    except Exception as e:
        logger.warning(f"[ATTEST] Boot measurement failed: {e}")
        return {"error": str(e), "source": "measurement_failed"}


def _hmac_sign(pae_bytes: bytes) -> dict:
    """HMAC-SHA3-256 signing (fallback). Honestly labelled."""
    sig = hmac_mod.new(_ATTEST_SECRET, pae_bytes, hashlib.sha3_256).hexdigest()
    return {
        "signature": sig,
        "signing_algorithm": "HMAC-SHA3-256",
        "signing_identity": "local:arda-policy-secret",
        "trust_mode": "local-only",
        "transparency_receipt": None,
    }


def _read_json_if_exists(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def _quote_binding_from_bundle(
    bundle: Dict[str, Any],
    *,
    artifact_digest: str,
) -> Optional[Dict[str, Any]]:
    quote = bundle.get("tpm_pcr_quote") or {}
    identity = bundle.get("tpm_identity") or {}
    software_state_binding = bundle.get("software_state_binding") or {}
    required_quote_fields = (
        "nonce",
        "pcr_selection",
        "quote_blob_b64",
        "signature_blob_b64",
        "ak_public_b64",
    )
    if not all(quote.get(field) for field in required_quote_fields):
        return None
    if str(quote.get("pcr_values", {}).get("11") or "").lower() in {"", "0" * 64}:
        return None
    if not software_state_binding.get("bound"):
        return None
    manifest_digest = str(software_state_binding.get("manifest_digest") or "").strip().lower()
    if manifest_digest and manifest_digest != artifact_digest.lower():
        return None
    if not identity.get("ak_certified_by_ek") and not identity.get("ek_certificate_present"):
        return None
    return {
        "nonce": quote["nonce"],
        "pcr_selection": quote["pcr_selection"],
        "pcr_values": quote.get("pcr_values", {}),
        "pcr_blob_b64": quote.get("pcr_blob_b64"),
        "quote_blob_b64": quote["quote_blob_b64"],
        "signature_blob_b64": quote["signature_blob_b64"],
        "ak_public_b64": quote["ak_public_b64"],
        "silicon_signed": bool(quote.get("silicon_signed")),
        "manufacturer_rooted": bool(
            identity.get("ak_certified_by_ek") or identity.get("ek_certificate_present")
        ),
        "manufacturer": identity.get("manufacturer"),
        "identity_chain_mode": identity.get("identity_chain_mode"),
        "software_state_binding": {
            "available": software_state_binding.get("available"),
            "bound": software_state_binding.get("bound"),
            "manifest_id": software_state_binding.get("manifest_id"),
            "manifest_digest": software_state_binding.get("manifest_digest"),
            "generation": software_state_binding.get("generation"),
            "policy_generation": software_state_binding.get("policy_generation"),
        },
        "chain_hash": bundle.get("chain_hash"),
        "mirror_id": bundle.get("mirror_id"),
        "evidence_timestamp": bundle.get("timestamp"),
        "quote_verification": bundle.get("quote_verification"),
    }


def _quote_bundle_sign(
    *,
    artifact_digest: str,
    quote_bundle: Optional[Dict[str, Any]] = None,
    evidence_bundle_path: Optional[str] = None,
) -> Optional[dict]:
    bundle = quote_bundle
    if bundle is None:
        bundle_path = evidence_bundle_path or os.getenv("ARDA_PHASE4_EVIDENCE_BUNDLE") or DEFAULT_PHASE4_EVIDENCE_BUNDLE_PATH
        bundle = _read_json_if_exists(bundle_path)
    if not isinstance(bundle, dict):
        return None
    quote_binding = _quote_binding_from_bundle(bundle, artifact_digest=artifact_digest)
    if quote_binding is None:
        return None
    return {
        "signature": quote_binding["signature_blob_b64"],
        "signing_algorithm": "tpm-quote-manifest-v1",
        "signing_identity": "TPM:manufacturer-rooted-quote",
        "trust_mode": "manufacturer-rooted-quote",
        "transparency_receipt": None,
        "quote_binding": quote_binding,
    }


def tpm_ak_available() -> bool:
    return (
        os.path.exists(DEFAULT_AK_CONTEXT_PATH)
        and os.path.exists(DEFAULT_AK_PUBLIC_PATH)
        and shutil.which("tpm2_sign") is not None
        and shutil.which("tpm2_verifysignature") is not None
        and shutil.which("tpm2_loadexternal") is not None
    )


def _tpm_ak_sign(pae_bytes: bytes) -> Optional[dict]:
    """Sign the DSSE PAE with the TPM-backed AK for asymmetric verification."""
    if not tpm_ak_available():
        return None
    with tempfile.TemporaryDirectory(prefix="arda-attest-ak-") as temp_dir:
        digest_path = os.path.join(temp_dir, "statement.digest")
        signature_path = os.path.join(temp_dir, "statement.sig")
        digest = hashlib.sha256(pae_bytes).digest()
        with open(digest_path, "wb") as handle:
            handle.write(digest)
        completed = subprocess.run(
            [
                shutil.which("tpm2_sign") or "tpm2_sign",
                "-c",
                DEFAULT_AK_CONTEXT_PATH,
                "-g",
                "sha256",
                "-s",
                "rsassa",
                "-d",
                "-f",
                "tss",
                "-o",
                signature_path,
                digest_path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0 or not os.path.exists(signature_path):
            logger.warning(
                "[ATTEST] TPM AK signing failed: %s",
                completed.stderr.strip() or completed.stdout.strip(),
            )
            return None
        with open(signature_path, "rb") as handle:
            signature_bytes = handle.read()
        with open(DEFAULT_AK_PUBLIC_PATH, "rb") as handle:
            ak_public_bytes = handle.read()
        return {
            "signature": base64.b64encode(signature_bytes).decode("ascii"),
            "signing_algorithm": "tpm-ak-rsassa-sha256",
            "signing_identity": "TPM:attestation-key",
            "trust_mode": "manufacturer-rooted-ak",
            "transparency_receipt": None,
            "ak_public_b64": base64.b64encode(ak_public_bytes).decode("ascii"),
            "ak_public_path": DEFAULT_AK_PUBLIC_PATH,
            "ak_context_path": DEFAULT_AK_CONTEXT_PATH,
            "signature_format": "tss",
        }


def _sigstore_sign(body_bytes: bytes) -> dict:
    """
    Signs using real Sigstore (Fulcio + Rekor).
    Returns the signature, certificate, and Rekor log entry.
    
    This is REAL external transparency: the signature is posted to
    rekor.sigstore.dev and can be independently verified by anyone.
    """
    try:
        from sigstore.sign import SigningContext
        from sigstore.models import Bundle

        ctx = SigningContext.production()
        with ctx.signer() as signer:
            result = signer.sign_artifact(body_bytes)
        
        # Extract the real transparency data
        bundle_json = result.to_json()
        bundle_data = json.loads(bundle_json) if isinstance(bundle_json, str) else bundle_json
        
        log_entry = bundle_data.get("verificationMaterial", {}).get("tlogEntries", [{}])[0]
        log_index = log_entry.get("logIndex", "unknown")
        
        return {
            "signature": bundle_json if isinstance(bundle_json, str) else json.dumps(bundle_data),
            "signing_algorithm": "sigstore:fulcio+rekor",
            "signing_identity": "OIDC:sigstore",
            "trust_mode": "external-transparency",
            "transparency_receipt": {
                "log": "rekor.sigstore.dev",
                "log_index": log_index,
                "integrated": True,
            },
            "bundle": bundle_data,
        }
    except Exception as e:
        logger.warning(f"[ATTEST] Sigstore signing failed: {e}. Falling back to HMAC.")
        return None


def sigstore_available() -> bool:
    """True when Sigstore signing dependencies appear available locally."""
    try:
        import sigstore.sign  # noqa: F401
    except Exception:
        return False
    return True


def should_use_sigstore(explicit: Optional[bool] = None) -> bool:
    """
    Decide whether envelope creation should attempt external signing.

    Environment overrides:
    - `ARDA_USE_SIGSTORE=true|false`
    - `ARDA_CLOUD_MANDATE=true` forces an attempt and fail-closed behavior upstream
    """
    env_value = os.getenv("ARDA_USE_SIGSTORE")
    if env_value is not None:
        return env_value.strip().lower() in {"1", "true", "yes", "on"}
    if explicit is not None:
        return explicit
    if os.getenv("ARDA_CLOUD_MANDATE", "").strip().lower() == "true":
        return True
    return sigstore_available()


def should_use_tpm_ak(explicit: Optional[bool] = None) -> bool:
    env_value = os.getenv("ARDA_USE_TPM_AK")
    if env_value is not None:
        return env_value.strip().lower() in {"1", "true", "yes", "on"}
    if explicit is not None:
        return explicit
    return tpm_ak_available()


def _load_sigstore_bundle(envelope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw = envelope.get("signature")
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _write_temp_json(payload: Dict[str, Any]) -> str:
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False)
    try:
        json.dump(payload, handle, sort_keys=True)
        handle.flush()
        return handle.name
    finally:
        handle.close()


def _try_sigstore_cli_verify(bundle: Dict[str, Any], statement: Dict[str, Any]) -> Optional[bool]:
    """
    Best-effort real verification using a local sigstore CLI if present.

    Returns:
    - True when verification succeeds
    - False when a verifier is present and verification fails
    - None when no usable verifier is available
    """
    cli = shutil.which("sigstore")
    if not cli:
        return None
    bundle_path = _write_temp_json(bundle)
    statement_path = _write_temp_json(statement)
    try:
        completed = subprocess.run(
            [cli, "verify", "bundle", "--bundle", bundle_path, statement_path],
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.returncode == 0
    except Exception as exc:
        logger.warning(f"[ATTEST] Sigstore CLI verification unavailable: {exc}")
        return None
    finally:
        for path in (bundle_path, statement_path):
            try:
                os.unlink(path)
            except OSError:
                pass


def get_envelope_trust_report(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Return a structured trust assessment for the attestation envelope."""
    algo = str(envelope.get("signing_algorithm") or "")
    report = {
        "algorithm": algo,
        "trust_mode": envelope.get("trust_mode"),
        "verified": False,
        "verification_mode": "none",
        "externally_verifiable": False,
        "transparency_integrated": False,
        "failure_reason": None,
    }

    if algo == "HMAC-SHA3-256":
        try:
            statement = envelope["payload"]
            body = _canonical_body(statement)
            pae_bytes = _pae(envelope["payload_type"], body)
            expected = hmac_mod.new(_ATTEST_SECRET, pae_bytes, hashlib.sha3_256).hexdigest()
            valid = hmac_mod.compare_digest(envelope["signature"], expected)
            report.update(
                {
                    "verified": valid,
                    "verification_mode": "local-hmac",
                    "externally_verifiable": False,
                    "failure_reason": None if valid else "hmac_mismatch",
                }
            )
            return report
        except Exception as exc:
            report["failure_reason"] = f"hmac_error:{exc}"
            return report

    if algo == "tpm-ak-rsassa-sha256":
        signature_b64 = envelope.get("signature")
        ak_public_b64 = envelope.get("ak_public_b64")
        signature_format = envelope.get("signature_format", "tss")
        if not signature_b64 or not ak_public_b64:
            report["failure_reason"] = "tpm_ak_artifacts_missing"
            return report
        if shutil.which("tpm2_loadexternal") is None or shutil.which("tpm2_verifysignature") is None:
            report["failure_reason"] = "tpm_ak_verifier_unavailable"
            return report
        with tempfile.TemporaryDirectory(prefix="arda-attest-ak-verify-") as temp_dir:
            public_path = os.path.join(temp_dir, "ak_public.pem")
            digest_path = os.path.join(temp_dir, "statement.digest")
            signature_path = os.path.join(temp_dir, "statement.sig")
            public_ctx = os.path.join(temp_dir, "ak_public.ctx")
            with open(public_path, "wb") as handle:
                handle.write(base64.b64decode(ak_public_b64))
            with open(digest_path, "wb") as handle:
                handle.write(hashlib.sha256(_pae(envelope["payload_type"], _canonical_body(envelope["payload"]))).digest())
            with open(signature_path, "wb") as handle:
                handle.write(base64.b64decode(signature_b64))
            load = subprocess.run(
                [
                    shutil.which("tpm2_loadexternal") or "tpm2_loadexternal",
                    "-C",
                    "n",
                    "-u",
                    public_path,
                    "-c",
                    public_ctx,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if load.returncode != 0:
                report["failure_reason"] = "tpm_ak_loadexternal_failed"
                return report
            verify = subprocess.run(
                [
                    shutil.which("tpm2_verifysignature") or "tpm2_verifysignature",
                    "-c",
                    public_ctx,
                    "-g",
                    "sha256",
                    "-d",
                    digest_path,
                    "-f",
                    signature_format,
                    "-s",
                    signature_path,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            report.update(
                {
                    "verified": verify.returncode == 0,
                    "verification_mode": "tpm-ak-public-verify",
                    "externally_verifiable": True,
                    "failure_reason": None if verify.returncode == 0 else "tpm_ak_signature_invalid",
                }
            )
            return report

    if algo == "tpm-quote-manifest-v1":
        quote_binding = envelope.get("quote_binding") or {}
        payload = envelope.get("payload") or {}
        if not isinstance(quote_binding, dict):
            report["failure_reason"] = "quote_binding_missing"
            return report
        if payload.get("artifact_digest") != quote_binding.get("software_state_binding", {}).get("manifest_digest"):
            report["failure_reason"] = "quote_binding_manifest_mismatch"
            return report
        if not quote_binding.get("manufacturer_rooted"):
            report["failure_reason"] = "quote_binding_not_manufacturer_rooted"
            return report
        if not quote_binding.get("silicon_signed"):
            report["failure_reason"] = "quote_binding_not_silicon_signed"
            return report
        if str(quote_binding.get("pcr_values", {}).get("11") or "").lower() in {"", "0" * 64}:
            report["failure_reason"] = "quote_binding_pcr11_zero"
            return report
        embedded_quote_verification = quote_binding.get("quote_verification")
        if isinstance(embedded_quote_verification, dict) and "ok" in embedded_quote_verification:
            report.update(
                {
                    "verified": bool(embedded_quote_verification.get("ok")),
                    "verification_mode": "tpm-quote-manifest-embedded",
                    "externally_verifiable": bool(embedded_quote_verification.get("ok")),
                    "failure_reason": None if embedded_quote_verification.get("ok") else "tpm_quote_signature_invalid",
                }
            )
            return report
        if shutil.which("tpm2_checkquote") is None:
            report["failure_reason"] = "tpm_quote_verifier_unavailable"
            return report
        try:
            quote_bytes = base64.b64decode(quote_binding["quote_blob_b64"], validate=True)
            signature_bytes = base64.b64decode(quote_binding["signature_blob_b64"], validate=True)
            ak_public_bytes = base64.b64decode(quote_binding["ak_public_b64"], validate=True)
            pcr_blob_b64 = quote_binding.get("pcr_blob_b64")
            pcr_blob_bytes = (
                base64.b64decode(pcr_blob_b64, validate=True)
                if pcr_blob_b64
                else None
            )
        except Exception:
            report["failure_reason"] = "quote_binding_decode_failed"
            return report
        with tempfile.TemporaryDirectory(prefix="arda-attest-quote-verify-") as temp_dir:
            public_path = os.path.join(temp_dir, "ak_public.pem")
            quote_path = os.path.join(temp_dir, "quote.bin")
            signature_path = os.path.join(temp_dir, "quote.sig")
            pcr_path = os.path.join(temp_dir, "quote.pcrs")
            with open(public_path, "wb") as handle:
                handle.write(ak_public_bytes)
            with open(quote_path, "wb") as handle:
                handle.write(quote_bytes)
            with open(signature_path, "wb") as handle:
                handle.write(signature_bytes)
            if pcr_blob_bytes is not None:
                with open(pcr_path, "wb") as handle:
                    handle.write(pcr_blob_bytes)
            else:
                with open(pcr_path, "w", encoding="utf-8") as handle:
                    handle.write("sha256:\n")
                    for index, value in sorted((quote_binding.get("pcr_values") or {}).items(), key=lambda item: int(item[0])):
                        handle.write(f"  {index}: 0x{str(value).lower()}\n")
            try:
                verify = subprocess.run(
                    [
                        shutil.which("tpm2_checkquote") or "tpm2_checkquote",
                        "-u",
                        public_path,
                        "-m",
                        quote_path,
                        "-s",
                        signature_path,
                        "-f",
                        pcr_path,
                        "-g",
                        "sha256",
                        "-q",
                        str(quote_binding.get("nonce") or ""),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError:
                report["failure_reason"] = "tpm_quote_verifier_exec_denied"
                return report
            report.update(
                {
                    "verified": verify.returncode == 0,
                    "verification_mode": "tpm-quote-manifest",
                    "externally_verifiable": verify.returncode == 0,
                    "failure_reason": None if verify.returncode == 0 else "tpm_quote_signature_invalid",
                }
            )
            return report

    if "sigstore" not in algo:
        report["failure_reason"] = "unknown_algorithm"
        return report

    bundle = _load_sigstore_bundle(envelope)
    receipt = envelope.get("transparency_receipt") or {}
    if not bundle:
        report["failure_reason"] = "sigstore_bundle_missing"
        return report
    verification_material = bundle.get("verificationMaterial") or {}
    tlog_entries = verification_material.get("tlogEntries") or []
    has_cert_material = bool(
        verification_material.get("certificate")
        or (verification_material.get("x509CertificateChain") or {}).get("certificates")
    )
    if not isinstance(receipt, dict) or not receipt.get("integrated") or not receipt.get("log_index"):
        report["failure_reason"] = "sigstore_transparency_receipt_missing"
        return report
    if not tlog_entries:
        report["failure_reason"] = "sigstore_tlog_missing"
        return report
    if not has_cert_material:
        report["failure_reason"] = "sigstore_certificate_missing"
        return report

    report["transparency_integrated"] = True
    report["externally_verifiable"] = True

    cli_verified = _try_sigstore_cli_verify(bundle, envelope.get("payload") or {})
    if cli_verified is True:
        report.update({"verified": True, "verification_mode": "sigstore-cli"})
        return report
    if cli_verified is False:
        report.update({"failure_reason": "sigstore_cli_verification_failed", "verification_mode": "sigstore-cli"})
        return report

    report.update(
        {
            "verified": True,
            "verification_mode": "sigstore-structural",
            "failure_reason": None,
        }
    )
    return report


def create_envelope(
    command: str,
    principal: str,
    token_id: str,
    lane: str,
    policy_id: str,
    policy_version: str,
    verdict: str,
    artifact_digest: str,
    policy_verdict: str,
    use_sigstore: Optional[bool] = None,
    use_tpm_ak: Optional[bool] = None,
    quote_bundle: Optional[Dict[str, Any]] = None,
    evidence_bundle_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Produces a signed DSSE-style attestation envelope.
    
    If use_sigstore=True, attempts real Sigstore signing with Fulcio+Rekor.
    Falls back to HMAC-SHA3-256 if Sigstore OIDC flow cannot complete.
    """
    if policy_verdict != "ALLOW":
        raise RuntimeError(
            f"[ATTEST] DENY: cannot attest a denied request. Verdict: {policy_verdict}"
        )

    boot_context = _get_boot_context()

    statement = {
        "type": DSSE_TYPE_URI,
        "artifact_digest": artifact_digest,
        "principal": principal,
        "token_id": token_id,
        "lane": lane,
        "policy_id": policy_id,
        "policy_version": policy_version,
        "verdict": verdict,
        "boot_context": boot_context,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    body = _canonical_body(statement)
    pae_bytes = _pae(DSSE_TYPE_URI, body)

    # [PHASE 12-c] Active Attestation Implementation
    # If the Cloud Mandate is set, Sigstore MUST succeed or we Fail-Closed.
    sig_data = None
    sig_data = _quote_bundle_sign(
        artifact_digest=artifact_digest,
        quote_bundle=quote_bundle,
        evidence_bundle_path=evidence_bundle_path,
    )
    if should_use_tpm_ak(use_tpm_ak):
        sig_data = sig_data or _tpm_ak_sign(pae_bytes)
    if sig_data is None and should_use_sigstore(use_sigstore):
        sig_data = _sigstore_sign(pae_bytes)
        if sig_data is None and os.getenv("ARDA_CLOUD_MANDATE") == "true":
            logger.critical("[ATTEST] CLOUD_SOVEREIGNTY_FAILURE: Active Attestation (Rekor) mandatory but failed.")
            raise RuntimeError("SOVEREIGNTY_LOG_FRACTURE: External witness (Sigstore) unavailable.")

    # Fall back to HMAC if not mandated
    if sig_data is None:
        sig_data = _hmac_sign(pae_bytes)

    envelope = {
        "payload_type": DSSE_TYPE_URI,
        "payload": statement,
        "signature": sig_data["signature"],
        "signing_algorithm": sig_data["signing_algorithm"],
        "signing_identity": sig_data["signing_identity"],
        "trust_mode": sig_data.get("trust_mode", "local-only"),
        "transparency_receipt": sig_data.get("transparency_receipt"),
    }
    if sig_data.get("ak_public_b64"):
        envelope["ak_public_b64"] = sig_data["ak_public_b64"]
        envelope["signature_format"] = sig_data.get("signature_format", "tss")
    if sig_data.get("quote_binding"):
        envelope["quote_binding"] = sig_data["quote_binding"]
    
    logger.info(
        f"[ATTEST] DSSE envelope signed for '{command}' "
        f"by '{principal}' (algo={sig_data['signing_algorithm']}, verdict={verdict})"
    )
    return envelope


def verify_envelope(envelope: Dict[str, Any]) -> bool:
    """
    Verifies a DSSE envelope's signature.
    HMAC envelopes are verified locally.
    Sigstore envelopes require a structured bundle and transparency metadata.
    """
    report = get_envelope_trust_report(envelope)
    if report["verified"]:
        logger.info(
            "[ATTEST] Envelope verified "
            f"(algo={report['algorithm']}, mode={report['verification_mode']}, "
            f"external={report['externally_verifiable']})"
        )
        return True
    logger.error(
        "[ATTEST] Envelope verification failed "
        f"(algo={report['algorithm']}, reason={report['failure_reason']})"
    )
    return False
