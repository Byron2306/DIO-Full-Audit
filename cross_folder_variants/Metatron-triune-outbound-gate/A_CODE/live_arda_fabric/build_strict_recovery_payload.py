"""Build a signed validation recovery payload for the live controller."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from dataclasses import replace, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# The runner invokes this file by absolute path from an evidence directory.
# Make the repository root importable regardless of the caller's cwd.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from cryptography.hazmat.primitives import serialization
from backend.services.arda_recovery_conformance import (
    RecoveryRequestV1,
    RecoveryWitnessVoteV1,
)
from backend.services.arda_trust_contracts import (
    ArdaAttestationResultV1,
    AttestationStatus,
    BeastCapabilityLeaseV1,
    EvidenceMode,
    canonical_json_bytes,
)


def _key(path: str):
    return serialization.load_pem_private_key(Path(path).read_bytes(), password=None)


def _sign(value, path: str, key_id: str):
    prepared = replace(
        value,
        signature_algorithm="ed25519",
        signature="",
        verification_material={"key_id": key_id},
    )
    signature = base64.b64encode(
        _key(path).sign(canonical_json_bytes(prepared.unsigned_payload()))
    ).decode("ascii")
    return replace(prepared, signature=signature)


def main() -> None:
    if len(sys.argv) != 6:
        raise SystemExit("usage: builder SESSION TARGET ISOLATION_RECEIPT STATE_JSON OUTPUT")
    session_id, target, isolation_receipt, state_path, output_path = sys.argv[1:]
    state = json.loads(Path(state_path).read_text())
    now = datetime.now(timezone.utc)
    issued = now - timedelta(seconds=2)
    expires = now + timedelta(minutes=2)
    nonce = os.urandom(16).hex()
    evidence_digest = "sha256:" + hashlib.sha256(
        f"{session_id}|{target}|{nonce}".encode()
    ).hexdigest()
    world_material = {
        "isolated": sorted(state.get("isolated", state.get("isolated_nodes", []))),
        "compromised": sorted(state.get("compromised", state.get("compromised_nodes", []))),
        "quorum_epoch": state["quorum_epoch"],
    }
    world_hash = "sha256:" + hashlib.sha256(
        json.dumps(world_material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    witness_values = []
    for witness in ("node-b-witness", "node-c-quorum"):
        witness_values.append(RecoveryWitnessVoteV1(
            vote_id=f"{session_id}:{witness}", witness_node_id=witness,
            target_node_id=target, session_id=session_id, nonce=nonce,
            quorum_epoch=state["quorum_epoch"], governance_epoch=os.environ.get("ARDA_GOVERNANCE_EPOCH", "lab-governance-1"),
            attestation_evidence_digest=evidence_digest, decision="recover",
            issued_at=issued.isoformat(), expires_at=expires.isoformat(),
            signature_algorithm="", signature="", verification_material={},
        ))
    witness_values = tuple(_sign(v, os.environ["ARDA_RECOVERY_WITNESS_PRIVATE_KEY"], "recovery-witness") for v in witness_values)
    attestation = ArdaAttestationResultV1(
        result_id=f"{session_id}:attestation", issuer="arda-verifier",
        policy_id="production-recovery", status=AttestationStatus.ACCEPTED,
        issued_at=issued.isoformat(), expires_at=expires.isoformat(),
        subject_node_id=target, subject_workload_digest=evidence_digest,
        evidence_bundle_id=f"{session_id}:bundle", evidence_digest=evidence_digest,
        nonce=nonce, environment="production", audience="arda-recovery-coordinator",
        assurance_class="hardware-attested", evidence_mode=EvidenceMode.ENFORCED,
        checks={"quote": True}, hard_failures=(), warnings=(), signature_algorithm="",
        signature="", verification_material={},
    )
    attestation = _sign(attestation, os.environ["ARDA_RECOVERY_ATTESTATION_PRIVATE_KEY"], "arda-verifier")
    capability = BeastCapabilityLeaseV1(
        lease_id=f"{session_id}:lease", authority_request_id=f"{session_id}:authority",
        authority_request_digest=evidence_digest, principal_id="validation-operator",
        mission_id=session_id, workspace_id="arda-fabric", node_id=target,
        workload_digest=evidence_digest, attestation_result_id=attestation.result_id,
        attestation_evidence_digest=attestation.evidence_digest, capability="arda.rejoin",
        parameters_digest=evidence_digest, data_scope=(), route_scope=("recovery",),
        output_scope=(target,), resource_ceiling={}, consequence_ceiling="critical",
        policy_generation="production-recovery", approval_receipt_ids=(f"{session_id}:approval",),
        audience="arda-recovery-coordinator", nonce=os.urandom(16).hex(),
        issued_at=issued.isoformat(), expires_at=expires.isoformat(), maximum_uses=1,
        revocation_epoch=0, signature_algorithm="", signature="", verification_material={},
    )
    capability = _sign(capability, os.environ["ARDA_RECOVERY_CAPABILITY_PRIVATE_KEY"], "beast-authority")
    request = RecoveryRequestV1(
        request_id=f"{session_id}:request", session_id=session_id, target_node_id=target,
        isolation_receipt_digest=isolation_receipt, attestation_result_id=attestation.result_id,
        attestation_evidence_digest=attestation.evidence_digest, capability_lease_id=capability.lease_id,
        governance_epoch=os.environ.get("ARDA_GOVERNANCE_EPOCH", "lab-governance-1"),
        world_state_hash=world_hash, quorum_epoch=state["quorum_epoch"], policy_generation="production-recovery",
        nonce=nonce, audience="arda-recovery-coordinator", issued_at=issued.isoformat(),
        expires_at=expires.isoformat(), witness_votes=witness_values, signature_algorithm="",
        signature="", verification_material={},
    )
    request = _sign(request, os.environ["ARDA_RECOVERY_REQUEST_PRIVATE_KEY"], "recovery-request")
    payload = {"request": asdict(request), "attestation": asdict(attestation), "capability": asdict(capability)}
    payload["attestation"]["status"] = attestation.status.value
    payload["attestation"]["evidence_mode"] = attestation.evidence_mode.value
    Path(output_path).write_text(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
