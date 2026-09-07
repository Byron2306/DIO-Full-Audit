#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.capability_execution_readiness_map import (  # noqa: E402
    READY_TOKEN,
    build_capability_execution_readiness_map,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the DIO capability execution readiness map."
    )
    parser.add_argument(
        "--implementation-rehearsal",
        required=True,
        type=Path,
        help="Path to controlled_local_implementation_rehearsal_receipt.json.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output directory for readiness map artifacts.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write readiness map artifacts and receipt.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = build_capability_execution_readiness_map(
        implementation_rehearsal_path=args.implementation_rehearsal,
        output_dir=args.output,
        execute=args.execute,
    )
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0 if receipt.status == READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
