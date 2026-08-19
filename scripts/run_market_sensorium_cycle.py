#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_sensorium.cycle import MarketSensoriumCycle  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the read-only DIO Market Sensorium cycle with temporal memory, ATLAS baselines and Hivenance observations."
    )
    parser.add_argument(
        "--refresh-public",
        action="store_true",
        help="Refresh the already-governed YouTube/RSS market intelligence lane before ingesting evidence.",
    )
    args = parser.parse_args()
    receipt = MarketSensoriumCycle(ROOT).run(refresh_public=args.refresh_public)
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
