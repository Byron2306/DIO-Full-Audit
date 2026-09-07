from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.controlled_transfer_runner import stage_controlled_transfer_run


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stage a DIO metamorphic adaptation controlled transfer run."
    )
    parser.add_argument(
        "--manifest",
        required=True,
        help="Path to controlled_transfer_manifest.json.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output directory for staged controlled transfer run artifacts.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Record execution request. Scaffold still does not execute encounters.",
    )
    args = parser.parse_args()

    receipt = stage_controlled_transfer_run(
        manifest_path=Path(args.manifest),
        output_dir=Path(args.output),
        execute=args.execute,
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
