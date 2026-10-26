#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_sensorium.core import MarketSensoriumStore  # noqa: E402
from market_sensorium.offers import import_offer_file  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import operator/permitted-search observations of advertised market offers into DIO Market Sensorium."
    )
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    with MarketSensoriumStore(ROOT / "state" / "market_sensorium" / "market_sensorium.sqlite") as store:
        receipt = import_offer_file(store, args.path)
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
