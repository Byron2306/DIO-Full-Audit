"""Strict ARDA verifier.

The verifier has no permissive cryptographic defaults. Quote verification,
envelope verification, event-log appraisal, result signing, and replay state
are explicit injected dependencies. A dependency failure is a hard failure.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Mapping, Protocol, Tuple

from backend.services.arda_trust_contracts import (
    ArdaAttestationResultV1,
    ArdaEvidenceBundleV1,
    ArdaVerificationPolicyV1,
    AttestationStatus,
    EvidenceMode,
    normalize_pcr_values,
    parse_utc,
)


class EvidenceSignatureVerifier(Protocol):
    def verify(self, bundle: ArdaEvidenceBundleV1) -> bool: ...


class TpmQuoteVerifier(Protocol):
    def verify(
        self,
        *,
        attestation_key_id: str,
        quote: str,
        signature: str,
        nonce: str,
        pcr_bank: str,
        pcr_selection: Tuple[int, ...],
        pcr_values: Mapping[int, str],
    ) -> bool: ...


class EventLogAppraiser(Protocol):
    def verify(
        self,
        *,
        event_log: Tuple[Mapping[str, Any], ...],
        claimed_digest: str,
        pcr_bank: str,
        pcr_values: Mapping[int, str],
    ) -> bool: ...


class AttestationResultSigner(Protocol):
    @property
    def issuer(self) -> str: ...

    def sign(self, payload: Mapping[str, Any]) -> Mapping[str, Any]: ...


class ReplayStore(Protocol):
    def consume(self, *, issuer: str, nonce: str, counter: int, expires_at: datetime) -> bool: ...


class InMemoryReplayStore:
    """Atomic process-local replay protection for tests and single-process use."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._nonces: Dict[Tuple[str, str], datetime] = {}
        self._counters: Dict[str, int] = {}

    def consume(self, *, issuer: str, nonce: str, counter: int, expires_at: datetime) -> bool:
        now = datetime.now(timezone.utc)
        key = (issuer, nonce)
        with self._lock:
            self._nonces = {
                stored_key: expiry
                for stored_key, expiry in self._nonces.items()
                if expiry > now
            }
            if key in self._nonces:
                return False
            previous_counter = self._counters.get(issuer, -1)
            if counter <= previous_counter:
                return False
            self._nonces[key] = expires_at
            self._counters[issuer] = counter
            return True


@dataclass(frozen=True)
class VerificationContext:
    expected_nonce: str
    now: datetime


