from __future__ import annotations

import copy
import json
from pathlib import Path

from products.commercial_proof import (
    ACCEPTANCE_PROVED,
    COMMERCIAL_PROVED,
    MARKET_PROVED,
    PAYMENT_PROVED,
    REPEATABLE_PROVED,
    VALIDATED_TOKEN,
    WTP_PROVED,
    ZERO_PILOT_TOKEN,
    evaluate_commercial_proof_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
ZERO_BUNDLE = ROOT / "config" / "commercial_proof" / "zero_value_professor_pilot.json"


def _load_zero() -> dict:
    return json.loads(ZERO_BUNDLE.read_text(encoding="utf-8"))


def _real_market() -> dict:
    return {
        "as_of": "2026-08-18",
        "buyer_segment": "South African SME owners buying evidence-backed professional services",
        "buyer_problem": "They need credible professional outputs without hiring a full specialist team for every task.",
        "methodology": (
            "Compare current source-bound competitor offers, observable price points and independent demand signals; "
            "retain source dates and URLs; refuse demo or simulated observations."
        ),
        "max_source_age_days": 180,
        "sources": [
            {
                "source_id": "SRC-1",
                "url": "https://competitor-one.example/services",
                "observed_at": "2026-08-10",
                "evidence_origin": "real_research",
            },
            {
                "source_id": "SRC-2",
                "url": "https://competitor-two.example/pricing",
                "observed_at": "2026-08-11",
                "evidence_origin": "real_research",
            },
            {
                "source_id": "SRC-3",
                "url": "https://market-signal.example/report",
                "observed_at": "2026-08-12",
                "evidence_origin": "real_research",
            },
        ],
        "competitor_offers": [
            {"name": "Competitor One", "source_id": "SRC-1", "offer": "Professional report"},
            {"name": "Competitor Two", "source_id": "SRC-2", "offer": "Advisory package"},
        ],
        "pricing_observations": [
            {"source_id": "SRC-1", "amount_minor": 390000, "currency": "ZAR"},
            {"source_id": "SRC-2", "amount_minor": 690000, "currency": "ZAR"},
        ],
        "demand_signals": [
            {"source_id": "SRC-1", "signal": "active commercial offer"},
            {"source_id": "SRC-3", "signal": "documented buyer demand"},
        ],
    }


def _real_bundle() -> dict:
    bundle = _load_zero()
    bundle["bundle_id"] = "CPG-REAL-001"
    bundle["product_id"] = "site_studio"
    bundle["market"] = _real_market()
    bundle["transaction"] = {
        "mode": "real_payment",
        "order_id": "ORDER-REAL-001",
        "customer_id": "CUSTOMER-001",
        "product_code": "SITE_STUDIO",
        "amount_minor": 100,
        "currency": "ZAR",
        "payment_required": True,
    }
    bundle["acceptance"] = {
        "state": "accepted",
        "customer_id": "CUSTOMER-001",
        "independent_customer": True,
        "customer_originated": True,
        "artifact_sha256": "sha256:" + "a" * 64,
        "source_kind": "outlook_customer_reply",
        "source_message_id": "MSG-001",
        "refund_state": "none",
        "dispute_state": "none",
    }
    return bundle


def _paid_edge_snapshot() -> dict:
    return {
        "schema": "dio.commerce_order.v1",
        "order_id": "ORDER-REAL-001",
        "product_code": "SITE_STUDIO",
        "amount_minor": 100,
        "currency": "ZAR",
        "state": "paid",
        "metadata": {"customer_id": "CUSTOMER-001"},
    }


def test_zero_value_professor_pilot_never_becomes_payment_or_wtp_proof():
    receipt = evaluate_commercial_proof_bundle(_load_zero(), root=ROOT)
    assert receipt["acceptance_token"] == ZERO_PILOT_TOKEN
    assert receipt["payment"]["payment_flow_executed"] is True
    assert receipt["payment"]["verified_payment"] == "NOT_APPLICABLE_ZERO_VALUE_PILOT"
    assert receipt["payment"]["willingness_to_pay"] == "WILLINGNESS_TO_PAY_UNPROVED"
    assert receipt["payment"]["revenue_minor"] == 0
    assert receipt["commercial_validation"] != COMMERCIAL_PROVED
    assert receipt["authority_created"] is False
    assert receipt["external_effects"] is False


def test_real_payment_refuses_claim_without_live_authenticated_edge_order():
    receipt = evaluate_commercial_proof_bundle(_real_bundle(), root=ROOT)
    assert receipt["market_viability"]["state"] == MARKET_PROVED
    assert receipt["payment"]["verified_payment"] != PAYMENT_PROVED
    assert receipt["payment"]["reason"] == "live_dio_edge_order_required"
    assert receipt["commercial_validation"] != COMMERCIAL_PROVED


def test_real_paid_order_plus_market_and_customer_acceptance_proves_commercial_validation():
    bundle = _real_bundle()
    receipt = evaluate_commercial_proof_bundle(bundle, root=ROOT, live_edge_order=_paid_edge_snapshot())
    assert receipt["professional_quality"]["passed"] is True
    assert receipt["market_viability"]["state"] == MARKET_PROVED
    assert receipt["payment"]["verified_payment"] == PAYMENT_PROVED
    assert receipt["payment"]["willingness_to_pay"] == WTP_PROVED
    assert receipt["customer_acceptance"]["commercial_customer_acceptance"] == ACCEPTANCE_PROVED
    assert receipt["commercial_validation"] == COMMERCIAL_PROVED
    assert receipt["acceptance_token"] == VALIDATED_TOKEN
    assert receipt["repeatable_commercial_proof"]["state"] != REPEATABLE_PROVED


def test_repeatable_commercial_proof_requires_three_independent_validated_engagements():
    bundle = _real_bundle()
    bundle["prior_validated_engagements"] = [
        {
            "order_id": "ORDER-PRIOR-001",
            "customer_id": "CUSTOMER-PRIOR-001",
            "independent_customer": True,
            "commercial_validation": COMMERCIAL_PROVED,
            "verified_payment": PAYMENT_PROVED,
            "customer_acceptance": ACCEPTANCE_PROVED,
            "receipt_sha256": "sha256:" + "b" * 64,
        },
        {
            "order_id": "ORDER-PRIOR-002",
            "customer_id": "CUSTOMER-PRIOR-002",
            "independent_customer": True,
            "commercial_validation": COMMERCIAL_PROVED,
            "verified_payment": PAYMENT_PROVED,
            "customer_acceptance": ACCEPTANCE_PROVED,
            "receipt_sha256": "sha256:" + "c" * 64,
        },
    ]
    receipt = evaluate_commercial_proof_bundle(bundle, root=ROOT, live_edge_order=_paid_edge_snapshot())
    assert receipt["commercial_validation"] == COMMERCIAL_PROVED
    assert receipt["repeatable_commercial_proof"]["state"] == REPEATABLE_PROVED
    assert receipt["repeatable_commercial_proof"]["validated_engagement_count"] == 3
    assert receipt["repeatable_commercial_proof"]["independent_customer_count"] == 3


def test_market_research_rejects_demo_or_simulated_sources():
    bundle = _real_bundle()
    bundle["market"]["sources"][0]["evidence_origin"] = "simulation"
    receipt = evaluate_commercial_proof_bundle(bundle, root=ROOT, live_edge_order=_paid_edge_snapshot())
    assert receipt["market_viability"]["state"] != MARKET_PROVED
    assert receipt["market_viability"]["checks"]["non_demo_sources_only"] is False
    assert receipt["commercial_validation"] != COMMERCIAL_PROVED
