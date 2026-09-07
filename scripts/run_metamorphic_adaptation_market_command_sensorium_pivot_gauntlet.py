from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.metamorphic_adaptation.market_command_sensorium_pivot_gauntlet import (  # noqa: E402
    MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_READY_TOKEN,
    run_market_command_sensorium_pivot_gauntlet,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the market command sensorium pivoting adaptation gauntlet.")
    parser.add_argument("--marketing-proof-boundary-pack", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    receipt = run_market_command_sensorium_pivot_gauntlet(
        marketing_proof_boundary_pack_path=args.marketing_proof_boundary_pack,
        output_dir=args.output,
        execute=args.execute,
    )
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0 if receipt.status == MARKET_COMMAND_SENSORIUM_PIVOT_GAUNTLET_READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
