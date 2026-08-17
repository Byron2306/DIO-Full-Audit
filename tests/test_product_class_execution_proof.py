from __future__ import annotations

import json
from pathlib import Path

import pytest

from products.obligationfamily.runner import FAMILY_DEFINITIONS
from products.product_class_execution_proof import (
    ProductClassExecutionProofError,
    run_execution_proof,
    verify_execution_proof,
)


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-08-17T20:00:00+00:00"
OPERATOR = "human.product_class_proof_test"


def _fixture(product_id: str) -> dict:
    definition = FAMILY_DEFINITIONS[product_id]
    root = ROOT / "config" / "products" / "golden" / definition["slug"]
    return {
        "source": json.loads((root / "reference_source.json").read_text(encoding="utf-8")),
        "evidence_inputs": json.loads((root / "reference_evidence.json").read_text(encoding="utf-8"))["evidence_records"],
    }


@pytest.mark.parametrize("product_id", sorted(FAMILY_DEFINITIONS))
def test_shared_harness_proves_each_obligation_family_route_without_promoting_authority(product_id: str, tmp_path: Path) -> None:
    output = tmp_path / FAMILY_DEFINITIONS[product_id]["slug"]
    result = run_execution_proof(
        product_id,
        _fixture(product_id),
        output_dir=output,
        operator_id=OPERATOR,
        now=NOW,
    )
    proof = result["proof"]
    assert proof["schema"] == "dio.product_class.execution_proof.v1"
    assert proof["product_id"] == product_id
    assert proof["adapter_family"] == "obligation_family"
    assert proof["executor_id"] == "obligation_family_internal_runner_v1"
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
    assert "does not prove" in proof["claim_ceiling"]
    assert (output / "PRODUCT_EXECUTION_PROOF.json").is_file()
    assert verify_execution_proof(output) == proof


def test_proof_verifier_detects_artifact_tampering(tmp_path: Path) -> None:
    product_id = "dio_grantproof"
    output = tmp_path / "grantproof"
    run_execution_proof(product_id, _fixture(product_id), output_dir=output, operator_id=OPERATOR, now=NOW)
    evidence_pack = output / "EVIDENCE_PACK.json"
    evidence_pack.write_text(evidence_pack.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    with pytest.raises(ProductClassExecutionProofError, match="hash mismatch"):
        verify_execution_proof(output)


def test_harness_refuses_missing_operator_unknown_product_and_dirty_output(tmp_path: Path) -> None:
    fixture = _fixture("dio_grantproof")
    with pytest.raises(ProductClassExecutionProofError, match="operator_id"):
        run_execution_proof("dio_grantproof", fixture, output_dir=tmp_path / "no-operator", operator_id="", now=NOW)
    with pytest.raises(ProductClassExecutionProofError, match="no execution-proof adapter"):
        run_execution_proof("dio_not_a_product", fixture, output_dir=tmp_path / "unknown", operator_id=OPERATOR, now=NOW)

    dirty = tmp_path / "dirty"
    dirty.mkdir()
    (dirty / "old-proof.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ProductClassExecutionProofError, match="must be empty"):
        run_execution_proof("dio_grantproof", fixture, output_dir=dirty, operator_id=OPERATOR, now=NOW)


def test_harness_refuses_cross_product_fixture(tmp_path: Path) -> None:
    tender_fixture = _fixture("dio_tenderproof")
    with pytest.raises(ValueError, match="source_type=grant"):
        run_execution_proof(
            "dio_grantproof",
            tender_fixture,
            output_dir=tmp_path / "wrong-source",
            operator_id=OPERATOR,
            now=NOW,
        )
