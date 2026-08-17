from __future__ import annotations

from pathlib import Path

import pytest

from products.evidence_profile_execution_proof import (
    EVIDENCE_PROFILE_IDS,
    _profiles_by_product,
    controlled_evidence_fixture,
    run_evidence_profile_execution_proof,
)
from products.product_class_execution_proof import (
    ProductClassExecutionProofError,
    verify_execution_proof,
)


NOW = "2026-08-17T20:30:00+00:00"
OPERATOR = "human.evidence_profile_execution_proof_test"
PRODUCTS = tuple(sorted(_profiles_by_product()))


def test_evidence_profile_adapter_covers_exact_expected_profiles() -> None:
    product_map = _profiles_by_product()
    assert len(product_map) == 10
    assert set(product_map.values()) == set(EVIDENCE_PROFILE_IDS)


@pytest.mark.parametrize("product_id", PRODUCTS)
def test_shared_evidence_adapter_proves_controlled_route_without_domain_or_release_authority(
    product_id: str,
    tmp_path: Path,
) -> None:
    profile_id = _profiles_by_product()[product_id]
    output = tmp_path / profile_id
    result = run_evidence_profile_execution_proof(
        product_id,
        controlled_evidence_fixture(profile_id),
        output_dir=output,
        operator_id=OPERATOR,
        now=NOW,
    )
    proof = result["proof"]
    assert proof["schema"] == "dio.product_class.execution_proof.v1"
    assert proof["product_id"] == product_id
    assert proof["profile_id"] == profile_id
    assert proof["adapter_family"] == "controlled_evidence_review"
    assert proof["executor_id"] == "controlled_evidence_review_v1"
    assert proof["suggested_engine"] == "evidex"
    assert proof["source_authority_scope"] == "controlled_fixture_only"
    assert proof["processor_invoked"] is True
    assert proof["controlled_processor_execution"] is True
    assert proof["execution_proof_state"] == "CONTROLLED_ROUTE_PROVED"
    assert proof["processor_receipt_internal_state"] == "COMPLETE"
    assert proof["human_review_gate"] == "NEEDS_YOU"
    assert proof["external_release_gate"] == "REFUSE"
    assert proof["authority_created"] is False
    assert proof["external_effects"] is False
    assert proof["external_release"] is False
    assert proof["public_launch_ready"] is False
    assert proof["route_snapshot"] == {
        "route_kind": "profile_extension",
        "suggested_engine": "evidex",
        "auto_promotable": False,
        "reconciliation_suggested_engine": "evidex",
    }
    assert verify_execution_proof(output) == proof

    matrix = result["processor_result"]["review_pack"]["requirement_evidence_matrix"]
    assert {row["requirement_key"]: row["review_state"] for row in matrix} == {
        "REQ-1": "SUPPORTED",
        "REQ-2": "CONTESTED",
    }
    assert not any(result["processor_result"]["receipt"]["forbidden_outcomes_created"].values())


def test_evidence_profile_proof_refuses_unapproved_or_cross_profile_fixture(tmp_path: Path) -> None:
    product_id = "dio_auditproof"
    fixture = controlled_evidence_fixture("auditproof")
    fixture["intake_authority_approved"] = False
    with pytest.raises(ProductClassExecutionProofError, match="intake_authority_approved"):
        run_evidence_profile_execution_proof(
            product_id,
            fixture,
            output_dir=tmp_path / "no-authority",
            operator_id=OPERATOR,
            now=NOW,
        )

    wrong = controlled_evidence_fixture("vendorproof")
    with pytest.raises(ProductClassExecutionProofError, match="profile mismatch"):
        run_evidence_profile_execution_proof(
            product_id,
            wrong,
            output_dir=tmp_path / "cross-profile",
            operator_id=OPERATOR,
            now=NOW,
        )


def test_evidence_profile_execution_proof_detects_review_artifact_tampering(tmp_path: Path) -> None:
    product_id = "dio_auditproof"
    output = tmp_path / "auditproof"
    run_evidence_profile_execution_proof(
        product_id,
        controlled_evidence_fixture("auditproof"),
        output_dir=output,
        operator_id=OPERATOR,
        now=NOW,
    )
    review_pack = output / "AUDITPROOF_REVIEW_PACK.json"
    review_pack.write_text(review_pack.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    with pytest.raises(ProductClassExecutionProofError, match="hash mismatch"):
        verify_execution_proof(output)
