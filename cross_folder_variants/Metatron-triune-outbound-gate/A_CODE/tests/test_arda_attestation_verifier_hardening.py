from __future__ import annotations

import hashlib
import hmac
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.services.arda_attestation_verifier import (
    InMemoryReplayStore,
    StrictArdaAttestationVerifier,
)
from backend.services.arda_trust_contracts import (
    ArdaEvidenceBundleV1,
    ArdaVerificationPolicyV1,
    BeastAuthorityRequestV1,
    BeastCapabilityLeaseV1,
    EvidenceMode,
    MetatronOutboundDecisionV1,
    canonical_json_bytes,
)


SECRET = b"test-only-verifier-key"


class EvidenceVerifier:
    def verify(self, bundle):
        expected = hmac.new(SECRET, canonical_json_bytes(bundle.unsigned_payload()), hashlib.sha256).hexdigest()
        return hmac.compare_digest(bundle.signature, expected)


class QuoteVerifier:
    def verify(self, **kwargs):
        expected = hmac.new(
            SECRET,
            f"{kwargs['attestation_key_id']}:{kwargs['nonce']}:{kwargs['quote']}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(kwargs["signature"], expected)


class EventLogVerifier:
    def verify(self, *, event_log, claimed_digest, **kwargs):
        digest = "sha256:" + hashlib.sha256(canonical_json_bytes({"events": event_log})).hexdigest()
        return hmac.compare_digest(digest, claimed_digest)


class ResultSigner:
    issuer = "arda-verifier:test"

    def sign(self, payload):
        signature = hmac.new(SECRET, canonical_json_bytes(payload), hashlib.sha256).hexdigest()
        return {
            "algorithm": "test-hmac-sha256",
            "signature": signature,
            "verification_material": {"key_id": "test-only"},
        }


def make_policy(**changes):
    policy = ArdaVerificationPolicyV1(
        policy_id="policy-prod-v1",
        environment="production",
        expected_audience="beast:relying-party",
        trusted_evidence_issuers=("arda-attester:node-a",),
        trusted_attestation_keys=("ak:node-a",),
        allowed_evidence_modes=(EvidenceMode.ENFORCED,),
        allowed_pcr_banks=("sha256",),
        required_pcrs=(0, 7, 11),
        accepted_pcr_values={0: ("aa",), 7: ("bb",), 11: ("cc",)},
        expected_workload_digest="sha256:" + "1" * 64,
        expected_configuration_digest="sha256:" + "2" * 64,
        maximum_age_seconds=300,
    )
    return replace(policy, **changes)


def make_bundle(now=None, **changes):
    now = now or datetime.now(timezone.utc)
    event_log = ({"pcr": 0, "digest": "aa", "event": "firmware"},)
    event_log_digest = "sha256:" + hashlib.sha256(
        canonical_json_bytes({"events": event_log})
    ).hexdigest()
    quote = "opaque-tpm-quote"
    nonce = "nonce-123"
    quote_signature = hmac.new(
        SECRET, f"ak:node-a:{nonce}:{quote}".encode(), hashlib.sha256
    ).hexdigest()
    bundle = ArdaEvidenceBundleV1(
        bundle_id="bundle-1",
        issuer="arda-attester:node-a",
        environment="production",
        evidence_mode=EvidenceMode.ENFORCED,
        subject_node_id="node-a",
        subject_workload_digest="sha256:" + "1" * 64,
        subject_configuration_digest="sha256:" + "2" * 64,
        audience=("beast:relying-party",),
        nonce=nonce,
        verifier_session_id="session-1",
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=2)).isoformat(),
        attestation_key_id="ak:node-a",
        quote=quote,
        quote_signature=quote_signature,
        pcr_bank="sha256",
        pcr_selection=(0, 7, 11),
        pcr_values={0: "aa", 7: "bb", 11: "cc"},
        secure_boot_enabled=True,
        event_log_digest=event_log_digest,
        event_log=event_log,
        formation_manifest_digest="sha256:" + "3" * 64,
        covenant_digest="sha256:" + "4" * 64,
        boot_id="boot-1",
        governance_epoch="epoch-1",
        replay_counter=1,
        signature_algorithm="test-hmac-sha256",
        signature="pending",
        verification_material={"key_id": "attester-test"},
    )
    bundle = replace(
        bundle,
        signature=hmac.new(
            SECRET, canonical_json_bytes(bundle.unsigned_payload()), hashlib.sha256
        ).hexdigest(),
    )
    if changes:
        bundle = replace(bundle, **changes)
        if "signature" not in changes:
            bundle = replace(
                bundle,
                signature=hmac.new(
                    SECRET, canonical_json_bytes(bundle.unsigned_payload()), hashlib.sha256
                ).hexdigest(),
            )
    return bundle


