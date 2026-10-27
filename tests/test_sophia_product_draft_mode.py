import json
from pathlib import Path

import pytest

from products.professional_evidence_corpus import materialize_customer_packet
from products.professional_evidence_enrichment import enrich_customer_packet
from products.professional_evidence_projection import load_packet


def test_product_prepares_explicit_held_diagnostic_without_promoting_constitutional_approval(tmp_path, monkeypatch):
    from products.professional_evidence_execution import _run_sophia
    import adapters.sophia.review_pipeline as adapter

    materialize_customer_packet("Sophia Review", tmp_path)
    packet_dir = next(tmp_path.glob("*/CUSTOMER_PACKET"))
    enrich_customer_packet("Sophia Review", packet_dir)
    packet = load_packet(packet_dir)

    def native(request, request_path, output, base_url, root):
        assert request["review_mode"] == "held_diagnostic_draft"
        output.mkdir(parents=True)
        (output / "SOPHIA_REVIEW_RECEIPT.json").write_text(json.dumps({"status":"needs_human_review","preparation_state":"engineering_draft_prepared","constitutional_release_authorized":False,"delivery_released":False,"metrics":{"diagnostic_source_checks_passed":True}}))
        (output / "REVIEWER_COMMENTARY.json").write_text(json.dumps({"provider":request["reasoned_provider"],"model":request["reasoned_model"],"remote_processing":False,"status":"held_diagnostic_draft","diagnostic_validation":{"passed":True},"validation":{"passed":False},"constitutional_release_authorized":False,"delivery_released":False}))
        return output

    monkeypatch.setattr(adapter, "run_review", native)
    result = _run_sophia(packet, tmp_path / "execution", incarnation="Sophia Review")
    assert result["terminal_artifact_kind"] == "held_diagnostic_academic_review_pack"
    assert result["constitutional_approval_verified"] is False
    assert result["receipt"]["delivery_released"] is False
