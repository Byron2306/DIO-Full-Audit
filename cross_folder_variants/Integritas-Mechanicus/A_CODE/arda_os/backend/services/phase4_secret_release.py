import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

from backend.services.boot_measurement import read_sealed_secret_bundle


class Phase4SecretReleaseError(RuntimeError):
    """Raised when Phase 4 attestation truth is insufficient for secret release."""


class Phase4SecretReleaseService:
    """
    Release high-authority material only after Phase 4 attestation truth passes.

    Phase 4 production release expects sealed material bundles on disk rather than
    raw authority secrets in ambient environment variables.
    """

    SECRET_BUNDLE_ENV_MAP = {
        "policy_signing": "ARDA_POLICY_SEALED_SECRET_BUNDLE",
        "attestation_signing": "ARDA_ATTESTATION_SEALED_SECRET_BUNDLE",
        "loader_authority": "ARDA_LOADER_AUTHORITY_SEALED_SECRET_BUNDLE",
    }

    SEAL_KEY_ENV = "ARDA_PHASE4_SEAL_KEY"

    def release(
        self,
        purpose: str,
        gate_result: Dict[str, Any],
        *,
        requester: str,
    ) -> Dict[str, Any]:
        if not gate_result.get("ok"):
            raise Phase4SecretReleaseError("phase4 attestation gate rejected release")
        if gate_result.get("proof_mode", {}).get("active"):
            raise Phase4SecretReleaseError("phase4 secret release is denied while proof-mode allowances are active")

        bundle_env = self.SECRET_BUNDLE_ENV_MAP.get(purpose)
        if not bundle_env:
            raise Phase4SecretReleaseError(f"unknown secret release purpose: {purpose}")

        bundle_path = os.getenv(bundle_env)
        if not bundle_path:
            raise Phase4SecretReleaseError(f"sealed secret bundle not configured for purpose: {purpose}")
        if not os.path.exists(bundle_path):
            raise Phase4SecretReleaseError(f"sealed secret bundle missing for purpose: {purpose}")

        bundle = read_sealed_secret_bundle(bundle_path)
        secret_value = self._unseal_bundle(bundle, gate_result)

        release_time = datetime.now(timezone.utc).isoformat()
        fingerprint = "sha256:" + hashlib.sha256(secret_value.encode("utf-8")).hexdigest()
        manifest_digest = gate_result.get("manifest_digest", "unknown")
        token_material = f"{purpose}:{requester}:{manifest_digest}:{release_time}:{fingerprint}"
        release_token = "sha256:" + hashlib.sha256(token_material.encode("utf-8")).hexdigest()

        return {
            "ok": True,
            "timestamp": release_time,
            "purpose": purpose,
            "requester": requester,
            "sealed_bundle_env": bundle_env,
            "sealed_bundle_path": os.path.abspath(bundle_path),
            "manifest_id": gate_result.get("manifest_id"),
            "manifest_digest": manifest_digest,
            "release_token": release_token,
            "secret_fingerprint": fingerprint,
            "sealing": {
                "schema": bundle.get("schema"),
                "key_id": bundle.get("key_id"),
            },
        }

    def _unseal_bundle(self, bundle: Dict[str, Any], gate_result: Dict[str, Any]) -> str:
        if bundle.get("schema") != "arda.phase4.sealed_secret.v1":
            raise Phase4SecretReleaseError("unsupported sealed secret schema")

        seal_key = os.getenv(self.SEAL_KEY_ENV)
        if not seal_key:
            raise Phase4SecretReleaseError("phase4 seal key not configured")

        aad = {
            "purpose": bundle.get("purpose"),
            "manifest_id": gate_result.get("manifest_id"),
            "manifest_digest": gate_result.get("manifest_digest"),
        }
        aad_bytes = json.dumps(aad, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ciphertext_b64 = bundle.get("ciphertext_b64", "")
        mac_hex = bundle.get("mac_sha256", "")
        try:
            ciphertext = base64.b64decode(ciphertext_b64, validate=True)
        except Exception as error:
            raise Phase4SecretReleaseError(f"sealed secret ciphertext invalid: {error}") from error

        mac = hmac.new(seal_key.encode("utf-8"), aad_bytes + b"." + ciphertext, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, mac_hex):
            raise Phase4SecretReleaseError("sealed secret integrity check failed")

        keystream = hashlib.sha256((seal_key + "|" + bundle.get("key_id", "default")).encode("utf-8")).digest()
        plaintext = bytes(
            byte ^ keystream[index % len(keystream)]
            for index, byte in enumerate(ciphertext)
        )
        try:
            secret_value = plaintext.decode("utf-8")
        except UnicodeDecodeError as error:
            raise Phase4SecretReleaseError(f"sealed secret plaintext invalid: {error}") from error

        expected_fingerprint = bundle.get("secret_fingerprint")
        actual_fingerprint = "sha256:" + hashlib.sha256(secret_value.encode("utf-8")).hexdigest()
        if expected_fingerprint and expected_fingerprint != actual_fingerprint:
            raise Phase4SecretReleaseError("sealed secret fingerprint mismatch")
        return secret_value

    @classmethod
    def build_sealed_bundle(
        cls,
        *,
        purpose: str,
        manifest_id: str,
        manifest_digest: str,
        secret_value: str,
        seal_key: str,
        key_id: str = "phase4-default",
    ) -> Dict[str, Any]:
        aad = {
            "purpose": purpose,
            "manifest_id": manifest_id,
            "manifest_digest": manifest_digest,
        }
        aad_bytes = json.dumps(aad, sort_keys=True, separators=(",", ":")).encode("utf-8")
        keystream = hashlib.sha256((seal_key + "|" + key_id).encode("utf-8")).digest()
        plaintext = secret_value.encode("utf-8")
        ciphertext = bytes(
            byte ^ keystream[index % len(keystream)]
            for index, byte in enumerate(plaintext)
        )
        return {
            "schema": "arda.phase4.sealed_secret.v1",
            "purpose": purpose,
            "key_id": key_id,
            "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
            "mac_sha256": hmac.new(seal_key.encode("utf-8"), aad_bytes + b"." + ciphertext, hashlib.sha256).hexdigest(),
            "secret_fingerprint": "sha256:" + hashlib.sha256(secret_value.encode("utf-8")).hexdigest(),
        }
