from __future__ import annotations

import json
from pathlib import Path

from products.professional_evidence_executor import PASS
from products.professional_evidence_vesper_gate import execute_customer_case_via_vesper


NOW = "2026-08-19T16:30:00+00:00"


def test_auditproof_runs_from_vesper_quarantine_bytes_to_professional_pack(tmp_path: Path) -> None:
    receipt = execute_customer_case_via_vesper(
        "AuditProof",
        tmp_path / "portfolio",
        operator_id="pytest.vesper.auditproof",
        now=NOW,
        online=False,
    )
    assert receipt["status"] == PASS, receipt.get("error")
    assert receipt["vesper_web_chat_front_door_verified"] is True
    assert receipt["chat_completed_before_product_execution"] is True
    assert receipt["product_consumed_vesper_quarantined_bytes"] is True
    assert receipt["executor_rematerialized_packet"] is False
    assert receipt["channel"] == "web_chat"
    assert receipt["whatsapp_used"] is False
    assert receipt["telegram_used"] is False
    assert receipt["product_pipeline_executed"] is True
    assert receipt["human_review_required"] is True
    assert receipt["external_send"] == "REFUSE"
    assert receipt["external_publication"] == "REFUSE"
    assert receipt["authority_created"] is False
    assert receipt["external_effects"] is False
    assert receipt["vesper_source_binding_count"] > 0
    assert all(row["rehydrated_into_product_packet"] is True for row in receipt["vesper_source_bindings"])

    case_root = tmp_path / "portfolio" / "auditproof"
    binding_path = case_root / "VESPER_WEB_CHAT" / "VESPER_WEB_CHAT_BINDING.json"
    outer_path = case_root / "PROFESSIONAL_EVIDENCE_RECEIPT.json"
    review_pack = case_root / "EXECUTION" / "AUDITPROOF_REVIEW_PACK.json"
    processing_receipt = case_root / "EXECUTION" / "AUDITPROOF_PROCESSING_RECEIPT.json"
    assert binding_path.is_file()
    assert outer_path.is_file()
    assert review_pack.is_file()
    assert processing_receipt.is_file()

    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    outer = json.loads(outer_path.read_text(encoding="utf-8"))
    pack = json.loads(review_pack.read_text(encoding="utf-8"))
    processing = json.loads(processing_receipt.read_text(encoding="utf-8"))
    assert binding["all_product_source_bytes_rehydrated_from_vesper_quarantine"] is True
    assert binding["executor_may_rematerialize_packet"] is False
    assert outer["rematerialized_by_executor"] is False
    assert outer["vesper_web_chat_front_door_verified"] is True
    assert outer["product_consumed_vesper_quarantined_bytes"] is True

    # Authority/release limits are not evidence contradictions. Every literal
    # customer fact remains source-backed while consequential audit judgement
    # stays behind the human gate.
    matrix = {row["requirement_key"]: row for row in pack["requirement_evidence_matrix"]}
    assert set(matrix) == {"REQ-01", "REQ-02", "REQ-03", "REQ-04"}
    assert all(row["review_state"] == "SUPPORTED" for row in matrix.values())
    assert all(row["case_state"] == "supported" for row in matrix.values())
    assert pack["issue_register"] == []
    assert processing["human_review_gate"] == "NEEDS_YOU"
    assert processing["external_release_gate"] == "REFUSE"
    assert processing["forbidden_outcomes_created"]["audit_opinion"] is False
    assert processing["forbidden_outcomes_created"]["control_effectiveness_certification"] is False


def test_auditproof_final_case_preserves_chat_quarantine_and_blind_examiner_separation(tmp_path: Path) -> None:
    receipt = execute_customer_case_via_vesper(
        "AuditProof",
        tmp_path / "portfolio",
        operator_id="pytest.vesper.auditproof",
        now=NOW,
        online=False,
    )
    assert receipt["status"] == PASS, receipt.get("error")
    case_root = tmp_path / "portfolio" / "auditproof"
    assert (case_root / "VESPER_WEB_CHAT" / "sessions").is_dir()
    assert (case_root / "VESPER_WEB_CHAT" / "state" / "vesper" / "quarantine").is_dir()
    assert (case_root / "BLIND_REVIEW.json").is_file()
    blind = json.loads((case_root / "BLIND_REVIEW.json").read_text(encoding="utf-8"))
    assert blind["examiner_loaded_after_execution"] is True
    assert blind["passed"] is True
    assert receipt["examiner_data_used_during_execution"] is False
