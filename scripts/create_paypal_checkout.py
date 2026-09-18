#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commerce.paypal_local import (
    LocalCommerceStore,
    PayPalLocalClient,
    PayPalLocalError,
)


DEFAULT_ORDER_DIR = ROOT / "state" / "commerce" / "orders"
DEFAULT_RECEIPT_DIR = ROOT / "state" / "commerce" / "payment_events"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create or retrieve a PayPal checkout directly from local DIO."
    )
    parser.add_argument("order_id")
    parser.add_argument("--order-dir", type=Path, default=DEFAULT_ORDER_DIR)
    parser.add_argument("--receipt-dir", type=Path, default=DEFAULT_RECEIPT_DIR)
    parser.add_argument(
        "--return-url",
        default=os.getenv("DIO_PAYPAL_RETURN_URL", ""),
    )
    parser.add_argument(
        "--cancel-url",
        default=os.getenv("DIO_PAYPAL_CANCEL_URL", ""),
    )
    args = parser.parse_args()

    if not args.return_url.startswith("https://"):
        raise PayPalLocalError(
            "Set DIO_PAYPAL_RETURN_URL or --return-url to an HTTPS informational page."
        )
    if not args.cancel_url.startswith("https://"):
        raise PayPalLocalError(
            "Set DIO_PAYPAL_CANCEL_URL or --cancel-url to an HTTPS informational page."
        )

    store = LocalCommerceStore(
        args.order_dir.resolve(),
        args.receipt_dir.resolve(),
    )
    order = store.load(args.order_id)
    if order.get("provider_order_id") and order.get("approval_url"):
        result = {
            "schema": "dio.local_paypal_checkout.v1",
            "order_id": order["order_id"],
            "provider_order_id": order["provider_order_id"],
            "approval_url": order["approval_url"],
            "provider_status": order.get("provider_status"),
            "cloudflare_used": False,
        }
    else:
        client = PayPalLocalClient.from_env()
        provider = client.create_order(
            order_id=order["order_id"],
            amount_minor=int(order["amount_minor"]),
            currency=str(order["currency"]),
            return_url=args.return_url,
            cancel_url=args.cancel_url,
        )
        order.update(
            {
                "payment_state": "awaiting_payment",
                "provider_order_id": provider["provider_order_id"],
                "provider_status": provider["provider_status"],
                "approval_url": provider["approval_url"],
                "provider_environment": client.environment,
                "cloudflare_used": False,
            }
        )
        store.save(order)
        result = {
            "schema": "dio.local_paypal_checkout.v1",
            "order_id": order["order_id"],
            **provider,
            "cloudflare_used": False,
        }

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, PayPalLocalError) as error:
        print(f"Local PayPal checkout creation failed: {error}", file=sys.stderr)
        raise SystemExit(2)
