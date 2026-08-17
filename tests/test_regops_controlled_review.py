from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from products.governed_case import new_case
from products.regops.materializer import materialize_regops_case
from products.regops.runner import run_controlled_regops_review


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-08-17T08:00:00+00:00"


def _case(tmp_path: Path, *, intake_state: str = "approved") -> dict:
    source_path = tmp_path / "source.json"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("{}", encoding="utf-8")
    return new_case(
        product="dio_regops",
        job_id="regops-controlled-test",
        source={"source": {}, "evidence": []},
        source_path=source_path,
        evidence_inputs=[
            "capability request",
            "requirement registry",
            "registrations or licences",
            "policies",
            "insurance or certificates",
            "deadline and owner records",
        ],
        expected_outputs=[
            "requirement register",
            "evidence receipt set",
            "deadline and renewal queue",
            "readiness decision",
            "professional escalation record",
        ],
        required_authorities=[
            "capability_owner",
            "compliance_owner",
            "professional_reviewer_when_required",
        ],
        intake_state=intake_state,
        now=NOW,
    )


def _evidence(prerequisite_id: str, digest: str, *, freshness: str = "current") -> dict:
    return {
        "evidence_kind": "operational_record",
        "source_ref": f"operations://controlled/{prerequisite_id}",
        "sha256": digest * 64,
        "target_prerequisite_ids": [prerequisite_id],
        "authority_grade": "source_backed",
        "trust_state": "trusted_for_review",
        "freshness_state": freshness,
    }


def _ai_fixture() -> dict:
    return json.loads(
        (
            ROOT
            / "config"
            / "products"
            / "golden"
            / "airegreadiness"
            / "reference_case.json"
        ).read_text(encoding="utf-8")
    )


def test_regops_mixed_profile_refuses_expired_mandatory_prerequisite_without_execution(
    tmp_path: Path,
) -> None:
    case = _case(tmp_path)
    before_gates = copy.deepcopy(case["gates"])

    result = run_controlled_regops_review(
        case,
        profile_id="profile.regops.mixed_operational_controlled_v1",
        prerequisites=[
            {
                "prerequisite_id": "REG-1",
                "statement": "Required operating registration is evidenced.",
                "mandatory": True,
                "dependency_prerequisite_ids": [],
                "expires_at": "2026-12-31T00:00:00+00:00",
            },
            {
                "prerequisite_id": "INS-1",
                "statement": "Required operating insurance is current.",
                "mandatory": True,
                "dependency_prerequisite_ids": [],
                "expires_at": "2026-08-01T00:00:00+00:00",
            },
        ],
        evidence_inputs=[
            _evidence("REG-1", "a"),
            _evidence("INS-1", "b"),
        ],
        gaps=[],
        ai_regulatory_context=None,
        output_dir=tmp_path / "out",
        operator_id="human.regops_test",
        now=NOW,
    )

    rows = {
        row["prerequisite_id"]: row
        for row in result["materialization"]["prerequisite_matrix"]
    }
    assert rows["REG-1"]["readiness_state"] == "SUPPORTED"
    assert rows["REG-1"]["deadline_state"] == "OPEN"
    assert rows["INS-1"]["readiness_state"] == "SUPPORTED"
    assert rows["INS-1"]["deadline_state"] == "EXPIRED"
    assert result["materialization"]["readiness_decision"]["state"] == "REFUSE"

    component = result["ai_regulatory_component"]
    assert component["state"] == "NOT_EVALUATED"
    assert component["relationship"] == "composition_reuse"
    assert component["external_release"] == "REFUSE"

    proof = result["proof_manifest"]
    assert proof["readiness_state"] == "REFUSE"
    assert proof["authority_created"] is False
    assert proof["execution_performed"] is False
    assert proof["external_effects"] is False
    assert proof["external_release"] is False
    for artifact in proof["artifacts"]:
        path = Path(result["output_dir"]) / artifact["filename"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]

    receipt = result["receipt"]
    assert receipt["internal_processing"] == "COMPLETE"
    assert receipt["readiness_state"] == "REFUSE"
    assert receipt["generic_executor_gate"] == "refuse"
    assert receipt["human_review_gate"] == "NEEDS_YOU"
    assert receipt["external_release_gate"] == "REFUSE"
    assert receipt["legal_clearance_created"] is False
    assert receipt["professional_decision_created"] is False
    assert receipt["filing_authority_created"] is False
    assert receipt["authority_created"] is False
    assert receipt["execution_performed"] is False
    assert receipt["external_effects"] is False
    assert receipt["external_release"] is False

    assert case["gates"] == before_gates
    assert not case["actions"]
    assert not case["decisions"]
    assert (tmp_path / "out" / "REGOPS_READINESS_PACK.json").is_file()
    assert (tmp_path / "out" / "REGOPS_READINESS_PACK.html").is_file()
    assert (tmp_path / "out" / "PROOF_MANIFEST.json").is_file()
    assert (tmp_path / "out" / "REGOPS_PROCESSING_RECEIPT.json").is_file()


def test_regops_allow_is_readiness_only_and_does_not_promote_execution(tmp_path: Path) -> None:
    case = _case(tmp_path)
    result = run_controlled_regops_review(
        case,
        profile_id="profile.regops.non_ai_prerequisites_v1",
        prerequisites=[
            {
                "prerequisite_id": "POL-1",
                "statement": "Required operational policy is current and evidenced.",
                "mandatory": True,
                "dependency_prerequisite_ids": [],
            }
        ],
        evidence_inputs=[_evidence("POL-1", "c")],
        gaps=[],
        ai_regulatory_context=None,
        output_dir=tmp_path / "out",
        operator_id="human.regops_test",
        now=NOW,
    )

    decision = result["materialization"]["readiness_decision"]
    assert decision["state"] == "ALLOW"
    assert "not legal clearance" in decision["meaning"]
    assert result["receipt"]["generic_executor_gate"] == "refuse"
    assert result["receipt"]["execution_performed"] is False
    assert result["receipt"]["external_release_gate"] == "REFUSE"
    assert next(
        row for row in case["gates"] if row["gate_id"] == "external_release"
    )["state"] == "needs_you"


