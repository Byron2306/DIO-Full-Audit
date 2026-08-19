from __future__ import annotations

import base64
import json
from pathlib import Path

from products.professional_evidence_corpus import materialize_customer_packet
from products.professional_evidence_projection import load_packet
from products.vesper_web_chat import (
    bind_professional_customer_packet,
    create_session,
    load_session,
    post_message,
)


NOW = "2026-08-19T16:00:00+00:00"


def test_product_site_session_binds_exact_canonical_incarnation(tmp_path: Path) -> None:
    state_root = tmp_path / "sessions"
    public = create_session(
        {"surface": "product_site", "incarnation_hint": "AuditProof"},
        state_root=state_root,
        conversation_id="VWC-AUDITPROOF-0001",
        now=NOW,
    )
    assert public["channel"] == "web_chat"
    assert public["route"]["state"] == "RESOLVED"
    assert public["route"]["incarnation"] == "AuditProof"
    assert public["authority_created"] is False
    assert public["external_effects"] is False
    assert public["external_send"] == "REFUSE"
    assert public["external_release"] == "REFUSE"


def test_web_chat_quarantines_csv_and_keeps_source_untrusted(tmp_path: Path) -> None:
    state_root = tmp_path / "sessions"
    create_session(
        {"surface": "product_site", "incarnation_hint": "AuditProof"},
        state_root=state_root,
        conversation_id="VWC-AUDITPROOF-0002",
        now=NOW,
    )
    csv_body = b"control_id,status\nAC-01,late review\n"
    result = post_message(
        "VWC-AUDITPROOF-0002",
        {
            "message": "Prepare an access-control audit evidence-readiness pack from this source register.",
            "incarnation_hint": "AuditProof",
            "attachments": [
                {
                    "filename": "control_register.csv",
                    "mime_type": "text/csv",
                    "role": "customer_source",
                    "content_base64": base64.b64encode(csv_body).decode("ascii"),
                }
            ],
        },
        state_root=state_root,
        quarantine_output_root=tmp_path / "quarantine_root",
        now=NOW,
    )
    assert result["receipt"]["channel"] == "web_chat"
    assert result["receipt"]["handoff_state"] == "READY_FOR_PRODUCT_EXECUTION"
    assert result["receipt"]["whatsapp_used"] is False
    assert result["receipt"]["telegram_used"] is False
    session = load_session("VWC-AUDITPROOF-0002", state_root=state_root)
    assert session["attachments"][0]["filename"] == "control_register.csv"
    assert session["attachments"][0]["trust_state"] == "captured_untrusted"
    assert session["attachments"][0]["extraction_state"] == "EXTRACTED"
    assert session["external_effects"] is False


def test_professional_packet_binding_uses_web_chat_without_examiner_or_messaging_apps(tmp_path: Path) -> None:
    materialized = materialize_customer_packet("AuditProof", tmp_path / "corpus")
    packet = load_packet(Path(materialized["packet_dir"]))
    binding = bind_professional_customer_packet(
        packet,
        "AuditProof",
        output_dir=tmp_path / "vesper",
        now=NOW,
    )
    assert binding["channel"] == "web_chat"
    assert binding["surface"] == "product_site"
    assert binding["resolved_incarnation"] == "AuditProof"
    assert binding["handoff_state"] == "READY_FOR_PRODUCT_EXECUTION"
    assert binding["sequence"] == ["VESPER_WEB_CHAT_INTAKE", "PRODUCT_EXECUTION"]
    assert binding["packet_fingerprint"] == packet["packet_fingerprint"]
    assert binding["source_attachment_count"] > 0
    assert binding["examiner_data_used"] is False
    assert binding["golden_fixture_used"] is False
    assert binding["whatsapp_used"] is False
    assert binding["telegram_used"] is False
    assert binding["authority_created"] is False
    assert binding["external_effects"] is False
    assert binding["external_send"] == "REFUSE"
    assert binding["external_release"] == "REFUSE"
    assert (tmp_path / "vesper" / "VESPER_WEB_CHAT_BINDING.json").is_file()


def test_professional_binding_contains_only_customer_source_files_not_examiner_truth(tmp_path: Path) -> None:
    materialized = materialize_customer_packet("VendorProof", tmp_path / "corpus")
    packet = load_packet(Path(materialized["packet_dir"]))
    bind_professional_customer_packet(packet, "VendorProof", output_dir=tmp_path / "vesper", now=NOW)
    texts = []
    for path in (tmp_path / "vesper").rglob("*.json"):
        try:
            texts.append(json.dumps(json.loads(path.read_text(encoding="utf-8")), sort_keys=True))
        except json.JSONDecodeError:
            continue
    combined = "\n".join(texts)
    assert "withheld_from_execution" not in combined
    assert "EXPECTED_FACTS.json" not in combined
    assert "PROHIBITED_OUTCOMES.json" not in combined
