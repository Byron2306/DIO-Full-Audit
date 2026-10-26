from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from evidence.intelligence import (
    evidence_gap_report,
    explain_claim_support,
    from_fusion_assertion,
    load_source_registry,
    project_evidence_assertion,
)
from fusion.contracts import make_assertion
from products.governed_case import add_claim, add_requirement, new_case

ROOT = Path(__file__).resolve().parents[1]


def _case(job_id: str = "evidence-wave3") -> dict:
    return new_case(
        product="dio_assurance",
        job_id=job_id,
        source={"source": {}},
        source_path=Path("/tmp/dio-evidence-source.json"),
        evidence_inputs=[],
        expected_outputs=[],
        required_authorities=["assurance_reviewer"],
        intake_state="approved",
    )


def _fusion_evidence(
    case: dict,
    *,
    issuer: str,
    subject_kind: str,
    subject_ref: str,
    source_ref: str,
    sha256: str | None = None,
    freshness: str = "current",
    trust: str = "trusted_for_review",
    assertion_type: str = "evidence",
) -> dict:
    payload = {"source_ref": source_ref}
    if sha256:
        payload["sha256"] = sha256
    return make_assertion(
        assertion_type=assertion_type,
        issuer_system=issuer,
        issuer_role="evidence_contributor",
        subject_kind=subject_kind,
        subject_ref=subject_ref,
        payload=payload,
        source_refs=[f"repo://{issuer}"],
        case_id=case["case_id"],
        epistemic_state="SUPPORTED" if assertion_type == "evidence" else "UNVERIFIED",
        authority_grade="source_backed",
        trust_state=trust,
        freshness_state=freshness,
        created_at="2026-08-11T17:00:00+00:00",
    )


def test_registry_covers_every_fusion_evidence_or_observation_contributor():
    registry = load_source_registry()
    bindings = json.loads((ROOT / "config" / "dio_fusion_bindings.json").read_text(encoding="utf-8"))
    expected = {
        system_id
        for system_id, primitives in bindings["bindings"].items()
        if {"evidence", "observation"}.intersection(primitives)
    }
    assert set(registry["contributors"]) == expected


def test_normalization_preserves_fusion_lineage_and_is_deterministic():
    case = _case("lineage")
    fusion = _fusion_evidence(
        case,
        issuer="sophia_integritas",
        subject_kind="case",
        subject_ref=case["case_id"],
        source_ref="sophia://lineage/claim-1",
    )
    one = from_fusion_assertion(fusion)
    two = from_fusion_assertion(fusion)
    assert one == two
    assert one["source_assertion_id"] == fusion["assertion_id"]
    assert one["lineage"]["source_refs"] == ["repo://sophia_integritas"]
    assert one["issuer"]["system_id"] == "sophia_integritas"


def test_non_evidence_fusion_assertion_is_refused():
    case = _case("wrong-primitive")
    assertion = make_assertion(
        assertion_type="challenge",
        issuer_system="seraph",
        issuer_role="challenge",
        subject_kind="case",
        subject_ref=case["case_id"],
        payload={"summary": "challenge"},
        case_id=case["case_id"],
    )
    with pytest.raises(ValueError, match="only evidence or observation"):
        from_fusion_assertion(assertion)


def test_unregistered_evidence_issuer_is_refused():
    case = _case("unknown-issuer")
    assertion = _fusion_evidence(
        case,
        issuer="unknown_machine",
        subject_kind="case",
        subject_ref=case["case_id"],
        source_ref="unknown://source",
    )
    with pytest.raises(ValueError, match="not a registered Evidence Intelligence contributor"):
        from_fusion_assertion(assertion)


def test_source_bound_custody_requires_hash():
    case = _case("source-bound")
    assertion = _fusion_evidence(
        case,
        issuer="beast",
        subject_kind="case",
        subject_ref=case["case_id"],
        source_ref="file://captured-source",
    )
    with pytest.raises(ValueError, match="source_bound evidence requires a sha256"):
        from_fusion_assertion(assertion)


def test_current_trusted_support_makes_claim_supported_and_reconstructible():
    case = _case("support")
    claim = add_claim(case, statement="The control is operating as described.")
    fusion = _fusion_evidence(
        case,
        issuer="sophia_integritas",
        subject_kind="claim",
        subject_ref=claim["claim_id"],
        source_ref="sophia://evidence/control-1",
    )
    assertion = from_fusion_assertion(
        fusion,
        relation="supports",
        target_type="claim",
        target_id=claim["claim_id"],
    )
    project_evidence_assertion(case, assertion)
    assert claim["epistemic_state"] == "SUPPORTED"
    explanation = explain_claim_support(case, claim["claim_id"])
    assert explanation["support_reconstructible"] is True
    assert len(explanation["supporting_evidence"]) == 1


def test_stale_support_is_preserved_but_does_not_support_current_claim():
    case = _case("stale-support")
    claim = add_claim(case, statement="The policy is currently effective.")
    fusion = _fusion_evidence(
        case,
        issuer="sophia_integritas",
        subject_kind="claim",
        subject_ref=claim["claim_id"],
        source_ref="sophia://policy/old",
        freshness="stale",
    )
    assertion = from_fusion_assertion(fusion, relation="supports", target_type="claim", target_id=claim["claim_id"])
    project_evidence_assertion(case, assertion)
    assert claim["epistemic_state"] == "UNVERIFIED"
    assert case["evidence"][0]["freshness_state"] == "stale"


