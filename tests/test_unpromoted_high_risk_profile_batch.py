from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from products.governed_case import new_case
from products.meta import load_meta_registry
from products.registry import load_portfolio
from products.unpromoted_evidence_profile import (
    load_unpromoted_evidence_profile,
    run_unpromoted_evidence_review,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-08-17T16:15:00+00:00"
PROFILES = (
    "controldrift",
    "ai_incidentroom",
    "criticalai_assurance",
    "cyberassurance",
    "dora_vendor_assurance",
    "incidentproof",
    "modelproof",
    "releaseproof",
    "suppliercyberproof",
)


def _case(tmp_path: Path, *, product: str, intake_state: str = "approved") -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source_path = tmp_path / "source.json"
    source_path.write_text("{}", encoding="utf-8")
    return new_case(
        product=product,
        job_id=f"controlled-{product}-{intake_state}",
        source={"source": {}, "evidence": []},
        source_path=source_path,
        evidence_inputs=["authorised requirements", "supporting governed evidence"],
        expected_outputs=[
            "requirement-evidence matrix",
            "issue register",
            "controlled evidence review pack",
            "human decision receipt",
        ],
        required_authorities=[
            "evidence_owner",
            "evidence_reviewer",
            "authorised_domain_decision_owner",
        ],
        intake_state=intake_state,
        now=NOW,
    )


@pytest.mark.parametrize("profile_id", PROFILES)
def test_high_risk_profiles_prepare_evidence_only_without_domain_authority(
    tmp_path: Path,
    profile_id: str,
) -> None:
    profile = load_unpromoted_evidence_profile(profile_id)
    case = _case(tmp_path / profile_id / "case", product=profile["product_id"])
    before = {
        field: copy.deepcopy(case[field])
        for field in ("gates", "actions", "decisions", "outputs")
    }

    result = run_unpromoted_evidence_review(
        case,
        profile_id=profile_id,
        requirements=[
            {
                "requirement_key": "CTRL-1",
                "statement": "The supplied requirement has current reviewable supporting evidence.",
                "kind": "control",
                "mandatory": True,
                "dependency_requirement_keys": [],
            }
        ],
        evidence_inputs=[
            {
                "evidence_kind": "controlled_source_record",
                "source_ref": f"{profile_id}://fixture/support",
                "sha256": "f" * 64,
                "target_requirement_keys": ["CTRL-1"],
                "relation": "supports",
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            }
        ],
        issues=[],
        output_dir=tmp_path / profile_id / "out",
        operator_id="human.high_risk_profile_test",
        now=NOW,
    )

    assert result["review_pack"]["requirement_evidence_matrix"][0]["review_state"] == "SUPPORTED"
    assert result["review_pack"]["human_review"]["final_domain_decision"] == "NEEDS_YOU"
    assert result["review_pack"]["human_review"]["decision_receipt_created"] is False
    assert result["review_pack"]["external_release"] == "REFUSE"
    assert result["receipt"]["internal_processing"] == "COMPLETE"
    assert result["receipt"]["execution_performed"] is False
    assert result["receipt"]["authority_created"] is False
    assert result["receipt"]["external_effects"] is False
    assert result["receipt"]["external_release"] is False
    assert not any(result["receipt"]["forbidden_outcomes_created"].values())

    for field in before:
        assert case[field] == before[field]



def test_high_risk_profiles_remain_unpromoted_noncanonical_and_without_engine_assignment() -> None:
    portfolio_ids = {row["id"] for row in load_portfolio()["products"]}
    composition_ids = {
        row["product_id"]
        for row in load_meta_registry()["vertical_compositions"]
    }
    routes = json.loads(
        (ROOT / "config" / "product_class_routes.json").read_text(encoding="utf-8")
    )
    reconciliation = json.loads(
        (ROOT / "config" / "product_class_reconciliation.json").read_text(encoding="utf-8")
    )

    for profile_id in PROFILES:
        profile = load_unpromoted_evidence_profile(profile_id)
        assert profile["identity_state"] == "genuine_profile_extension_unpromoted"
        assert profile["canonical_portfolio_registration"] is False
        assert profile["scope_basis"] == "atlas_product_class_name_and_reconciliation_route_only"
        assert profile["product_id"] not in portfolio_ids
        assert profile["product_id"] not in composition_ids
        assert routes["product_classes"][profile_id] == {
            "route_kind": "profile_extension",
            "suggested_engine": None,
            "auto_promotable": False,
        }
        assert reconciliation["genuine_profile_extensions"][profile_id]["suggested_engine"] is None
        assert profile_id not in reconciliation["exact_canonical_incarnations"]
        assert profile_id not in reconciliation["equivalence_candidates"]
        assert profile_id not in reconciliation["resolved_composition_bindings"]


@pytest.mark.parametrize("profile_id", PROFILES)
def test_high_risk_profiles_require_approved_intake_authority(
    tmp_path: Path,
    profile_id: str,
) -> None:
    profile = load_unpromoted_evidence_profile(profile_id)
    pending = _case(
        tmp_path / profile_id / "pending",
        product=profile["product_id"],
        intake_state="pending",
    )
    with pytest.raises(RuntimeError, match="approved intake authority"):
        run_unpromoted_evidence_review(
            pending,
            profile_id=profile_id,
            requirements=[
                {
                    "requirement_key": "CTRL-1",
                    "statement": "A bounded high-risk evidence requirement exists.",
                    "kind": "control",
                    "dependency_requirement_keys": [],
                }
            ],
            evidence_inputs=[],
            issues=[],
            output_dir=tmp_path / profile_id / "pending-out",
            operator_id="human.high_risk_profile_test",
            now=NOW,
        )
