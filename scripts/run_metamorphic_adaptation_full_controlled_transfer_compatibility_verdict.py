from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.full_controlled_transfer_compatibility_verdict import (
    write_full_transfer_compatibility_verdict,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate DIO full controlled transfer native compatibility verdict."
    )
    parser.add_argument("--execution-receipt", required=True)
    parser.add_argument("--execution-receipts", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    verdict = write_full_transfer_compatibility_verdict(
        execution_receipt_path=Path(args.execution_receipt),
        execution_receipts_path=Path(args.execution_receipts),
        output_path=Path(args.output),
    )

    print(json.dumps(asdict(verdict), indent=2, sort_keys=True))
    print(verdict.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
