from __future__ import annotations

from pathlib import Path

import pytest

from authority.canonical import (
    AuthorityPlaneError,
    authorize_valinor,
    load_authority_config,
    make_arda_execution_identity,
    make_authority_receipt,
    make_capability_lease,
    record_execution_receipt,
    revoke_capability_lease,
    validate_capability_lease,
)
from products.governed_case import new_case, propose_action, set_gate

ISSUED = "2026-08-11T18:00:00+00:00"
AUTH_EXPIRY = "2026-08-13T18:00:00+00:00"
LEASE_EXPIRY = "2026-08-12T18:00:00+00:00"
EXECUTED = "2026-08-11T18:30:00+00:00"
SHA = "sha256:" + ("a" * 64)
EVIDENCE_SHA = "sha256:" + ("b" * 64)


class AllowRuntime:
    def syscall(self, entity_id: str, syscall_name: str) -> str:
        return f"syscall:{entity_id}:{syscall_name}"

    def access_secret(self, entity_id: str, secret_name: str) -> bool:
        return True

    def open_socket(self, entity_id: str):
        return {"entity_id": entity_id, "mode": "socket"}

    def send_ipc(self, entity_id: str):
        return {"entity_id": entity_id, "mode": "ipc"}

    def write_stream(self, entity_id: str, target: str):
        return {"entity_id": entity_id, "target": target, "mode": "write"}

    def apply_flow_shape(self, entity_id: str):
        return {"entity_id": entity_id, "mode": "flow"}


class RefuseRuntime(AllowRuntime):
    def write_stream(self, entity_id: str, target: str):
        raise PermissionError("Valinor policy refused write")


def _case(job_id: str = "authority-wave4") -> dict:
    return new_case(
        product="dio_agent_authority",
        job_id=job_id,
        source={"source": {}},
        source_path=Path("/tmp/dio-authority-source.json"),
        evidence_inputs=[],
        expected_outputs=[],
        required_authorities=["operator"],
        intake_state="approved",
    )


def _internal_action(case: dict, capability: str = "draft_internal") -> dict:
    return propose_action(
        case,
        action_type=capability,
        description="Perform a bounded internal operation",
        risk_tier="reversible_internal",
        reversibility="reversible",
        required_gate_ids=["intake_authority"],
        proposed_by="vesper_presence",
    )


def _external_action(case: dict, capability: str = "outlook_send") -> dict:
    set_gate(
        case,
        gate_id="external_release",
        state="allow",
        reason="Explicit human release for this governed case.",
        actor_id="human:byron",
    )
    return propose_action(
        case,
        action_type=capability,
        description="Perform one bounded external operation",
        risk_tier="external",
        reversibility="compensatable",
        required_gate_ids=["intake_authority", "external_release"],
        proposed_by="outlook_triage",
    )


def _authority(case: dict, action: dict, capability: str, *, actor_type: str = "human", scope: list[str] | None = None, verdict: str = "ALLOW") -> dict:
    return make_authority_receipt(
        case,
        action_id=action["action_id"],
        capability=capability,
        actor_id="human:byron" if actor_type == "human" else "system:test",
        actor_type=actor_type,
        authority_scope=scope or [capability],
        verdict=verdict,
        evidence_refs=["decision://human-review"],
        issued_at=ISSUED,
        expires_at=AUTH_EXPIRY,
    )


def _lease(case: dict, action: dict, authority: dict, *, audience: str = "dio-executor") -> dict:
    return make_capability_lease(
        case,
        action_id=action["action_id"],
        authority_receipt=authority,
        principal_id="executor:test",
        audience=audience,
        route_scope=["local://bounded"],
        output_scope=["receipt_only"],
        resource_ceiling={"operations": 1},
        issued_at=ISSUED,
        expires_at=LEASE_EXPIRY,
        maximum_uses=1,
        revocation_epoch=3,
    )


def _arda(*, audience: str = "dio-executor", mode: str = "observed", status: str = "accepted") -> dict:
    return make_arda_execution_identity(
        node_id="node-local",
        workload_digest=SHA,
        attestation_result_id="ATTEST-1",
        attestation_evidence_digest=EVIDENCE_SHA,
        evidence_mode=mode,
        attestation_status=status,
        environment="local",
        audience=audience,
        issued_at=ISSUED,
        expires_at=LEASE_EXPIRY,
    )


def test_authority_config_preserves_constitutional_roles():
    config = load_authority_config()
    assert config["kernel_authority"] == "Valinor"
    assert config["execution_identity_authority"] == "ARDA"
    assert set(config["granting_actor_types"]) == {"human", "organisation"}
    assert config["laws"]["evidence_is_not_authority"] is True
    assert config["laws"]["arda_identity_is_not_kernel_authority"] is True


def test_machine_system_cannot_mint_consequential_authority():
    case = _case("machine-authority")
    action = _internal_action(case)
    with pytest.raises(AuthorityPlaneError, match="human or organisational"):
        _authority(case, action, "draft_internal", actor_type="system")


