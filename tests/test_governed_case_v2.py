from __future__ import annotations

from pathlib import Path

import pytest

from products.governed_case import (
    CASE_SCHEMA,
    add_actor,
    add_claim,
    add_evidence,
    canonical_hash,
    link_evidence,
    new_case,
    propose_action,
    raise_challenge,
    refresh_temporal_state,
    resolve_challenge,
    set_gate,
    validate_case,
)


def make_case(tmp_path: Path, intake_state: str = "approved") -> dict:
    source_path = tmp_path / "source.json"
    source_path.write_text("{}", encoding="utf-8")
    return new_case(
        product="dio_assurance",
        job_id="dio_assurance-test-001",
        source={
            "source": {"lead_id": "LEAD-1", "conversation_id": "CONV-1"},
            "attribution": {"campaign_id": "CMP-1"},
            "evidence": [],
        },
        source_path=source_path,
        evidence_inputs=["AI system inventory", "approval record"],
        expected_outputs=["control-evidence matrix"],
        required_authorities=["system_owner", "release_operator"],
        intake_state=intake_state,
        framework_ids=["FRAMEWORK-1"],
        jurisdiction_ids=["ZA"],
        subject_ref="AI-SYSTEM-1",
        world_state_ref="WORLD-1",
        now="2026-08-11T13:00:00+00:00",
    )


def test_case_v2_bootstrap_preserves_scope_lineage_and_gates(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    assert case["schema"] == CASE_SCHEMA
    assert case["scope"]["framework_ids"] == ["FRAMEWORK-1"]
    assert case["scope"]["jurisdiction_ids"] == ["ZA"]
    assert case["lineage"]["lead_id"] == "LEAD-1"
    gates = {row["gate_id"]: row for row in case["gates"]}
    assert gates["intake_authority"]["state"] == "allow"
    assert gates["generic_executor"]["state"] == "refuse"
    assert gates["external_release"]["state"] == "needs_you"
    validate_case(case)


def test_claim_evidence_and_challenge_lifecycle(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    requirement = case["requirements"][0]
    claim = add_claim(case, statement="The AI system has an identified owner.", requirement_ids=[requirement["requirement_id"]])
    assert claim["epistemic_state"] == "UNVERIFIED"

    evidence = add_evidence(
        case,
        kind="approval_record",
        source_ref="records/system-owner.json",
        sha256="a" * 64,
        observed_at="2026-08-11T12:00:00+00:00",
        authority_grade="authoritative",
        trust_state="trusted_for_review",
        freshness_state="current",
    )
    link_evidence(case, evidence_id=evidence["evidence_id"], claim_id=claim["claim_id"], requirement_id=requirement["requirement_id"])
    assert claim["epistemic_state"] == "SUPPORTED"
    assert requirement["state"] == "supported"
    assert requirement["state"] != "satisfied"

    challenge = raise_challenge(
        case,
        target_type="claim",
        target_id=claim["claim_id"],
        challenge_type="alternative_hypothesis",
        severity="material",
        hypothesis="The named owner may no longer hold the role.",
        raised_by="seraph",
    )
    assert claim["epistemic_state"] == "CONTESTED"
    resolve_challenge(case, challenge_id=challenge["challenge_id"], state="dismissed", resolved_by="human-reviewer", resolution="Current HR evidence confirms the owner remains assigned.")
    assert claim["epistemic_state"] == "SUPPORTED"
    validate_case(case)


def test_claim_revision_inherits_lineage_but_not_identity(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    first = add_claim(case, statement="The control is implemented.")
    second = add_claim(case, statement="The control is implemented and reviewed quarterly.", parent_claim_id=first["claim_id"])
    assert second["parent_claim_id"] == first["claim_id"]
    assert second["lineage_id"] == first["lineage_id"]
    assert second["claim_id"] != first["claim_id"]
    assert second["fingerprint"] != first["fingerprint"]
    assert first["epistemic_state"] == "UNVERIFIED"
    assert second["epistemic_state"] == "UNVERIFIED"


def test_allow_gate_rejects_untrusted_or_stale_evidence(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    add_actor(case, actor_id="reviewer-1", actor_type="human", role="release_operator", authority_scope=["external_release"])
    evidence = add_evidence(
        case,
        kind="review_receipt",
        source_ref="review/receipt.json",
        sha256="b" * 64,
        trust_state="captured_untrusted",
        freshness_state="current",
    )
    with pytest.raises(ValueError):
        set_gate(
            case,
            gate_id="external_release",
            state="allow",
            reason="Attempted release.",
            actor_id="reviewer-1",
            required_evidence_ids=[evidence["evidence_id"]],
        )

    evidence["trust_state"] = "trusted_for_review"
    evidence["freshness_state"] = "stale"
    with pytest.raises(ValueError):
        set_gate(
            case,
            gate_id="external_release",
            state="allow",
            reason="Attempted stale release.",
            actor_id="reviewer-1",
            required_evidence_ids=[evidence["evidence_id"]],
        )

    evidence["freshness_state"] = "current"
    gate = set_gate(
        case,
        gate_id="external_release",
        state="allow",
        reason="Human reviewer approved release against current trusted evidence.",
        actor_id="reviewer-1",
        required_evidence_ids=[evidence["evidence_id"]],
    )
    assert gate["state"] == "allow"
    assert gate["decision_id"]
    validate_case(case)


def test_generic_executor_refusal_blocks_action(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    action = propose_action(
        case,
        action_type="publish_assurance_pack",
        description="Publish the reviewed assurance pack.",
        risk_tier="external",
        reversibility="compensatable",
        required_gate_ids=["intake_authority", "generic_executor", "external_release"],
        proposed_by="dio",
    )
    assert action["state"] == "blocked"
    validate_case(case)


def test_expired_evidence_drops_supported_claim_back_to_unverified(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    claim = add_claim(case, statement="The certificate is current.")
    evidence = add_evidence(
        case,
        kind="certificate",
        source_ref="certificates/cert.pdf",
        sha256="c" * 64,
        observed_at="2026-08-10T00:00:00+00:00",
        expires_at="2026-08-11T14:00:00+00:00",
        trust_state="trusted_for_review",
        freshness_state="current",
    )
    link_evidence(case, evidence_id=evidence["evidence_id"], claim_id=claim["claim_id"])
    assert claim["epistemic_state"] == "SUPPORTED"
    refresh_temporal_state(case, now="2026-08-11T15:00:00+00:00")
    assert evidence["freshness_state"] == "expired"
    assert claim["epistemic_state"] == "UNVERIFIED"
    validate_case(case)


def test_case_hash_changes_when_evidence_state_changes(tmp_path: Path) -> None:
    case = make_case(tmp_path)
    before = canonical_hash(case)
    evidence = add_evidence(case, kind="policy", source_ref="policy.md", sha256="d" * 64)
    after = canonical_hash(case)
    assert before != after
    evidence["trust_state"] = "trusted_for_review"
    assert canonical_hash(case) != after
