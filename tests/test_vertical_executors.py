from __future__ import annotations

from pathlib import Path

import pytest

from authority.canonical import (
    authorize_valinor,
    make_arda_execution_identity,
    make_authority_receipt,
    make_capability_lease,
)
from executors.vertical import (
    VerticalExecutorError,
    execute_vertical_capability,
    load_vertical_executor_registry,
    prepare_vertical_execution,
)
from products.governed_case import new_case, propose_action, set_gate

ISSUED = "2026-08-11T18:00:00+00:00"
AUTH_EXPIRY = "2026-08-13T18:00:00+00:00"
LEASE_EXPIRY = "2026-08-12T18:00:00+00:00"
EXECUTED = "2026-08-11T18:30:00+00:00"
SHA = "sha256:" + ("c" * 64)
EVIDENCE_SHA = "sha256:" + ("d" * 64)


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


def _case(job_id: str) -> dict:
    return new_case(
        product="dio_agent_authority",
        job_id=job_id,
        source={"source": {}},
        source_path=Path("/tmp/dio-wave5-source.json"),
        evidence_inputs=[],
        expected_outputs=[],
        required_authorities=["operator"],
        intake_state="approved",
    )


def _chain(*, capability: str, external: bool = False, audience: str = "vertical:test", mode: str = "observed"):
    case = _case(capability)
    required_gates = ["intake_authority"]
    risk_tier = "reversible_internal"
    scope = [capability]
    if external:
        set_gate(
            case,
            gate_id="external_release",
            state="allow",
            reason="Explicit human release for Wave 5 test.",
            actor_id="human:byron",
        )
        required_gates.append("external_release")
        risk_tier = "external"
        scope.append("external_release")

    action = propose_action(
        case,
        action_type=capability,
        description=f"Execute bounded {capability}",
        risk_tier=risk_tier,
        reversibility="compensatable" if external else "reversible",
        required_gate_ids=required_gates,
        proposed_by="wave5-test",
    )
    authority = make_authority_receipt(
        case,
        action_id=action["action_id"],
        capability=capability,
        actor_id="human:byron",
        actor_type="human",
        authority_scope=scope,
        verdict="ALLOW",
        evidence_refs=["decision://wave5-human-review"],
        issued_at=ISSUED,
        expires_at=AUTH_EXPIRY,
    )
    lease = make_capability_lease(
        case,
        action_id=action["action_id"],
        authority_receipt=authority,
        principal_id="executor:wave5",
        audience=audience,
        route_scope=["vertical://bounded"],
        output_scope=["receipt_only"],
        resource_ceiling={"operations": 1},
        issued_at=ISSUED,
        expires_at=LEASE_EXPIRY,
        maximum_uses=1,
        revocation_epoch=4,
    )
    valinor = authorize_valinor(
        lease,
        entity_id="executor:wave5",
        operation="write",
        target=f"vertical://{capability}",
        runtime=AllowRuntime(),
        authorized_at="2026-08-11T18:10:00+00:00",
    )
    arda = make_arda_execution_identity(
        node_id="node-wave5",
        workload_digest=SHA,
        attestation_result_id="ATTEST-W5",
        attestation_evidence_digest=EVIDENCE_SHA,
        evidence_mode=mode,
        attestation_status="accepted",
        environment="test",
        audience=audience,
        issued_at=ISSUED,
        expires_at=LEASE_EXPIRY,
    )
    return case, action, lease, valinor, arda


def _capabilities(registry: dict) -> dict[tuple[str, str], dict]:
    return {
        (executor["executor_id"], cap["capability"]): cap
        for executor in registry["executors"]
        for cap in executor["capabilities"]
    }


def test_registry_preserves_wave5_constitution():
    registry = load_vertical_executor_registry()
    laws = registry["laws"]
    assert laws["generic_executor"] is False
    assert laws["automatic_external_actions"] is False
    assert laws["receipt_required"] is True
    assert laws["wave4_authority_chain_required"] is True
    assert laws["bound_means_real_entrypoint"] is True
    assert laws["unproven_external_capabilities_are_locked"] is True


def test_registry_has_eight_vertical_families_and_eight_bound_capabilities():
    registry = load_vertical_executor_registry()
    assert len(registry["executors"]) == 8
    caps = _capabilities(registry)
    assert sum(cap["binding_state"] == "bound" for cap in caps.values()) == 8
    assert sum(cap["binding_state"] == "locked" for cap in caps.values()) == 8


