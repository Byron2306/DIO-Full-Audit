#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from products.control_deck_gauntlet import ACCEPTANCE_TOKEN, run_control_deck_gauntlet


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Phase 9 GoldenEye Control Deck Portfolio OS gauntlet.")
    parser.add_argument("--output", default="/tmp/dio-phase9-control-deck")
    args = parser.parse_args()
    receipt = run_control_deck_gauntlet(output_dir=Path(args.output))
    print(json.dumps({
        "deterministic_projection": receipt["deterministic_projection"],
        "external_release_gate": receipt["external_release_gate"],
        "meta_primitive_count": receipt["meta_primitive_count"],
        "registered_product_count": receipt["registered_product_count"],
        "suite_count": receipt["suite_count"],
    }, indent=2, sort_keys=True))
    print(ACCEPTANCE_TOKEN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