def test_blocked_action_cannot_receive_authority_or_lease():
    case = _case("blocked")
    action = propose_action(
        case,
        action_type="outlook_send",
        description="Blocked external send",
        risk_tier="external",
        reversibility="compensatable",
        required_gate_ids=["external_release"],
        proposed_by="outlook_triage",
    )
    assert action["state"] == "blocked"
    with pytest.raises(AuthorityPlaneError, match="already-approved"):
        make_authority_receipt(
            case,
            action_id=action["action_id"],
            capability="outlook_send",
            actor_id="human:byron",
            actor_type="human",
            authority_scope=["outlook_send", "external_release"],
            verdict="ALLOW",
            issued_at=ISSUED,
            expires_at=AUTH_EXPIRY,
        )


def test_authority_scope_is_capability_bound_and_external_scope_is_explicit():
    case = _case("scope")
    action = _external_action(case)
    with pytest.raises(AuthorityPlaneError, match="does not include"):
        _authority(case, action, "outlook_send", scope=["external_release"])
    with pytest.raises(AuthorityPlaneError, match="external_release"):
        _authority(case, action, "outlook_send", scope=["outlook_send"])
    receipt = _authority(case, action, "outlook_send", scope=["outlook_send", "external_release"])
    assert receipt["verdict"] == "ALLOW"


def test_capability_lease_binds_authority_action_expiry_and_revocation_epoch():
    case = _case("lease-binding")
    action = _internal_action(case)
    authority = _authority(case, action, "draft_internal")
    lease = _lease(case, action, authority)
    assert lease["authority_receipt_id"] == authority["authority_receipt_id"]
    assert lease["action_digest"] == authority["action_digest"]
    assert lease["maximum_uses"] == 1
    assert lease["revocation_epoch"] == 3
    assert lease["state"] == "active"


def test_lease_identity_stays_stable_when_revoked():
    case = _case("revocation")
    action = _internal_action(case)
    authority = _authority(case, action, "draft_internal")
    lease = _lease(case, action, authority)
    revoked = revoke_capability_lease(lease, reason="operator revoked", revoked_at=EXECUTED)
    assert revoked["lease_id"] == lease["lease_id"]
    assert revoked["fingerprint"] == lease["fingerprint"]
    assert revoked["state"] == "revoked"
    with pytest.raises(AuthorityPlaneError, match="not active"):
        validate_capability_lease(revoked, now=EXECUTED)


def test_expired_lease_is_refused():
    case = _case("expired")
    action = _internal_action(case)
    authority = _authority(case, action, "draft_internal")
    lease = _lease(case, action, authority)
    with pytest.raises(AuthorityPlaneError, match="expired"):
        validate_capability_lease(lease, now="2026-08-13T19:00:00+00:00")


def test_valinor_authorization_is_lease_bound_and_not_execution():
    case = _case("valinor")
    action = _internal_action(case)
    authority = _authority(case, action, "draft_internal")
    lease = _lease(case, action, authority)
    authorization = authorize_valinor(
        lease,
        entity_id="executor:test",
        operation="write",
        target="internal://draft",
        runtime=AllowRuntime(),
        authorized_at="2026-08-11T18:10:00+00:00",
    )
    assert authorization["state"] == "VALINOR_ALLOW"
    assert authorization["allowed"] is True
    assert authorization["lease_id"] == lease["lease_id"]
    assert authorization["external_action_executed"] is False


def test_valinor_refusal_cannot_be_used_for_execution():
    case = _case("valinor-refuse")
    action = _internal_action(case)
    authority = _authority(case, action, "draft_internal")
    lease = _lease(case, action, authority)
    authorization = authorize_valinor(
        lease,
        entity_id="executor:test",
        operation="write",
        target="internal://draft",
        runtime=RefuseRuntime(),
        authorized_at="2026-08-11T18:10:00+00:00",
    )
    assert authorization["state"] == "VALINOR_REFUSE"
    with pytest.raises(AuthorityPlaneError, match="Valinor ALLOW"):
        record_execution_receipt(
            case,
            action_id=action["action_id"],
            lease=lease,
            valinor_authorization=authorization,
            arda_identity=_arda(),
            executor_system="document_studio",
            executor_receipt_ref="executor://doc/1",
            success=True,
            executed_at=EXECUTED,
        )


def test_arda_is_execution_identity_not_kernel_authority():
    identity = _arda()
    assert identity["identity_authority"] == "ARDA"
    assert identity["kernel_authority"] is False
    assert identity["attestation_status"] == "accepted"


