from __future__ import annotations

import json

from portfolio_runtime import ROOT


RUNNER = ROOT / "scripts" / "run_professional_evidence_portfolio.py"
GATE = ROOT / "products" / "professional_evidence_vesper_gate.py"
ROUTES = ROOT / "config" / "professional_evidence_portfolio" / "v1" / "routes.json"


def test_portfolio_runner_uses_vesper_gate_not_direct_customer_executor() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "from products.professional_evidence_vesper_gate import execute_customer_case_via_vesper" in source
    assert "receipt = execute_customer_case_via_vesper(" in source
    assert "receipt = execute_customer_case(" not in source


def test_53_acceptance_requires_every_vesper_front_door() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert 'ACCEPTANCE_TOKEN = "DIO_PROFESSIONAL_EVIDENCE_PORTFOLIO_53_VERIFIED"' in source
    assert "vesper_verified_count == 53" in source
    assert "all_vesper_verified" in source
    assert '"vesper_web_chat_front_door_required": True' in source
    assert '"required_front_door": "vesper_web_chat"' in source
    assert '"whatsapp_required": False' in source
    assert '"telegram_required": False' in source
    assert "counts[PASS] == 53" in source
    assert "counts[FAIL] == 0" in source
    assert "counts[BLOCKED] == 0" in source


def test_vesper_gate_requires_chat_before_product_execution() -> None:
    source = GATE.read_text(encoding="utf-8")
    preflight = source.index("def _prepare_vesper_preflight")
    binding = source.index("binding, chat_root = _prepare_vesper_preflight")
    execution = source.index("product_receipt = execute_customer_case(")
    assert preflight < binding < execution
    assert 'binding.get("channel") != "web_chat"' in source
    assert 'binding.get("handoff_state") != "READY_FOR_PRODUCT_EXECUTION"' in source
    assert 'binding.get("resolved_incarnation") != incarnation' in source
    assert 'binding.get("whatsapp_used") is not False' in source
    assert 'binding.get("telegram_used") is not False' in source


def test_vesper_and_product_execution_bind_same_literal_packet() -> None:
    source = GATE.read_text(encoding="utf-8")
    assert "product_packet_fingerprint != str(binding.get(\"packet_fingerprint\") or \"\")" in source
    assert '"golden_fixture_used": False' in source
    assert '"examiner_data_used_during_execution": False' in source
    assert '"sequence": ["VESPER_WEB_CHAT_INTAKE", "PRODUCT_EXECUTION", "HUMAN_REVIEW_GATE"]' in source


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
    assert policy["whatsapp_required"] is False
    assert policy["telegram_required"] is False
    assert policy["missing_vesper_front_door"] == "REFUSE"
