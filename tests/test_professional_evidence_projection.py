from __future__ import annotations

import json
from pathlib import Path

import pytest

from products.professional_evidence_corpus import materialize_customer_packet
from products.professional_evidence_enrichment import enrich_customer_packet
from products.professional_evidence_projection import (
    ProfessionalEvidenceProjectionError,
    ai_trust_projection,
    load_packet,
    obligation_projection,
    review_projection,
)


def _packet(tmp_path: Path, incarnation: str):
    materialize_customer_packet(incarnation, tmp_path)
    root = tmp_path / incarnation.lower().replace(" & ", "-").replace(" ", "-")
    # Use actual materialized directory rather than guessing punctuation if needed.
    root = next(path for path in tmp_path.iterdir() if path.is_dir())
    enrich_customer_packet(incarnation, root / "CUSTOMER_PACKET")
    return load_packet(root / "CUSTOMER_PACKET"), root


def test_review_projection_uses_only_allowed_governed_evidence_vocabulary(tmp_path: Path) -> None:
    packet, _ = _packet(tmp_path, "AuditProof")
    projection = review_projection(packet, profile_id="auditproof")
    assert projection["examiner_data_used"] is False
    assert projection["packet_fingerprint"] == packet["packet_fingerprint"]
    for row in projection["review_evidence_inputs"]:
        assert row["authority_grade"] == "source_backed"
        assert row["trust_state"] == "trusted_for_review"
        assert row["freshness_state"] == "current"
        assert row["source_ref"].startswith("customer-packet://")


def test_obligation_projection_is_customer_packet_bound(tmp_path: Path) -> None:
    packet, _ = _packet(tmp_path, "TenderProof")
    projection = obligation_projection(packet, source_type="tender", owner_role="Bid manager")
    assert projection["examiner_data_used"] is False
    assert projection["source"]["source_type"] == "tender"
    assert projection["source"]["source_ref"].startswith("customer-packet://")
    assert len(projection["source"]["clauses"]) >= 3
    assert all(row["authority_grade"] == "source_backed" for row in projection["evidence_inputs"])


def test_agent_authority_projection_preserves_prompt_injection_and_refused_action(tmp_path: Path) -> None:
    packet, _ = _packet(tmp_path, "Agent Authority")
    projection = ai_trust_projection(packet, source_type="ai_agent", intended_use="mail_assistance", inject_actions=True)
    assert projection["customer_packet_fingerprint"] == packet["packet_fingerprint"]
    assert any(row["effect"] == "external_send" for row in projection["requested_actions"])
    assert not any(row["effect"] == "external_send" for row in projection["allowed_capabilities"])
    assert "ignore previous instructions" in projection["attachments"][0]["text"].lower()


def test_packet_hash_tamper_is_refused(tmp_path: Path) -> None:
    packet, root = _packet(tmp_path, "Evidex EvidenceOps")
    source = root / "CUSTOMER_PACKET" / "SOURCES" / "02_evidence_register.csv"
    source.write_text(source.read_text(encoding="utf-8") + "\nTAMPERED\n", encoding="utf-8")
    with pytest.raises(ProfessionalEvidenceProjectionError, match="hash drifted"):
        load_packet(root / "CUSTOMER_PACKET")


def test_examiner_directory_cannot_be_loaded_as_execution_packet(tmp_path: Path) -> None:
    _, root = _packet(tmp_path, "HOMS Exam")
    with pytest.raises(ProfessionalEvidenceProjectionError):
        load_packet(root / "EXAMINER")
