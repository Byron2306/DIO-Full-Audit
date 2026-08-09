from __future__ import annotations

import hashlib
import hmac
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.services.arda_trust_contracts import BeastCapabilityLeaseV1, canonical_json_bytes
from backend.services.capability_lease_store import (
    CapabilityLeaseError,
    CapabilityLeaseUnavailable,
    SqliteCapabilityLeaseStore,
)


SECRET = b"lease-test-key"


class LeaseVerifier:
    def verify(self, lease):
        expected = hmac.new(SECRET, canonical_json_bytes(lease.unsigned_payload()), hashlib.sha256).hexdigest()
        return hmac.compare_digest(lease.signature, expected)


def make_lease(now=None, **changes):
    now = now or datetime.now(timezone.utc)
    lease = BeastCapabilityLeaseV1(
        lease_id="lease-1",
        authority_request_id="request-1",
        authority_request_digest="sha256:" + "1" * 64,
        principal_id="operator-1",
        mission_id="mission-1",
        workspace_id="workspace-1",
        node_id="node-a",
        workload_digest="sha256:" + "2" * 64,
        attestation_result_id="arda-result-1",
        attestation_evidence_digest="sha256:" + "3" * 64,
        capability="deploy.release",
        parameters_digest="sha256:" + "4" * 64,
        data_scope=("confidential",),
        route_scope=("production",),
        output_scope=("release-bucket",),
        resource_ceiling={"cpu_seconds": 30},
        consequence_ceiling="high",
        policy_generation="beast-policy-1",
        approval_receipt_ids=("approval-1", "approval-2"),
        audience="metatron-outbound-gate",
        nonce="lease-nonce",
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=2)).isoformat(),
        maximum_uses=1,
        revocation_epoch=0,
        signature_algorithm="test-hmac",
        signature="pending",
        verification_material={"key_id": "test"},
    )
    lease = replace(
        lease,
        signature=hmac.new(
            SECRET, canonical_json_bytes(lease.unsigned_payload()), hashlib.sha256
        ).hexdigest(),
    )
    if changes:
        lease = replace(lease, **changes)
        if "signature" not in changes:
            lease = replace(
                lease,
                signature=hmac.new(
                    SECRET, canonical_json_bytes(lease.unsigned_payload()), hashlib.sha256
                ).hexdigest(),
            )
    return lease


def test_atomic_single_use_consumption(tmp_path):
    store = SqliteCapabilityLeaseStore(tmp_path / "leases.sqlite", signature_verifier=LeaseVerifier())
    lease = make_lease()
    store.register(lease)

    def consume_once():
        try:
            return store.consume(
                lease.lease_id,
                expected_audience=lease.audience,
                authority_request_digest=lease.authority_request_digest,
            ).lease_id
        except CapabilityLeaseUnavailable:
            return "refused"

    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes = list(executor.map(lambda _: consume_once(), range(8)))

    assert outcomes.count(lease.lease_id) == 1
    assert outcomes.count("refused") == 7
    assert store.state(lease.lease_id)["status"] == "consumed"
    assert store.state(lease.lease_id)["used_count"] == 1


def test_wrong_audience_or_request_digest_does_not_consume(tmp_path):
    store = SqliteCapabilityLeaseStore(tmp_path / "leases.sqlite", signature_verifier=LeaseVerifier())
    lease = make_lease()
    store.register(lease)

    with pytest.raises(CapabilityLeaseUnavailable, match="audience"):
        store.consume(
            lease.lease_id,
            expected_audience="wrong",
            authority_request_digest=lease.authority_request_digest,
        )
    with pytest.raises(CapabilityLeaseUnavailable, match="authority_request_digest"):
        store.consume(
            lease.lease_id,
            expected_audience=lease.audience,
            authority_request_digest="sha256:" + "9" * 64,
        )

    assert store.state(lease.lease_id)["used_count"] == 0