def test_bound_capabilities_have_real_entrypoint_metadata():
    registry = load_vertical_executor_registry()
    for cap in _capabilities(registry).values():
        if cap["binding_state"] == "bound":
            assert cap["entrypoint_kind"] in {"core_callable", "core_cli", "workspace_mount"}
            assert isinstance(cap["entrypoint_ref"], str) and cap["entrypoint_ref"]
        else:
            assert cap["mode"] == "hard_locked"
            assert cap["entrypoint_kind"] == "none"
            assert cap["entrypoint_ref"] is None
            assert cap["lock_reason"]


def test_unproven_dangerous_capabilities_are_hard_locked():
    caps = _capabilities(load_vertical_executor_registry())
    expected = {
        ("vesper_presence", "vesper_external_reply"),
        ("homs", "efundi_publish_marks"),
        ("nichefoundry", "nichefoundry_publish_campaign"),
        ("document_studio", "document_release_external"),
        ("commerce_autorelease", "fulfilment_release"),
        ("market_command", "campaign_release"),
        ("market_command", "campaign_spend"),
        ("phoenix", "phoenix_live_order"),
    }
    assert {key for key, cap in caps.items() if cap["binding_state"] == "locked"} == expected


def test_outlook_remote_draft_is_not_mislabeled_as_local():
    caps = _capabilities(load_vertical_executor_registry())
    draft = caps[("outlook_graph", "outlook_draft_create")]
    assert draft["external_side_effect"] is True
    assert draft["mode"] == "explicit_environment_gate"
    assert draft["entrypoint_ref"] == "scripts/sync_outlook_mail.py:create_outlook_draft"


def test_locked_capability_refuses_before_specialist_execution():
    case, _, lease, valinor, arda = _chain(capability="phoenix_live_order", external=True)
    with pytest.raises(VerticalExecutorError, match="hard locked"):
        prepare_vertical_execution(
            executor_id="phoenix",
            capability="phoenix_live_order",
            lease=lease,
            valinor_authorization=valinor,
            arda_identity=arda,
            payload={"symbol": "BTC/USD"},
            environment_gate=True,
            requested_at=EXECUTED,
        )


def test_external_capability_requires_explicit_environment_gate():
    case, _, lease, valinor, arda = _chain(capability="outlook_send", external=True)
    with pytest.raises(VerticalExecutorError, match="environment gate"):
        prepare_vertical_execution(
            executor_id="outlook_graph",
            capability="outlook_send",
            lease=lease,
            valinor_authorization=valinor,
            arda_identity=arda,
            payload={"draft_id": "draft-1"},
            environment_gate=False,
            requested_at=EXECUTED,
        )


def test_external_capability_requires_observed_or_enforced_arda():
    case, _, lease, valinor, arda = _chain(capability="outlook_send", external=True, mode="synthetic")
    with pytest.raises(VerticalExecutorError, match="observed or enforced"):
        prepare_vertical_execution(
            executor_id="outlook_graph",
            capability="outlook_send",
            lease=lease,
            valinor_authorization=valinor,
            arda_identity=arda,
            payload={"draft_id": "draft-1"},
            environment_gate=True,
            requested_at=EXECUTED,
        )


def test_capability_lease_must_match_vertical_capability():
    case, _, lease, valinor, arda = _chain(capability="document_convert")
    with pytest.raises(VerticalExecutorError, match="does not match"):
        prepare_vertical_execution(
            executor_id="homs",
            capability="homs_prepare_assessment",
            lease=lease,
            valinor_authorization=valinor,
            arda_identity=arda,
            payload={"job_id": "x"},
            requested_at=EXECUTED,
        )


def test_payload_is_bound_into_vertical_request_identity():
    case, _, lease, valinor, arda = _chain(capability="document_convert")
    first = prepare_vertical_execution(
        executor_id="document_studio",
        capability="document_convert",
        lease=lease,
        valinor_authorization=valinor,
        arda_identity=arda,
        payload={"source": "a.docx", "output": "a.pdf"},
        requested_at=EXECUTED,
    )
    second = prepare_vertical_execution(
        executor_id="document_studio",
        capability="document_convert",
        lease=lease,
        valinor_authorization=valinor,
        arda_identity=arda,
        payload={"source": "a.docx", "output": "b.pdf"},
        requested_at=EXECUTED,
    )
    assert first["payload_digest"] != second["payload_digest"]
    assert first["vertical_request_id"] != second["vertical_request_id"]


