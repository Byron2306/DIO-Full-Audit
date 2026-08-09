from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import hmac

import pytest

from backend.services.arda_trust_contracts import BeastCapabilityLeaseV1, canonical_json_bytes
from backend.services.capability_lease_store import SqliteCapabilityLeaseStore
from backend.services.notation_token import NotationTokenService
from backend.services.capability_authority import StrictCapabilityLeaseSignatureVerifier


SECRET = b"notation-capability-test"


class LeaseVerifier:
    def verify(self, lease):
        expected = hmac.new(
            SECRET, canonical_json_bytes(lease.unsigned_payload()), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, lease.signature)


def make_lease(now):
    lease = BeastCapabilityLeaseV1(
        lease_id="lease-notation-1",
        authority_request_id="request-1",
        authority_request_digest="sha256:" + "1" * 64,
        principal_id="operator-1",
        mission_id="mission-1",
        workspace_id="workspace-1",
        node_id="node-1",
        workload_digest="sha256:" + "2" * 64,
        attestation_result_id="result-1",
        attestation_evidence_digest="sha256:" + "3" * 64,
        capability="deploy.release",
        parameters_digest="sha256:" + "4" * 64,
        data_scope=("confidential",),
        route_scope=("production",),
        output_scope=("release",),
        resource_ceiling={"cpu_seconds": 30},
        consequence_ceiling="high",
        policy_generation="policy-7",
        approval_receipt_ids=("approval-1", "approval-2"),
        audience="metatron-outbound-gate",
        nonce="nonce-1",
        issued_at=(now - timedelta(seconds=1)).isoformat(),
        expires_at=(now + timedelta(minutes=2)).isoformat(),
        maximum_uses=1,
        revocation_epoch=0,
        signature_algorithm="test-hmac",
        signature="pending",
        verification_material={"key_id": "test"},
    )
    return replace(
        lease,
        signature=hmac.new(
            SECRET, canonical_json_bytes(lease.unsigned_payload()), hashlib.sha256
        ).hexdigest(),
    )


@pytest.mark.asyncio
async def test_notation_requires_and_preserves_exact_beast_capability_binding(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    lease = make_lease(now)
    store = SqliteCapabilityLeaseStore(tmp_path / "leases.sqlite", signature_verifier=LeaseVerifier())
    store.register(lease)
    service = NotationTokenService()

    monkeypatch.setattr(
        "backend.services.notation_token.quantum_security.sign_notation_token",
        lambda _payload: {"signature_ref": "test-signature"},
    )
    monkeypatch.setattr(
        "backend.services.notation_token.quantum_security.verify_notation_token_signature",
        lambda _payload, signature_ref: signature_ref == "test-signature",
    )

    action_digest = "sha256:" + "a" * 64
    target_digest = "sha256:" + "b" * 64
    token = await service.mint_authorized_notation_token(
        lease=lease,
        lease_store=store,
        expected_audience=lease.audience,
        action_digest=action_digest,
        parameters_digest=lease.parameters_digest,
        target_digest=target_digest,
        epoch_id="epoch-1",
        score_id="score-1",
        genre_mode="fortified",
        voice_role="deployment",
        world_state_hash="world-1",
        response_class="deploy.release",
        ttl_seconds=60,
    )

    assert store.state(lease.lease_id)["status"] == "bound"
    assert token.capability_lease_id == lease.lease_id
    assert token.authority_request_digest == lease.authority_request_digest
    assert token.action_digest == action_digest
    assert token.audience == lease.audience

    epoch = {
        "epoch_id": "epoch-1",
        "score_id": "score-1",
        "genre_mode": "fortified",
        "strictness_level": "normal",
        "world_state_hash": "world-1",
        "started_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(minutes=5)).isoformat(),
        "status": "active",
    }
    valid = await service.validate_notation_token(
        token,
        epoch,
        "world-1",
        context={
            "require_capability": True,
            "capability_lease_id": lease.lease_id,
            "authority_request_digest": lease.authority_request_digest,
            "action_digest": action_digest,
            "audience": lease.audience,
            "target_digest": target_digest,
        },
    )
    assert valid["valid"] is True

    substituted = await service.validate_notation_token(
        token,
        epoch,
        "world-1",
        context={
            "require_capability": True,
            "capability_lease_id": lease.lease_id,
            "authority_request_digest": lease.authority_request_digest,
            "action_digest": "sha256:" + "c" * 64,
            "audience": lease.audience,
            "target_digest": target_digest,
        },
    )
    assert substituted["valid"] is False
    assert "notation_action_binding_invalid" in substituted["reasons"]


def test_production_capability_verifier_accepts_only_real_ed25519_signature():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    now = datetime.now(timezone.utc)
    unsigned = replace(
        make_lease(now),
        signature_algorithm="ed25519",
        signature="pending",
        verification_material={},
    )
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    signed = replace(
        unsigned,
        verification_material={"public_key": public.hex()},
    )
    signed = replace(
        signed,
        signature=private.sign(canonical_json_bytes(signed.unsigned_payload())).hex(),
    )
    verifier = StrictCapabilityLeaseSignatureVerifier()
    assert verifier.verify(signed) is True
    assert verifier.verify(replace(signed, signature="00" * 64)) is False
    assert verifier.verify(replace(signed, signature_algorithm="test-hmac")) is False