def make_verifier(replay_store=None, **changes):
    dependencies = {
        "evidence_signature_verifier": EvidenceVerifier(),
        "quote_verifier": QuoteVerifier(),
        "event_log_appraiser": EventLogVerifier(),
        "result_signer": ResultSigner(),
        "replay_store": replay_store or InMemoryReplayStore(),
    }
    dependencies.update(changes)
    return StrictArdaAttestationVerifier(**dependencies)


def test_strict_verifier_accepts_complete_enforced_evidence():
    now = datetime.now(timezone.utc)
    result = make_verifier().verify(
        make_bundle(now), make_policy(), expected_nonce="nonce-123", now=now
    )

    assert result.accepted is True
    assert result.hard_failures == ()
    assert result.signature
    assert all(result.checks.values())


@pytest.mark.parametrize(
    ("change", "failure"),
    [
        ({"environment": "development"}, "environment_match"),
        ({"audience": ("other-service",)}, "audience_match"),
        ({"attestation_key_id": "ak:unknown"}, "attestation_key_trusted"),
        ({"subject_workload_digest": "sha256:" + "9" * 64}, "workload_digest_match"),
        ({"secure_boot_enabled": False}, "secure_boot_accepted"),
        ({"pcr_values": {0: "wrong", 7: "bb", 11: "cc"}}, "pcr_baselines_match"),
        ({"collector_errors": ("tpm_unavailable",)}, "required_collectors_succeeded"),
    ],
)
def test_each_trust_dimension_fails_closed(change, failure):
    now = datetime.now(timezone.utc)
    result = make_verifier().verify(
        make_bundle(now, **change), make_policy(), expected_nonce="nonce-123", now=now
    )

    assert result.accepted is False
    assert failure in result.hard_failures


def test_simulated_evidence_cannot_satisfy_production_policy():
    now = datetime.now(timezone.utc)
    result = make_verifier().verify(
        make_bundle(now, evidence_mode=EvidenceMode.SIMULATED),
        make_policy(),
        expected_nonce="nonce-123",
        now=now,
    )
    assert result.accepted is False
    assert "evidence_mode_allowed" in result.hard_failures


def test_nonce_mismatch_and_replay_are_rejected_atomically():
    now = datetime.now(timezone.utc)
    replay_store = InMemoryReplayStore()
    verifier = make_verifier(replay_store=replay_store)
    bundle = make_bundle(now)

    mismatch = verifier.verify(bundle, make_policy(), expected_nonce="wrong", now=now)
    assert mismatch.accepted is False
    assert "nonce_match" in mismatch.hard_failures

    # A failed request still consumes a cryptographically valid presented nonce,
    # preventing it from being retried under a more favorable policy context.
    replay = verifier.verify(bundle, make_policy(), expected_nonce="nonce-123", now=now)
    assert replay.accepted is False
    assert "replay_state_valid" in replay.hard_failures


def test_quote_or_signature_dependency_failure_is_a_hard_failure():
    class BrokenVerifier:
        def verify(self, *args, **kwargs):
            raise RuntimeError("verification backend unavailable")

    now = datetime.now(timezone.utc)
    result = make_verifier(
        quote_verifier=BrokenVerifier(),
        evidence_signature_verifier=BrokenVerifier(),
    ).verify(make_bundle(now), make_policy(), expected_nonce="nonce-123", now=now)

    assert result.accepted is False
    assert "quote_valid" in result.hard_failures
    assert "evidence_signature_valid" in result.hard_failures


