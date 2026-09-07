from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.full_controlled_transfer_plan import (
    write_full_controlled_transfer_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan the full DIO real controlled transfer run."
    )
    parser.add_argument("--real-pilot-digest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--encounters-per-arm", type=int, default=5)
    args = parser.parse_args()

    plan = write_full_controlled_transfer_plan(
        real_pilot_digest_path=Path(args.real_pilot_digest),
        output_path=Path(args.output),
        encounters_per_arm=args.encounters_per_arm,
    )

    print(json.dumps(asdict(plan), indent=2, sort_keys=True))
    print(plan.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
