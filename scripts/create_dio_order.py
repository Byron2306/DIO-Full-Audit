#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.sync_dio_edge_events import DEFAULT_CONFIG, EdgeError, edge_request, read_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Register a DIO order before issuing its payment link.")
    parser.add_argument("order_id")
    parser.add_argument("product_code")
    parser.add_argument("amount_minor", type=int, help="Exact amount in cents, for example 95000 for R950.00")
    parser.add_argument("--currency", default="ZAR")
    parser.add_argument("--job-id", default="")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config = read_config(args.config.resolve())
    token = Path(config["edge_token_path"]).expanduser().read_text(encoding="utf-8").strip()
    result = edge_request(
        str(config["base_url"]).rstrip("/") + "/api/dio/orders",
        token,
        method="POST",
        payload={
            "order_id": args.order_id,
            "product_code": args.product_code,
            "amount_minor": args.amount_minor,
            "currency": args.currency,
            "metadata": {"job_id": args.job_id} if args.job_id else {},
        },
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EdgeError, OSError) as error:
        print(f"DIO order creation failed: {error}", file=sys.stderr)
        raise SystemExit(2)
