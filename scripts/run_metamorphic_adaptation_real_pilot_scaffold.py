from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.real_pilot_scaffold import stage_real_pilot_encounters


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stage a limited real native DIO controlled transfer pilot."
    )
    parser.add_argument("--real-plan", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    receipt = stage_real_pilot_encounters(
        real_plan_path=Path(args.real_plan),
        output_dir=Path(args.output),
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
