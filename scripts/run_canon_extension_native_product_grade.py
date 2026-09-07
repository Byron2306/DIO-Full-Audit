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
from products.product_grade_gauntlet import run_product_grade_gauntlet


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run native normal, messy, and adversarial ProductGrade across all fifteen DIO canon extensions. "
            "The run verifies controlled buyer-artifact capability and provenance; commercial validation and "
            "external authority remain separate truths."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "state" / "product_grade" / "canon_extensions",
        help="Output root for native 15x3 canon-extension ProductGrade receipts.",
    )
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="Return non-zero unless all 15 canon extensions and all 45 controlled journeys verify.",
    )
    args = parser.parse_args()

    output_root = args.output.expanduser().resolve()
    studio_receipt = run_product_grade_gauntlet(
        output_dir=output_root.parent / "studio_product_grade_support",
        root=ROOT,
    )
    receipt = run_native_product_grade_batch(
        root=ROOT,
        output_root=output_root,
        studio_product_grade_receipt=studio_receipt,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print(receipt["acceptance_token"])

    if args.require_all and receipt["acceptance_token"] != NATIVE_BATCH_VERIFIED_TOKEN:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
