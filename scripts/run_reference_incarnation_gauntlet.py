from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from products.reference_gauntlet import ACCEPTANCE_TOKEN, run_gauntlet


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the DIO Phase 7 Reference Incarnation Gauntlet.")
    parser.add_argument("--output", type=Path, default=ROOT / "state" / "reference_incarnation_gauntlet")
    args = parser.parse_args()
    receipt = run_gauntlet(output_dir=args.output)
    print(json.dumps({"incarnation_count": receipt["incarnation_count"], "shared_core_integrity": receipt["shared_core_integrity"], "deterministic_execution": receipt["deterministic_execution"], "external_release": receipt["external_release"]}, indent=2, sort_keys=True))
    print(ACCEPTANCE_TOKEN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
