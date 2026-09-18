#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commerce.paypal_local import (
    LocalCommerceStore,
    PayPalLocalClient,
    PayPalLocalError,
    completed_capture,
    verify_capture,
    verify_provider_order,
)
from scripts.manage_mail_intent import DEFAULT_EVENT_LOG, emit_event


DEFAULT_ORDER_DIR = ROOT / "state" / "commerce" / "orders"
DEFAULT_RECEIPT_DIR = ROOT / "state" / "commerce" / "payment_events"


def reconcile_order(
    client: PayPalLocalClient,
    store: LocalCommerceStore,
    order: dict[str, Any],
    event_log: Path,
) -> dict[str, Any]:
    provider_order_id = str(order.get("provider_order_id") or "")
    if not provider_order_id:
        return {
            "order_id": order["order_id"],
            "state": order["payment_state"],
            "action": "no_provider_order",
        }

    provider = client.get_order(provider_order_id)
    verify_provider_order(order, provider)
    provider_status = str(provider.get("status") or "").upper()
    order["provider_status"] = provider_status

    if provider_status == "APPROVED" and order.get("payment_state") != "paid":
        provider = client.capture_order(provider_order_id)
        verify_provider_order(order, provider)
        provider_status = str(provider.get("status") or "").upper()
        order["provider_status"] = provider_status

    capture = completed_capture(provider)
    if capture is not None:
        capture_id = str(capture.get("id") or "")
        if not capture_id:
            raise PayPalLocalError("completed PayPal capture omitted capture ID")
        detailed = client.get_capture(capture_id)
        status = str(detailed.get("status") or "").upper()
        order["provider_capture_id"] = capture_id
        order["provider_capture_status"] = status

        if status == "COMPLETED":
            verify_capture(order, detailed)
            was_paid = order.get("payment_state") == "paid"
            order["payment_state"] = "paid"
            order["external_funds_moved"] = True
            order["revenue_recognised"] = True
            receipt = store.receipt(
                order,
                provider_order=provider,
                capture=detailed,
            )
            order["payment_receipt_sha256"] = receipt["receipt_sha256"]
            store.save(order)
            if not was_paid:
                emit_event(
                    event_log,
                    "payment.succeeded",
                    "info",
                    "commerce_order",
                    str(order["order_id"]),
                    {
                        "provider": "paypal",
                        "provider_order_id": provider_order_id,
                        "provider_capture_id": capture_id,
                        "amount_minor": order["amount_minor"],
                        "currency": order["currency"],
                        "fulfilment_released": False,
                        "cloudflare_used": False,
                    },
                )
            return {
                "order_id": order["order_id"],
                "state": "paid",
                "action": "verified_completed_capture",
                "receipt_sha256": receipt["receipt_sha256"],
            }

    capture_id = str(order.get("provider_capture_id") or "")
    if capture_id:
        detailed = client.get_capture(capture_id)
        capture_status = str(detailed.get("status") or "").upper()
        order["provider_capture_status"] = capture_status
        if capture_status in {"REFUNDED"}:
            order["payment_state"] = "refunded"
            order["external_funds_moved"] = False
            order["revenue_recognised"] = False
        elif capture_status in {"PARTIALLY_REFUNDED", "DENIED"}:
            order["payment_state"] = "held"
            order["external_funds_moved"] = False
            order["revenue_recognised"] = False

    store.save(order)
    return {
        "order_id": order["order_id"],
        "state": order["payment_state"],
        "provider_status": provider_status,
        "provider_capture_status": order.get("provider_capture_status"),
        "action": "observed",
    }


def monitored_orders(store: LocalCommerceStore) -> list[dict[str, Any]]:
    if not store.order_dir.is_dir():
        return []
    rows = []
    for path in sorted(store.order_dir.glob("*.json")):
        try:
            order = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if order.get("provider") == "paypal" and order.get("provider_order_id"):
            rows.append(order)
    return rows


def reconcile_once(
    client: PayPalLocalClient,
    store: LocalCommerceStore,
    event_log: Path,
) -> dict[str, Any]:
    results = []
    for order in monitored_orders(store):
        try:
            results.append(
                reconcile_order(client, store, order, event_log)
            )
        except PayPalLocalError as exc:
            order["payment_state"] = "held"
            order["last_payment_error"] = str(exc)[:500]
            order["external_funds_moved"] = False
            order["revenue_recognised"] = False
            store.save(order)
            results.append(
                {
                    "order_id": order["order_id"],
                    "state": "held",
                    "action": "provider_verification_failed",
                    "error": str(exc),
                }
            )
    return {
        "schema": "dio.phase9.paypal_poll_receipt.v1",
        "orders_checked": len(results),
        "results": results,
        "transport_mode": "outbound_provider_poll",
        "cloudflare_used": False,
        "browser_return_grants_payment_state": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reconcile PayPal state locally through outbound provider API polling."
    )
    parser.add_argument("--order-dir", type=Path, default=DEFAULT_ORDER_DIR)
    parser.add_argument("--receipt-dir", type=Path, default=DEFAULT_RECEIPT_DIR)
    parser.add_argument("--event-log", type=Path, default=DEFAULT_EVENT_LOG)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=30.0)
    args = parser.parse_args()

    client = PayPalLocalClient.from_env()
    store = LocalCommerceStore(
        args.order_dir.resolve(),
        args.receipt_dir.resolve(),
    )
    while True:
        result = reconcile_once(
            client,
            store,
            args.event_log.resolve(),
        )
        print(json.dumps(result, indent=2), flush=True)
        if not args.watch:
            return 0
        time.sleep(max(args.interval, 15.0))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, PayPalLocalError) as error:
        print(f"Local PayPal reconciliation failed: {error}", file=sys.stderr)
        raise SystemExit(2)
