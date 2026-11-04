from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.canon_extension_native_product_grade import (
    NATIVE_BATCH_BASELINE_TOKEN,
    NATIVE_BATCH_VERIFIED_TOKEN,
    run_native_product_grade_batch,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run native dual-bound ProductGrade across the eleven receipt-bound DIO canon extensions. "
            "The run measures controlled buyer-artifact execution only; commercial validation and external authority remain unproved."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="DIO root containing the current canon surfaces and historical lineage anchor.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output root for native canon-extension ProductGrade receipts.",
    )
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="Return non-zero unless all eleven receipt-bound canon extensions reach native PRODUCT_GRADE_VERIFIED.",
    )
    args = parser.parse_args()

    product_root = args.root.expanduser().resolve()
    output_root = (args.output.expanduser().resolve() if args.output else
                   product_root / "state" / "product_grade" / "canon_extensions")
    receipt = run_native_product_grade_batch(
        root=product_root,
        output_root=output_root,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print(receipt["acceptance_token"])

    if args.require_all and receipt["acceptance_token"] != NATIVE_BATCH_VERIFIED_TOKEN:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
