from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.canon_portfolio_product_grade import (
    PORTFOLIO_BASELINE_TOKEN,
    PORTFOLIO_VERIFIED_TOKEN,
    run_canon_portfolio_product_grade,
)


HISTORICAL_ANCHOR_PATH = (
    ROOT / "evidence" / "historical" / "PROFESSIONAL_EVIDENCE_53_X3_ANCHOR.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Bind the immutable historical 53x3 DIO proof anchor to a verified 15x3 canon-extension receipt "
            "and emit the 68-product / 204-journey portfolio ProductGrade receipt."
        )
    )
    parser.add_argument(
        "--extension-receipt",
        required=True,
        type=Path,
        help="Path to CANON_EXTENSION_PRODUCT_GRADE_RECEIPT.json from the verified 15x3 extension run.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output directory for the immutable 68x3 portfolio aggregation receipt.",
    )
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="Return non-zero unless the final portfolio token verifies 68 products and 204 controlled journeys.",
    )
    args = parser.parse_args()

    extension_path = args.extension_receipt.expanduser().resolve()
    extension_receipt = json.loads(extension_path.read_text(encoding="utf-8"))
    if not isinstance(extension_receipt, dict):
        raise ValueError("canon extension ProductGrade receipt must be a JSON object")

    receipt = run_canon_portfolio_product_grade(
        historical_anchor_path=HISTORICAL_ANCHOR_PATH,
        extension_receipt=extension_receipt,
        output_dir=args.output.expanduser().resolve(),
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print(receipt["acceptance_token"])

    if args.require_all and receipt["acceptance_token"] != PORTFOLIO_VERIFIED_TOKEN:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
