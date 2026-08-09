from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import pytest

from backend.services.arda_recovery_conformance import (
    LiveRecoveryProofImporter,
    RecoveryError,
    RecoveryReplayStore,
    RecoveryRequestV1,
    RecoveryWitnessVoteV1,
    StrictRecoveryCoordinator,
)
from backend.services.arda_trust_contracts import (
    ArdaAttestationResultV1,
    AttestationStatus,
    BeastCapabilityLeaseV1,
    EvidenceMode,
)
from backend.services.arda_recovery_runtime import RecoveryRuntimeState, StrictRecoveryRuntime


NOW = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


class FakeVerifier:
    def verify(self, payload, signature, algorithm, material):
        return signature == "valid" and algorithm == "test-v1"


class FakeSigner:
    def sign(self, payload):
        return "test-result-v1", "signed:" + str(len(payload)), {"key_id": "recovery-test"}


def _vote(witness: str, *, vote_id: str | None = None, signature: str = "valid"):
    return RecoveryWitnessVoteV1(
        vote_id=vote_id or f"vote-{witness}",
        witness_node_id=witness,
        target_node_id="node-a",
        session_id="session-1",
        nonce="nonce-1",
        quorum_epoch=7,
        governance_epoch="gov-9",
        attestation_evidence_digest=DIGEST_A,
        decision="recover",
        issued_at=(NOW - timedelta(seconds=10)).isoformat(),
        expires_at=(NOW + timedelta(minutes=2)).isoformat(),
        signature_algorithm="test-v1",
        signature=signature,
        verification_material={"key_id": witness},
    )


def _request(**changes):
    value = RecoveryRequestV1(
        request_id="recovery-request-1",
        session_id="session-1",
        target_node_id="node-a",
        isolation_receipt_digest=DIGEST_B,
        attestation_result_id="attestation-1",
        attestation_evidence_digest=DIGEST_A,
        capability_lease_id="lease-1",
        governance_epoch="gov-9",
        world_state_hash=DIGEST_B,
        quorum_epoch=7,
        policy_generation="policy-4",
        nonce="nonce-1",
        audience="arda-recovery-coordinator",
        issued_at=(NOW - timedelta(seconds=10)).isoformat(),
        expires_at=(NOW + timedelta(minutes=2)).isoformat(),
        witness_votes=(_vote("node-b"), _vote("node-c")),
        signature_algorithm="test-v1",
        signature="valid",
        verification_material={"key_id": "requester"},
    )
    return replace(value, **changes)


def _attestation(**changes):
    value = ArdaAttestationResultV1(
        result_id="attestation-1",
        issuer="arda-verifier",
        policy_id="production-recovery",
        status=AttestationStatus.ACCEPTED,
        issued_at=(NOW - timedelta(seconds=20)).isoformat(),
        expires_at=(NOW + timedelta(minutes=3)).isoformat(),
        subject_node_id="node-a",
        subject_workload_digest=DIGEST_A,
        evidence_bundle_id="bundle-1",
        evidence_digest=DIGEST_A,
        nonce="quote-nonce",
        environment="production",
        audience="arda-recovery-coordinator",
        assurance_class="hardware",
        evidence_mode=EvidenceMode.ENFORCED,
        checks={"quote": True},
        hard_failures=(),
        warnings=(),
        signature_algorithm="test-v1",
        signature="valid",
        verification_material={"key_id": "arda-verifier"},
    )
    return replace(value, **changes)


def _capability(**changes):
    value = BeastCapabilityLeaseV1(
        lease_id="lease-1",
        authority_request_id="authority-1",
        authority_request_digest=DIGEST_B,
        principal_id="operator-1",
        mission_id="recovery-mission-1",
        workspace_id="arda",
        node_id="node-a",
        workload_digest=DIGEST_A,
        attestation_result_id="attestation-1",
        attestation_evidence_digest=DIGEST_A,
        capability="arda.rejoin",
        parameters_digest=DIGEST_B,
        data_scope=(),
        route_scope=("recovery",),
        output_scope=("node-a",),
        resource_ceiling={},
        consequence_ceiling="critical",
        policy_generation="policy-4",
        approval_receipt_ids=("approval-1",),
        audience="arda-recovery-coordinator",
        nonce="capability-nonce",
        issued_at=(NOW - timedelta(seconds=15)).isoformat(),
        expires_at=(NOW + timedelta(minutes=2)).isoformat(),
        maximum_uses=1,
        revocation_epoch=0,
        signature_algorithm="test-v1",
        signature="valid",
        verification_material={"key_id": "beast-authority"},
    )
    return replace(value, **changes)


