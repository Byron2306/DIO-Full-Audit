from __future__ import annotations

import json

from portfolio_runtime import ROOT


RUNNER = ROOT / "scripts" / "run_professional_evidence_portfolio.py"
GATE = ROOT / "products" / "professional_evidence_vesper_gate.py"
PREPARED = ROOT / "products" / "professional_evidence_prepared_executor.py"
ROUTES = ROOT / "config" / "professional_evidence_portfolio" / "v1" / "routes.json"


def test_portfolio_runner_uses_vesper_gate_not_direct_customer_executor() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "from products.professional_evidence_vesper_gate import execute_customer_case_via_vesper" in source
    assert "receipt = execute_customer_case_via_vesper(" in source
    assert "receipt = execute_customer_case(" not in source


def test_53_acceptance_requires_every_vesper_front_door_and_quarantined_bytes() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert 'ACCEPTANCE_TOKEN = "DIO_PROFESSIONAL_EVIDENCE_PORTFOLIO_53_VERIFIED"' in source
    assert "vesper_verified_count == 53" in source
    assert "quarantine_consumed_count == 53" in source
    assert "executor_rematerialization_count == 0" in source
    assert "all_vesper_verified" in source
    assert 'row.get("product_consumed_vesper_quarantined_bytes") is True' in source
    assert 'row.get("executor_rematerialized_packet") is False' in source
    assert '"vesper_web_chat_front_door_required": True' in source
    assert '"required_front_door": "vesper_web_chat"' in source
    assert '"whatsapp_required": False' in source
    assert '"telegram_required": False' in source
    assert "counts[PASS] == 53" in source
    assert "counts[FAIL] == 0" in source
    assert "counts[BLOCKED] == 0" in source


def test_vesper_gate_requires_chat_and_quarantine_before_product_execution() -> None:
    source = GATE.read_text(encoding="utf-8")
    prepare = source.index("def _prepare_vesper_front_door")
    binding = source.index("binding, case_root = _prepare_vesper_front_door")
    execution = source.index("product_receipt = execute_prepared_customer_case(")
    assert prepare < binding < execution
    assert 'binding.get("channel") != "web_chat"' in source
    assert 'binding.get("handoff_state") != "READY_FOR_PRODUCT_EXECUTION"' in source
    assert 'binding.get("resolved_incarnation") != incarnation' in source
    assert 'binding.get("whatsapp_used") is not False' in source
    assert 'binding.get("telegram_used") is not False' in source
    assert "_rehydrate_sources_from_quarantine(packet, chat_root)" in source


def test_product_executor_consumes_via_quarantine_without_second_materialisation() -> None:
    gate = GATE.read_text(encoding="utf-8")
    prepared = PREPARED.read_text(encoding="utf-8")
    assert "execute_prepared_customer_case(" in gate
    assert "execute_customer_case(" not in gate
    assert "from products.professional_evidence_corpus import materialize_customer_packet" not in prepared
    assert "from products.professional_evidence_enrichment import enrich_customer_packet" not in prepared
    assert "materialize_customer_packet(" not in prepared
    assert "enrich_customer_packet(" not in prepared
    assert 'prepared_by != "vesper_web_chat"' in prepared
    assert '"rematerialized_by_executor": False' in prepared
    assert "source.write_bytes(quarantine_path.read_bytes())" in gate
    assert '"rehydrated_into_product_packet": True' in gate
    assert '"product_consumed_vesper_quarantined_bytes": quarantine_consumed' in gate


def test_vesper_and_product_execution_bind_same_literal_packet() -> None:
    source = GATE.read_text(encoding="utf-8")
    assert "packet_fingerprint != str(binding.get(\"packet_fingerprint\") or \"\")" in source
    assert '"golden_fixture_used": False' in source
    assert '"examiner_data_used_during_execution": False' in source
    assert '"sequence": ["VESPER_WEB_CHAT_INTAKE", "VESPER_QUARANTINE_REHYDRATION", "PRODUCT_EXECUTION", "HUMAN_REVIEW_GATE"]' in source


def test_professional_routes_constitution_declares_53_canonical_products_and_vesper_front_door() -> None:
    routes = json.loads(ROUTES.read_text(encoding="utf-8"))
    policy = routes["policy"]
    assert len(routes["routes"]) == 53
    assert policy["customer_packet_must_be_literal"] is True
    assert policy["examiner_truth_must_be_withheld"] is True
    assert policy["halfway_fixture_counts_as_full_pipeline"] is False
    assert policy["required_front_door"] == "vesper_web_chat"
    assert policy["vesper_channel"] == "web_chat"
    assert policy["vesper_must_precede_product_execution"] is True
    assert policy["vesper_packet_fingerprint_must_match_product_packet"] is True
    assert policy["vesper_quarantine_must_feed_product_source_bytes"] is True
    assert policy["executor_rematerialization_after_vesper"] == "REFUSE"
    assert policy["whatsapp_required"] is False
    assert policy["telegram_required"] is False
    assert policy["missing_vesper_front_door"] == "REFUSE"
