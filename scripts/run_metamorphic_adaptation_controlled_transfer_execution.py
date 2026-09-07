from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.controlled_transfer_execution import (
    execute_controlled_transfer_fixture,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute DIO metamorphic adaptation controlled transfer fixture encounters."
    )
    parser.add_argument("--run-receipt", required=True)
    parser.add_argument("--encounters", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Records execution request. This runner executes fixture encounters only.",
    )
    args = parser.parse_args()

    receipt = execute_controlled_transfer_fixture(
        run_receipt_path=Path(args.run_receipt),
        encounter_receipts_path=Path(args.encounters),
        output_dir=Path(args.output),
        execute=args.execute,
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
