#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commerce.paypal_local import (  # noqa: E402
    LocalCommerceStore,
    PayPalLocalClient,
    PayPalLocalError,
    reconcile_local_paypal_order,
)


DEFAULT_ORDER_DIR = ROOT / "state" / "commerce" / "orders"
DEFAULT_RECEIPT_DIR = ROOT / "state" / "commerce" / "payment_events"


def reconcile_pending(
    *,
    store: LocalCommerceStore,
    client: PayPalLocalClient,
    capture_approved: bool,
) -> dict:
    results = []
    errors = []
    for order in store.pending():
        order_id = str(order.get("order_id") or "")
        if not order_id:
            continue
        try:
            results.append(
                reconcile_local_paypal_order(
                    store,
                    client,
                    order_id,
                    capture_approved=capture_approved,
                )
            )
        except Exception as exc:
            errors.append(
                {
                    "order_id": order_id,
                    "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                }
            )
    return {
        "schema": "dio.local_paypal_reconciliation_batch.v1",
        "checked": len(results) + len(errors),
        "results": results,
        "errors": errors,
        "capture_approved": capture_approved,
        "transport_mode": "outbound_provider_poll",
        "cloudflare_used": False,
        "webhook_required": False,
        "browser_return_authority": False,
        "authority_created": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile local DIO PayPal orders by outbound provider polling. "
            "Browser return URLs never create payment truth."
        )
    )
    parser.add_argument("order_id", nargs="?")
    parser.add_argument("--order-dir", type=Path, default=DEFAULT_ORDER_DIR)
    parser.add_argument("--receipt-dir", type=Path, default=DEFAULT_RECEIPT_DIR)
    parser.add_argument(
        "--capture-approved",
        action="store_true",
        help=(
            "Permit capture of PayPal orders already in APPROVED state. "
            "Without this flag reconciliation is read-only."
        ),
    )
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=15.0)
    args = parser.parse_args()

    store = LocalCommerceStore(
        args.order_dir.resolve(),
        args.receipt_dir.resolve(),
    )
    client = PayPalLocalClient.from_env()

    while True:
        if args.order_id:
            result = reconcile_local_paypal_order(
                store,
                client,
                args.order_id,
                capture_approved=args.capture_approved,
            )
        else:
            result = reconcile_pending(
                store=store,
                client=client,
                capture_approved=args.capture_approved,
            )

        print(json.dumps(result, indent=2), flush=True)
        if not args.watch:
            return 0
        time.sleep(max(args.interval, 5.0))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, PayPalLocalError) as exc:
        print(f"Local PayPal reconciliation failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
