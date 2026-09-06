from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.canon_extension_product_grade import (
    PROOF_VERIFIED_TOKEN,
    VERIFIED_TOKEN,
    run_canon_extension_product_grade_gauntlet,
)
from products.product_grade_gauntlet import run_product_grade_gauntlet


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run truth-bound ProductGrade verification across all 15 DIO canon extensions."
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output directory for canon-extension and supporting Studio ProductGrade receipts.",
    )
    parser.add_argument(
        "--require-proof",
        action="store_true",
        help="Return non-zero unless all 15 canon extensions have verified receipt-bound canon proof.",
    )
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="Return non-zero unless all 15 canon extensions reach full PRODUCT_GRADE_VERIFIED.",
    )
    args = parser.parse_args()
    output_dir = Path(args.output).resolve()
    studio_receipt = run_product_grade_gauntlet(
        output_dir=output_dir / "studio_product_grade",
        root=ROOT,
    )
    receipt = run_canon_extension_product_grade_gauntlet(
        output_dir=output_dir,
        root=ROOT,
        studio_product_grade_receipt=studio_receipt,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print(receipt["proof_acceptance_token"])
    print(receipt["acceptance_token"])
    if args.require_proof and receipt["proof_acceptance_token"] != PROOF_VERIFIED_TOKEN:
        return 2
    if args.require_all and receipt["acceptance_token"] != VERIFIED_TOKEN:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
