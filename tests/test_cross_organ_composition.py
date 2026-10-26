from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from authority.canonical import (
    authorize_valinor,
    make_arda_execution_identity,
    make_authority_receipt,
    make_capability_lease,
)
from composition import (
    CompositionError,
    finalize_case_composition,
    load_composition_profiles,
    make_composition_ledger,
    make_vertical_execution_bundle,
    ready_stage_ids,
    record_case_stage,
    validate_composition_ledger,
)
from executors.vertical import VerticalExecutorError, execute_vertical_capability, prepare_vertical_execution
from fusion.contracts import make_assertion
from products.governed_case import new_case, propose_action, set_gate

ISSUED = "2026-08-11T19:15:00+00:00"
AUTHORIZED = "2026-08-11T19:20:00+00:00"
EXECUTED = "2026-08-11T19:25:00+00:00"
AUTH_EXPIRY = "2026-08-13T19:15:00+00:00"
LEASE_EXPIRY = "2026-08-12T19:15:00+00:00"
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


def make_case(tmp_path: Path, job_id: str = "wave6") -> dict:
    source_path = tmp_path / f"{job_id}.json"
    source_path.write_text("{}", encoding="utf-8")
    return new_case(
        product="dio_agent_authority",
        job_id=job_id,
        source={"source": {}, "attribution": {}, "evidence": []},
        source_path=source_path,
        evidence_inputs=[],
        expected_outputs=[],
        required_authorities=["operator", "release_operator"],
        intake_state="approved",
        now=ISSUED,
    )


def fusion_artifact(
    case: dict,
    system_id: str,
    assertion_type: str,
    stage_id: str,
    *,
    severity: str = "advisory",
    source_refs: list[str] | None = None,
) -> dict:
    if assertion_type in {"evidence", "observation"}:
        payload = {
            "source_ref": f"{system_id}://{stage_id}",
            "sha256": "c" * 64,
            "observed_at": ISSUED,
        }
    elif assertion_type == "challenge":
        payload = {
            "target_type": "case",
            "target_id": case["case_id"],
            "challenge_type": "alternative_hypothesis",
            "severity": severity,
            "hypothesis": f"{system_id} challenge at {stage_id}",
        }
    elif assertion_type == "requirement":
        payload = {
            "statement": f"Requirement produced at {stage_id}",
            "kind": "framework",
            "mandatory": True,
        }
    elif assertion_type == "decision":
        payload = {
            "decision_type": "requirement",
            "verdict": "ALLOW",
            "reasoning_summary": f"{system_id} readiness recorded at {stage_id}",
        }
    elif assertion_type == "receipt":
        payload = {"status": "complete", "stage_id": stage_id}
    else:
        raise AssertionError(assertion_type)
    return make_assertion(
        assertion_type=assertion_type,
        issuer_system=system_id,
        issuer_role=stage_id,
        subject_kind="case",
        subject_ref=case["case_id"],
        payload=payload,
        source_refs=source_refs or [],
        case_id=case["case_id"],
        created_at=ISSUED,
        epistemic_state="N/A" if assertion_type == "receipt" else "UNVERIFIED",
        authority_grade="N/A" if assertion_type == "receipt" else "source_backed",
        trust_state="N/A" if assertion_type == "receipt" else "captured_untrusted",
        freshness_state="N/A" if assertion_type == "receipt" else "current",
    )


