from __future__ import annotations

from pathlib import Path

from commerce.paypal_local import (
    LocalCommerceStore,
    completed_capture,
    reconcile_local_paypal_order,
    verify_capture,
    verify_provider_order,
)


class FakeClient:
    environment = "sandbox"

    def __init__(
        self,
        *,
        order_status: str = "APPROVED",
        capture_summary_status: str | None = None,
        capture_detail_status: str = "COMPLETED",
    ):
        self.order_status = order_status
        self.capture_summary_status = capture_summary_status
        self.capture_detail_status = capture_detail_status
        self.capture_calls = 0

    def get_order(self, provider_order_id):
        payments = {}
        if self.capture_summary_status is not None:
            payments = {
                "captures": [{
                    "id": "CAPTURE-1",
                    "status": self.capture_summary_status,
                    "amount": {
                        "currency_code": "USD",
                        "value": "49.00",
                    },
                }]
            }
        return {
            "id": provider_order_id,
            "status": self.order_status,
            "purchase_units": [{
                "invoice_id": "ORDER-1",
                "custom_id": "ORDER-1",
                "amount": {
                    "currency_code": "USD",
                    "value": "49.00",
                },
                "payments": payments,
            }],
        }

    def capture_order(self, provider_order_id):
        self.capture_calls += 1
        self.order_status = "COMPLETED"
        self.capture_summary_status = "COMPLETED"
        return self.get_order(provider_order_id)

    def get_capture(self, capture_id):
        assert capture_id == "CAPTURE-1"
        return {
            "id": capture_id,
            "status": self.capture_detail_status,
            "amount": {
                "currency_code": "USD",
                "value": "49.00",
            },
        }


def _store_with_order(tmp_path: Path) -> LocalCommerceStore:
    store = LocalCommerceStore(
        tmp_path / "orders",
        tmp_path / "receipts",
    )
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
    return store


def test_approved_provider_order_does_not_auto_capture(tmp_path: Path) -> None:
    store = _store_with_order(tmp_path)
    client = FakeClient(order_status="APPROVED")

    result = reconcile_local_paypal_order(
        store,
        client,
        "ORDER-1",
        capture_approved=False,
    )
    saved = store.load("ORDER-1")

    assert client.capture_calls == 0
    assert result["payment_state"] == "approved_awaiting_capture"
    assert saved["payment_state"] == "approved_awaiting_capture"
    assert result["external_funds_moved"] is False
    assert result["browser_return_authority"] is False
    assert result["cloudflare_used"] is False
    assert result["webhook_required"] is False
    assert saved["fulfilment_released"] is False


def test_explicit_capture_then_provider_truth_reconciles_to_paid(
    tmp_path: Path,
) -> None:
    store = _store_with_order(tmp_path)
    client = FakeClient(order_status="APPROVED")

    result = reconcile_local_paypal_order(
        store,
        client,
        "ORDER-1",
        capture_approved=True,
    )
    saved = store.load("ORDER-1")

    assert client.capture_calls == 1
    assert result["payment_state"] == "paid"
    assert saved["payment_state"] == "paid"
    assert saved["external_funds_moved"] is True
    assert saved["fulfilment_released"] is False
    assert len(saved["payment_receipt_sha256"]) == 64
    assert list((tmp_path / "receipts").glob("*.json"))


def test_existing_completed_capture_reconciles_without_capture_action(
    tmp_path: Path,
) -> None:
    store = _store_with_order(tmp_path)
    client = FakeClient(
        order_status="COMPLETED",
        capture_summary_status="COMPLETED",
        capture_detail_status="COMPLETED",
    )

    result = reconcile_local_paypal_order(
        store,
        client,
        "ORDER-1",
        capture_approved=False,
    )

    assert client.capture_calls == 0
    assert result["payment_state"] == "paid"
    assert result["external_funds_moved"] is True
    assert result["fulfilment_released"] is False


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
            "amount": {
                "currency_code": "USD",
                "value": "48.00",
            },
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
        "amount": {
            "currency_code": "USD",
            "value": "49.00",
        },
    }
    verify_capture(local, capture)

    wrong = {
        **capture,
        "amount": {
            "currency_code": "USD",
            "value": "50.00",
        },
    }
    try:
        verify_capture(local, wrong)
        assert False, "wrong capture amount must be rejected"
    except Exception as exc:
        assert "amount" in str(exc).lower()


def test_refund_poll_removes_paid_state(tmp_path: Path) -> None:
    store = _store_with_order(tmp_path)
    order = store.load("ORDER-1")
    order.update({
        "provider_capture_id": "CAPTURE-1",
        "payment_state": "paid",
        "external_funds_moved": True,
        "payment_receipt_sha256": "a" * 64,
    })
    store.save(order)

    client = FakeClient(
        order_status="COMPLETED",
        capture_summary_status="COMPLETED",
        capture_detail_status="REFUNDED",
    )
    result = reconcile_local_paypal_order(
        store,
        client,
        "ORDER-1",
        capture_approved=False,
    )
    saved = store.load("ORDER-1")

    assert result["payment_state"] == "refunded"
    assert saved["payment_state"] == "refunded"
    assert saved["external_funds_moved"] is False
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
