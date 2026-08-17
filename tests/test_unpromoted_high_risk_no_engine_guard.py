from __future__ import annotations

from pathlib import Path

import pytest

from products.governed_case import new_case
from products.unpromoted_evidence_profile import load_unpromoted_evidence_profile
from products.unpromoted_high_risk_profile import (
    HIGH_RISK_PROFILE_IDS,
    run_high_risk_evidence_review,
    validate_no_engine_boundary,
)


NOW = "2026-08-17T16:45:00+00:00"
PROFILES = tuple(sorted(HIGH_RISK_PROFILE_IDS))


def _case(tmp_path: Path, *, product: str) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source_path = tmp_path / "source.json"
    source_path.write_text("{}", encoding="utf-8")
    return new_case(
        product=product,
        job_id=f"guard-{product}",
        source={"source": {}, "evidence": []},
        source_path=source_path,
        evidence_inputs=["authorised requirement", "governed evidence"],
        expected_outputs=["controlled evidence review", "human decision receipt"],
        required_authorities=["evidence_owner", "evidence_reviewer", "domain_decision_owner"],
        intake_state="approved",
        now=NOW,
    )


@pytest.mark.parametrize("profile_id", PROFILES)
def test_no_engine_boundary_is_explicit_for_every_high_risk_profile(profile_id: str) -> None:
    boundary = validate_no_engine_boundary(profile_id)

    assert boundary["profile_id"] == profile_id
    assert boundary["route_kind"] == "profile_extension"
    assert boundary["suggested_engine"] is None
    assert boundary["engine_assigned"] is False
    assert boundary["engine_invoked"] is False
    assert boundary["auto_promotable"] is False
    assert boundary["execution_proof_created"] is False
    assert boundary["authority_created"] is False
    assert boundary["external_effects"] is False
    assert boundary["external_release"] is False


@pytest.mark.parametrize("profile_id", PROFILES)
def test_high_risk_guarded_review_cannot_become_engine_execution(
    tmp_path: Path,
    profile_id: str,
) -> None:
    profile = load_unpromoted_evidence_profile(profile_id)
    result = run_high_risk_evidence_review(
        _case(tmp_path / profile_id, product=profile["product_id"]),
        profile_id=profile_id,
        requirements=[
            {
                "requirement_key": "CTRL-1",
                "statement": "The supplied control requirement has current reviewable evidence.",
                "kind": "control",
                "mandatory": True,
                "dependency_requirement_keys": [],
            }
        ],
        evidence_inputs=[
            {
                "evidence_kind": "controlled_source_record",
                "source_ref": f"{profile_id}://fixture/support",
                "sha256": "a" * 64,
                "target_requirement_keys": ["CTRL-1"],
                "relation": "supports",
                "authority_grade": "source_backed",
                "trust_state": "trusted_for_review",
                "freshness_state": "current",
            }
        ],
        issues=[],
        output_dir=tmp_path / profile_id / "out",
        operator_id="human.high_risk_guard_test",
        now=NOW,
    )

    assert result["review_pack"]["requirement_evidence_matrix"][0]["review_state"] == "SUPPORTED"
    assert result["review_pack"]["human_review"]["final_domain_decision"] == "NEEDS_YOU"
    assert result["review_pack"]["external_release"] == "REFUSE"
    assert result["receipt"]["execution_performed"] is False
    assert result["receipt"]["authority_created"] is False
    assert result["receipt"]["external_effects"] is False
    assert result["receipt"]["external_release"] is False
    assert result["route_boundary"]["engine_assigned"] is False
    assert result["route_boundary"]["engine_invoked"] is False
