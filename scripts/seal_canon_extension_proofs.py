from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.canon_extension_proof_seal import SEAL_TOKEN, seal_all_receipt_bound_extensions


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Seal current receipt-bound canon-extension artifacts to their preserved historical generation receipts. "
            "This creates provenance receipts only; it does not create ProductGrade or commercial validation."
        )
    )
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="Return non-zero unless every receipt-bound canon extension is sealed successfully.",
    )
    args = parser.parse_args()
    receipt = seal_all_receipt_bound_extensions(root=ROOT)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print(receipt["acceptance_token"])
    if args.require_all and receipt["acceptance_token"] != SEAL_TOKEN:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
