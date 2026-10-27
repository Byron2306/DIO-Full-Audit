from __future__ import annotations

import json
from pathlib import Path

from adapters.legalis.decision_ledger import issue_decision
from adapters.legalis.service import bind_to_governed_case, evaluate_capability
from adapters.legalis.valinor_bridge import authorize_valinor_boundary
from products.governed_case import new_case

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = json.loads((ROOT / "config" / "legalis" / "legal_identity.json").read_text(encoding="utf-8"))
REGISTRY = json.loads((ROOT / "config" / "legalis" / "requirement_registry.json").read_text(encoding="utf-8"))
NOW = "2026-08-11T15:00:00+00:00"


def test_seeded_identity_is_explicitly_unregistered_and_mailbox_classified():
    assert IDENTITY["registered_entity"] is False
    assert IDENTITY["registered_company"] is False
    assert IDENTITY["entity_type"] == "unregistered_trading_brand"
    assert IDENTITY["contact_channels"]["linkedin_community_management"]["domain_classification"] == "personal_domain"


def test_missing_operator_check_yields_needs_you_not_fake_allow():
    decision = evaluate_capability(capability_id="linkedin_community_management_vetting", identity=IDENTITY, registry=REGISTRY, now=NOW)
    assert decision["verdict"] == "NEEDS_YOU"
    assert decision["configured_prerequisites_satisfied"] is False


def test_configured_prerequisites_can_allow_without_claiming_legal_clearance():
    decision = evaluate_capability(capability_id="linkedin_community_management_vetting", identity=IDENTITY, registry=REGISTRY, operator_checks={"platform_requirements_reviewed": {"value": True, "receipt_ref": "operator://linkedin-review"}}, now=NOW)
    assert decision["verdict"] == "ALLOW"
    assert decision["legal_clearance"] is False
    assert decision["legal_opinion"] is False
    assert decision["kernel_authority"] == "Valinor"
    assert decision["kernel_enforcement_performed"] is False


def test_consequential_contract_gate_refuses_explicit_missing_approval():
    decision = evaluate_capability(capability_id="contract_or_filing", identity=IDENTITY, registry=REGISTRY, operator_checks={"authorised_human_or_professional_approval": False}, now=NOW)
    assert decision["verdict"] == "REFUSE"


def test_expired_evidence_does_not_satisfy_requirement():
    registry = {"schema": "dio.legalis.requirement_registry.v1", "registry_id": "test", "capabilities": [{"capability_id": "evidence_test", "requirements": [{"requirement_id": "current_authority", "kind": "evidence", "evidence_kind": "authority_receipt", "minimum_authority_grade": "source_backed", "stale_verdict": "NEEDS_YOU"}]}]}
    decision = evaluate_capability(capability_id="evidence_test", identity=IDENTITY, registry=registry, evidence=[{"evidence_id": "E-1", "kind": "authority_receipt", "source_ref": "authority://example", "authority_grade": "source_backed", "trust_state": "trusted_for_review", "expires_at": "2026-08-10T00:00:00+00:00"}], now=NOW)
    assert decision["verdict"] == "NEEDS_YOU"
    assert decision["requirement_results"][0]["state"] == "stale"


def test_legalis_projects_a_distinct_gate_into_governed_case(tmp_path: Path):
    decision = evaluate_capability(capability_id="public_marketing_release", identity=IDENTITY, registry=REGISTRY, operator_checks={"public_claim_review_complete": True}, now=NOW)
    case = new_case(product="dio_assurance", job_id="job-legalis-test", source={}, source_path=tmp_path / "source.json", evidence_inputs=[], expected_outputs=[], required_authorities=["operator", "release_authority"], intake_state="approved", now=NOW)
    gate = bind_to_governed_case(case, decision, receipt_ref="receipt://legalis/test")
    assert gate["gate_id"] == "legalis:public_marketing_release"
    assert gate["state"] == "allow"
    assert "receipt://legalis/test" in case["event_refs"]
    assert next(row for row in case["gates"] if row["gate_id"] == "external_release")["state"] == "needs_you"


class FakeRuntime:
    def __init__(self): self.calls = []
    def write_stream(self, entity_id, target): self.calls.append(("write", entity_id, target)); return {"allowed": True}
    def open_socket(self, entity_id): self.calls.append(("socket", entity_id, None)); return {"allowed": True}
    def send_ipc(self, entity_id): self.calls.append(("ipc", entity_id, None)); return {"allowed": True}
    def access_secret(self, entity_id, target): self.calls.append(("secret", entity_id, target)); return True
    def syscall(self, entity_id, target): self.calls.append(("syscall", entity_id, target)); return "allowed"
    def apply_flow_shape(self, entity_id): self.calls.append(("flow", entity_id, None)); return {"allowed": True}


def _authenticated(tmp_path, monkeypatch, capability_id, target, operator_checks=None):
    monkeypatch.setenv("DIO_LEGALIS_HMAC_KEYS_JSON", json.dumps({"test-epoch": "k" * 32}))
    monkeypatch.setenv("DIO_LEGALIS_HMAC_KEY_EPOCH", "test-epoch")
    request = {
        "capability_id": capability_id,
        "case_id": "CASE-TEST",
        "operator_checks": operator_checks or {},
        "valinor": {"entity_id": "dio-workflows", "operation": "write", "target": target},
    }
    envelope = issue_decision(
        tmp_path,
        request=request,
        actor_id="test-operator",
        policy_version="test-policy-v1",
    )
    evidence = envelope["evidence_binding"]
    return envelope, request, evidence


def test_valinor_is_not_invoked_unless_legalis_allows(tmp_path, monkeypatch):
    runtime = FakeRuntime()
    envelope, request, evidence = _authenticated(tmp_path, monkeypatch, "contract_or_filing", "external://contract")
    receipt = authorize_valinor_boundary(decision_id=envelope["decision_id"], state_root=tmp_path, request=request, evidence=evidence, expected_capability="contract_or_filing", expected_policy_version="test-policy-v1", entity_id="dio-workflows", operation="write", target="external://contract", runtime=runtime)
    assert receipt["allowed"] is False
    assert receipt["state"] == "LEGALIS_NOT_ALLOWED"
    assert runtime.calls == []


def test_valinor_remains_kernel_authority_after_legalis_allow(tmp_path, monkeypatch):
    runtime = FakeRuntime()
    checks = {"public_claim_review_complete": {"value": True, "receipt_ref": "operator://review/test"}}
    envelope, request, evidence = _authenticated(tmp_path, monkeypatch, "public_marketing_release", "public://marketing", checks)
    receipt = authorize_valinor_boundary(decision_id=envelope["decision_id"], state_root=tmp_path, request=request, evidence=evidence, expected_capability="public_marketing_release", expected_policy_version="test-policy-v1", entity_id="dio-workflows", operation="write", target="public://marketing", runtime=runtime)
    assert receipt["allowed"] is True
    assert receipt["state"] == "VALINOR_ALLOW"
    assert receipt["external_action_executed"] is False
    assert runtime.calls == [("write", "dio-workflows", "public://marketing")]
