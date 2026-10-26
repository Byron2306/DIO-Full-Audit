from __future__ import annotations

import copy
from pathlib import Path

import pytest

from products.accreditation.materializer import materialize_accreditation_case
from products.governed_case import new_case, validate_case


NOW = "2026-08-17T08:00:00+00:00"


def _case(tmp_path: Path) -> dict:
    source_path = tmp_path / "source.json"
    source_path.write_text("{}", encoding="utf-8")
    return new_case(
        product="dio_accreditation",
        job_id="accreditation-controlled-test",
        source={"source": {}, "evidence": []},
        source_path=source_path,
        evidence_inputs=[
            "standards or criteria",
            "programme documents",
            "policies",
            "meeting records",
            "performance evidence",
            "corrective-action records",
        ],
        expected_outputs=[
            "standards-evidence matrix",
            "gap register",
            "corrective-action tracker",
            "review pack",
            "signatory receipt",
        ],
        required_authorities=[
            "programme_owner",
            "quality_assurance_reviewer",
            "authorised_signatory",
        ],
        intake_state="approved",
        now=NOW,
    )


def _criteria() -> list[dict]:
    return [
        {
            "criterion_id": "STD-1",
            "statement": "The programme demonstrates an approved and current curriculum structure.",
            "mandatory": True,
            "dependency_criterion_ids": [],
        },
        {
            "criterion_id": "STD-2",
            "statement": "Programme review evidence demonstrates implementation of the approved curriculum.",
            "mandatory": True,
            "dependency_criterion_ids": ["STD-1"],
        },
        {
            "criterion_id": "STD-3",
            "statement": "Corrective actions are tracked where review identifies unresolved gaps.",
            "mandatory": True,
            "dependency_criterion_ids": [],
        },
        {
            "criterion_id": "STD-4",
            "statement": "Institutional evidence supports the declared quality-assurance control.",
            "mandatory": True,
            "dependency_criterion_ids": [],
        },
        {
            "criterion_id": "STD-5",
            "statement": "Required programme evidence exists for the criterion.",
            "mandatory": True,
            "dependency_criterion_ids": [],
        },
    ]


def test_materializer_projects_truthful_readiness_states_without_authority_mutation(tmp_path: Path) -> None:
    case = _case(tmp_path)
    before = {
        "gates": copy.deepcopy(case["gates"]),
        "actions": copy.deepcopy(case["actions"]),
        "decisions": copy.deepcopy(case["decisions"]),
    }

    receipt = materialize_accreditation_case(
        case,
        framework_id="framework.education_accreditation",
        criteria=_criteria(),
        evidence_inputs=[
            {
                "evidence_kind": "curriculum_record",
                "source_ref": "programme://curriculum/2026",
                "sha256": "1" * 64,
                "target_criterion_ids": ["STD-1"],
                "authority_grade": "authoritative",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            },
            {
                "evidence_kind": "review_record",
                "source_ref": "programme://review/2026",
                "sha256": "2" * 64,
                "target_criterion_ids": ["STD-2"],
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            },
            {
                "evidence_kind": "corrective_action_record",
                "source_ref": "programme://actions/2024",
                "sha256": "3" * 64,
                "target_criterion_ids": ["STD-3"],
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "stale",
            },
            {
                "evidence_kind": "quality_record",
                "source_ref": "programme://quality/2026",
                "sha256": "4" * 64,
                "target_criterion_ids": ["STD-4"],
                "relation": "contradicts",
                "authority_grade": "independent",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
                "hypothesis": "Independent review evidence contradicts the declared control.",
            },
        ],
        gaps=[
            {
                "criterion_id": "STD-2",
                "challenge_type": "missing_evidence",
                "severity": "material",
                "hypothesis": "Implementation evidence covers only part of the programme.",
            },
            {
                "criterion_id": "STD-5",
                "challenge_type": "missing_evidence",
                "severity": "material",
                "hypothesis": "No programme evidence has been supplied for this criterion.",
            },
        ],
        raised_by="human.qa_reviewer",
    )

    states = {
        row["criterion_id"]: row["readiness_state"]
        for row in receipt["standards_evidence_matrix"]
    }
    assert states == {
        "STD-1": "SUPPORTED",
        "STD-2": "PARTIAL",
        "STD-3": "STALE",
        "STD-4": "CONTESTED",
        "STD-5": "UNKNOWN",
    }

    assert case["gates"] == before["gates"]
    assert case["actions"] == before["actions"]
    assert case["decisions"] == before["decisions"]
    assert next(row for row in case["gates"] if row["gate_id"] == "generic_executor")["state"] == "refuse"
    assert next(row for row in case["gates"] if row["gate_id"] == "external_release")["state"] == "needs_you"
    assert receipt["authority_created"] is False
    assert receipt["execution_performed"] is False
    assert receipt["external_release"] is False
    validate_case(case)


def test_missing_without_declared_gap_remains_unknown(tmp_path: Path) -> None:
    case = _case(tmp_path)
    receipt = materialize_accreditation_case(
        case,
        framework_id="framework.education_accreditation",
        criteria=[_criteria()[0]],
        evidence_inputs=[],
        gaps=[],
        raised_by="human.qa_reviewer",
    )
    row = receipt["standards_evidence_matrix"][0]
    assert row["case_state"] == "evidence_needed"
    assert row["readiness_state"] == "UNKNOWN"


def test_materialization_is_idempotent_and_stable(tmp_path: Path) -> None:
    case = _case(tmp_path)
    kwargs = {
        "framework_id": "framework.education_accreditation",
        "criteria": [_criteria()[0]],
        "evidence_inputs": [
            {
                "evidence_kind": "curriculum_record",
                "source_ref": "programme://curriculum/2026",
                "sha256": "a" * 64,
                "target_criterion_ids": ["STD-1"],
                "authority_grade": "authoritative",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            }
        ],
        "gaps": [],
        "raised_by": "human.qa_reviewer",
    }

    first = materialize_accreditation_case(case, **kwargs)
    counts = (
        len(case["requirements"]),
        len(case["evidence"]),
        len(case["challenges"]),
    )
    second = materialize_accreditation_case(case, **kwargs)

    assert first["standards_evidence_matrix"] == second["standards_evidence_matrix"]
    assert counts == (
        len(case["requirements"]),
        len(case["evidence"]),
        len(case["challenges"]),
    )


def test_unknown_criterion_mapping_refuses(tmp_path: Path) -> None:
    case = _case(tmp_path)
    with pytest.raises(ValueError, match="known target_criterion_ids"):
        materialize_accreditation_case(
            case,
            framework_id="framework.education_accreditation",
            criteria=[_criteria()[0]],
            evidence_inputs=[
                {
                    "source_ref": "programme://bad",
                    "target_criterion_ids": ["STD-NOT-REAL"],
                }
            ],
            raised_by="human.qa_reviewer",
        )


def test_wrong_product_and_missing_operator_refuse(tmp_path: Path) -> None:
    case = _case(tmp_path)

    with pytest.raises(ValueError, match="explicit human/operator identity"):
        materialize_accreditation_case(
            case,
            framework_id="framework.education_accreditation",
            criteria=[_criteria()[0]],
            evidence_inputs=[],
            raised_by="",
        )

    case["product"] = "dio_vendorproof"
    with pytest.raises(ValueError, match="product=dio_accreditation"):
        materialize_accreditation_case(
            case,
            framework_id="framework.education_accreditation",
            criteria=[_criteria()[0]],
            evidence_inputs=[],
            raised_by="human.qa_reviewer",
        )
