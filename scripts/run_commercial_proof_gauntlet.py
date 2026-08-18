from __future__ import annotations

import argparse
import json
from pathlib import Path

from products.commercial_proof_v1_1 import (
    COMMERCIAL_PROVED,
    ZERO_PILOT_TOKEN,
    run_commercial_proof_gauntlet,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate source-bound market, payment and customer-acceptance evidence without laundering zero-value pilots or self-payments into commercial proof."
    )
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--edge-config",
        type=Path,
        default=None,
        help="Required for real_payment mode. Fetches the current authenticated DIO Edge order state.",
    )
    parser.add_argument(
        "--require-commercial-validation",
        action="store_true",
        help="Exit non-zero unless COMMERCIAL_VALIDATION_PROVED is reached.",
    )
    parser.add_argument(
        "--require-zero-pilot-ready",
        action="store_true",
        help="Exit non-zero unless the zero-value pilot flow is structurally ready.",
    )
    args = parser.parse_args()

    receipt = run_commercial_proof_gauntlet(
        bundle_path=args.bundle,
        output_dir=args.output,
        edge_config_path=args.edge_config,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print(receipt["acceptance_token"])

    if args.require_commercial_validation and receipt["commercial_validation"] != COMMERCIAL_PROVED:
        return 2
    if args.require_zero_pilot_ready and receipt["acceptance_token"] != ZERO_PILOT_TOKEN:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
