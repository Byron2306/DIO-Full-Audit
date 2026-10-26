from __future__ import annotations

from pathlib import Path

from products.contractproof_execution_proof import run_contractproof_execution_proof
from products.product_class_execution_proof import verify_execution_proof


NOW = "2026-08-17T21:15:00+00:00"
OPERATOR = "human.contractproof_execution_proof_test"


def test_contractproof_proof_executes_full_vesper_owned_route_and_stops_at_draft(tmp_path: Path) -> None:
    output = tmp_path / "contractproof"
    result = run_contractproof_execution_proof(output_dir=output, operator_id=OPERATOR, now=NOW)
    proof = result["proof"]

    assert proof["schema"] == "dio.product_class.execution_proof.v1"
    assert proof["product_id"] == "dio_contractproof"
    assert proof["adapter_family"] == "vesper_contractproof_attachment_journey"
    assert proof["inbound_owner"] == "vesper"
    assert proof["executor_id"] == "contractproof_internal_runner_v1"
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
    assert proof["journey"]["deterministic_execution"] == "PASS"
    assert proof["journey"]["source_binding"] == "PASS"
    assert proof["journey"]["proof_integrity"] == "PASS"
    assert proof["journey"]["vesper_intake"] == "PASS"
    assert proof["journey"]["outlook_draft"] == "PASS"
    assert proof["journey"]["evidence_fanout_guard"] == "PASS"
    assert proof["journey"]["sent"] is False
    assert proof["route_snapshot"]["inbound_owner"] == "vesper"
    assert proof["route_snapshot"]["auto_promotable"] is False
    assert verify_execution_proof(output) == proof

    downstream = result["downstream_receipt"]
    assert downstream["proof_integrity_verified"] is True
    assert downstream["authority_created"] is False
    assert downstream["waiver_created"] is False
    assert downstream["legal_opinion_created"] is False
    assert downstream["external_effects"] is False
    assert downstream["external_release"] is False


def test_contractproof_proof_contains_vesper_and_draft_receipts(tmp_path: Path) -> None:
    output = tmp_path / "contractproof"
    proof = run_contractproof_execution_proof(output_dir=output, operator_id=OPERATOR, now=NOW)["proof"]
    names = {row["filename"] for row in proof["artifacts"]}
    assert any(name.endswith("VESPER_INTAKE_RECEIPT.json") for name in names)
    assert any("outlook_smart_bot/drafts/" in name for name in names)
    assert "vesper_contractproof_journey/first/fulfilment/proof/CONTRACTPROOF_RECEIPT.json" in names
    assert "vesper_contractproof_journey/first/fulfilment/proof/EVIDENCE_PACK.pdf" in names