def record_semantic_prefix(case: dict, ledger: dict, *, challenge_severity: str = "advisory") -> None:
    record_case_stage(case, ledger, stage_id="ingress", artifacts=[fusion_artifact(case, "vesper_presence", "observation", "ingress")], recorded_at=ISSUED)
    record_case_stage(case, ledger, stage_id="epistemic", artifacts=[fusion_artifact(case, "sophia_integritas", "evidence", "epistemic")], recorded_at=ISSUED)
    record_case_stage(case, ledger, stage_id="provenance", artifacts=[fusion_artifact(case, "evidex", "evidence", "provenance")], recorded_at=ISSUED)
    record_case_stage(case, ledger, stage_id="custody", artifacts=[fusion_artifact(case, "beast", "receipt", "custody")], recorded_at=ISSUED)
    record_case_stage(case, ledger, stage_id="adversarial", artifacts=[fusion_artifact(case, "seraph", "challenge", "adversarial", severity=challenge_severity)], recorded_at=ISSUED)
    record_case_stage(case, ledger, stage_id="coherence", artifacts=[fusion_artifact(case, "metatron", "observation", "coherence")], recorded_at=ISSUED)
    record_case_stage(case, ledger, stage_id="framework", artifacts=[fusion_artifact(case, "dio_core", "requirement", "framework")], recorded_at=ISSUED)
    record_case_stage(case, ledger, stage_id="legal_readiness", artifacts=[fusion_artifact(case, "legalis", "decision", "legal_readiness")], recorded_at=ISSUED)


def external_authority_chain(case: dict, *, capability: str = "outlook_send", audience: str = "outlook_graph") -> tuple[dict, dict, dict, dict, dict]:
    set_gate(
        case,
        gate_id="external_release",
        state="allow",
        reason="Explicit human release for the Wave 6 composition test.",
        actor_id="human:byron",
    )
    action = propose_action(
        case,
        action_type=capability,
        description="Perform one bounded external Wave 6 composition action",
        risk_tier="external",
        reversibility="compensatable",
        required_gate_ids=["intake_authority", "external_release"],
        proposed_by="outlook_triage",
    )
    authority = make_authority_receipt(
        case,
        action_id=action["action_id"],
        capability=capability,
        actor_id="human:byron",
        actor_type="human",
        authority_scope=[capability, "external_release"],
        verdict="ALLOW",
        evidence_refs=["composition://human-review"],
        issued_at=ISSUED,
        expires_at=AUTH_EXPIRY,
    )
    lease = make_capability_lease(
        case,
        action_id=action["action_id"],
        authority_receipt=authority,
        principal_id=f"executor:{audience}",
        audience=audience,
        route_scope=["outlook://bounded"],
        output_scope=["receipt_only"],
        resource_ceiling={"operations": 1},
        issued_at=ISSUED,
        expires_at=LEASE_EXPIRY,
        maximum_uses=1,
        revocation_epoch=6,
    )
    valinor = authorize_valinor(
        lease,
        entity_id=audience,
        operation="write",
        target="outlook://send",
        runtime=AllowRuntime(),
        authorized_at=AUTHORIZED,
    )
    arda = make_arda_execution_identity(
        node_id="node-wave6",
        workload_digest=SHA,
        attestation_result_id="ATTEST-WAVE6",
        attestation_evidence_digest=EVIDENCE_SHA,
        evidence_mode="observed",
        attestation_status="accepted",
        environment="local-test",
        audience=audience,
        issued_at=ISSUED,
        expires_at=LEASE_EXPIRY,
    )
    return action, authority, lease, valinor, arda


def execute_outlook(case: dict, lease: dict, valinor: dict, arda: dict, *, payload: dict | None = None) -> dict:
    def specialist(envelope: dict) -> dict:
        request = envelope["request"]
        return {
            "receipt_ref": "outlook://send/WAVE6-TEST",
            "success": True,
            "vertical_request_id": request["vertical_request_id"],
            "payload_digest": request["payload_digest"],
        }

    result = execute_vertical_capability(
        case,
        executor_id="outlook_graph",
        capability="outlook_send",
        lease=lease,
        valinor_authorization=valinor,
        arda_identity=arda,
        specialist_executor=specialist,
        payload=payload or {"draft_id": "draft-wave6", "recipient_ref": "test-recipient"},
        environment_gate=True,
        executed_at=EXECUTED,
    )
    return make_vertical_execution_bundle(result)


