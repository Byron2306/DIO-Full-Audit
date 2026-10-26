from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from products.high_risk_execution_proof import (
    controlled_high_risk_fixture,
    high_risk_profiles_by_product,
    run_high_risk_execution_proof,
)
from products.product_class_execution_proof import ProductClassExecutionProofError, verify_execution_proof
from products.unpromoted_high_risk_profile import HIGH_RISK_PROFILE_IDS


NOW = "2026-08-17T21:50:00+00:00"


def _product_for(profile_id: str) -> str:
    matches = [product_id for product_id, bound_profile in high_risk_profiles_by_product().items() if bound_profile == profile_id]
    assert len(matches) == 1
    return matches[0]


@pytest.mark.parametrize("profile_id", sorted(HIGH_RISK_PROFILE_IDS))
def test_high_risk_route_proof_executes_review_processor_without_assigning_domain_engine(
    tmp_path: Path,
    profile_id: str,
) -> None:
    product_id = _product_for(profile_id)
    out = tmp_path / profile_id
    result = run_high_risk_execution_proof(
        product_id,
        controlled_high_risk_fixture(profile_id),
        output_dir=out,
        operator_id="human.high_risk_execution_proof_test",
        now=NOW,
    )
    proof = result["proof"]
    assert proof["product_id"] == product_id
    assert proof["profile_id"] == profile_id
    assert proof["adapter_family"] == "high_risk_controlled_review_no_engine"
    assert proof["executor_id"] == "controlled_evidence_review_v1"
    assert proof["suggested_engine"] is None
    assert proof["domain_engine_assigned"] is False
    assert proof["domain_engine_invoked"] is False
    assert proof["domain_execution_proved"] is False
    assert proof["processor_invoked"] is True
    assert proof["controlled_processor_execution"] is True
    assert proof["execution_proof_state"] == "CONTROLLED_ROUTE_PROVED"
    assert proof["human_review_gate"] == "NEEDS_YOU"
    assert proof["external_release_gate"] == "REFUSE"
    assert proof["authority_created"] is False
    assert proof["external_effects"] is False
    assert proof["external_release"] is False
    assert proof["public_launch_ready"] is False
    assert proof["route_boundary"]["engine_assigned"] is False
    assert proof["route_boundary"]["engine_invoked"] is False
    assert proof["route_boundary"]["execution_proof_created"] is False
    assert result["processor_result"]["receipt"]["execution_performed"] is False
    assert verify_execution_proof(out) == proof


def test_high_risk_route_proof_refuses_fixture_identity_drift(tmp_path: Path) -> None:
    profile_id = "controldrift"
    fixture = copy.deepcopy(controlled_high_risk_fixture(profile_id))
    fixture["profile_id"] = "incidentproof"
    with pytest.raises(ProductClassExecutionProofError, match="fixture profile mismatch"):
        run_high_risk_execution_proof(
            _product_for(profile_id),
            fixture,
            output_dir=tmp_path / "wrong",
            operator_id="human.high_risk_execution_proof_test",
            now=NOW,
        )


def test_high_risk_route_proof_detects_top_level_tamper(tmp_path: Path) -> None:
    out = tmp_path / "tamper"
    product_id = _product_for("releaseproof")
    run_high_risk_execution_proof(
        product_id,
        controlled_high_risk_fixture("releaseproof"),
        output_dir=out,
        operator_id="human.high_risk_execution_proof_test",
        now=NOW,
    )
    path = out / "PRODUCT_EXECUTION_PROOF.json"
    proof = json.loads(path.read_text(encoding="utf-8"))
    proof["domain_engine_assigned"] = True
    path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ProductClassExecutionProofError, match="fingerprint mismatch"):
        verify_execution_proof(out)
