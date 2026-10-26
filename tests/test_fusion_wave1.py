from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from fusion.case_projection import project_assertion
from fusion.contracts import make_assertion, validate_assertion
from products.governed_case import new_case


def make_case(tmp_path: Path) -> dict:
    source_path = tmp_path / "source.json"
    source_path.write_text("{}", encoding="utf-8")
    return new_case(
        product="dio_assurance",
        job_id="fusion-wave1-test",
        source={"source": {}, "attribution": {}, "evidence": []},
        source_path=source_path,
        evidence_inputs=[],
        expected_outputs=["receipt"],
        required_authorities=["operator", "release_operator"],
        intake_state="approved",
        now="2026-08-11T17:30:00+00:00",
    )


def test_fusion_schema_and_deterministic_fingerprint() -> None:
    schema = json.loads(Path("schemas/dio_fusion_assertion.schema.json").read_text(encoding="utf-8"))
    row = make_assertion(
        assertion_type="evidence",
        issuer_system="beast",
        issuer_role="evidence_custody",
        subject_kind="artifact",
        subject_ref="artifact://1",
        payload={"sha256": "a" * 64},
        created_at="2026-08-11T17:30:00+00:00",
    )
    Draft202012Validator(schema).validate(row)
    twin = make_assertion(
        assertion_type="evidence",
        issuer_system="beast",
        issuer_role="evidence_custody",
        subject_kind="artifact",
        subject_ref="artifact://1",
        payload={"sha256": "a" * 64},
        created_at="2026-08-11T17:30:00+00:00",
    )
    assert row["assertion_id"] == twin["assertion_id"]
    assert row["fingerprint"] == twin["fingerprint"]


def test_non_valinor_organ_cannot_mint_kernel_authority() -> None:
    with pytest.raises(ValueError, match="Only Valinor"):
        make_assertion(
            assertion_type="authority",
            issuer_system="seraph",
            issuer_role="challenge",
            subject_kind="action",
            subject_ref="action://1",
            payload={"verdict": "ALLOW"},
            kernel_authorized=True,
        )


def test_machine_organ_cannot_mint_external_release() -> None:
    with pytest.raises(ValueError, match="human authority"):
        make_assertion(
            assertion_type="authority",
            issuer_system="legalis",
            issuer_role="requirements",
            subject_kind="release",
            subject_ref="release://1",
            payload={"verdict": "ALLOW"},
            external_release_authorized=True,
        )


def test_valinor_may_record_kernel_authorization_without_release_authority() -> None:
    row = make_assertion(
        assertion_type="authority",
        issuer_system="valinor",
        issuer_role="kernel",
        subject_kind="operation",
        subject_ref="write://bounded",
        payload={"verdict": "VALINOR_ALLOW"},
        kernel_authorized=True,
    )
    validate_assertion(row)
    assert row["authority"]["kernel_authorized"] is True
    assert row["authority"]["external_release_authorized"] is False


def test_every_mandatory_fusion_system_has_a_primitive_binding() -> None:
    registry = json.loads(Path("config/dio_fusion_registry.json").read_text(encoding="utf-8"))
    bindings = json.loads(Path("config/dio_fusion_bindings.json").read_text(encoding="utf-8"))
    schema = json.loads(Path("schemas/dio_fusion_bindings.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(bindings)
    mandatory = {row["system_id"] for row in registry["systems"] if row["must_participate_before_deification"]}
    assert mandatory == set(bindings["bindings"])
    assert all(bindings["bindings"][system_id] for system_id in mandatory)


def test_seraph_challenge_projects_into_case_without_authority_promotion(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    before = {row["gate_id"]: row["state"] for row in case["gates"]}
    assertion = make_assertion(
        assertion_type="challenge",
        issuer_system="seraph",
        issuer_role="adversarial_challenge",
        subject_kind="case",
        subject_ref=case["case_id"],
        payload={
            "target_type": "case",
            "target_id": case["case_id"],
            "challenge_type": "alternative_hypothesis",
            "severity": "material",
            "hypothesis": "The proposed result may reflect manipulated evidence.",
        },
    )
    project_assertion(case, assertion)
    assert case["challenges"][-1]["raised_by"] == "seraph"
    assert {row["gate_id"]: row["state"] for row in case["gates"]} == before
    assert f"fusion://{assertion['assertion_id']}" in case["event_refs"]


def test_outlook_external_capability_request_is_blocked_by_normal_case_gates(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    assertion = make_assertion(
        assertion_type="capability_request",
        issuer_system="outlook_triage",
        issuer_role="mail_drafter",
        subject_kind="mail",
        subject_ref="mail://thread-1",
        payload={
            "capability": "send_reply",
            "description": "Send a drafted Outlook reply.",
            "external": True,
            "risk_tier": "external",
            "reversibility": "compensatable",
        },
        human_required=True,
    )
    project_assertion(case, assertion)
    action = case["actions"][-1]
    assert action["state"] == "blocked"
    assert "generic_executor" in action["required_gate_ids"]
    assert "external_release" in action["required_gate_ids"]


def test_evidence_and_receipt_share_the_case_event_spine(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    evidence = make_assertion(
        assertion_type="evidence",
        issuer_system="evidex",
        issuer_role="evidence_pack",
        subject_kind="claim_source",
        subject_ref="evidex://pack-1",
        payload={"source_ref": "evidex://pack-1", "sha256": "b" * 64},
        authority_grade="source_backed",
        trust_state="captured_untrusted",
        freshness_state="current",
    )
    project_assertion(case, evidence)
    assert case["evidence"][-1]["kind"] == "fusion:evidex:evidence"
    assert case["evidence"][-1]["trust_state"] == "captured_untrusted"

    receipt = make_assertion(
        assertion_type="receipt",
        issuer_system="document_studio",
        issuer_role="transformer",
        subject_kind="artifact",
        subject_ref="artifact://converted",
        payload={"status": "complete"},
        epistemic_state="N/A",
        authority_grade="N/A",
        trust_state="N/A",
        freshness_state="N/A",
    )
    project_assertion(case, receipt)
    assert f"fusion://{receipt['assertion_id']}" in case["event_refs"]
