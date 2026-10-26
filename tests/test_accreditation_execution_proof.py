from __future__ import annotations

from pathlib import Path

import pytest

from products.accreditation_execution_proof import controlled_accreditation_fixture, run_accreditation_execution_proof
from products.product_class_execution_proof import ProductClassExecutionProofError, verify_execution_proof


NOW = "2026-08-17T21:45:00+00:00"
OPERATOR = "human.accreditation_execution_proof_test"


def test_homs_accreditation_composition_executes_without_minting_accreditation_authority(tmp_path: Path) -> None:
    output = tmp_path / "accreditation"
    result = run_accreditation_execution_proof(
        controlled_accreditation_fixture(),
        output_dir=output,
        operator_id=OPERATOR,
        now=NOW,
    )
    proof = result["proof"]
    assert proof["schema"] == "dio.product_class.execution_proof.v1"
    assert proof["product_id"] == "dio_accreditation"
    assert proof["atlas_product_class"] == "homs_accreditation"
    assert proof["adapter_family"] == "accreditation_controlled_review"
    assert proof["executor_id"] == "accreditation_controlled_review_v1"
    assert proof["processor_invoked"] is True
    assert proof["controlled_processor_execution"] is True
    assert proof["execution_proof_state"] == "CONTROLLED_ROUTE_PROVED"
    assert proof["processor_receipt_internal_state"] == "COMPLETE"
    assert proof["regulated_component_state"] == "CONTROLLED_CONTEXT_EVALUATED"
    assert proof["human_review_gate"] == "NEEDS_YOU"
    assert proof["external_release_gate"] == "REFUSE"
    assert proof["authority_created"] is False
    assert proof["external_effects"] is False
    assert proof["external_release"] is False
    assert proof["public_launch_ready"] is False
    assert proof["route_snapshot"]["relationship"] == "composition_reuse"
    assert proof["route_snapshot"]["canonical_product_id"] == "dio_accreditation"
    assert proof["route_snapshot"]["reusable_component_product_id"] == "dio_educationaccreditationproof"
    assert verify_execution_proof(output) == proof

    receipt = result["processor_result"]["receipt"]
    assert receipt["signatory_receipt_created"] is False
    assert receipt["accreditation_decision_created"] is False
    assert receipt["institutional_attestation_created"] is False
    assert receipt["regulator_acceptance_created"] is False
    assert receipt["execution_performed"] is False


def test_homs_accreditation_proof_refuses_unapproved_fixture(tmp_path: Path) -> None:
    fixture = controlled_accreditation_fixture()
    fixture["intake_authority_approved"] = False
    with pytest.raises(ProductClassExecutionProofError, match="intake_authority_approved"):
        run_accreditation_execution_proof(
            fixture,
            output_dir=tmp_path / "no-authority",
            operator_id=OPERATOR,
            now=NOW,
        )
