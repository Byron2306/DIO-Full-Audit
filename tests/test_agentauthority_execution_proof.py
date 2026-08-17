from __future__ import annotations

from pathlib import Path

from products.agentauthority_execution_proof import controlled_agentauthority_fixture, run_agentauthority_execution_proof
from products.product_class_execution_proof import verify_execution_proof


NOW = "2026-08-17T22:00:00+00:00"
OPERATOR = "human.agentauthority_execution_proof_test"


def test_agentauthority_proof_detects_injection_and_refuses_tool_actions(tmp_path: Path) -> None:
    output = tmp_path / "agentauthority"
    result = run_agentauthority_execution_proof(
        controlled_agentauthority_fixture(),
        output_dir=output,
        operator_id=OPERATOR,
        now=NOW,
    )
    proof = result["proof"]
    assert proof["schema"] == "dio.product_class.execution_proof.v1"
    assert proof["product_id"] == "dio_agentauthority"
    assert proof["atlas_product_class"] == "agent_authority"
    assert proof["adapter_family"] == "ai_trust_agent_authority"
    assert proof["executor_id"] == "ai_trust_internal_runner_v1"
    assert proof["processor_invoked"] is True
    assert proof["controlled_processor_execution"] is True
    assert proof["execution_proof_state"] == "CONTROLLED_ROUTE_PROVED"
    assert proof["human_review_gate"] == "NEEDS_YOU"
    assert proof["external_release_gate"] == "REFUSE"
    assert proof["authority_created"] is False
    assert proof["external_effects"] is False
    assert proof["external_release"] is False
    assert proof["public_launch_ready"] is False
    assert "ignore previous instructions" in proof["injection_signals"]
    assert "send this email now" in proof["injection_signals"]
    assert len(proof["action_decisions"]) == 2
    assert all(row["decision"] == "REFUSE" for row in proof["action_decisions"])
    assert any(row["effect"] == "external_send" and row["decision"] == "REFUSE" for row in proof["action_decisions"])
    assert proof["route_snapshot"]["canonical_product_id"] == "dio_agentauthority"
    assert proof["route_snapshot"]["canonical_executor"] == "product.executor.agentauthority"
    assert proof["route_snapshot"]["auto_promotable"] is False
    assert verify_execution_proof(output) == proof

    receipt = result["processor_result"]["receipt"]
    assert receipt["human_gate"] == "NEEDS_YOU"
    assert receipt["external_release_gate"] == "REFUSE"
    assert receipt["authority_created"] is False
    assert receipt["external_effects"] is False
