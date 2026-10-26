from __future__ import annotations

from pathlib import Path

import pytest

from products.product_class_execution_proof import ProductClassExecutionProofError, verify_execution_proof
from products.vamp_profile_execution_proof import (
    controlled_vamp_fixture,
    run_vamp_profile_execution_proof,
    vamp_profiles_by_product,
)


NOW = "2026-08-17T20:45:00+00:00"
OPERATOR = "human.vamp_execution_proof_test"
PRODUCTS = tuple(sorted(vamp_profiles_by_product()))


def test_vamp_execution_adapter_covers_promotion_and_cpd_profiles() -> None:
    product_map = vamp_profiles_by_product()
    assert product_map == {
        "dio_cpdproof": "cpdproof",
        "dio_promotionproof": "promotionproof",
    }


@pytest.mark.parametrize("product_id", PRODUCTS)
def test_vamp_snapshot_bridge_proves_controlled_route_without_hr_or_award_authority(
    product_id: str,
    tmp_path: Path,
) -> None:
    profile_id = vamp_profiles_by_product()[product_id]
    output = tmp_path / profile_id
    result = run_vamp_profile_execution_proof(
        product_id,
        controlled_vamp_fixture(profile_id),
        output_dir=output,
        operator_id=OPERATOR,
        now=NOW,
    )
    proof = result["proof"]
    assert proof["schema"] == "dio.product_class.execution_proof.v1"
    assert proof["product_id"] == product_id
    assert proof["profile_id"] == profile_id
    assert proof["adapter_family"] == "vamp_snapshot_review"
    assert proof["suggested_engine"] == "vamp"
    assert proof["source_authority_scope"] == "controlled_fixture_only"
    assert proof["processor_invoked"] is True
    assert proof["controlled_processor_execution"] is True
    assert proof["execution_proof_state"] == "CONTROLLED_ROUTE_PROVED"
    assert proof["human_review_gate"] == "NEEDS_YOU"
    assert proof["external_release_gate"] == "REFUSE"
    assert proof["authority_created"] is False
    assert proof["external_effects"] is False
    assert proof["external_release"] is False
    assert proof["public_launch_ready"] is False
    assert proof["vamp_source_binding"]["rating_generated"] is False
    assert proof["vamp_source_binding"]["employment_decision_generated"] is False
    assert verify_execution_proof(output) == proof

    states = {
        row["requirement_key"]: row["review_state"]
        for row in result["processor_result"]["review_pack"]["requirement_evidence_matrix"]
    }
    assert states == {"OBJ-1": "SUPPORTED", "OBJ-2": "PARTIAL", "OBJ-3": "UNKNOWN"}


def test_vamp_execution_proof_refuses_unapproved_or_rated_fixture(tmp_path: Path) -> None:
    product_id = "dio_promotionproof"
    fixture = controlled_vamp_fixture("promotionproof")
    fixture["intake_authority_approved"] = False
    with pytest.raises(ProductClassExecutionProofError, match="intake_authority_approved"):
        run_vamp_profile_execution_proof(
            product_id,
            fixture,
            output_dir=tmp_path / "no-authority",
            operator_id=OPERATOR,
            now=NOW,
        )

    rated = controlled_vamp_fixture("promotionproof")
    rated["vamp_snapshot"]["release"]["rating_generated"] = True
    with pytest.raises(RuntimeError, match="generated a rating"):
        run_vamp_profile_execution_proof(
            product_id,
            rated,
            output_dir=tmp_path / "rated",
            operator_id=OPERATOR,
            now=NOW,
        )