def test_rejected_arda_identity_blocks_execution():
    case = _case("arda-refuse")
    action = _internal_action(case)
    authority = _authority(case, action, "draft_internal")
    lease = _lease(case, action, authority)
    valinor = authorize_valinor(
        lease,
        entity_id="executor:test",
        operation="write",
        target="internal://draft",
        runtime=AllowRuntime(),
        authorized_at="2026-08-11T18:10:00+00:00",
    )
    with pytest.raises(AuthorityPlaneError, match="accepted ARDA"):
        record_execution_receipt(
            case,
            action_id=action["action_id"],
            lease=lease,
            valinor_authorization=valinor,
            arda_identity=_arda(status="rejected"),
            executor_system="document_studio",
            executor_receipt_ref="executor://doc/2",
            success=True,
            executed_at=EXECUTED,
        )


def test_external_execution_rejects_simulated_or_synthetic_arda_identity():
    case = _case("external-identity")
    action = _external_action(case)
    authority = _authority(case, action, "outlook_send", scope=["outlook_send", "external_release"])
    lease = _lease(case, action, authority)
    valinor = authorize_valinor(
        lease,
        entity_id="outlook-triage",
        operation="write",
        target="outlook://send",
        runtime=AllowRuntime(),
        authorized_at="2026-08-11T18:10:00+00:00",
    )
    with pytest.raises(AuthorityPlaneError, match="observed or enforced"):
        record_execution_receipt(
            case,
            action_id=action["action_id"],
            lease=lease,
            valinor_authorization=valinor,
            arda_identity=_arda(mode="synthetic"),
            executor_system="outlook_triage",
            executor_receipt_ref="outlook://send/1",
            success=True,
            executed_at=EXECUTED,
        )


def test_generic_executor_is_refused_even_with_full_authority_chain():
    case = _case("generic")
    action = _internal_action(case)
    authority = _authority(case, action, "draft_internal")
    lease = _lease(case, action, authority)
    valinor = authorize_valinor(
        lease,
        entity_id="executor:test",
        operation="write",
        target="internal://draft",
        runtime=AllowRuntime(),
        authorized_at="2026-08-11T18:10:00+00:00",
    )
    with pytest.raises(AuthorityPlaneError, match="Generic DIO execution"):
        record_execution_receipt(
            case,
            action_id=action["action_id"],
            lease=lease,
            valinor_authorization=valinor,
            arda_identity=_arda(),
            executor_system="generic_executor",
            executor_receipt_ref="generic://1",
            success=True,
            executed_at=EXECUTED,
        )


def test_successful_bounded_execution_records_case_receipt_and_consumes_lease():
    case = _case("execute")
    action = _internal_action(case)
    authority = _authority(case, action, "draft_internal")
    lease = _lease(case, action, authority)
    valinor = authorize_valinor(
        lease,
        entity_id="document-studio",
        operation="write",
        target="internal://draft",
        runtime=AllowRuntime(),
        authorized_at="2026-08-11T18:10:00+00:00",
    )
    receipt, consumed = record_execution_receipt(
        case,
        action_id=action["action_id"],
        lease=lease,
        valinor_authorization=valinor,
        arda_identity=_arda(),
        executor_system="document_studio",
        executor_receipt_ref="executor://document-studio/receipt-1",
        success=True,
        executed_at=EXECUTED,
    )
    assert receipt["schema"] == "dio.execution.receipt.v1"
    assert receipt["authority"]["lease_id"] == lease["lease_id"]
    assert receipt["authority"]["valinor_authorization_id"] == valinor["authorization_id"]
    assert consumed["lease_id"] == lease["lease_id"]
    assert consumed["fingerprint"] == lease["fingerprint"]
    assert consumed["state"] == "consumed"
    assert case["actions"][0]["state"] == "executed"
    assert case["actions"][0]["capability_lease_id"] == lease["lease_id"]
    assert f"execution://{receipt['execution_receipt_id']}" in case["event_refs"]
    assert "executor://document-studio/receipt-1" in case["event_refs"]
    with pytest.raises(AuthorityPlaneError, match="not active"):
        validate_capability_lease(consumed, now=EXECUTED)


def test_external_execution_can_pass_only_with_full_chain_and_observed_identity():
    case = _case("external-pass")
    action = _external_action(case)
    authority = _authority(case, action, "outlook_send", scope=["outlook_send", "external_release"])
    lease = _lease(case, action, authority)
    valinor = authorize_valinor(
        lease,
        entity_id="outlook-triage",
        operation="write",
        target="outlook://send",
        runtime=AllowRuntime(),
        authorized_at="2026-08-11T18:10:00+00:00",
    )
    receipt, consumed = record_execution_receipt(
        case,
        action_id=action["action_id"],
        lease=lease,
        valinor_authorization=valinor,
        arda_identity=_arda(mode="observed"),
        executor_system="outlook_triage",
        executor_receipt_ref="outlook://send/receipt-1",
        success=True,
        executed_at=EXECUTED,
    )
    assert receipt["success"] is True
    assert consumed["state"] == "consumed"
    assert case["actions"][0]["state"] == "executed"
