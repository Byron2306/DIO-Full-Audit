from __future__ import annotations

from products.evidence_reconciliation import reconcile_evidence


def _source() -> dict:
    return {"source_ref": "test://contract", "clauses": [
        {"clause_id": "7", "text": "The Supplier shall deliver a signed delivery note."},
        {"clause_id": "10", "text": "The Supplier must maintain valid insurance."},
        {"clause_id": "13", "text": "The Customer shall provide final acceptance."},
        {"clause_id": "16", "text": "The Supplier must notify an incident within 24 hours."},
        {"clause_id": "19", "text": "The Supplier shall remedy failed inspections."},
    ]}


def _row(identifier: str, name: str, text: str) -> dict:
    return {"attachment_id": identifier, "filename": name, "role": "evidence", "extraction_state": "EXTRACTED", "extracted_text": text}


def test_specific_reconciliation_blocks_blanket_fanout() -> None:
    manifest = {"attachments": [
        _row("ATT-1", "delivery.json", '{"target_clause": 1, "signed": false}'),
        _row("ATT-2", "insurance.txt", "Target clause: 2. Certificate expired 2025-01-01."),
        _row("ATT-3", "incident.txt", "Clause 4. Notice was late at 30 hours after the incident."),
        _row("ATT-4", "mystery.txt", "Unrelated foghorn maintenance log."),
    ]}
    result = reconcile_evidence(manifest, _source(), now="2026-08-16T12:00:00+00:00")
    assert result["fanout_guard"] == "PASS"
    assert result["mappings"][0]["target_locators"] == ["7"]
    assert result["mappings"][0]["relation"] == "contradicts"
    assert result["mappings"][1]["freshness_state"] == "expired"
    assert result["mappings"][2]["observed_signals"] == ["LATE_NOTICE"]
    assert result["mappings"][3]["target_locators"] == []
    assert result["unresolved_attachment_ids"] == ["ATT-4"]
    assert all(row["automatic_acceptance"] is False and row["human_gate"] == "NEEDS_YOU" for row in result["mappings"])