def test_signature_failure_and_epoch_revocation_fail_closed(tmp_path):
    store = SqliteCapabilityLeaseStore(tmp_path / "leases.sqlite", signature_verifier=LeaseVerifier())
    with pytest.raises(CapabilityLeaseError, match="signature"):
        store.register(make_lease(signature="forged"))

    lease = make_lease()
    store.register(lease)
    assert store.advance_revocation_epoch(1, reason="compromise") == 1
    assert store.state(lease.lease_id)["status"] == "revoked"
    with pytest.raises(CapabilityLeaseUnavailable, match="status:revoked"):
        store.consume(
            lease.lease_id,
            expected_audience=lease.audience,
            authority_request_digest=lease.authority_request_digest,
        )
    with pytest.raises(CapabilityLeaseError, match="revocation epoch"):
        store.register(replace(make_lease(lease_id="lease-2"), revocation_epoch=0))


def test_notation_binding_reserves_then_exact_executor_consumes(tmp_path):
    store = SqliteCapabilityLeaseStore(tmp_path / "leases.sqlite", signature_verifier=LeaseVerifier())
    lease = make_lease()
    action_digest = "sha256:" + "a" * 64
    store.register(lease)
    bound = store.bind_notation(
        lease.lease_id,
        notation_token_id="notation-1",
        expected_audience=lease.audience,
        authority_request_digest=lease.authority_request_digest,
        action_digest=action_digest,
    )
    assert bound.lease_id == lease.lease_id
    assert store.state(lease.lease_id)["status"] == "bound"
    assert store.state(lease.lease_id)["used_count"] == 0

    consumed = store.consume_bound(
        lease.lease_id,
        notation_token_id="notation-1",
        expected_audience=lease.audience,
        authority_request_digest=lease.authority_request_digest,
        action_digest=action_digest,
    )
    assert consumed.lease_id == lease.lease_id
    assert store.state(lease.lease_id)["status"] == "consumed"
    assert store.state(lease.lease_id)["used_count"] == 1


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("notation_token_id", "notation-other", "notation_token"),
        ("authority_request_digest", "sha256:" + "b" * 64, "bound_request_digest"),
        ("action_digest", "sha256:" + "c" * 64, "action_digest"),
        ("expected_audience", "wrong-audience", "audience"),
    ],
)
def test_bound_capability_rejects_cross_action_substitution(tmp_path, field, value, match):
    store = SqliteCapabilityLeaseStore(tmp_path / f"{field}.sqlite", signature_verifier=LeaseVerifier())
    lease = make_lease()
    arguments = {
        "notation_token_id": "notation-1",
        "expected_audience": lease.audience,
        "authority_request_digest": lease.authority_request_digest,
        "action_digest": "sha256:" + "a" * 64,
    }
    store.register(lease)
    store.bind_notation(lease.lease_id, **arguments)
    arguments[field] = value
    with pytest.raises(CapabilityLeaseUnavailable, match=match):
        store.consume_bound(lease.lease_id, **arguments)
    assert store.state(lease.lease_id)["status"] == "bound"


def test_bound_capability_is_single_use_under_concurrency(tmp_path):
    store = SqliteCapabilityLeaseStore(tmp_path / "bound-race.sqlite", signature_verifier=LeaseVerifier())
    lease = make_lease()
    arguments = {
        "notation_token_id": "notation-1",
        "expected_audience": lease.audience,
        "authority_request_digest": lease.authority_request_digest,
        "action_digest": "sha256:" + "a" * 64,
    }
    store.register(lease)
    store.bind_notation(lease.lease_id, **arguments)

    def consume_once():
        try:
            return store.consume_bound(lease.lease_id, **arguments).lease_id
        except CapabilityLeaseUnavailable:
            return "refused"

    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes = list(executor.map(lambda _: consume_once(), range(8)))
    assert outcomes.count(lease.lease_id) == 1
    assert outcomes.count("refused") == 7
