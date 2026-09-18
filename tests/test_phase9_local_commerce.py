from __future__ import annotations

from pathlib import Path

from commerce.paypal_local import (
    LocalCommerceStore,
    completed_capture,
    verify_capture,
    verify_provider_order,
)
from scripts.reconcile_paypal_local import reconcile_order


class FakeClient:
    environment = "sandbox"

    def __init__(self):
        self.captured = False
        self.capture_status = "COMPLETED"

    def get_order(self, provider_order_id):
        status = "COMPLETED" if self.captured else "APPROVED"
        payments = {
            "captures": [{
                "id": "CAPTURE-1",
                "status": "COMPLETED",
                "amount": {"currency_code": "USD", "value": "49.00"},
            }]
        } if self.captured else {}
        return {
            "id": provider_order_id,
            "status": status,
            "purchase_units": [{
                "invoice_id": "ORDER-1",
                "custom_id": "ORDER-1",
                "amount": {"currency_code": "USD", "value": "49.00"},
                "payments": payments,
            }],
        }

    def capture_order(self, provider_order_id):
        self.captured = True
        return self.get_order(provider_order_id)

    def get_capture(self, capture_id):
        return {
            "id": capture_id,
            "status": self.capture_status,
            "amount": {"currency_code": "USD", "value": "49.00"},
        }


def test_local_order_store_and_provider_truth_reconcile_to_paid(tmp_path: Path) -> None:
    store = LocalCommerceStore(tmp_path / "orders", tmp_path / "receipts")
    order = store.register(
        order_id="ORDER-1",
        product_code="SOPHIA",
        amount_minor=4900,
        currency="USD",
        lineage={"job_id": "JOB-1"},
    )
    order.update({
        "provider_order_id": "PAYPAL-1",
        "approval_url": "https://paypal.example/approve",
        "payment_state": "awaiting_payment",
    })
    store.save(order)

    result = reconcile_order(
        FakeClient(),
        store,
        store.load("ORDER-1"),
        tmp_path / "events.jsonl",
    )
    saved = store.load("ORDER-1")

    assert result["state"] == "paid"
    assert saved["payment_state"] == "paid"
    assert saved["external_funds_moved"] is True
    assert saved["revenue_recognised"] is True
    assert saved["fulfilment_released"] is False
    assert len(saved["payment_receipt_sha256"]) == 64
    assert list((tmp_path / "receipts").glob("*.json"))


def test_paypal_amount_or_currency_mismatch_fails_closed(tmp_path: Path) -> None:
    store = LocalCommerceStore(tmp_path / "orders", tmp_path / "receipts")
    local = store.register(
        order_id="ORDER-1",
        product_code="SOPHIA",
        amount_minor=4900,
        currency="USD",
    )
    provider = {
        "id": "PAYPAL-1",
        "status": "COMPLETED",
        "purchase_units": [{
            "invoice_id": "ORDER-1",
            "custom_id": "ORDER-1",
            "amount": {"currency_code": "USD", "value": "48.00"},
        }],
    }
    try:
        verify_provider_order(local, provider)
        assert False, "provider amount mismatch must be rejected"
    except Exception as exc:
        assert "amount" in str(exc).lower()


def test_completed_capture_requires_exact_local_amount() -> None:
    local = {
        "order_id": "ORDER-1",
        "amount_minor": 4900,
        "currency": "USD",
    }
    capture = {
        "id": "CAPTURE-1",
        "status": "COMPLETED",
        "amount": {"currency_code": "USD", "value": "49.00"},
    }
    verify_capture(local, capture)

    wrong = {
        **capture,
        "amount": {"currency_code": "USD", "value": "50.00"},
    }
    try:
        verify_capture(local, wrong)
        assert False, "wrong capture amount must be rejected"
    except Exception as exc:
        assert "amount" in str(exc).lower()


def test_refund_poll_removes_paid_state(tmp_path: Path) -> None:
    store = LocalCommerceStore(tmp_path / "orders", tmp_path / "receipts")
    order = store.register(
        order_id="ORDER-1",
        product_code="SOPHIA",
        amount_minor=4900,
        currency="USD",
    )
    order.update({
        "provider_order_id": "PAYPAL-1",
        "provider_capture_id": "CAPTURE-1",
        "payment_state": "paid",
        "external_funds_moved": True,
        "revenue_recognised": True,
    })
    store.save(order)

    client = FakeClient()
    client.captured = True
    client.capture_status = "REFUNDED"
    result = reconcile_order(
        client,
        store,
        store.load("ORDER-1"),
        tmp_path / "events.jsonl",
    )
    saved = store.load("ORDER-1")

    assert result["state"] == "refunded"
    assert saved["payment_state"] == "refunded"
    assert saved["external_funds_moved"] is False
    assert saved["revenue_recognised"] is False
    assert saved["fulfilment_released"] is False


def test_completed_capture_helper_does_not_accept_noncompleted_capture() -> None:
    provider = {
        "purchase_units": [{
            "payments": {
                "captures": [
                    {"id": "C1", "status": "PENDING"},
                    {"id": "C2", "status": "DENIED"},
                ]
            }
        }]
    }
    assert completed_capture(provider) is None
