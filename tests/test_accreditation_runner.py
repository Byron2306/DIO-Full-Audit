from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from products.accreditation.runner import run_controlled_accreditation_review
from products.governed_case import new_case


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-08-17T08:00:00+00:00"


def _case(tmp_path: Path, *, intake_state: str = "approved") -> dict:
    source_path = tmp_path / "source.json"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("{}", encoding="utf-8")
    return new_case(
        product="dio_accreditation",
        job_id="accreditation-runner-controlled-test",
        source={"source": {}, "evidence": []},
        source_path=source_path,
        evidence_inputs=["standards or criteria", "programme documents"],
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
        intake_state=intake_state,
        now=NOW,
    )


def _regulatory_fixture() -> dict:
    return json.loads(
        (
            ROOT
            / "config"
            / "products"
            / "golden"
            / "educationaccreditationproof"
            / "reference_case.json"
        ).read_text(encoding="utf-8")
    )


def test_controlled_review_binds_regulated_component_without_minting_authority(tmp_path: Path) -> None:
    case = _case(tmp_path)
    before_gates = copy.deepcopy(case["gates"])

    result = run_controlled_accreditation_review(
        case,
        framework_id="framework.education_accreditation",
        criteria=[
            {
                "criterion_id": "ACC-1",
                "statement": "Programme evidence is mapped to the selected accreditation criterion.",
                "mandatory": True,
                "dependency_criterion_ids": [],
            },
            {
                "criterion_id": "ACC-2",
                "statement": "Open accreditation gaps are explicitly retained for human review.",
                "mandatory": True,
                "dependency_criterion_ids": [],
            },
        ],
        evidence_inputs=[
            {
                "evidence_kind": "programme_record",
                "source_ref": "programme://controlled/evidence-1",
                "sha256": "a" * 64,
                "target_criterion_ids": ["ACC-1"],
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            }
        ],
        gaps=[
            {
                "criterion_id": "ACC-2",
                "challenge_type": "missing_evidence",
                "severity": "material",
                "hypothesis": "Controlled fixture intentionally retains an unresolved gap.",
            }
        ],
        regulatory_context=_regulatory_fixture(),
        output_dir=tmp_path / "out",
        operator_id="human.accreditation_test",
        now=NOW,
    )

    component = result["regulated_component"]
    assert component["reusable_component_product_id"] == "dio_educationaccreditationproof"
    assert component["relationship"] == "composition_reuse"
    assert component["state"] == "CONTROLLED_CONTEXT_EVALUATED"
    assert component["dimensions"]["temporal_validity"] == "STALE"
    assert component["dimensions"]["licensing"] == "REFUSE"
    assert component["external_release"] == "REFUSE"
    assert component["authority_created"] is False
    assert component["external_effects"] is False

    pack = result["review_pack"]
    states = {
        row["criterion_id"]: row["readiness_state"]
        for row in pack["standards_evidence_matrix"]
    }
    assert states == {"ACC-1": "SUPPORTED", "ACC-2": "UNKNOWN"}
    assert pack["human_review"]["signatory_receipt_created"] is False
    assert pack["external_release"] == "REFUSE"

    proof = result["proof_manifest"]
    assert proof["execution_performed"] is False
    assert proof["authority_created"] is False
    assert proof["external_release"] is False
    assert proof["regulated_component"]["relationship"] == "composition_reuse"
    for artifact in proof["artifacts"]:
        path = Path(result["output_dir"]) / artifact["filename"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]

    receipt = result["receipt"]
    assert receipt["internal_processing"] == "COMPLETE"
    assert receipt["generic_executor_gate"] == "refuse"
    assert receipt["human_review_gate"] == "NEEDS_YOU"
    assert receipt["external_release_gate"] == "REFUSE"
    assert receipt["signatory_receipt_created"] is False
    assert receipt["accreditation_decision_created"] is False
    assert receipt["institutional_attestation_created"] is False
    assert receipt["regulator_acceptance_created"] is False
    assert receipt["authority_created"] is False
    assert receipt["execution_performed"] is False
    assert receipt["external_effects"] is False
    assert receipt["external_release"] is False

    assert case["gates"] == before_gates
    assert not case["actions"]
    assert not case["decisions"]
    assert (tmp_path / "out" / "ACCREDITATION_REVIEW_PACK.json").is_file()
    assert (tmp_path / "out" / "ACCREDITATION_REVIEW_PACK.html").is_file()
    assert (tmp_path / "out" / "PROOF_MANIFEST.json").is_file()
    assert (tmp_path / "out" / "ACCREDITATION_PROCESSING_RECEIPT.json").is_file()


def test_controlled_review_without_regulatory_context_records_not_evaluated(tmp_path: Path) -> None:
    case = _case(tmp_path)
    result = run_controlled_accreditation_review(
        case,
        framework_id="framework.education_accreditation",
        criteria=[
            {
                "criterion_id": "ACC-1",
                "statement": "Programme evidence is available.",
                "mandatory": True,
                "dependency_criterion_ids": [],
            }
        ],
        evidence_inputs=[],
        gaps=[],
        regulatory_context=None,
        output_dir=tmp_path / "out",
        operator_id="human.accreditation_test",
        now=NOW,
    )
    component = result["regulated_component"]
    assert component["state"] == "NOT_EVALUATED"
    assert component["external_release"] == "REFUSE"
    assert result["receipt"]["internal_processing"] == "COMPLETE"


def test_controlled_review_refuses_unapproved_intake_and_wrong_component_source(tmp_path: Path) -> None:
    pending = _case(tmp_path / "pending", intake_state="pending")
    with pytest.raises(RuntimeError, match="approved intake authority"):
        run_controlled_accreditation_review(
            pending,
            framework_id="framework.education_accreditation",
            criteria=[
                {
                    "criterion_id": "ACC-1",
                    "statement": "Programme evidence is available.",
                    "mandatory": True,
                    "dependency_criterion_ids": [],
                }
            ],
            evidence_inputs=[],
            gaps=[],
            regulatory_context=None,
            output_dir=tmp_path / "pending-out",
            operator_id="human.accreditation_test",
            now=NOW,
        )

    case = _case(tmp_path / "wrong")
    bad = _regulatory_fixture()
    bad["source_type"] = "wrong_source"
    with pytest.raises(ValueError, match="source_type=education_accreditation_context"):
        run_controlled_accreditation_review(
            case,
            framework_id="framework.education_accreditation",
            criteria=[
                {
                    "criterion_id": "ACC-1",
                    "statement": "Programme evidence is available.",
                    "mandatory": True,
                    "dependency_criterion_ids": [],
                }
            ],
            evidence_inputs=[],
            gaps=[],
            regulatory_context=bad,
            output_dir=tmp_path / "wrong-out",
            operator_id="human.accreditation_test",
            now=NOW,
        )
