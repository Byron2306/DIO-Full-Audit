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
    parser = argparse.ArgumentParser(description="Create or retrieve a secure PayPal checkout for a registered DIO order.")
    parser.add_argument("order_id")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config = read_config(args.config.resolve())
    token = Path(config["edge_token_path"]).expanduser().read_text(encoding="utf-8").strip()
    result = edge_request(
        str(config["base_url"]).rstrip("/")
        + f"/api/dio/orders/{args.order_id}/checkout/paypal",
        token,
        method="POST",
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EdgeError, OSError) as error:
        print(f"PayPal checkout creation failed: {error}", file=sys.stderr)
        raise SystemExit(2)
