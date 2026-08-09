"""Off-box Phase 4 verifier service.

This service is intended to run on a verifier host rather than the attested
host. It accepts the manifest, attestation envelope, and evidence bundle as
request payloads, evaluates the Phase 4 gate, and can optionally sign the
verdict with an operator-provisioned Ed25519 key.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.services.os_enforcement_service import OsEnforcementService


def _canonical_json_bytes(value: Dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _read_json_path(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def _load_quote_verification_sidecar(evidence_bundle_path: str) -> Optional[Dict[str, Any]]:
    try:
        evidence_path = Path(evidence_bundle_path).expanduser().resolve()
    except Exception:
        return None
    sidecar_path = evidence_path.parent / "08_quote_verification.json"
    if not sidecar_path.is_file():
        return None
    try:
        return json.loads(sidecar_path.read_text(encoding="utf-8"))
    except Exception:
        return None


class Phase4VerifyRequest(BaseModel):
    manifest: Optional[Dict[str, Any]] = None
    manifest_path: Optional[str] = None
    attestation_envelope: Optional[Dict[str, Any]] = None
    attestation_envelope_path: Optional[str] = None
    evidence_bundle: Optional[Dict[str, Any]] = None
    evidence_bundle_path: Optional[str] = None
    quote_verification: Optional[Dict[str, Any]] = None
    quote_verification_path: Optional[str] = None
    pcr_baseline: Optional[Dict[str, Any]] = None
    pcr_baseline_path: Optional[str] = None
    require_sigstore: bool = False
    require_verifier_nonce: bool = True
    require_tpm_quote_verification: bool = True
    allow_attested_only_boot: bool = False
    allow_missing_boot_measurement_for_live_proof: bool = False

    def resolved_manifest(self) -> Dict[str, Any]:
        if self.manifest is not None:
            return self.manifest
        if self.manifest_path:
            return _read_json_path(self.manifest_path)
        raise ValueError("manifest or manifest_path is required")

    def resolved_attestation_envelope(self) -> Dict[str, Any]:
        if self.attestation_envelope is not None:
            return self.attestation_envelope
        if self.attestation_envelope_path:
            return _read_json_path(self.attestation_envelope_path)
        raise ValueError("attestation_envelope or attestation_envelope_path is required")

    def resolved_evidence_bundle(self) -> Dict[str, Any]:
        resolved_quote_verification = self.resolved_quote_verification()
        if self.evidence_bundle is not None:
            bundle = dict(self.evidence_bundle)
            if "quote_verification" not in bundle and resolved_quote_verification is not None:
                bundle["quote_verification"] = resolved_quote_verification
            elif "quote_verification" not in bundle and self.evidence_bundle_path:
                quote_verification = _load_quote_verification_sidecar(self.evidence_bundle_path)
                if quote_verification is not None:
                    bundle["quote_verification"] = quote_verification
            return bundle
        if self.evidence_bundle_path:
            bundle = _read_json_path(self.evidence_bundle_path)
            quote_verification = resolved_quote_verification or _load_quote_verification_sidecar(self.evidence_bundle_path)
            if quote_verification is not None:
                bundle["quote_verification"] = quote_verification
            return bundle
        raise ValueError("evidence_bundle or evidence_bundle_path is required")

    def resolved_quote_verification(self) -> Optional[Dict[str, Any]]:
        if self.quote_verification is not None:
            return self.quote_verification
        if self.quote_verification_path:
            return _read_json_path(self.quote_verification_path)
        return None

    def resolved_pcr_baseline(self) -> Optional[Dict[str, Any]]:
        if self.pcr_baseline is not None:
            return self.pcr_baseline
        if self.pcr_baseline_path:
            return _read_json_path(self.pcr_baseline_path)
        return None


class Phase4VerifyResponse(BaseModel):
    verifier: Dict[str, Any]
    trust_summary: Dict[str, Any]
    gate: Dict[str, Any]
    signed_verdict: Optional[Dict[str, Any]] = None


class _Ed25519VerdictSigner:
    def __init__(self, private_key_path: str, public_key_path: Optional[str] = None, *, key_id: str) -> None:
        from cryptography.hazmat.primitives import serialization

        self.key_id = key_id
        self._private = serialization.load_pem_private_key(
            Path(private_key_path).read_bytes(),
            password=None,
        )
        self._public_bytes = (
            Path(public_key_path).read_bytes()
            if public_key_path and Path(public_key_path).is_file()
            else self._private.public_key().public_bytes_raw()
        )

    @property
    def public_key_b64(self) -> str:
        return base64.b64encode(self._public_bytes).decode("ascii")

    def sign(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        signature = self._private.sign(_canonical_json_bytes(payload))
        return {
            "algorithm": "ed25519",
            "signature": base64.b64encode(signature).decode("ascii"),
            "verification_material": {
                "key_id": self.key_id,
                "public_key": self.public_key_b64,
            },
        }


def _load_signer_from_env() -> Optional[_Ed25519VerdictSigner]:
    private_key = str(os.environ.get("ARDA_VERIFIER_PRIVATE_KEY") or "").strip()
    if not private_key:
        return None
    public_key = str(os.environ.get("ARDA_VERIFIER_PUBLIC_KEY") or "").strip() or None
    key_id = str(os.environ.get("ARDA_VERIFIER_KEY_ID") or "arda-phase4-verifier").strip()
    return _Ed25519VerdictSigner(private_key, public_key, key_id=key_id)


def _signer_status_from_env() -> Dict[str, Any]:
    private_key = str(os.environ.get("ARDA_VERIFIER_PRIVATE_KEY") or "").strip()
    public_key = str(os.environ.get("ARDA_VERIFIER_PUBLIC_KEY") or "").strip() or None
    key_id = str(os.environ.get("ARDA_VERIFIER_KEY_ID") or "arda-phase4-verifier").strip()
    if not private_key:
        return {
            "configured": False,
            "enabled": False,
            "key_id": key_id,
            "error": None,
        }
    try:
        signer = _Ed25519VerdictSigner(private_key, public_key, key_id=key_id)
    except Exception as error:
        return {
            "configured": True,
            "enabled": False,
            "key_id": key_id,
            "error": str(error),
        }
    return {
        "configured": True,
        "enabled": True,
        "key_id": key_id,
        "error": None,
        "public_key_b64": signer.public_key_b64,
    }


def _build_signed_verdict(result: Dict[str, Any], signer: _Ed25519VerdictSigner) -> Dict[str, Any]:
    issued_at = datetime.now(timezone.utc).isoformat()
    authorized_states = [
        state.strip()
        for state in str(os.environ.get("ARDA_VERIFIER_AUTHORIZED_STATES", "observe,enforce,lockdown,rescue")).split(",")
        if state.strip()
    ]
    payload = {
        "schema_version": "arda.phase4.verifier_result.v1",
        "verdict_id": "verdict-" + uuid.uuid4().hex,
        "verifier_id": str(os.environ.get("ARDA_VERIFIER_ID") or "arda-phase4-remote-verifier"),
        "manifest_id": result.get("manifest_id"),
        "manifest_digest": result.get("manifest_digest"),
        "attestation_timestamp": result.get("attestation_timestamp"),
        "issued_at": issued_at,
        "ok": bool(result.get("ok")),
        "production_ready": bool(result.get("production_ready")),
        "local_attestation_passed": bool(result.get("local_attestation_passed")),
        "externally_verifiable_attestation": bool(result.get("externally_verifiable_attestation")),
        "failures": list(result.get("failures") or ()),
        "authorized_states": authorized_states,
        "attestation_envelope_trust": dict(result.get("attestation_envelope_trust") or {}),
        "tpm_identity": dict((result.get("local_evidence") or {}).get("tpm_identity") or {}),
        "request_digest": "sha256:" + hashlib.sha256(
            _canonical_json_bytes(
                {
                    "manifest_id": result.get("manifest_id"),
                    "manifest_digest": result.get("manifest_digest"),
                    "attestation_timestamp": result.get("attestation_timestamp"),
                    "ok": bool(result.get("ok")),
                    "production_ready": bool(result.get("production_ready")),
                    "failures": list(result.get("failures") or ()),
                }
            )
        ).hexdigest(),
    }
    signed = signer.sign(payload)
    return {
        **payload,
        "signature_algorithm": signed["algorithm"],
        "signature": signed["signature"],
        "verification_material": signed["verification_material"],
    }


def _transparency_stub(result: Dict[str, Any], signed_verdict: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    seed = {
        "verdict_id": (signed_verdict or {}).get("verdict_id"),
        "manifest_id": result.get("manifest_id"),
        "manifest_digest": result.get("manifest_digest"),
        "attestation_timestamp": result.get("attestation_timestamp"),
    }
    entry_hash = "sha256:" + hashlib.sha256(_canonical_json_bytes(seed)).hexdigest()
    return {
        "integrated": False,
        "mode": "local-verifier-ledger-stub",
        "entry_hash": entry_hash,
        "verdict_id": (signed_verdict or {}).get("verdict_id"),
        "note": "append-only transparency backend not yet attached",
    }


app = FastAPI(title="ARDA Phase 4 Remote Verifier", version="1.0.0")


@app.get("/api/health")
def health() -> Dict[str, Any]:
    signer_status = _signer_status_from_env()
    return {
        "ok": True,
        "service": "arda-phase4-remote-verifier",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "signed_verdicts_enabled": signer_status["enabled"],
        "signer": signer_status,
        "verifier_id": str(os.environ.get("ARDA_VERIFIER_ID") or "arda-phase4-remote-verifier"),
    }


@app.post("/verify/phase4", response_model=Phase4VerifyResponse)
def verify_phase4(request: Phase4VerifyRequest) -> Dict[str, Any]:
    service = OsEnforcementService(arm=False)
    try:
        try:
            manifest = request.resolved_manifest()
            attestation_envelope = request.resolved_attestation_envelope()
            evidence_bundle = request.resolved_evidence_bundle()
            pcr_baseline = request.resolved_pcr_baseline()
            gate = service.evaluate_phase4_attestation_gate(
                manifest,
                attestation_envelope,
                None,
                evidence_bundle,
                pcr_baseline,
                request.require_tpm_quote_verification,
                request.allow_attested_only_boot,
                request.allow_missing_boot_measurement_for_live_proof,
                request.require_verifier_nonce,
                request.require_sigstore,
            )
        except Exception as exc:
            debug_context = {
                "error": str(exc),
                "request_flags": {
                    "require_sigstore": request.require_sigstore,
                    "require_verifier_nonce": request.require_verifier_nonce,
                    "require_tpm_quote_verification": request.require_tpm_quote_verification,
                    "allow_attested_only_boot": request.allow_attested_only_boot,
                    "allow_missing_boot_measurement_for_live_proof": request.allow_missing_boot_measurement_for_live_proof,
                },
                "paths_present": {
                    "manifest_path": bool(request.manifest_path),
                    "attestation_envelope_path": bool(request.attestation_envelope_path),
                    "evidence_bundle_path": bool(request.evidence_bundle_path),
                    "quote_verification_path": bool(request.quote_verification_path),
                    "pcr_baseline_path": bool(request.pcr_baseline_path),
                },
                "inline_present": {
                    "manifest": request.manifest is not None,
                    "attestation_envelope": request.attestation_envelope is not None,
                    "evidence_bundle": request.evidence_bundle is not None,
                    "quote_verification": request.quote_verification is not None,
                    "pcr_baseline": request.pcr_baseline is not None,
                },
                "resolved_bundle_summary": {
                    "has_quote_verification": isinstance(evidence_bundle.get("quote_verification"), dict),
                    "quote_verification_keys": sorted((evidence_bundle.get("quote_verification") or {}).keys()) if isinstance(evidence_bundle.get("quote_verification"), dict) else [],
                    "has_tpm_quote": isinstance(evidence_bundle.get("tpm_pcr_quote"), dict),
                    "bundle_keys": sorted(evidence_bundle.keys())[:40],
                } if "evidence_bundle" in locals() and isinstance(evidence_bundle, dict) else None,
            }
            raise HTTPException(status_code=400, detail={"message": f"phase4 verification failed: {exc}", "debug": debug_context}) from exc

        signer_status = _signer_status_from_env()
        if signer_status["configured"] and not signer_status["enabled"]:
            raise HTTPException(
                status_code=500,
                detail=f"verifier signer misconfigured: {signer_status['error']}",
            )
        signer = _load_signer_from_env()
        signed_verdict = _build_signed_verdict(gate, signer) if signer is not None else None
        transparency_receipt = _transparency_stub(gate, signed_verdict)
        return {
            "verifier": {
                "service": "arda-phase4-remote-verifier",
                "verifier_id": str(os.environ.get("ARDA_VERIFIER_ID") or "arda-phase4-remote-verifier"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "signed_verdicts_enabled": signer_status["enabled"],
                "signer": signer_status,
            },
            "trust_summary": {
                "local_attestation_passed": gate.get("local_attestation_passed"),
                "externally_verifiable_attestation": gate.get("externally_verifiable_attestation"),
                "production_ready": gate.get("production_ready"),
                "attestation_envelope": {
                    "algorithm": gate.get("attestation_envelope_trust", {}).get("algorithm"),
                    "verification_mode": gate.get("attestation_envelope_trust", {}).get("verification_mode"),
                    "externally_verifiable": gate.get("attestation_envelope_trust", {}).get("externally_verifiable"),
                    "transparency_integrated": gate.get("attestation_envelope_trust", {}).get("transparency_integrated"),
                    "trust_mode": gate.get("attestation_envelope_trust", {}).get("trust_mode"),
                },
                "tpm_identity": gate.get("local_evidence", {}).get("tpm_identity"),
            },
            "gate": gate,
            "signed_verdict": signed_verdict,
            "transparency_receipt": transparency_receipt,
        }
    finally:
        service.shutdown()
