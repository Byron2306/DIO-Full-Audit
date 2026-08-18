from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.product_grade_gauntlet import VERIFIED_TOKEN, run_product_grade_gauntlet


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DIO ProductGrade verification across the proved Studio portfolio.")
    parser.add_argument("--output", required=True, help="Output directory for ProductGrade receipts and buyer-review packets.")
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="Return non-zero unless every Studio reaches DIO_PRODUCT_GRADE_VERIFIED.",
    )
    args = parser.parse_args()
    receipt = run_product_grade_gauntlet(output_dir=Path(args.output))
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print(receipt["acceptance_token"])
    if args.require_all and receipt["acceptance_token"] != VERIFIED_TOKEN:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
