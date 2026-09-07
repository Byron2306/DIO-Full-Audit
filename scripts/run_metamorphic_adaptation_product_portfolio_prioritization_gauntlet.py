from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.metamorphic_adaptation.product_portfolio_prioritization_gauntlet import (  # noqa: E402
    PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_READY_TOKEN,
    run_product_portfolio_prioritization_gauntlet,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run governed product portfolio prioritization gauntlet.")
    parser.add_argument("--product-incarnation-marketing-pack", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    receipt = run_product_portfolio_prioritization_gauntlet(
        product_incarnation_marketing_pack_path=args.product_incarnation_marketing_pack,
        output_dir=args.output,
        execute=args.execute,
    )
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0 if receipt.status == PRODUCT_PORTFOLIO_PRIORITIZATION_GAUNTLET_READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