def test_specialist_callback_is_not_called_when_preflight_fails():
    case, _, lease, valinor, arda = _chain(capability="outlook_send", external=True)
    called = False

    def specialist(_: dict) -> dict:
        nonlocal called
        called = True
        return {}

    with pytest.raises(VerticalExecutorError, match="environment gate"):
        execute_vertical_capability(
            case,
            executor_id="outlook_graph",
            capability="outlook_send",
            lease=lease,
            valinor_authorization=valinor,
            arda_identity=arda,
            specialist_executor=specialist,
            payload={"draft_id": "draft-1"},
            environment_gate=False,
            executed_at=EXECUTED,
        )
    assert called is False


def test_specialist_receipt_must_echo_exact_request_and_payload():
    case, _, lease, valinor, arda = _chain(capability="document_convert")

    def forged(envelope: dict) -> dict:
        request = envelope["request"]
        return {
            "success": True,
            "receipt_ref": "document://convert/receipt-1",
            "vertical_request_id": "VEXEC-FORGED",
            "payload_digest": request["payload_digest"],
        }

    with pytest.raises(VerticalExecutorError, match="exact vertical request"):
        execute_vertical_capability(
            case,
            executor_id="document_studio",
            capability="document_convert",
            lease=lease,
            valinor_authorization=valinor,
            arda_identity=arda,
            specialist_executor=forged,
            payload={"source": "a.docx", "output": "a.pdf"},
            executed_at=EXECUTED,
        )


def test_specialist_receipt_prefix_is_enforced():
    case, _, lease, valinor, arda = _chain(capability="document_convert")

    def wrong_prefix(envelope: dict) -> dict:
        request = envelope["request"]
        return {
            "success": True,
            "receipt_ref": "outlook://send/not-a-document-receipt",
            "vertical_request_id": request["vertical_request_id"],
            "payload_digest": request["payload_digest"],
        }

    with pytest.raises(VerticalExecutorError, match="prefix"):
        execute_vertical_capability(
            case,
            executor_id="document_studio",
            capability="document_convert",
            lease=lease,
            valinor_authorization=valinor,
            arda_identity=arda,
            specialist_executor=wrong_prefix,
            payload={"source": "a.docx", "output": "a.pdf"},
            executed_at=EXECUTED,
        )


def test_successful_local_vertical_execution_closes_wave4_receipt_and_consumes_lease():
    case, action, lease, valinor, arda = _chain(capability="document_convert")

    def specialist(envelope: dict) -> dict:
        request = envelope["request"]
        return {
            "success": True,
            "receipt_ref": "document://convert/receipt-1",
            "vertical_request_id": request["vertical_request_id"],
            "payload_digest": request["payload_digest"],
            "files": ["out.pdf"],
        }

    result = execute_vertical_capability(
        case,
        executor_id="document_studio",
        capability="document_convert",
        lease=lease,
        valinor_authorization=valinor,
        arda_identity=arda,
        specialist_executor=specialist,
        payload={"source": "a.docx", "output": "a.pdf"},
        executed_at=EXECUTED,
    )
    assert result["execution_receipt"]["schema"] == "dio.execution.receipt.v1"
    assert result["execution_receipt"]["executor_system"] == "document_studio"
    assert result["consumed_lease"]["state"] == "consumed"
    assert result["consumed_lease"]["lease_id"] == lease["lease_id"]
    assert case["actions"][0]["action_id"] == action["action_id"]
    assert case["actions"][0]["state"] == "executed"


def test_successful_external_outlook_execution_requires_full_chain_and_gate():
    case, _, lease, valinor, arda = _chain(capability="outlook_send", external=True)

    def specialist(envelope: dict) -> dict:
        request = envelope["request"]
        return {
            "success": True,
            "receipt_ref": "outlook://send/mail-receipt-1",
            "vertical_request_id": request["vertical_request_id"],
            "payload_digest": request["payload_digest"],
            "provider_status": "accepted",
        }

    result = execute_vertical_capability(
        case,
        executor_id="outlook_graph",
        capability="outlook_send",
        lease=lease,
        valinor_authorization=valinor,
        arda_identity=arda,
        specialist_executor=specialist,
        payload={"draft_id": "immutable-draft-id"},
        environment_gate=True,
        executed_at=EXECUTED,
    )
    assert result["request"]["external_side_effect"] is True
    assert result["request"]["entrypoint_ref"] == "scripts/sync_outlook_mail.py:send_outlook_draft"
    assert result["execution_receipt"]["success"] is True
