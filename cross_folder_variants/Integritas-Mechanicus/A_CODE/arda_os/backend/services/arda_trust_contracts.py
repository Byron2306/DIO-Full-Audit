"""Versioned, fail-closed contracts for ARDA evidence and appraisal.

This module is intentionally independent from the legacy attestation models.
It gives the hardening track a narrow boundary that cannot accept a bare
``is_attested`` or ``lawful`` boolean as evidence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple


class EvidenceMode(str, Enum):
    SIMULATED = "simulated"
    SYNTHETIC = "synthetic"
    OBSERVED = "observed"
    ENFORCED = "enforced"


class AttestationStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def sha256_digest(value: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def parse_utc(value: str) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class ArdaEvidenceBundleV1:
    bundle_id: str
    issuer: str
    environment: str
    evidence_mode: EvidenceMode
    subject_node_id: str
    subject_workload_digest: str
    subject_configuration_digest: str
    audience: Tuple[str, ...]
    nonce: str
    verifier_session_id: str
    issued_at: str
    expires_at: str
    attestation_key_id: str
    quote: str
    quote_signature: str
    pcr_bank: str
    pcr_selection: Tuple[int, ...]
    pcr_values: Mapping[int, str]
    secure_boot_enabled: bool
    event_log_digest: str
    event_log: Tuple[Mapping[str, Any], ...]
    formation_manifest_digest: str
    covenant_digest: str
    boot_id: str
    governance_epoch: str
    replay_counter: int
    collector_errors: Tuple[str, ...] = ()
    optional_evidence_gaps: Tuple[str, ...] = ()
    signature_algorithm: str = ""
    signature: str = ""
    verification_material: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = "1.0"
    beast_object_type: str = "arda_evidence_bundle"

    def unsigned_payload(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["evidence_mode"] = self.evidence_mode.value
        payload.pop("signature", None)
        return payload

    def evidence_digest(self) -> str:
        return sha256_digest(self.unsigned_payload())

    def validate_shape(self) -> None:
        if self.schema_version != "1.0":
            raise ValueError("unsupported ARDA evidence schema version")
        required = {
            "bundle_id": self.bundle_id,
            "issuer": self.issuer,
            "environment": self.environment,
            "subject_node_id": self.subject_node_id,
            "subject_workload_digest": self.subject_workload_digest,
            "audience": self.audience,
            "nonce": self.nonce,
            "verifier_session_id": self.verifier_session_id,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "attestation_key_id": self.attestation_key_id,
            "quote": self.quote,
            "quote_signature": self.quote_signature,
            "pcr_bank": self.pcr_bank,
            "pcr_selection": self.pcr_selection,
            "pcr_values": self.pcr_values,
            "event_log_digest": self.event_log_digest,
            "formation_manifest_digest": self.formation_manifest_digest,
            "covenant_digest": self.covenant_digest,
            "boot_id": self.boot_id,
            "governance_epoch": self.governance_epoch,
            "signature_algorithm": self.signature_algorithm,
            "signature": self.signature,
        }
        missing = [name for name, value in required.items() if value in (None, "", (), {})]
        if missing:
            raise ValueError("missing ARDA evidence fields: " + ",".join(sorted(missing)))
        if self.replay_counter < 0:
            raise ValueError("replay counter must be non-negative")
        if not self.subject_workload_digest.startswith("sha256:"):
            raise ValueError("workload identity must be a sha256 digest")
        parse_utc(self.issued_at)
        parse_utc(self.expires_at)


@dataclass(frozen=True)
class ArdaVerificationPolicyV1:
    policy_id: str
    environment: str
    expected_audience: str
    trusted_evidence_issuers: Tuple[str, ...]
    trusted_attestation_keys: Tuple[str, ...]
    allowed_evidence_modes: Tuple[EvidenceMode, ...]
    allowed_pcr_banks: Tuple[str, ...]
    required_pcrs: Tuple[int, ...]
    accepted_pcr_values: Mapping[int, Tuple[str, ...]]
    expected_workload_digest: str
    expected_configuration_digest: Optional[str] = None
    require_secure_boot: bool = True
    require_event_log: bool = True
    maximum_age_seconds: int = 300
    schema_version: str = "1.0"
    beast_object_type: str = "arda_verification_policy"

    def validate_shape(self) -> None:
        if self.schema_version != "1.0":
            raise ValueError("unsupported ARDA verification policy version")
        if not self.policy_id or not self.environment or not self.expected_audience:
            raise ValueError("policy identity, environment, and audience are required")
        if not self.trusted_evidence_issuers or not self.trusted_attestation_keys:
            raise ValueError("policy requires explicit issuer and attestation-key trust roots")
        if not self.allowed_evidence_modes:
            raise ValueError("policy requires explicit evidence modes")
        if self.maximum_age_seconds <= 0:
            raise ValueError("maximum evidence age must be positive")
        if not self.expected_workload_digest.startswith("sha256:"):
            raise ValueError("policy workload identity must be a sha256 digest")


@dataclass(frozen=True)
class ArdaAttestationResultV1:
    result_id: str
    issuer: str
    policy_id: str
    status: AttestationStatus
    issued_at: str
    expires_at: str
    subject_node_id: str
    subject_workload_digest: str
    evidence_bundle_id: str
    evidence_digest: str
    nonce: str
    environment: str
    audience: str
    assurance_class: str
    evidence_mode: EvidenceMode
    checks: Mapping[str, bool]
    hard_failures: Tuple[str, ...]
    warnings: Tuple[str, ...]
    signature_algorithm: str
    signature: str
    verification_material: Mapping[str, Any]
    schema_version: str = "1.0"
    beast_object_type: str = "arda_attestation_result"

    def unsigned_payload(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["evidence_mode"] = self.evidence_mode.value
        payload.pop("signature", None)
        return payload

    @property
    def accepted(self) -> bool:
        return self.status is AttestationStatus.ACCEPTED and not self.hard_failures


@dataclass(frozen=True)
class BeastAuthorityRequestV1:
    request_id: str
    mission_id: str
    workspace_id: str
    sourceplan_id: str
    actor_id: str
    capability: str
    consequence_class: str
    source_digest: str
    artifact_digest: str
    workload_digest: str
    configuration_digest: str
    target_environment: str
    target_node_id: str
    route_scope: Tuple[str, ...]
    output_scope: Tuple[str, ...]
    data_classifications: Tuple[str, ...]
    resource_ceiling: Mapping[str, Any]
    network_policy_id: str
    approval_receipt_ids: Tuple[str, ...]
    beast_policy_generation: str
    evidence_root: str
    audience: str
    nonce: str
    issued_at: str
    expires_at: str
    request_digest: str = ""
    schema_version: str = "1.0"
    beast_object_type: str = "beast_authority_request"

    def canonical_payload(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload.pop("request_digest", None)
        return payload

    def computed_digest(self) -> str:
        return sha256_digest(self.canonical_payload())

    def validate_shape(self) -> None:
        if self.schema_version != "1.0":
            raise ValueError("unsupported BEAST authority request version")
        required = (
            self.request_id,
            self.mission_id,
            self.workspace_id,
            self.sourceplan_id,
            self.actor_id,
            self.capability,
            self.consequence_class,
            self.workload_digest,
            self.configuration_digest,
            self.target_environment,
            self.network_policy_id,
            self.beast_policy_generation,
            self.evidence_root,
            self.audience,
            self.nonce,
        )
        if any(not value for value in required):
            raise ValueError("BEAST authority request has missing required fields")
        if self.request_digest and self.request_digest != self.computed_digest():
            raise ValueError("BEAST authority request digest mismatch")
        if parse_utc(self.issued_at) >= parse_utc(self.expires_at):
            raise ValueError("BEAST authority request validity window is invalid")


@dataclass(frozen=True)
class BeastCapabilityLeaseV1:
    lease_id: str
    authority_request_id: str
    authority_request_digest: str
    principal_id: str
    mission_id: str
    workspace_id: str
    node_id: str
    workload_digest: str
    attestation_result_id: str
    attestation_evidence_digest: str
    capability: str
    parameters_digest: str
    data_scope: Tuple[str, ...]
    route_scope: Tuple[str, ...]
    output_scope: Tuple[str, ...]
    resource_ceiling: Mapping[str, Any]
    consequence_ceiling: str
    policy_generation: str
    approval_receipt_ids: Tuple[str, ...]
    audience: str
    nonce: str
    issued_at: str
    expires_at: str
    maximum_uses: int
    revocation_epoch: int
    signature_algorithm: str
    signature: str
    verification_material: Mapping[str, Any]
    schema_version: str = "1.0"
    beast_object_type: str = "beast_capability_lease"

    def unsigned_payload(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload.pop("signature", None)
        return payload

    def validate_shape(self) -> None:
        if self.schema_version != "1.0":
            raise ValueError("unsupported BEAST capability lease version")
        if self.maximum_uses <= 0 or self.revocation_epoch < 0:
            raise ValueError("capability lease use/revocation bounds are invalid")
        if not self.signature or not self.signature_algorithm:
            raise ValueError("capability lease must be signed")
        if parse_utc(self.issued_at) >= parse_utc(self.expires_at):
            raise ValueError("capability lease validity window is invalid")


@dataclass(frozen=True)
class MetatronOutboundDecisionV1:
    decision_id: str
    queue_id: str
    action_id: str
    request_digest: str
    normalized_action: str
    canonical_target: str
    capability_lease_id: str
    attestation_result_id: str
    governance_epoch: str
    notation_token_id: str
    score_id: str
    world_state_hash: str
    manifold_digest: str
    checks: Mapping[str, bool]
    hard_vetoes: Tuple[str, ...]
    approval_receipt_ids: Tuple[str, ...]
    break_glass_receipt_id: Optional[str]
    status: str
    policy_version: str
    audience: str
    issued_at: str
    expires_at: str
    maximum_uses: int
    evidence_root: str
    signature_algorithm: str
    signature: str
    verification_material: Mapping[str, Any]
    schema_version: str = "1.0"
    beast_object_type: str = "metatron_outbound_decision"

    def unsigned_payload(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload.pop("signature", None)
        return payload

    @property
    def approved(self) -> bool:
        return self.status == "approved" and not self.hard_vetoes and all(self.checks.values())

    def validate_shape(self) -> None:
        if self.schema_version != "1.0":
            raise ValueError("unsupported Metatron outbound decision version")
        if self.status not in {"approved", "denied", "pending"}:
            raise ValueError("invalid Metatron decision status")
        if self.maximum_uses != 1:
            raise ValueError("outbound decisions must be single-use")
        if self.status == "approved" and not self.approved:
            raise ValueError("approved decision contains a failed check or hard veto")
        if not self.signature or not self.signature_algorithm:
            raise ValueError("outbound decision must be signed")
        if parse_utc(self.issued_at) >= parse_utc(self.expires_at):
            raise ValueError("outbound decision validity window is invalid")


def normalize_pcr_values(values: Mapping[Any, Any]) -> Dict[int, str]:
    return {int(index): str(value).lower() for index, value in values.items()}


def evidence_modes(values: Iterable[EvidenceMode]) -> Tuple[str, ...]:
    return tuple(value.value for value in values)
