"""Live recovery wiring: strict authorization must precede rejoin effects."""

from __future__ import annotations

from dataclasses import dataclass
import base64
import os
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence
from datetime import datetime

from .arda_recovery_conformance import (
    RecoveryAuthorizationV1,
    RecoveryRequestV1,
    RecoveryWitnessVoteV1,
    StrictRecoveryCoordinator,
)
from .arda_trust_contracts import (
    ArdaAttestationResultV1,
    AttestationStatus,
    BeastCapabilityLeaseV1,
    EvidenceMode,
)
from .arda_recovery_conformance import RecoveryReplayStore


class TrustedEd25519Verifier:
    """Verify only against an operator-provisioned PEM trust root."""

    def __init__(self, public_key_path: str, *, key_id: str):
        from cryptography.hazmat.primitives import serialization
        self.key_id = key_id
        self._key = serialization.load_pem_public_key(Path(public_key_path).read_bytes())

    def verify(self, payload, signature, algorithm, material):
        if algorithm != "ed25519" or material.get("key_id") != self.key_id:
            return False
        try:
            self._key.verify(base64.b64decode(signature, validate=True), payload)
            return True
        except Exception:
            return False


class Ed25519RecoverySigner:
    def __init__(self, private_key_path: str, *, key_id: str):
        from cryptography.hazmat.primitives import serialization
        self.key_id = key_id
        self._key = serialization.load_pem_private_key(Path(private_key_path).read_bytes(), password=None)

    def sign(self, payload):
        signature = self._key.sign(payload)
        return "ed25519", base64.b64encode(signature).decode("ascii"), {"key_id": self.key_id}


class RecoveryActuator(Protocol):
    def rejoin(self, authorization: RecoveryAuthorizationV1) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class RecoveryRuntimeState:
    isolated_node_ids: Sequence[str]
    compromised_node_ids: Sequence[str]
    governance_epoch: str
    world_state_hash: str
    quorum_epoch: int
    revocation_epoch: int
    now: datetime | None = None


class StrictRecoveryRuntime:
    def __init__(self, coordinator: StrictRecoveryCoordinator, actuator: RecoveryActuator):
        self._coordinator = coordinator
        self._actuator = actuator

    @staticmethod
    def parse(payload: Mapping[str, Any]):
        request_data = dict(payload["request"])
        request_data["witness_votes"] = tuple(
            RecoveryWitnessVoteV1(**vote) for vote in request_data.get("witness_votes", ())
        )
        request = RecoveryRequestV1(**request_data)
        attestation_data = dict(payload["attestation"])
        attestation_data["status"] = AttestationStatus(attestation_data["status"])
        attestation_data["evidence_mode"] = EvidenceMode(attestation_data["evidence_mode"])
        attestation = ArdaAttestationResultV1(**attestation_data)
        capability_data = dict(payload["capability"])
        for name in ("data_scope", "route_scope", "output_scope", "approval_receipt_ids"):
            capability_data[name] = tuple(capability_data.get(name) or ())
        return request, attestation, BeastCapabilityLeaseV1(**capability_data)

    def recover(
        self, payload: Mapping[str, Any], state: RecoveryRuntimeState
    ) -> Mapping[str, Any]:
        request, attestation, capability = self.parse(payload)
        authorization = self._coordinator.authorize(
            request,
            attestation,
            capability,
            isolated_node_ids=state.isolated_node_ids,
            compromised_node_ids=state.compromised_node_ids,
            active_governance_epoch=state.governance_epoch,
            active_world_state_hash=state.world_state_hash,
            active_quorum_epoch=state.quorum_epoch,
            active_revocation_epoch=state.revocation_epoch,
            now=state.now,
        )
        effect = self._actuator.rejoin(authorization)
        if effect.get("rejoined") is not True:
            raise RuntimeError("recovery actuator did not prove rejoin")
        return {"authorization": authorization, "effect": dict(effect)}


def build_production_recovery_runtime(
    *, replay_database: str, actuator: RecoveryActuator
) -> StrictRecoveryRuntime:
    """Build production runtime only from explicit, provisioned trust roots."""
    required = {
        "request": os.environ.get("ARDA_RECOVERY_REQUEST_PUBLIC_KEY"),
        "witness": os.environ.get("ARDA_RECOVERY_WITNESS_PUBLIC_KEY"),
        "attestation": os.environ.get("ARDA_RECOVERY_ATTESTATION_PUBLIC_KEY"),
        "capability": os.environ.get("ARDA_RECOVERY_CAPABILITY_PUBLIC_KEY"),
        "result_private": os.environ.get("ARDA_RECOVERY_RESULT_PRIVATE_KEY"),
    }
    if any(not path for path in required.values()):
        raise RuntimeError("production recovery trust roots are not fully configured")
    if any(not Path(path).is_file() for path in required.values()):
        raise RuntimeError("production recovery trust root file is missing")
    coordinator = StrictRecoveryCoordinator(
        request_verifier=TrustedEd25519Verifier(required["request"], key_id="recovery-request"),
        witness_verifier=TrustedEd25519Verifier(required["witness"], key_id="recovery-witness"),
        attestation_verifier=TrustedEd25519Verifier(required["attestation"], key_id="arda-verifier"),
        capability_verifier=TrustedEd25519Verifier(required["capability"], key_id="beast-authority"),
        signer=Ed25519RecoverySigner(required["result_private"], key_id="arda-recovery-authority"),
        replay_store=RecoveryReplayStore(replay_database),
        environment="production",
    )
    return StrictRecoveryRuntime(coordinator, actuator)
