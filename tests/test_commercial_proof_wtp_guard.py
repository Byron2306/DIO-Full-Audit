from __future__ import annotations

from products import commercial_proof_v1_1 as proof


def _paid_edge_order(order_id: str = "ORDER-1") -> dict:
    return {
        "order_id": order_id,
        "state": "paid",
        "amount_minor": 100,
        "currency": "ZAR",
        "product_code": "SITE_STUDIO",
    }


def test_verified_self_payment_does_not_prove_wtp():
    transaction = {
        "mode": "real_payment",
        "order_id": "ORDER-1",
        "customer_id": "operator-self-test",
        "product_code": "SITE_STUDIO",
        "amount_minor": 100,
        "currency": "ZAR",
        "payment_required": True,
    }
    payment = proof.evaluate_payment(transaction, live_edge_order=_paid_edge_order())
    assert payment["verified_payment"] == proof.PAYMENT_PROVED
    assert payment["willingness_to_pay"] == proof.WTP_UNPROVED
    assert payment["wtp_corroboration"] == "INDEPENDENT_CUSTOMER_ACCEPTANCE_REQUIRED"


def test_independent_paid_customer_acceptance_promotes_wtp(monkeypatch):
    monkeypatch.setattr(
        proof.base,
        "verify_professional_proof",
        lambda bundle, root=proof.ROOT: {"passed": True, "reason": "test"},
    )
    monkeypatch.setattr(
        proof.base,
        "evaluate_market_evidence",
        lambda market: {"passed": True, "state": proof.MARKET_PROVED},
    )

    bundle = {
        "schema": "dio.commercial_proof_bundle.v1",
        "bundle_id": "CPG-TEST-INDEPENDENT-1",
        "product_id": "site_studio",
        "professional_proof": {},
        "market": {},
        "transaction": {
            "mode": "real_payment",
            "order_id": "ORDER-1",
            "customer_id": "CUSTOMER-1",
            "product_code": "SITE_STUDIO",
            "amount_minor": 100,
            "currency": "ZAR",
            "payment_required": True,
        },
        "acceptance": {
            "state": "accepted",
            "customer_id": "CUSTOMER-1",
            "independent_customer": True,
            "customer_originated": True,
            "artifact_sha256": "sha256:" + "a" * 64,
            "source_kind": "outlook_customer_reply",
            "source_message_id": "MSG-1",
            "refund_state": "none",
            "dispute_state": "none",
        },
        "prior_validated_engagements": [],
    }

    receipt = proof.evaluate_commercial_proof_bundle(bundle, live_edge_order=_paid_edge_order())
    assert receipt["payment"]["verified_payment"] == proof.PAYMENT_PROVED
    assert receipt["payment"]["willingness_to_pay"] == proof.WTP_PROVED
    assert receipt["payment"]["wtp_corroboration"] == "INDEPENDENT_CUSTOMER_PAYMENT_AND_ACCEPTANCE"
    assert receipt["customer_acceptance"]["commercial_customer_acceptance"] == proof.ACCEPTANCE_PROVED
    assert receipt["commercial_validation"] == proof.COMMERCIAL_PROVED
    assert receipt["acceptance_token"] == proof.VALIDATED_TOKEN


def test_non_independent_acceptance_cannot_promote_wtp(monkeypatch):
    monkeypatch.setattr(
        proof.base,
        "verify_professional_proof",
        lambda bundle, root=proof.ROOT: {"passed": True, "reason": "test"},
    )
    monkeypatch.setattr(
        proof.base,
        "evaluate_market_evidence",
        lambda market: {"passed": True, "state": proof.MARKET_PROVED},
    )

    bundle = {
        "schema": "dio.commercial_proof_bundle.v1",
        "bundle_id": "CPG-TEST-SELF-1",
        "product_id": "site_studio",
        "professional_proof": {},
        "market": {},
        "transaction": {
            "mode": "real_payment",
            "order_id": "ORDER-1",
            "customer_id": "operator-self-test",
            "product_code": "SITE_STUDIO",
            "amount_minor": 100,
            "currency": "ZAR",
            "payment_required": True,
        },
        "acceptance": {
            "state": "accepted",
            "customer_id": "operator-self-test",
            "independent_customer": False,
            "customer_originated": True,
            "artifact_sha256": "sha256:" + "b" * 64,
            "source_kind": "outlook_customer_reply",
            "source_message_id": "MSG-SELF",
            "refund_state": "none",
            "dispute_state": "none",
        },
        "prior_validated_engagements": [],
    }

    receipt = proof.evaluate_commercial_proof_bundle(bundle, live_edge_order=_paid_edge_order())
    assert receipt["payment"]["verified_payment"] == proof.PAYMENT_PROVED
    assert receipt["payment"]["willingness_to_pay"] == proof.WTP_UNPROVED
    assert receipt["customer_acceptance"]["commercial_customer_acceptance"] == proof.ACCEPTANCE_UNPROVED
    assert receipt["commercial_validation"] == proof.COMMERCIAL_UNPROVED
