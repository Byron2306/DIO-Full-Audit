"""MA6 recovery/rejoin authorization and live-proof import.

The existing Docker/WireGuard/nftables harness remains native observed
evidence.  Production rejoin authority is issued only from fresh, independently
verified, quorum-bound inputs and is replay-safe.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence, Tuple

from backend.services.arda_trust_contracts import (
    ArdaAttestationResultV1,
    AttestationStatus,
    BeastCapabilityLeaseV1,
    EvidenceMode,
    canonical_json_bytes,
    parse_utc,
    sha256_digest,
)


class RecoveryError(RuntimeError):
    pass


class RecoverySignatureVerifier(Protocol):
    def verify(self, payload: bytes, signature: str, algorithm: str, material: Mapping[str, Any]) -> bool: ...


class RecoveryResultSigner(Protocol):
    def sign(self, payload: bytes) -> Tuple[str, str, Mapping[str, Any]]: ...


@dataclass(frozen=True)
class RecoveryWitnessVoteV1:
    vote_id: str
    witness_node_id: str
    target_node_id: str
    session_id: str
    nonce: str
    quorum_epoch: int
    governance_epoch: str
    attestation_evidence_digest: str
    decision: str
    issued_at: str
    expires_at: str
    signature_algorithm: str
    signature: str
    verification_material: Mapping[str, Any]

    def unsigned_payload(self) -> Mapping[str, Any]:
        value = asdict(self)
        value.pop("signature", None)
        return value


@dataclass(frozen=True)
class RecoveryRequestV1:
    request_id: str
    session_id: str
    target_node_id: str
    isolation_receipt_digest: str
    attestation_result_id: str
    attestation_evidence_digest: str
    capability_lease_id: str
    governance_epoch: str
    world_state_hash: str
    quorum_epoch: int
    policy_generation: str
    nonce: str
    audience: str
    issued_at: str
    expires_at: str
    witness_votes: Tuple[RecoveryWitnessVoteV1, ...]
    signature_algorithm: str
    signature: str
    verification_material: Mapping[str, Any]

    def unsigned_payload(self) -> Mapping[str, Any]:
        value = asdict(self)
        value["witness_votes"] = [vote.unsigned_payload() | {"signature": vote.signature} for vote in self.witness_votes]
        value.pop("signature", None)
        return value


@dataclass(frozen=True)
class RecoveryAuthorizationV1:
    authorization_id: str
    request_id: str
    session_id: str
    target_node_id: str
    attestation_result_id: str
    capability_lease_id: str
    quorum_epoch: int
    governance_epoch: str
    witness_vote_ids: Tuple[str, ...]
    issued_at: str
    expires_at: str
    audience: str
    status: str
    checks: Mapping[str, bool]
    signature_algorithm: str
    signature: str
    verification_material: Mapping[str, Any]

    def unsigned_payload(self) -> Mapping[str, Any]:
        value = asdict(self)
        value.pop("signature", None)
        # Result signing metadata is returned by the signer.  Excluding it
        # keeps the payload identical before and after that metadata is known.
        value.pop("signature_algorithm", None)
        value.pop("verification_material", None)
        return value


def _is_sha256_digest(value: str) -> bool:
    return bool(re.fullmatch(r"sha256:[0-9a-f]{64}", str(value or "")))


class RecoveryReplayStore:
    def __init__(self, path: str) -> None:
        # FastAPI may dispatch concurrent recovery requests across worker
        # threads.  Keep the single connection safe and preserve the atomic
        # BEGIN IMMEDIATE consume operation.
        self._db = sqlite3.connect(
            path, isolation_level=None, timeout=10.0, check_same_thread=False
        )
        self._lock = threading.RLock()
        self._db.execute("PRAGMA busy_timeout=10000")
        for _ in range(100):
            try:
                self._db.execute("PRAGMA journal_mode=WAL")
                break
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() or _ == 99:
                    raise
                time.sleep(0.01)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS recovery_replay("
            "nonce TEXT PRIMARY KEY, request_id TEXT NOT NULL, consumed_at TEXT NOT NULL, "
            "capability_lease_id TEXT)"
        )
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(recovery_replay)")}
        if "capability_lease_id" not in columns:
            self._db.execute("ALTER TABLE recovery_replay ADD COLUMN capability_lease_id TEXT")
        self._db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS recovery_capability_once "
            "ON recovery_replay(capability_lease_id) WHERE capability_lease_id IS NOT NULL"
        )

    def consume(
        self, nonce: str, request_id: str, capability_lease_id: str, now: datetime
    ) -> None:
        with self._lock:
            try:
                self._db.execute("BEGIN IMMEDIATE")
                self._db.execute(
                    "INSERT INTO recovery_replay("
                    "nonce,request_id,consumed_at,capability_lease_id) VALUES(?,?,?,?)",
                    (nonce, request_id, now.isoformat(), capability_lease_id),
                )
                self._db.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                self._db.execute("ROLLBACK")
                raise RecoveryError("recovery nonce or capability lease was already consumed") from exc


class StrictRecoveryCoordinator:
    def __init__(
        self,
        *,
        request_verifier: RecoverySignatureVerifier,
        witness_verifier: RecoverySignatureVerifier,
        attestation_verifier: RecoverySignatureVerifier,
        capability_verifier: RecoverySignatureVerifier,
        signer: RecoveryResultSigner,
        replay_store: RecoveryReplayStore,
        environment: str,
        audience: str = "arda-recovery-coordinator",
        minimum_witnesses: int = 2,
        maximum_age_seconds: int = 300,
    ) -> None:
        self._requests = request_verifier
        self._witnesses = witness_verifier
        self._attestations = attestation_verifier
        self._capabilities = capability_verifier
        self._signer = signer
        self._replay = replay_store
        self._environment = environment
        self._audience = audience
        self._minimum_witnesses = minimum_witnesses
        self._maximum_age = maximum_age_seconds

    def authorize(
        self,
        request: RecoveryRequestV1,
        attestation: ArdaAttestationResultV1,
        capability: BeastCapabilityLeaseV1,
        *,
        isolated_node_ids: Sequence[str],
        compromised_node_ids: Sequence[str],
        active_governance_epoch: str,
        active_world_state_hash: str,
        active_quorum_epoch: int,
        active_revocation_epoch: int,
        now: datetime | None = None,
    ) -> RecoveryAuthorizationV1:
        instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        checks: dict[str, bool] = {}
        checks["target_isolated"] = request.target_node_id in set(isolated_node_ids)
        checks["target_not_witness"] = all(
            vote.witness_node_id != request.target_node_id for vote in request.witness_votes
        )
        checks["request_audience"] = request.audience == self._audience
        issued, expires = parse_utc(request.issued_at), parse_utc(request.expires_at)
        checks["request_fresh"] = (
            issued <= instant < expires
            and (instant - issued).total_seconds() <= self._maximum_age
        )
        checks["request_signature"] = self._requests.verify(
            canonical_json_bytes(request.unsigned_payload()),
            request.signature,
            request.signature_algorithm,
            request.verification_material,
        )
        checks["attestation_accepted"] = (
            attestation.status is AttestationStatus.ACCEPTED
            and attestation.accepted
            and attestation.environment == self._environment
            and attestation.audience == self._audience
            and instant < parse_utc(attestation.expires_at)
        )
        checks["attestation_binding"] = (
            request.attestation_result_id == attestation.result_id
            and request.attestation_evidence_digest == attestation.evidence_digest
            and request.target_node_id == attestation.subject_node_id
        )
        checks["attestation_signature"] = self._attestations.verify(
            canonical_json_bytes(attestation.unsigned_payload()),
            attestation.signature,
            attestation.signature_algorithm,
            attestation.verification_material,
        )
        checks["governance_epoch"] = request.governance_epoch == active_governance_epoch
        checks["world_state_hash"] = request.world_state_hash == active_world_state_hash
        checks["quorum_epoch"] = request.quorum_epoch == active_quorum_epoch
        checks["isolation_receipt"] = _is_sha256_digest(request.isolation_receipt_digest)
        capability_issued = parse_utc(capability.issued_at)
        capability_expires = parse_utc(capability.expires_at)
        checks["capability_fresh"] = capability_issued <= instant < capability_expires
        checks["capability_binding"] = (
            request.capability_lease_id == capability.lease_id
            and request.target_node_id == capability.node_id
            and request.attestation_result_id == capability.attestation_result_id
            and request.attestation_evidence_digest == capability.attestation_evidence_digest
            and capability.capability in {"arda.recover", "arda.rejoin"}
            and capability.audience == self._audience
            and capability.maximum_uses == 1
        )
        checks["capability_revocation_epoch"] = (
            capability.revocation_epoch >= active_revocation_epoch
        )
        checks["capability_signature"] = self._capabilities.verify(
            canonical_json_bytes(capability.unsigned_payload()),
            capability.signature,
            capability.signature_algorithm,
            capability.verification_material,
        )

        compromised = set(compromised_node_ids)
        distinct_witnesses = set()
        votes_valid = True
        for vote in request.witness_votes:
            vote_issued, vote_expires = parse_utc(vote.issued_at), parse_utc(vote.expires_at)
            bound = (
                vote.target_node_id == request.target_node_id
                and vote.session_id == request.session_id
                and vote.nonce == request.nonce
                and vote.quorum_epoch == request.quorum_epoch
                and vote.governance_epoch == request.governance_epoch
                and vote.attestation_evidence_digest == request.attestation_evidence_digest
                and vote.decision == "recover"
                and vote.witness_node_id not in compromised
                and vote_issued <= instant < vote_expires
            )
            signed = self._witnesses.verify(
                canonical_json_bytes(vote.unsigned_payload()),
                vote.signature,
                vote.signature_algorithm,
                vote.verification_material,
            )
            votes_valid = votes_valid and bound and signed
            if bound and signed:
                distinct_witnesses.add(vote.witness_node_id)
        checks["witness_votes_valid"] = votes_valid
        checks["witness_quorum"] = len(distinct_witnesses) >= self._minimum_witnesses

        failures = tuple(name for name, passed in checks.items() if not passed)
        if failures:
            raise RecoveryError("recovery authorization veto: " + ",".join(failures))
        self._replay.consume(
            request.nonce, request.request_id, capability.lease_id, instant
        )

        unsigned = RecoveryAuthorizationV1(
            authorization_id="recovery:" + hashlib.sha256(
                canonical_json_bytes(request.unsigned_payload())
            ).hexdigest()[:24],
            request_id=request.request_id,
            session_id=request.session_id,
            target_node_id=request.target_node_id,
            attestation_result_id=attestation.result_id,
            capability_lease_id=request.capability_lease_id,
            quorum_epoch=request.quorum_epoch,
            governance_epoch=request.governance_epoch,
            witness_vote_ids=tuple(vote.vote_id for vote in request.witness_votes),
            issued_at=instant.isoformat(),
            expires_at=min(expires, parse_utc(attestation.expires_at), capability_expires).isoformat(),
            audience="arda-recovery-actuator",
            status="authorized",
            checks=checks,
            signature_algorithm="pending",
            signature="",
            verification_material={},
        )
        algorithm, signature, material = self._signer.sign(
            canonical_json_bytes(unsigned.unsigned_payload())
        )
        return RecoveryAuthorizationV1(
            **(asdict(unsigned) | {
                "signature_algorithm": algorithm,
                "signature": signature,
                "verification_material": material,
            })
        )


class LiveRecoveryProofImporter:
    REQUIRED_ASSERTIONS = (
        "node_is_isolated",
        "protected_asset_blocked_during_isolation",
        "remediation_endpoint_allowed_during_isolation",
        "bad_quorum_vote_rejected",
        "bad_recovery_witness_rejected",
        "lawful_witness_accepted",
        "node_re_admitted",
        "quorum_returns_lawful",
        "recovery_recorded_in_ledger",
        "wireguard_allowedips_restricted_during_isolation",
        "wireguard_allowedips_restored_after_recovery",
        "network_routes_restored_after_recovery",
    )

    def import_bundle(self, root: Path) -> Mapping[str, Any]:
        manifest_path = root / "00_manifest.json"
        assertions_path = root / "assertions.json"
        if not manifest_path.is_file() or not assertions_path.is_file():
            raise RecoveryError("live recovery proof bundle is incomplete")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assertions = json.loads(assertions_path.read_text(encoding="utf-8"))
        missing = [name for name in self.REQUIRED_ASSERTIONS if assertions.get(name) is not True]
        if missing:
            raise RecoveryError("live recovery proof assertions failed: " + ",".join(missing))
        file_digests = {}
        for path in sorted(root.iterdir()):
            if path.is_file():
                file_digests[path.name] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        return {
            "schema": "arda_live_recovery_import.v1",
            "evidence_mode": EvidenceMode.OBSERVED.value,
            "production_authority": False,
            "session_id": manifest.get("session_id"),
            "bundle_digest": sha256_digest(file_digests),
            "assertions": {name: True for name in self.REQUIRED_ASSERTIONS},
            "file_digests": file_digests,
            "limitations": (
                "lab_hmac_recovery_proof",
                "controller_credential_defaults_possible",
                "import_is_evidence_not_rejoin_authority",
            ),
        }