def _refingerprint_authority(row: dict) -> dict:
    forged = copy.deepcopy(row)
    forged.pop("fingerprint", None)
    forged.pop("authority_receipt_id", None)
    raw = json.dumps(forged, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    forged["fingerprint"] = digest
    forged["authority_receipt_id"] = f"AUTH-{digest[:16].upper()}"
    return forged


def test_composition_registry_schema_and_constitutional_laws() -> None:
    schema = json.loads(Path("schemas/dio_composition_profiles.schema.json").read_text(encoding="utf-8"))
    payload = json.loads(Path("config/dio_composition_profiles.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(payload)
    loaded = load_composition_profiles()
    assert loaded["laws"]["composition_has_no_authority"] is True
    assert loaded["laws"]["valinor_remains_sole_kernel_authority"] is True
    assert loaded["laws"]["external_execution_requires_wave5_bundle"] is True


def test_full_profile_is_a_real_dependency_dag() -> None:
    profile = next(row for row in load_composition_profiles()["profiles"] if row["profile_id"] == "full_governed_external_action")
    stages = {row["stage_id"]: row for row in profile["stages"]}
    assert len(stages) == 14
    assert stages["epistemic"]["depends_on"] == ["ingress"]
    assert stages["provenance"]["depends_on"] == ["ingress"]
    assert set(stages["custody"]["depends_on"]) == {"epistemic", "provenance"}
    assert set(stages["vertical_execution"]["depends_on"]) == {"kernel_authority", "execution_identity"}
    assert stages["egress"]["depends_on"] == ["vertical_execution"]


def test_composition_plan_is_deterministic_for_same_case_profile_and_time(tmp_path: Path) -> None:
    case = make_case(tmp_path, "deterministic")
    first = make_composition_ledger(case, profile_id="full_governed_external_action", created_at=ISSUED)
    second = make_composition_ledger(case, profile_id="full_governed_external_action", created_at=ISSUED)
    assert first["plan"]["composition_id"] == second["plan"]["composition_id"]
    assert first["plan"]["fingerprint"] == second["plan"]["fingerprint"]
    assert first["plan"]["authority"]["composition_has_authority"] is False


def test_ingress_fans_out_to_sophia_and_evidex(tmp_path: Path) -> None:
    case = make_case(tmp_path, "fanout")
    ledger = make_composition_ledger(case, profile_id="full_governed_external_action", created_at=ISSUED)
    assert ready_stage_ids(ledger) == ["ingress"]
    record_case_stage(case, ledger, stage_id="ingress", artifacts=[fusion_artifact(case, "vesper_presence", "observation", "ingress")], recorded_at=ISSUED)
    assert set(ready_stage_ids(ledger)) == {"epistemic", "provenance"}


def test_dependency_cannot_be_bypassed(tmp_path: Path) -> None:
    case = make_case(tmp_path, "dependency")
    ledger = make_composition_ledger(case, profile_id="full_governed_external_action", created_at=ISSUED)
    with pytest.raises(CompositionError, match="blocked by dependency ingress"):
        record_case_stage(case, ledger, stage_id="epistemic", artifacts=[fusion_artifact(case, "sophia_integritas", "evidence", "epistemic")], recorded_at=ISSUED)


def test_wrong_organ_issuer_is_transactionally_refused(tmp_path: Path) -> None:
    case = make_case(tmp_path, "wrong-issuer")
    ledger = make_composition_ledger(case, profile_id="full_governed_external_action", created_at=ISSUED)
    before_case = copy.deepcopy(case)
    before_ledger = copy.deepcopy(ledger)
    wrong = fusion_artifact(case, "evidex", "observation", "ingress")
    with pytest.raises(CompositionError, match="expected issuer vesper_presence"):
        record_case_stage(case, ledger, stage_id="ingress", artifacts=[wrong], recorded_at=ISSUED)
    assert case == before_case
    assert ledger == before_ledger


def test_cross_case_artifact_is_refused(tmp_path: Path) -> None:
    case = make_case(tmp_path, "case-a")
    other = make_case(tmp_path, "case-b")
    ledger = make_composition_ledger(case, profile_id="full_governed_external_action", created_at=ISSUED)
    alien = fusion_artifact(other, "vesper_presence", "observation", "ingress")
    with pytest.raises(CompositionError, match="not bound to this composition case"):
        record_case_stage(case, ledger, stage_id="ingress", artifacts=[alien], recorded_at=ISSUED)


def test_blocking_seraph_challenge_stops_human_authority(tmp_path: Path) -> None:
    case = make_case(tmp_path, "blocking-seraph")
    ledger = make_composition_ledger(case, profile_id="full_governed_external_action", created_at=ISSUED)
    record_semantic_prefix(case, ledger, challenge_severity="blocking")
    _, authority, _, _, _ = external_authority_chain(case)
    with pytest.raises(CompositionError, match="blocking challenges remain open"):
        record_case_stage(case, ledger, stage_id="human_authority", artifacts=[authority], recorded_at=AUTHORIZED)


def test_machine_forged_authority_is_rejected_even_if_refingerprinted(tmp_path: Path) -> None:
    case = make_case(tmp_path, "machine-authority")
    ledger = make_composition_ledger(case, profile_id="full_governed_external_action", created_at=ISSUED)
    record_semantic_prefix(case, ledger)
    _, authority, _, _, _ = external_authority_chain(case)
    forged = copy.deepcopy(authority)
    forged["actor"]["actor_type"] = "system"
    forged = _refingerprint_authority(forged)
    with pytest.raises(CompositionError, match="Machine/service authority receipts are not accepted"):
        record_case_stage(case, ledger, stage_id="human_authority", artifacts=[forged], recorded_at=AUTHORIZED)


def test_capability_lease_must_bind_the_composition_authority_receipt(tmp_path: Path) -> None:
    case = make_case(tmp_path, "lease-authority-binding")
    ledger = make_composition_ledger(case, profile_id="full_governed_external_action", created_at=ISSUED)
    record_semantic_prefix(case, ledger)
    action, authority_a, lease_a, _, _ = external_authority_chain(case)
    authority_b = make_authority_receipt(
        case,
        action_id=action["action_id"],
        capability="outlook_send",
        actor_id="organisation:test",
        actor_type="organisation",
        authority_scope=["outlook_send", "external_release"],
        verdict="ALLOW",
        issued_at=ISSUED,
        expires_at=AUTH_EXPIRY,
    )
    record_case_stage(case, ledger, stage_id="human_authority", artifacts=[authority_b], recorded_at=AUTHORIZED)
    with pytest.raises(CompositionError, match="not bound to the composition authority receipt"):
        record_case_stage(case, ledger, stage_id="capability_lease", artifacts=[lease_a], recorded_at=AUTHORIZED)
    assert authority_a["authority_receipt_id"] != authority_b["authority_receipt_id"]


def test_valinor_authorization_must_bind_exact_composition_lease(tmp_path: Path) -> None:
    case = make_case(tmp_path, "valinor-lease-binding")
    ledger = make_composition_ledger(case, profile_id="full_governed_external_action", created_at=ISSUED)
    record_semantic_prefix(case, ledger)
    action, authority, lease_a, _, _ = external_authority_chain(case)
    record_case_stage(case, ledger, stage_id="human_authority", artifacts=[authority], recorded_at=AUTHORIZED)
    record_case_stage(case, ledger, stage_id="capability_lease", artifacts=[lease_a], recorded_at=AUTHORIZED)
    lease_b = make_capability_lease(
        case,
        action_id=action["action_id"],
        authority_receipt=authority,
        principal_id="executor:other",
        audience="other-audience",
        issued_at=ISSUED,
        expires_at=LEASE_EXPIRY,
        maximum_uses=1,
        revocation_epoch=7,
    )
    valinor_b = authorize_valinor(
        lease_b,
        entity_id="other-audience",
        operation="write",
        target="outlook://send",
        runtime=AllowRuntime(),
        authorized_at=AUTHORIZED,
    )
    with pytest.raises(CompositionError, match="not bound to this lease"):
        record_case_stage(case, ledger, stage_id="kernel_authority", artifacts=[valinor_b], recorded_at=AUTHORIZED)


def test_arda_identity_must_match_lease_audience(tmp_path: Path) -> None:
    case = make_case(tmp_path, "arda-audience")
    ledger = make_composition_ledger(case, profile_id="full_governed_external_action", created_at=ISSUED)
    record_semantic_prefix(case, ledger)
    _, authority, lease, _, _ = external_authority_chain(case)
    record_case_stage(case, ledger, stage_id="human_authority", artifacts=[authority], recorded_at=AUTHORIZED)
    record_case_stage(case, ledger, stage_id="capability_lease", artifacts=[lease], recorded_at=AUTHORIZED)
    wrong = make_arda_execution_identity(
        node_id="node-wave6",
        workload_digest=SHA,
        attestation_result_id="ATTEST-WRONG",
        attestation_evidence_digest=EVIDENCE_SHA,
        evidence_mode="observed",
        attestation_status="accepted",
        environment="local-test",
        audience="wrong-audience",
        issued_at=ISSUED,
        expires_at=LEASE_EXPIRY,
    )
    with pytest.raises(CompositionError, match="audience does not match"):
        record_case_stage(case, ledger, stage_id="execution_identity", artifacts=[wrong], recorded_at=AUTHORIZED)


def test_locked_wave5_capability_cannot_enter_composition_execution(tmp_path: Path) -> None:
    case = make_case(tmp_path, "locked-phoenix")
    set_gate(case, gate_id="external_release", state="allow", reason="test", actor_id="human:byron")
    action = propose_action(
        case,
        action_type="phoenix_live_order",
        description="Attempt a live Phoenix order",
        risk_tier="irreversible",
        reversibility="irreversible",
        required_gate_ids=["intake_authority", "external_release"],
        proposed_by="phoenix",
    )
    authority = make_authority_receipt(
        case,
        action_id=action["action_id"],
        capability="phoenix_live_order",
        actor_id="human:byron",
        actor_type="human",
        authority_scope=["phoenix_live_order", "external_release"],
        verdict="ALLOW",
        issued_at=ISSUED,
        expires_at=AUTH_EXPIRY,
    )
    lease = make_capability_lease(
        case,
        action_id=action["action_id"],
        authority_receipt=authority,
        principal_id="executor:phoenix",
        audience="phoenix",
        issued_at=ISSUED,
        expires_at=LEASE_EXPIRY,
    )
    valinor = authorize_valinor(lease, entity_id="phoenix", operation="write", target="phoenix://live-order", runtime=AllowRuntime(), authorized_at=AUTHORIZED)
    arda = make_arda_execution_identity(
        node_id="node-wave6",
        workload_digest=SHA,
        attestation_result_id="ATTEST-PHOENIX",
        attestation_evidence_digest=EVIDENCE_SHA,
        evidence_mode="observed",
        attestation_status="accepted",
        environment="local-test",
        audience="phoenix",
        issued_at=ISSUED,
        expires_at=LEASE_EXPIRY,
    )
    with pytest.raises(VerticalExecutorError, match="hard locked"):
        prepare_vertical_execution(
            executor_id="phoenix",
            capability="phoenix_live_order",
            lease=lease,
            valinor_authorization=valinor,
            arda_identity=arda,
            payload={"symbol": "BTC/USD", "side": "buy"},
            environment_gate=True,
            requested_at=EXECUTED,
        )


def test_vertical_bundle_payload_tamper_is_refused(tmp_path: Path) -> None:
    case = make_case(tmp_path, "payload-tamper")
    ledger = make_composition_ledger(case, profile_id="full_governed_external_action", created_at=ISSUED)
    record_semantic_prefix(case, ledger)
    _, authority, lease, valinor, arda = external_authority_chain(case)
    record_case_stage(case, ledger, stage_id="human_authority", artifacts=[authority], recorded_at=AUTHORIZED)
    record_case_stage(case, ledger, stage_id="capability_lease", artifacts=[lease], recorded_at=AUTHORIZED)
    record_case_stage(case, ledger, stage_id="kernel_authority", artifacts=[valinor], recorded_at=AUTHORIZED)
    record_case_stage(case, ledger, stage_id="execution_identity", artifacts=[arda], recorded_at=AUTHORIZED)
    bundle = execute_outlook(case, lease, valinor, arda)
    bundle["specialist_receipt"]["payload_digest"] = "sha256:" + ("0" * 64)
    with pytest.raises(CompositionError, match="payload digest"):
        record_case_stage(case, ledger, stage_id="vertical_execution", artifacts=[bundle], recorded_at=EXECUTED)


def test_needs_you_stage_can_resume_with_explicit_revision_lineage(tmp_path: Path) -> None:
    case = make_case(tmp_path, "resume")
    ledger = make_composition_ledger(case, profile_id="full_governed_external_action", created_at=ISSUED)
    first = record_case_stage(case, ledger, stage_id="ingress", status="needs_you", summary="Identity clarification required", recorded_at=ISSUED)
    assert ledger["state"] == "needs_you"
    second = record_case_stage(case, ledger, stage_id="ingress", artifacts=[fusion_artifact(case, "vesper_presence", "observation", "ingress")], recorded_at=AUTHORIZED)
    assert second["supersedes_stage_receipt_id"] == first["stage_receipt_id"]
    assert set(ready_stage_ids(ledger)) == {"epistemic", "provenance"}
    validate_composition_ledger(ledger)


def test_full_external_cross_organ_composition_completes_on_one_case_spine(tmp_path: Path) -> None:
    case = make_case(tmp_path, "full-organism")
    ledger = make_composition_ledger(case, profile_id="full_governed_external_action", created_at=ISSUED)
    record_semantic_prefix(case, ledger)
    _, authority, lease, valinor, arda = external_authority_chain(case)
    record_case_stage(case, ledger, stage_id="human_authority", artifacts=[authority], recorded_at=AUTHORIZED)
    record_case_stage(case, ledger, stage_id="capability_lease", artifacts=[lease], recorded_at=AUTHORIZED)
    record_case_stage(case, ledger, stage_id="kernel_authority", artifacts=[valinor], recorded_at=AUTHORIZED)
    record_case_stage(case, ledger, stage_id="execution_identity", artifacts=[arda], recorded_at=AUTHORIZED)
    bundle = execute_outlook(case, lease, valinor, arda, payload={"draft_id": "draft-wave6", "recipient_ref": "test-recipient"})
    record_case_stage(case, ledger, stage_id="vertical_execution", artifacts=[bundle], recorded_at=EXECUTED)
    execution_id = bundle["execution_receipt"]["execution_receipt_id"]
    egress = fusion_artifact(
        case,
        "vesper_presence",
        "receipt",
        "egress",
        source_refs=[f"execution://{execution_id}"],
    )
    record_case_stage(case, ledger, stage_id="egress", artifacts=[egress], recorded_at=EXECUTED)
    receipt = finalize_case_composition(case, ledger, completed_at=EXECUTED)

    assert receipt["state"] == "COMPOSITION_COMPLETE"
    assert receipt["final_state"] == "executed_and_egressed"
    assert receipt["authority"]["composition_created_authority"] is False
    assert receipt["authority"]["kernel_authority"] == "Valinor"
    assert receipt["authority_chain"]["authority_receipt_id"] == authority["authority_receipt_id"]
    assert receipt["authority_chain"]["lease_id"] == lease["lease_id"]
    assert receipt["authority_chain"]["valinor_authorization_id"] == valinor["authorization_id"]
    assert receipt["authority_chain"]["arda_execution_identity_id"] == arda["execution_identity_id"]
    assert receipt["authority_chain"]["execution_receipt_id"] == execution_id
    assert len(receipt["stage_receipt_ids"]) == 14
    assert f"composition://{receipt['composition_receipt_id']}" in case["event_refs"]
    assert f"execution://{execution_id}" in case["event_refs"]
    assert ledger["state"] == "complete"
