#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from products.registry import load_portfolio  # noqa: E402
from scripts.build_phase3_campaigns import write_index, write_layer  # noqa: E402


def marketable_products() -> list[dict]:
    return [
        product
        for product in load_portfolio()["products"]
        if product.get("campaign_enabled") is True and product.get("customer_facing") is True
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build governed campaign/storyboard packs for the new DIO product portfolio.")
    parser.add_argument("--out", default=str(ROOT / "campaigns" / "product_portfolio_wave1"))
    args = parser.parse_args()

    out_root = Path(args.out).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    products = marketable_products()
    created = [write_layer(product, out_root) for product in products]
    write_index(products, out_root)

    print(f"Built {len(created)} governed portfolio campaign pack(s).")
    print("DIO CapitalRoom is intentionally excluded because it is internal-only.")
    for path in created:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
