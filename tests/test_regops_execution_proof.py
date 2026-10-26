from __future__ import annotations

from pathlib import Path

import pytest

from products.product_class_execution_proof import ProductClassExecutionProofError, verify_execution_proof
from products.regops_execution_proof import controlled_regops_fixture, run_regops_execution_proof


NOW = "2026-08-17T21:30:00+00:00"
OPERATOR = "human.regops_execution_proof_test"


def test_regops_proof_executes_controlled_readiness_with_bounded_ai_component(tmp_path: Path) -> None:
    output = tmp_path / "regops"
    result = run_regops_execution_proof(
        controlled_regops_fixture(),
        output_dir=output,
        operator_id=OPERATOR,
        now=NOW,
    )
    proof = result["proof"]
    assert proof["schema"] == "dio.product_class.execution_proof.v1"
    assert proof["product_id"] == "dio_regops"
    assert proof["adapter_family"] == "regops_controlled_readiness"
    assert proof["executor_id"] == "regops_controlled_readiness_v1"
    assert proof["processor_invoked"] is True
    assert proof["controlled_processor_execution"] is True
    assert proof["execution_proof_state"] == "CONTROLLED_ROUTE_PROVED"
    assert proof["processor_receipt_internal_state"] == "COMPLETE"
    assert proof["ai_regulatory_component_state"] == "CONTROLLED_CONTEXT_EVALUATED"
    assert proof["human_review_gate"] == "NEEDS_YOU"
    assert proof["external_release_gate"] == "REFUSE"
    assert proof["authority_created"] is False
    assert proof["external_effects"] is False
    assert proof["external_release"] is False
    assert proof["public_launch_ready"] is False
    assert proof["route_snapshot"]["relationship"] == "composition_reuse"
    assert proof["route_snapshot"]["reusable_component_product_id"] == "dio_airegreadiness"
    assert proof["route_snapshot"]["auto_promotable"] is False
    assert verify_execution_proof(output) == proof

    receipt = result["processor_result"]["receipt"]
    assert receipt["legal_clearance_created"] is False
    assert receipt["professional_decision_created"] is False
    assert receipt["filing_authority_created"] is False
    assert receipt["execution_performed"] is False


def test_regops_execution_proof_refuses_unapproved_fixture(tmp_path: Path) -> None:
    fixture = controlled_regops_fixture()
    fixture["intake_authority_approved"] = False
    with pytest.raises(ProductClassExecutionProofError, match="intake_authority_approved"):
        run_regops_execution_proof(
            fixture,
            output_dir=tmp_path / "no-authority",
            operator_id=OPERATOR,
            now=NOW,
        )
