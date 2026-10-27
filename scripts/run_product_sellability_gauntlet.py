#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.product_grade_sellability_gauntlet import run_product_sellability_gauntlet


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the DIO ProductGrade plus semantic-visual sellability gauntlet."
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    receipt = run_product_sellability_gauntlet(output_dir=args.output, root=ROOT)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print(receipt["acceptance_token"])
    return 0 if receipt["all_sellability_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