def _coordinator(tmp_path):
    verifier = FakeVerifier()
    return StrictRecoveryCoordinator(
        request_verifier=verifier,
        witness_verifier=verifier,
        attestation_verifier=verifier,
        capability_verifier=verifier,
        signer=FakeSigner(),
        replay_store=RecoveryReplayStore(str(tmp_path / "replay.sqlite3")),
        environment="production",
    )


def _authorize(coordinator, request=None, attestation=None, capability=None, **context):
    return coordinator.authorize(
        request or _request(),
        attestation or _attestation(),
        capability or _capability(),
        isolated_node_ids=context.pop("isolated_node_ids", ("node-a",)),
        compromised_node_ids=context.pop("compromised_node_ids", ()),
        active_governance_epoch=context.pop("active_governance_epoch", "gov-9"),
        active_world_state_hash=context.pop("active_world_state_hash", DIGEST_B),
        active_quorum_epoch=context.pop("active_quorum_epoch", 7),
        active_revocation_epoch=context.pop("active_revocation_epoch", 0),
        now=NOW,
        **context,
    )


def test_authorizes_fresh_quorum_bound_recovery(tmp_path):
    result = _authorize(_coordinator(tmp_path))
    assert result.status == "authorized"
    assert result.target_node_id == "node-a"
    assert result.capability_lease_id == "lease-1"
    assert result.signature_algorithm == "test-result-v1"
    assert all(result.checks.values())
    assert "signature" not in result.unsigned_payload()
    assert "signature_algorithm" not in result.unsigned_payload()
    assert "verification_material" not in result.unsigned_payload()


def test_recovery_nonce_is_single_use(tmp_path):
    coordinator = _coordinator(tmp_path)
    _authorize(coordinator)
    with pytest.raises(RecoveryError, match="already consumed"):
        _authorize(coordinator)


def test_recovery_capability_is_single_use_even_with_fresh_nonce(tmp_path):
    coordinator = _coordinator(tmp_path)
    _authorize(coordinator)
    votes = (
        replace(_vote("node-b"), nonce="nonce-2"),
        replace(_vote("node-c"), nonce="nonce-2"),
    )
    second = _request(request_id="recovery-request-2", nonce="nonce-2", witness_votes=votes)
    with pytest.raises(RecoveryError, match="capability lease was already consumed"):
        _authorize(coordinator, request=second)


def test_concurrent_recovery_capability_consumption_has_one_winner(tmp_path):
    path = str(tmp_path / "race.sqlite3")

    def consume(index):
        try:
            RecoveryReplayStore(path).consume(
                f"nonce-{index}", f"request-{index}", "lease-race", NOW
            )
            return "won"
        except RecoveryError:
            return "lost"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(consume, (1, 2)))
    assert sorted(outcomes) == ["lost", "won"]


