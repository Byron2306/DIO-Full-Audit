from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.native_compatibility import write_native_compatibility_summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Classify a DIO metamorphic adaptation native execution receipt."
    )
    parser.add_argument(
        "--receipt",
        required=True,
        help="Path to native_execution_receipt.json.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write native_compatibility_summary.json.",
    )
    args = parser.parse_args()

    summary = write_native_compatibility_summary(
        Path(args.receipt),
        Path(args.output),
    )

    print(json.dumps(asdict(summary), indent=2, sort_keys=True))
    print(summary.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
