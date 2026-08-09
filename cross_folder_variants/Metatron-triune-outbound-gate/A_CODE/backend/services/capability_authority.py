"""Strict verification and durable storage for BEAST-issued capability leases."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Optional

from backend.services.arda_trust_contracts import BeastCapabilityLeaseV1, canonical_json_bytes
from backend.services.capability_lease_store import SqliteCapabilityLeaseStore


class StrictCapabilityLeaseSignatureVerifier:
    """Verify Ed25519 leases using explicit public verification material."""

    @staticmethod
    def _decode(value: str) -> bytes:
        text = str(value or "").strip()
        if not text:
            raise ValueError("missing encoded signature material")
        try:
            return bytes.fromhex(text)
        except ValueError:
            return base64.b64decode(text, validate=True)

    def verify(self, lease: BeastCapabilityLeaseV1) -> bool:
        if str(lease.signature_algorithm).lower() != "ed25519":
            return False
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

            public_key = self._decode(str(lease.verification_material.get("public_key") or ""))
            signature = self._decode(lease.signature)
            Ed25519PublicKey.from_public_bytes(public_key).verify(
                signature,
                canonical_json_bytes(lease.unsigned_payload()),
            )
            return True
        except Exception:
            return False


_store: Optional[SqliteCapabilityLeaseStore] = None


def get_capability_lease_store() -> SqliteCapabilityLeaseStore:
    global _store
    if _store is not None:
        return _store
    environment = str(os.environ.get("ENVIRONMENT") or os.environ.get("ARDA_ENV") or "local").lower()
    configured = str(os.environ.get("BEAST_CAPABILITY_DB") or "").strip()
    if environment == "production" and not configured:
        raise RuntimeError("production requires an explicit durable BEAST_CAPABILITY_DB")
    path = Path(configured or "/tmp/metatron-beast-capabilities.sqlite3")
    path.parent.mkdir(parents=True, exist_ok=True)
    _store = SqliteCapabilityLeaseStore(
        path,
        signature_verifier=StrictCapabilityLeaseSignatureVerifier(),
    )
    return _store

