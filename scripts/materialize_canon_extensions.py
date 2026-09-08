from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.canon_extension_materializer import MATERIALIZED_TOKEN, materialize_receipt_bound_extensions


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Deterministically materialize the 11 receipt-bound canon-extension surfaces from their configured "
            "native profiles and bind lineage to the immutable historical 53x3 anchor."
        )
    )
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="Return non-zero unless all 11 receipt-bound canon extensions materialize successfully.",
    )
    args = parser.parse_args()

    receipt = materialize_receipt_bound_extensions(root=ROOT)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print(receipt["acceptance_token"])
    if args.require_all and receipt["acceptance_token"] != MATERIALIZED_TOKEN:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
