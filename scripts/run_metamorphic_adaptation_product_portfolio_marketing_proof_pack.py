from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.metamorphic_adaptation.product_portfolio_marketing_proof_pack import (  # noqa: E402
    PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_READY_TOKEN,
    build_product_portfolio_marketing_proof_pack,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build T12 product portfolio marketing proof pack.")
    parser.add_argument("--product-portfolio-prioritization", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    receipt = build_product_portfolio_marketing_proof_pack(
        product_portfolio_prioritization_path=args.product_portfolio_prioritization,
        output_dir=args.output,
    )
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0 if receipt.status == PRODUCT_PORTFOLIO_MARKETING_PROOF_PACK_READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