def test_cross_system_authority_contracts_reject_digest_or_veto_confusion():
    now = datetime.now(timezone.utc)
    later = (now + timedelta(minutes=2)).isoformat()
    authority = BeastAuthorityRequestV1(
        request_id="request-1",
        mission_id="mission-1",
        workspace_id="workspace-1",
        sourceplan_id="sourceplan-1",
        actor_id="operator-1",
        capability="deploy.release",
        consequence_class="high",
        source_digest="sha256:" + "1" * 64,
        artifact_digest="sha256:" + "2" * 64,
        workload_digest="sha256:" + "3" * 64,
        configuration_digest="sha256:" + "4" * 64,
        target_environment="production",
        target_node_id="node-a",
        route_scope=("production",),
        output_scope=("release-bucket",),
        data_classifications=("confidential",),
        resource_ceiling={"cpu_seconds": 30},
        network_policy_id="network-prod-v1",
        approval_receipt_ids=("approval-1", "approval-2"),
        beast_policy_generation="beast-policy-7",
        evidence_root="sha256:" + "5" * 64,
        audience="arda-verifier",
        nonce="authority-nonce",
        issued_at=now.isoformat(),
        expires_at=later,
    )
    authority.validate_shape()
    with pytest.raises(ValueError, match="digest mismatch"):
        replace(authority, request_digest="sha256:" + "0" * 64).validate_shape()

    lease = BeastCapabilityLeaseV1(
        lease_id="lease-1",
        authority_request_id=authority.request_id,
        authority_request_digest=authority.computed_digest(),
        principal_id=authority.actor_id,
        mission_id=authority.mission_id,
        workspace_id=authority.workspace_id,
        node_id=authority.target_node_id,
        workload_digest=authority.workload_digest,
        attestation_result_id="arda-result-1",
        attestation_evidence_digest="sha256:" + "6" * 64,
        capability=authority.capability,
        parameters_digest="sha256:" + "7" * 64,
        data_scope=authority.data_classifications,
        route_scope=authority.route_scope,
        output_scope=authority.output_scope,
        resource_ceiling=authority.resource_ceiling,
        consequence_ceiling=authority.consequence_class,
        policy_generation=authority.beast_policy_generation,
        approval_receipt_ids=authority.approval_receipt_ids,
        audience="metatron-outbound-gate",
        nonce="lease-nonce",
        issued_at=now.isoformat(),
        expires_at=later,
        maximum_uses=1,
        revocation_epoch=0,
        signature_algorithm="test",
        signature="signed",
        verification_material={"key_id": "beast-test"},
    )
    lease.validate_shape()

    decision = MetatronOutboundDecisionV1(
        decision_id="decision-1",
        queue_id="queue-1",
        action_id="action-1",
        request_digest=authority.computed_digest(),
        normalized_action="deploy.release",
        canonical_target="node-a",
        capability_lease_id=lease.lease_id,
        attestation_result_id=lease.attestation_result_id,
        governance_epoch="epoch-1",
        notation_token_id="notation-1",
        score_id="fortified-high-v1",
        world_state_hash="sha256:" + "8" * 64,
        manifold_digest="sha256:" + "9" * 64,
        checks={"lease": True, "attestation": True, "transport": True},
        hard_vetoes=(),
        approval_receipt_ids=authority.approval_receipt_ids,
        break_glass_receipt_id=None,
        status="approved",
        policy_version="metatron-policy-1",
        audience="metatron-executor",
        issued_at=now.isoformat(),
        expires_at=later,
        maximum_uses=1,
        evidence_root="sha256:" + "a" * 64,
        signature_algorithm="test",
        signature="signed",
        verification_material={"key_id": "metatron-test"},
    )
    decision.validate_shape()
    with pytest.raises(ValueError, match="failed check or hard veto"):
        replace(decision, hard_vetoes=("attestation",)).validate_shape()