def test_regops_supported_prerequisite_with_professional_boundary_needs_you(
    tmp_path: Path,
) -> None:
    case = _case(tmp_path)
    receipt = materialize_regops_case(
        case,
        profile_id="profile.regops.professional_review_v1",
        prerequisites=[
            {
                "prerequisite_id": "PRO-1",
                "statement": "Professional interpretation is required before consequential use.",
                "mandatory": True,
                "professional_review_required": True,
                "dependency_prerequisite_ids": [],
            }
        ],
        evidence_inputs=[_evidence("PRO-1", "d")],
        gaps=[],
        raised_by="human.regops_test",
        now=NOW,
    )
    assert receipt["prerequisite_matrix"][0]["readiness_state"] == "SUPPORTED"
    assert receipt["readiness_decision"]["state"] == "NEEDS_YOU"
    assert receipt["readiness_decision"]["professional_review_prerequisite_ids"] == [
        "PRO-1"
    ]
    assert receipt["authority_created"] is False
    assert receipt["execution_performed"] is False


def test_regops_binds_airegreadiness_as_bounded_component(tmp_path: Path) -> None:
    case = _case(tmp_path)
    result = run_controlled_regops_review(
        case,
        profile_id="profile.regops.mixed_ai_operational_v1",
        prerequisites=[
            {
                "prerequisite_id": "OWN-1",
                "statement": "Capability ownership is explicit.",
                "mandatory": True,
                "dependency_prerequisite_ids": [],
            }
        ],
        evidence_inputs=[_evidence("OWN-1", "e")],
        gaps=[],
        ai_regulatory_context=_ai_fixture(),
        output_dir=tmp_path / "out",
        operator_id="human.regops_test",
        now=NOW,
    )

    component = result["ai_regulatory_component"]
    assert component["reusable_component_product_id"] == "dio_airegreadiness"
    assert component["relationship"] == "composition_reuse"
    assert component["state"] == "CONTROLLED_CONTEXT_EVALUATED"
    assert component["dimensions"]["source_authority"] == "SUPPORTED"
    assert component["dimensions"]["ai_trust_binding"] == "SUPPORTED"
    assert component["external_release"] == "REFUSE"
    assert component["authority_created"] is False
    assert component["external_effects"] is False
    assert result["receipt"]["ai_regulatory_component_state"] == (
        "CONTROLLED_CONTEXT_EVALUATED"
    )


def test_regops_materializer_refuses_unknown_evidence_target_and_wrong_product(
    tmp_path: Path,
) -> None:
    case = _case(tmp_path)
    with pytest.raises(ValueError, match="known target_prerequisite_ids"):
        materialize_regops_case(
            case,
            profile_id="profile.regops.controlled_v1",
            prerequisites=[
                {
                    "prerequisite_id": "REG-1",
                    "statement": "Registration is evidenced.",
                    "mandatory": True,
                    "dependency_prerequisite_ids": [],
                }
            ],
            evidence_inputs=[_evidence("NOT-REAL", "f")],
            gaps=[],
            raised_by="human.regops_test",
            now=NOW,
        )

    wrong = _case(tmp_path / "wrong")
    wrong["product"] = "dio_vendorproof"
    with pytest.raises(ValueError, match="product=dio_regops"):
        materialize_regops_case(
            wrong,
            profile_id="profile.regops.controlled_v1",
            prerequisites=[
                {
                    "prerequisite_id": "REG-1",
                    "statement": "Registration is evidenced.",
                    "mandatory": True,
                    "dependency_prerequisite_ids": [],
                }
            ],
            evidence_inputs=[],
            gaps=[],
            raised_by="human.regops_test",
            now=NOW,
        )


def test_regops_runner_refuses_unapproved_intake_and_wrong_ai_component_source(
    tmp_path: Path,
) -> None:
    pending = _case(tmp_path / "pending", intake_state="pending")
    with pytest.raises(RuntimeError, match="approved intake authority"):
        run_controlled_regops_review(
            pending,
            profile_id="profile.regops.controlled_v1",
            prerequisites=[
                {
                    "prerequisite_id": "REG-1",
                    "statement": "Registration is evidenced.",
                    "mandatory": True,
                    "dependency_prerequisite_ids": [],
                }
            ],
            evidence_inputs=[],
            gaps=[],
            ai_regulatory_context=None,
            output_dir=tmp_path / "pending-out",
            operator_id="human.regops_test",
            now=NOW,
        )

    case = _case(tmp_path / "wrong-source")
    bad = _ai_fixture()
    bad["source_type"] = "wrong_source"
    with pytest.raises(ValueError, match="source_type=ai_regulatory_context"):
        run_controlled_regops_review(
            case,
            profile_id="profile.regops.controlled_v1",
            prerequisites=[
                {
                    "prerequisite_id": "REG-1",
                    "statement": "Registration is evidenced.",
                    "mandatory": True,
                    "dependency_prerequisite_ids": [],
                }
            ],
            evidence_inputs=[],
            gaps=[],
            ai_regulatory_context=bad,
            output_dir=tmp_path / "wrong-source-out",
            operator_id="human.regops_test",
            now=NOW,
        )
