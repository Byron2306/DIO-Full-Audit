from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.metamorphic_adaptation.market_command_marketing_proof_pack import (  # noqa: E402
    MARKET_COMMAND_MARKETING_PROOF_PACK_READY_TOKEN,
    build_market_command_marketing_proof_pack,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build T7 market-command marketing proof pack.")
    parser.add_argument("--marketing-proof-boundary-pack", required=True, type=Path)
    parser.add_argument("--market-command-pivot-gauntlet", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    receipt = build_market_command_marketing_proof_pack(
        marketing_proof_boundary_pack_path=args.marketing_proof_boundary_pack,
        market_command_pivot_gauntlet_path=args.market_command_pivot_gauntlet,
        output_dir=args.output,
    )
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0 if receipt.status == MARKET_COMMAND_MARKETING_PROOF_PACK_READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
