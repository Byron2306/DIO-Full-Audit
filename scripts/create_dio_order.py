#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from commerce.paypal_local import LocalCommerceStore


DEFAULT_ORDER_DIR = ROOT / "state" / "commerce" / "orders"
DEFAULT_RECEIPT_DIR = ROOT / "state" / "commerce" / "payment_events"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Register a local DIO order before issuing its PayPal payment link."
    )
    parser.add_argument("order_id")
    parser.add_argument("product_code")
    parser.add_argument("amount_minor", type=int)
    parser.add_argument("--currency", default="USD")
    parser.add_argument("--job-id", default="")
    parser.add_argument("--order-dir", type=Path, default=DEFAULT_ORDER_DIR)
    parser.add_argument("--receipt-dir", type=Path, default=DEFAULT_RECEIPT_DIR)
    args = parser.parse_args()

    store = LocalCommerceStore(
        args.order_dir.resolve(),
        args.receipt_dir.resolve(),
    )
    order = store.register(
        order_id=args.order_id,
        product_code=args.product_code,
        amount_minor=args.amount_minor,
        currency=args.currency,
        lineage={"job_id": args.job_id} if args.job_id else {},
    )
    print(json.dumps(order, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"DIO local order creation failed: {error}", file=sys.stderr)
        raise SystemExit(2)
