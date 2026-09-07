from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.full_controlled_transfer_scaffold import (
    stage_full_controlled_transfer_run,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stage the full DIO real controlled transfer run."
    )
    parser.add_argument("--full-plan", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    receipt = stage_full_controlled_transfer_run(
        full_plan_path=Path(args.full_plan),
        output_dir=Path(args.output),
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