@pytest.mark.parametrize(
    ("request_obj", "attestation_obj", "capability_obj", "context", "failure"),
    (
        (_request(audience="wrong"), None, None, {}, "request_audience"),
        (_request(issued_at=(NOW - timedelta(minutes=10)).isoformat()), None, None, {}, "request_fresh"),
        (_request(signature="forged"), None, None, {}, "request_signature"),
        (_request(isolation_receipt_digest="sha256:not-a-digest"), None, None, {}, "isolation_receipt"),
        (None, _attestation(subject_node_id="node-z"), None, {}, "attestation_binding"),
        (None, _attestation(signature="forged"), None, {}, "attestation_signature"),
        (None, None, _capability(node_id="node-z"), {}, "capability_binding"),
        (None, None, _capability(signature="forged"), {}, "capability_signature"),
        (None, None, _capability(expires_at=(NOW - timedelta(seconds=1)).isoformat()), {}, "capability_fresh"),
        (None, None, None, {"isolated_node_ids": ()}, "target_isolated"),
        (None, None, None, {"active_governance_epoch": "gov-old"}, "governance_epoch"),
        (None, None, None, {"active_world_state_hash": DIGEST_A}, "world_state_hash"),
        (None, None, None, {"active_quorum_epoch": 8}, "quorum_epoch"),
        (None, None, None, {"active_revocation_epoch": 1}, "capability_revocation_epoch"),
        (None, None, None, {"compromised_node_ids": ("node-b",)}, "witness_votes_valid"),
    ),
)
def test_recovery_fails_closed(
    tmp_path, request_obj, attestation_obj, capability_obj, context, failure
):
    with pytest.raises(RecoveryError, match=failure):
        _authorize(
            _coordinator(tmp_path), request_obj, attestation_obj, capability_obj, **context
        )


def test_target_cannot_witness_its_own_recovery(tmp_path):
    request = _request(witness_votes=(_vote("node-a"), _vote("node-c")))
    with pytest.raises(RecoveryError, match="target_not_witness"):
        _authorize(_coordinator(tmp_path), request=request)


def test_duplicate_witness_does_not_form_quorum(tmp_path):
    request = _request(witness_votes=(_vote("node-b", vote_id="one"), _vote("node-b", vote_id="two")))
    with pytest.raises(RecoveryError, match="witness_quorum"):
        _authorize(_coordinator(tmp_path), request=request)


def test_live_proof_import_is_observed_evidence_not_authority(tmp_path):
    assertions = {name: True for name in LiveRecoveryProofImporter.REQUIRED_ASSERTIONS}
    (tmp_path / "00_manifest.json").write_text(json.dumps({"session_id": "live-1"}))
    (tmp_path / "assertions.json").write_text(json.dumps(assertions))
    (tmp_path / "packet_capture.pcap").write_bytes(b"observed")
    imported = LiveRecoveryProofImporter().import_bundle(tmp_path)
    assert imported["evidence_mode"] == "observed"
    assert imported["production_authority"] is False
    assert imported["session_id"] == "live-1"
    assert imported["bundle_digest"].startswith("sha256:")


def test_live_proof_import_rejects_failed_assertion(tmp_path):
    assertions = {name: True for name in LiveRecoveryProofImporter.REQUIRED_ASSERTIONS}
    assertions["bad_recovery_witness_rejected"] = False
    (tmp_path / "00_manifest.json").write_text("{}")
    (tmp_path / "assertions.json").write_text(json.dumps(assertions))
    with pytest.raises(RecoveryError, match="bad_recovery_witness_rejected"):
        LiveRecoveryProofImporter().import_bundle(tmp_path)


class RecordingActuator:
    def __init__(self):
        self.calls = []

    def rejoin(self, authorization):
        self.calls.append(authorization.authorization_id)
        return {"rejoined": True, "authorization_id": authorization.authorization_id}


def test_runtime_actuates_only_after_strict_authorization(tmp_path):
    actuator = RecordingActuator()
    runtime = StrictRecoveryRuntime(_coordinator(tmp_path), actuator)
    payload = {
        "request": asdict(_request()),
        "attestation": asdict(_attestation()),
        "capability": asdict(_capability()),
    }
    state = RecoveryRuntimeState(("node-a",), (), "gov-9", DIGEST_B, 7, 0, NOW)
    result = runtime.recover(payload, state)
    assert result["effect"]["rejoined"] is True
    assert len(actuator.calls) == 1


def test_runtime_never_calls_actuator_after_veto(tmp_path):
    actuator = RecordingActuator()
    runtime = StrictRecoveryRuntime(_coordinator(tmp_path), actuator)
    payload = {
        "request": asdict(_request(signature="forged")),
        "attestation": asdict(_attestation()),
        "capability": asdict(_capability()),
    }
    state = RecoveryRuntimeState(("node-a",), (), "gov-9", DIGEST_B, 7, 0, NOW)
    with pytest.raises(RecoveryError, match="request_signature"):
        runtime.recover(payload, state)
    assert actuator.calls == []