class StrictArdaAttestationVerifier:
    def __init__(
        self,
        *,
        evidence_signature_verifier: EvidenceSignatureVerifier,
        quote_verifier: TpmQuoteVerifier,
        event_log_appraiser: EventLogAppraiser,
        result_signer: AttestationResultSigner,
        replay_store: ReplayStore,
    ) -> None:
        self.evidence_signature_verifier = evidence_signature_verifier
        self.quote_verifier = quote_verifier
        self.event_log_appraiser = event_log_appraiser
        self.result_signer = result_signer
        self.replay_store = replay_store

    def verify(
        self,
        bundle: ArdaEvidenceBundleV1,
        policy: ArdaVerificationPolicyV1,
        *,
        expected_nonce: str,
        now: datetime | None = None,
    ) -> ArdaAttestationResultV1:
        policy.validate_shape()
        checks: Dict[str, bool] = {}
        failures = []
        warnings = list(bundle.optional_evidence_gaps)
        instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

        try:
            bundle.validate_shape()
            checks["shape_valid"] = True
        except Exception as exc:
            checks["shape_valid"] = False
            failures.append(f"shape_invalid:{type(exc).__name__}")

        issued_at = self._timestamp(bundle.issued_at, "issued_at", failures)
        expires_at = self._timestamp(bundle.expires_at, "expires_at", failures)

        self._check(checks, failures, "issuer_trusted", bundle.issuer in policy.trusted_evidence_issuers)
        self._check(checks, failures, "environment_match", bundle.environment == policy.environment)
        self._check(checks, failures, "audience_match", policy.expected_audience in bundle.audience)
        self._check(checks, failures, "nonce_match", bool(expected_nonce) and bundle.nonce == expected_nonce)
        self._check(checks, failures, "evidence_mode_allowed", bundle.evidence_mode in policy.allowed_evidence_modes)
        self._check(checks, failures, "attestation_key_trusted", bundle.attestation_key_id in policy.trusted_attestation_keys)
        self._check(checks, failures, "pcr_bank_allowed", bundle.pcr_bank in policy.allowed_pcr_banks)
        self._check(
            checks,
            failures,
            "pcr_selection_complete",
            set(policy.required_pcrs).issubset(set(bundle.pcr_selection)),
        )
        self._check(
            checks,
            failures,
            "workload_digest_match",
            bundle.subject_workload_digest == policy.expected_workload_digest,
        )
        config_match = (
            policy.expected_configuration_digest is None
            or bundle.subject_configuration_digest == policy.expected_configuration_digest
        )
        self._check(checks, failures, "configuration_digest_match", config_match)
        self._check(
            checks,
            failures,
            "secure_boot_accepted",
            (not policy.require_secure_boot) or bundle.secure_boot_enabled is True,
        )
        self._check(checks, failures, "required_collectors_succeeded", not bundle.collector_errors)

        fresh = bool(
            issued_at
            and expires_at
            and issued_at <= instant < expires_at
            and (instant - issued_at).total_seconds() <= policy.maximum_age_seconds
        )
        self._check(checks, failures, "freshness_valid", fresh)

        normalized_values = normalize_pcr_values(bundle.pcr_values)
        pcr_baselines_match = all(
            index in normalized_values
            and normalized_values[index] in {value.lower() for value in accepted}
            for index, accepted in policy.accepted_pcr_values.items()
        )
        self._check(checks, failures, "pcr_baselines_match", pcr_baselines_match)

        signature_valid = self._safe_call(
            lambda: self.evidence_signature_verifier.verify(bundle)
        )
        self._check(checks, failures, "evidence_signature_valid", signature_valid)

        quote_valid = self._safe_call(
            lambda: self.quote_verifier.verify(
                attestation_key_id=bundle.attestation_key_id,
                quote=bundle.quote,
                signature=bundle.quote_signature,
                nonce=bundle.nonce,
                pcr_bank=bundle.pcr_bank,
                pcr_selection=bundle.pcr_selection,
                pcr_values=normalized_values,
            )
        )
        self._check(checks, failures, "quote_valid", quote_valid)

        event_log_valid = (not policy.require_event_log) or self._safe_call(
            lambda: self.event_log_appraiser.verify(
                event_log=bundle.event_log,
                claimed_digest=bundle.event_log_digest,
                pcr_bank=bundle.pcr_bank,
                pcr_values=normalized_values,
            )
        )
        self._check(checks, failures, "event_log_valid", event_log_valid)

        replay_valid = bool(
            expires_at
            and self._safe_call(
                lambda: self.replay_store.consume(
                    issuer=bundle.issuer,
                    nonce=bundle.nonce,
                    counter=bundle.replay_counter,
                    expires_at=expires_at,
                )
            )
        )
        self._check(checks, failures, "replay_state_valid", replay_valid)

        status = AttestationStatus.ACCEPTED if not failures else AttestationStatus.REJECTED
        result_expiry = min(
            expires_at or instant,
            instant + timedelta(seconds=policy.maximum_age_seconds),
        )
        unsigned = {
            "result_id": f"arda-result-{uuid.uuid4().hex}",
            "issuer": self.result_signer.issuer,
            "policy_id": policy.policy_id,
            "status": status.value,
            "issued_at": instant.isoformat(),
            "expires_at": result_expiry.isoformat(),
            "subject_node_id": bundle.subject_node_id,
            "subject_workload_digest": bundle.subject_workload_digest,
            "evidence_bundle_id": bundle.bundle_id,
            "evidence_digest": bundle.evidence_digest(),
            "nonce": bundle.nonce,
            "environment": bundle.environment,
            "audience": policy.expected_audience,
            "assurance_class": "hardware_attested" if status is AttestationStatus.ACCEPTED else "rejected",
            "evidence_mode": bundle.evidence_mode.value,
            "checks": checks,
            "hard_failures": tuple(failures),
            "warnings": tuple(warnings),
            "schema_version": "1.0",
            "beast_object_type": "arda_attestation_result",
        }
        signature = self.result_signer.sign(unsigned)
        return ArdaAttestationResultV1(
            **{key: value for key, value in unsigned.items() if key not in {"status", "evidence_mode"}},
            status=status,
            evidence_mode=bundle.evidence_mode,
            signature_algorithm=str(signature.get("algorithm") or ""),
            signature=str(signature.get("signature") or ""),
            verification_material=dict(signature.get("verification_material") or {}),
        )

    @staticmethod
    def _check(checks: Dict[str, bool], failures: list[str], name: str, value: bool) -> None:
        checks[name] = bool(value)
        if not value:
            failures.append(name)

    @staticmethod
    def _timestamp(raw: str, name: str, failures: list[str]) -> datetime | None:
        try:
            return parse_utc(raw)
        except Exception:
            failures.append(f"{name}_invalid")
            return None

    @staticmethod
    def _safe_call(operation: Any) -> bool:
        try:
            return operation() is True
        except Exception:
            return False
