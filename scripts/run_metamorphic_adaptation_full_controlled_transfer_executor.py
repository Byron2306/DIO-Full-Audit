from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.full_controlled_transfer_executor import (
    execute_full_controlled_transfer,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute the full DIO real controlled transfer native smoke run."
    )
    parser.add_argument("--scaffold-receipt", required=True)
    parser.add_argument("--scaffold-encounters", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    args = parser.parse_args()

    receipt = execute_full_controlled_transfer(
        scaffold_receipt_path=Path(args.scaffold_receipt),
        scaffold_encounters_path=Path(args.scaffold_encounters),
        output_dir=Path(args.output),
        execute=args.execute,
        timeout_seconds=args.timeout_seconds,
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