def test_current_trusted_negative_evidence_refutes_claim():
    case = _case("negative-current")
    claim = add_claim(case, statement="Phoenix has a persistent independent edge.")
    support = from_fusion_assertion(
        _fusion_evidence(
            case,
            issuer="sophia_integritas",
            subject_kind="claim",
            subject_ref=claim["claim_id"],
            source_ref="sophia://hypothesis/edge",
        ),
        relation="supports",
        target_type="claim",
        target_id=claim["claim_id"],
    )
    project_evidence_assertion(case, support)
    negative = from_fusion_assertion(
        _fusion_evidence(
            case,
            issuer="phoenix",
            subject_kind="claim",
            subject_ref=claim["claim_id"],
            source_ref="phoenix://temporal-validation/no-edge",
        ),
        relation="contradicts",
        target_type="claim",
        target_id=claim["claim_id"],
    )
    project_evidence_assertion(case, negative)
    assert claim["epistemic_state"] == "REFUTED"


def test_stale_negative_evidence_is_advisory_not_current_refutation():
    case = _case("negative-stale")
    claim = add_claim(case, statement="The current control is effective.")
    support = from_fusion_assertion(
        _fusion_evidence(
            case,
            issuer="sophia_integritas",
            subject_kind="claim",
            subject_ref=claim["claim_id"],
            source_ref="sophia://control/current",
        ),
        relation="supports",
        target_type="claim",
        target_id=claim["claim_id"],
    )
    project_evidence_assertion(case, support)
    stale_negative = from_fusion_assertion(
        _fusion_evidence(
            case,
            issuer="phoenix",
            subject_kind="claim",
            subject_ref=claim["claim_id"],
            source_ref="phoenix://old-contradiction",
            freshness="stale",
        ),
        relation="contradicts",
        target_type="claim",
        target_id=claim["claim_id"],
    )
    project_evidence_assertion(case, stale_negative)
    assert claim["epistemic_state"] == "SUPPORTED"
    assert case["challenges"][-1]["severity"] == "advisory"
    assert case["challenges"][-1]["challenge_type"] == "stale_evidence"


def test_requirement_support_uses_same_evidence_spine():
    case = _case("requirement-support")
    requirement = add_requirement(case, statement="A moderation record is available.", kind="framework", source_ref="homs://moderation")
    assertion = from_fusion_assertion(
        _fusion_evidence(
            case,
            issuer="homs",
            subject_kind="requirement",
            subject_ref=requirement["requirement_id"],
            source_ref="homs://moderation/receipt-1",
        ),
        relation="supports",
        target_type="requirement",
        target_id=requirement["requirement_id"],
    )
    project_evidence_assertion(case, assertion)
    assert requirement["state"] == "supported"
    assert requirement["evidence_ids"]


def test_requirement_contradiction_becomes_challenge_not_satisfaction():
    case = _case("requirement-contradiction")
    requirement = add_requirement(case, statement="Public claim review is complete.", kind="framework", source_ref="market://review")
    assertion = from_fusion_assertion(
        _fusion_evidence(
            case,
            issuer="market_command",
            subject_kind="requirement",
            subject_ref=requirement["requirement_id"],
            source_ref="market://review/missing",
        ),
        relation="contradicts",
        target_type="requirement",
        target_id=requirement["requirement_id"],
    )
    project_evidence_assertion(case, assertion)
    assert requirement["state"] != "supported"
    assert case["challenges"][-1]["target_id"] == requirement["requirement_id"]
    assert case["challenges"][-1]["severity"] == "material"


def test_evidence_projection_cannot_mutate_authority_or_execution_surfaces():
    case = _case("authority-boundary")
    before = copy.deepcopy({"gates": case["gates"], "actions": case["actions"], "decisions": case["decisions"]})
    assertion = from_fusion_assertion(
        _fusion_evidence(
            case,
            issuer="outlook_triage",
            assertion_type="observation",
            subject_kind="case",
            subject_ref=case["case_id"],
            source_ref="outlook://thread/123",
        ),
        relation="observes",
        target_type="case",
        target_id=case["case_id"],
    )
    project_evidence_assertion(case, assertion)
    after = {"gates": case["gates"], "actions": case["actions"], "decisions": case["decisions"]}
    assert after == before


def test_gap_report_exposes_missing_and_stale_truth():
    case = _case("gaps")
    claim = add_claim(case, statement="Evidence is complete.")
    requirement = add_requirement(case, statement="Evidence pack is complete.", kind="framework", source_ref="evidex://pack")
    assertion = from_fusion_assertion(
        _fusion_evidence(
            case,
            issuer="sophia_integritas",
            subject_kind="claim",
            subject_ref=claim["claim_id"],
            source_ref="sophia://old-evidence",
            freshness="expired",
        ),
        relation="supports",
        target_type="claim",
        target_id=claim["claim_id"],
    )
    project_evidence_assertion(case, assertion)
    report = evidence_gap_report(case)
    assert report["has_gaps"] is True
    assert claim["claim_id"] in report["unverified_claim_ids"]
    assert requirement["requirement_id"] in report["requirement_gap_ids"]
    assert report["stale_or_expired_evidence_ids"]
