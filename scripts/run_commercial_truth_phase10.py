#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from products.commercial_truth_gauntlet import ACCEPTANCE_TOKEN, run_commercial_truth_gauntlet


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Phase 10 Commercial Truth Layer gauntlet.")
    parser.add_argument("--output", default="/tmp/dio-phase10-commercial-truth")
    args = parser.parse_args()
    receipt = run_commercial_truth_gauntlet(output_dir=Path(args.output))
    print(json.dumps({
        "attributed_paid_case_count": receipt["attributed_paid_case_count"],
        "deterministic_projection": receipt["deterministic_projection"],
        "economically_proven_product_count": receipt["economically_proven_product_count"],
        "live_verified_payment_count": receipt["live_verified_payment_count"],
        "product_count": receipt["product_count"],
    }, indent=2, sort_keys=True))
    print(ACCEPTANCE_TOKEN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
