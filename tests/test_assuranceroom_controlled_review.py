from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from products.assuranceroom.runner import (
    load_assuranceroom_profile,
    run_controlled_assuranceroom_review,
)
from products.governed_case import new_case
from products.meta import load_meta_registry
from products.registry import load_portfolio


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-08-17T13:45:00+00:00"


def _case(
    tmp_path: Path,
    *,
    product: str = "dio_assuranceroom",
    intake_state: str = "approved",
) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source_path = tmp_path / "source.json"
    source_path.write_text("{}", encoding="utf-8")
    return new_case(
        product=product,
        job_id=f"assuranceroom-controlled-{product}-{intake_state}",
        source={"source": {}, "evidence": []},
        source_path=source_path,
        evidence_inputs=["declared assurance requirements", "supporting evidence"],
        expected_outputs=[
            "requirement-evidence matrix",
            "issue register",
            "open-question list",
            "assurance evidence review pack",
            "human assurance decision receipt",
        ],
        required_authorities=[
            "assurance_owner",
            "evidence_reviewer",
            "authorised_assurance_decision_owner",
        ],
        intake_state=intake_state,
        now=NOW,
    )


def test_controlled_assuranceroom_review_surfaces_support_and_gaps_without_assurance_authority(
    tmp_path: Path,
) -> None:
    case = _case(tmp_path / "case")
    before = {
        field: copy.deepcopy(case[field])
        for field in ("gates", "actions", "decisions", "outputs")
    }

    result = run_controlled_assuranceroom_review(
        case,
        requirements=[
            {
                "requirement_key": "AR-1",
                "statement": "The declared assurance control has current reviewable evidence.",
                "kind": "control",
                "mandatory": True,
                "dependency_requirement_keys": [],
            },
            {
                "requirement_key": "AR-2",
                "statement": "The declared assurance requirement has supporting evidence available for review.",
                "kind": "control",
                "mandatory": True,
                "dependency_requirement_keys": [],
            },
        ],
        evidence_inputs=[
            {
                "evidence_kind": "control_evidence_record",
                "source_ref": "assurance://controlled/control-evidence",
                "sha256": "c" * 64,
                "target_requirement_keys": ["AR-1"],
                "relation": "supports",
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            },
        ],
        issues=[],
        output_dir=tmp_path / "out",
        operator_id="human.assuranceroom_test",
        now=NOW,
    )

    states = {
        row["requirement_key"]: row["review_state"]
        for row in result["review_pack"]["requirement_evidence_matrix"]
    }
    assert states == {"AR-1": "SUPPORTED", "AR-2": "UNKNOWN"}

    pack = result["review_pack"]
    assert pack["meta_composition"]["required_meta_products"] == [
        "meta_evidence",
        "meta_assurance",
        "meta_room",
    ]
    assert pack["meta_composition"]["release_guard_meta_product"] == "meta_authority"
    assert pack["human_review"]["evidence_review"] == "NEEDS_YOU"
    assert pack["human_review"]["final_domain_decision"] == "NEEDS_YOU"
    assert pack["human_review"]["decision_receipt_created"] is False
    assert pack["external_release"] == "REFUSE"
    assert not any(pack["forbidden_outcomes_created"].values())

    proof = result["proof_manifest"]
    assert proof["authority_created"] is False
    assert proof["execution_performed"] is False
    assert proof["external_effects"] is False
    assert proof["external_release"] is False
    assert not any(proof["forbidden_outcomes_created"].values())
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
    assert receipt["authority_created"] is False
    assert receipt["execution_performed"] is False
    assert receipt["external_effects"] is False
    assert receipt["external_release"] is False
    assert not any(receipt["forbidden_outcomes_created"].values())

    for field in before:
        assert case[field] == before[field]

    assert (tmp_path / "out" / "ASSURANCEROOM_REVIEW_PACK.json").is_file()
    assert (tmp_path / "out" / "ASSURANCEROOM_REVIEW_PACK.html").is_file()
    assert (tmp_path / "out" / "PROOF_MANIFEST.json").is_file()
    assert (tmp_path / "out" / "ASSURANCEROOM_PROCESSING_RECEIPT.json").is_file()


def test_assuranceroom_profile_remains_unpromoted_and_outside_canonical_portfolio() -> None:
    profile = load_assuranceroom_profile()
    assert profile["identity_state"] == "genuine_profile_extension_unpromoted"
    assert profile["canonical_portfolio_registration"] is False
    assert profile["scope_basis"] == "atlas_product_class_name_and_reconciliation_route_only"

    portfolio_ids = {row["id"] for row in load_portfolio()["products"]}
    composition_ids = {
        row["product_id"]
        for row in load_meta_registry()["vertical_compositions"]
    }
    assert "dio_assuranceroom" not in portfolio_ids
    assert "dio_assuranceroom" not in composition_ids

    reconciliation = json.loads(
        (ROOT / "config" / "product_class_reconciliation.json").read_text(
            encoding="utf-8"
        )
    )
    assert reconciliation["genuine_profile_extensions"]["assuranceroom"]["suggested_engine"] == "evidex"
    assert "assuranceroom" not in reconciliation["exact_canonical_incarnations"]
    assert "assuranceroom" not in reconciliation["equivalence_candidates"]
    assert "assuranceroom" not in reconciliation["resolved_composition_bindings"]


def test_assuranceroom_refuses_unapproved_intake_and_wrong_product(tmp_path: Path) -> None:
    pending = _case(tmp_path / "pending", intake_state="pending")
    with pytest.raises(RuntimeError, match="approved intake authority"):
        run_controlled_assuranceroom_review(
            pending,
            requirements=[
                {
                    "requirement_key": "AR-1",
                    "statement": "A bounded assurance evidence requirement exists.",
                    "kind": "control",
                    "dependency_requirement_keys": [],
                }
            ],
            evidence_inputs=[],
            issues=[],
            output_dir=tmp_path / "pending-out",
            operator_id="human.assuranceroom_test",
            now=NOW,
        )

    wrong = _case(tmp_path / "wrong", product="dio_auditproof")
    with pytest.raises(ValueError, match="requires product=dio_assuranceroom"):
        run_controlled_assuranceroom_review(
            wrong,
            requirements=[
                {
                    "requirement_key": "AR-1",
                    "statement": "A bounded assurance evidence requirement exists.",
                    "kind": "control",
                    "dependency_requirement_keys": [],
                }
            ],
            evidence_inputs=[],
            issues=[],
            output_dir=tmp_path / "wrong-out",
            operator_id="human.assuranceroom_test",
            now=NOW,
        )
