from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from products.governed_case import new_case
from products.vendorproof.runner import run_controlled_vendorproof_review

NOW = "2026-08-17T12:00:00+00:00"


def _case(tmp_path: Path, *, intake_state: str = "approved") -> dict:
    source_path = tmp_path / "source.json"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("{}", encoding="utf-8")
    return new_case(
        product="dio_vendorproof",
        job_id="vendorproof-controlled-test",
        source={"source": {}, "evidence": []},
        source_path=source_path,
        evidence_inputs=[
            "vendor questionnaire",
            "policies",
            "certificates",
            "contracts",
            "security or privacy documentation",
            "insurance or registration evidence",
        ],
        expected_outputs=[
            "requirement-evidence matrix",
            "contradiction and stale-evidence register",
            "open-question list",
            "vendor review pack",
            "human decision receipt",
        ],
        required_authorities=[
            "vendor_risk_owner",
            "evidence_reviewer",
            "final_vendor_decision_owner",
        ],
        intake_state=intake_state,
        now=NOW,
    )


def test_vendorproof_controlled_review_maps_evidence_without_vendor_decision(tmp_path: Path) -> None:
    case = _case(tmp_path)
    before = {
        "gates": copy.deepcopy(case["gates"]),
        "actions": copy.deepcopy(case["actions"]),
        "decisions": copy.deepcopy(case["decisions"]),
        "outputs": copy.deepcopy(case["outputs"]),
    }

    result = run_controlled_vendorproof_review(
        case,
        requirements=[
            {
                "requirement_key": "VND-SEC-1",
                "statement": "The vendor supplies current independent security assurance evidence.",
                "kind": "request",
                "mandatory": True,
            },
            {
                "requirement_key": "VND-PRIV-1",
                "statement": "The vendor supplies current privacy and data-processing documentation.",
                "kind": "request",
                "mandatory": True,
            },
            {
                "requirement_key": "VND-INS-1",
                "statement": "The vendor supplies current insurance evidence where required.",
                "kind": "request",
                "mandatory": True,
            },
        ],
        evidence_inputs=[
            {
                "evidence_kind": "security_certificate",
                "source_ref": "vendor://controlled/security-certificate",
                "sha256": "a" * 64,
                "target_requirement_keys": ["VND-SEC-1"],
                "relation": "supports",
                "authority_grade": "independent",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            },
            {
                "evidence_kind": "privacy_policy",
                "source_ref": "vendor://controlled/privacy-policy",
                "sha256": "b" * 64,
                "target_requirement_keys": ["VND-PRIV-1"],
                "relation": "contradicts",
                "severity": "material",
                "hypothesis": "The supplied privacy policy conflicts with the questionnaire response.",
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            },
            {
                "evidence_kind": "insurance_certificate",
                "source_ref": "vendor://controlled/insurance-certificate",
                "sha256": "c" * 64,
                "target_requirement_keys": ["VND-INS-1"],
                "relation": "supports",
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "expired",
            },
        ],
        issues=[
            {
                "requirement_key": "VND-INS-1",
                "challenge_type": "missing_evidence",
                "severity": "material",
                "question": "Provide a current insurance certificate.",
            }
        ],
        output_dir=tmp_path / "out",
        operator_id="human.vendor_risk_test",
        now=NOW,
    )

    states = {
        row["requirement_key"]: row["review_state"]
        for row in result["review_pack"]["requirement_evidence_matrix"]
    }
    assert states == {
        "VND-INS-1": "STALE",
        "VND-PRIV-1": "CONTESTED",
        "VND-SEC-1": "SUPPORTED",
    }

    pack = result["review_pack"]
    assert pack["meta_composition"]["required_meta_products"] == [
        "meta_evidence",
        "meta_assurance",
        "meta_room",
    ]
    assert pack["meta_composition"]["release_guard_meta_product"] == "meta_authority"
    assert pack["human_review"]["final_domain_decision"] == "NEEDS_YOU"
    assert pack["external_release"] == "REFUSE"
    assert all(value is False for value in pack["forbidden_outcomes_created"].values())

    proof = result["proof_manifest"]
    assert proof["authority_created"] is False
    assert proof["execution_performed"] is False
    assert proof["external_effects"] is False
    assert proof["external_release"] is False
    assert all(value is False for value in proof["forbidden_outcomes_created"].values())
    for artifact in proof["artifacts"]:
        path = Path(result["output_dir"]) / artifact["filename"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]

    receipt = result["receipt"]
    assert receipt["internal_processing"] == "COMPLETE"
    assert receipt["generic_executor_gate"] == "refuse"
    assert receipt["human_review_gate"] == "NEEDS_YOU"
    assert receipt["external_release_gate"] == "REFUSE"
    assert receipt["domain_decision_created"] is False
    assert receipt["domain_score_created"] is False
    assert all(value is False for value in receipt["forbidden_outcomes_created"].values())
    assert receipt["authority_created"] is False
    assert receipt["execution_performed"] is False
    assert receipt["external_effects"] is False
    assert receipt["external_release"] is False

    assert case["gates"] == before["gates"]
    assert case["actions"] == before["actions"]
    assert case["decisions"] == before["decisions"]
    assert case["outputs"] == before["outputs"]

    assert (tmp_path / "out" / "VENDORPROOF_REVIEW_PACK.json").is_file()
    assert (tmp_path / "out" / "VENDORPROOF_REVIEW_PACK.html").is_file()
    assert (tmp_path / "out" / "PROOF_MANIFEST.json").is_file()
    assert (tmp_path / "out" / "VENDORPROOF_PROCESSING_RECEIPT.json").is_file()


def test_vendorproof_controlled_review_refuses_unapproved_intake(tmp_path: Path) -> None:
    case = _case(tmp_path, intake_state="pending")
    with pytest.raises(RuntimeError, match="approved intake authority"):
        run_controlled_vendorproof_review(
            case,
            requirements=[
                {
                    "requirement_key": "VND-1",
                    "statement": "Vendor evidence is available.",
                    "mandatory": True,
                }
            ],
            evidence_inputs=[],
            issues=[],
            output_dir=tmp_path / "out",
            operator_id="human.vendor_risk_test",
            now=NOW,
        )


def test_vendorproof_controlled_review_requires_explicit_operator(tmp_path: Path) -> None:
    case = _case(tmp_path)
    with pytest.raises(ValueError, match="explicit operator_id"):
        run_controlled_vendorproof_review(
            case,
            requirements=[
                {
                    "requirement_key": "VND-1",
                    "statement": "Vendor evidence is available.",
                    "mandatory": True,
                }
            ],
            evidence_inputs=[],
            issues=[],
            output_dir=tmp_path / "out",
            operator_id="",
            now=NOW,
        )
