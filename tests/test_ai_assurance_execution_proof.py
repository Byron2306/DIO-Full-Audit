from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from products.ai_assurance_execution_proof import (
    controlled_ai_assurance_fixture,
    run_ai_assurance_execution_proof,
)
from products.product_class_execution_proof import ProductClassExecutionProofError, verify_execution_proof


NOW = "2026-08-17T22:00:00+00:00"


def test_ai_assurance_executes_aitrust_component_then_broader_control_evidence_review(tmp_path: Path) -> None:
    out = tmp_path / "ai-assurance"
    result = run_ai_assurance_execution_proof(
        controlled_ai_assurance_fixture(),
        output_dir=out,
        operator_id="human.ai_assurance_execution_proof_test",
        now=NOW,
    )
    proof = result["proof"]
    assert proof["product_id"] == "dio_assurance"
    assert proof["atlas_product_class"] == "dio_ai_assurance"
    assert proof["adapter_family"] == "ai_assurance_composition_reuse"
    assert proof["execution_proof_state"] == "CONTROLLED_ROUTE_PROVED"
    assert proof["processor_invoked"] is True
    assert proof["controlled_processor_execution"] is True
    assert proof["component_product_id"] == "dio_aitrustproof"
    assert proof["component_executor_id"] == "ai_trust_internal_runner_v1"
    assert proof["component_execution_proved"] is True
    assert proof["identity_equivalence_rejected"] is True
    assert proof["composition_review_processor"] == "controlled_evidence_review_v1"
    assert proof["control_evidence_states"] == {
        "AI-ASSURANCE-INVENTORY": "SUPPORTED",
        "AI-ASSURANCE-REVIEW-BOUNDARY": "SUPPORTED",
        "AI-ASSURANCE-TRUST-EVALUATION": "SUPPORTED",
    }
    assert proof["human_review_gate"] == "NEEDS_YOU"
    assert proof["external_release_gate"] == "REFUSE"
    assert proof["authority_created"] is False
    assert proof["external_effects"] is False
    assert proof["external_release"] is False
    assert proof["public_launch_ready"] is False
    assert proof["route_snapshot"]["relationship"] == "composition_reuse"
    assert proof["route_snapshot"]["canonical_product_id"] == "dio_assurance"
    assert proof["route_snapshot"]["reusable_component_product_id"] == "dio_aitrustproof"
    assert proof["route_snapshot"]["identity_state"] == "identity_equivalence_rejected"
    assert result["component_result"]["receipt"]["human_gate"] == "NEEDS_YOU"
    assert result["component_result"]["receipt"]["external_release_gate"] == "REFUSE"
    assert result["processor_result"]["receipt"]["execution_performed"] is False
    assert verify_execution_proof(out) == proof
    assert (out / "component_aitrustproof" / "AI_TRUST_RECEIPT.json").is_file()
    assert (out / "DIOAIASSURANCE_PROCESSING_RECEIPT.json").is_file()


def test_ai_assurance_refuses_wrong_component_source_type(tmp_path: Path) -> None:
    fixture = copy.deepcopy(controlled_ai_assurance_fixture())
    fixture["ai_trust_payload"]["source_type"] = "ai_agent"
    with pytest.raises(ProductClassExecutionProofError, match="requires an ai_system"):
        run_ai_assurance_execution_proof(
            fixture,
            output_dir=tmp_path / "wrong-source",
            operator_id="human.ai_assurance_execution_proof_test",
            now=NOW,
        )


def test_ai_assurance_top_level_proof_tamper_is_detected(tmp_path: Path) -> None:
    out = tmp_path / "tamper"
    run_ai_assurance_execution_proof(
        controlled_ai_assurance_fixture(),
        output_dir=out,
        operator_id="human.ai_assurance_execution_proof_test",
        now=NOW,
    )
    path = out / "PRODUCT_EXECUTION_PROOF.json"
    proof = json.loads(path.read_text(encoding="utf-8"))
    proof["identity_equivalence_rejected"] = False
    path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ProductClassExecutionProofError, match="fingerprint mismatch"):
        verify_execution_proof(out)
