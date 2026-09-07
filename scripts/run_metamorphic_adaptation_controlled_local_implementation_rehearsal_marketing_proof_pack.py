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

from experiments.metamorphic_adaptation.controlled_local_implementation_rehearsal_marketing_proof_pack import (  # noqa: E402
    READY_TOKEN,
    build_controlled_implementation_rehearsal_marketing_proof_pack,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the T14 controlled local implementation rehearsal marketing proof pack."
    )
    parser.add_argument(
        "--controlled-local-implementation-rehearsal",
        type=Path,
        required=True,
        help="Path to controlled_local_implementation_rehearsal_receipt.json.",
    )
    parser.add_argument("--output", type=Path, required=True, help="Output directory for the proof pack.")
    args = parser.parse_args()

    receipt = build_controlled_implementation_rehearsal_marketing_proof_pack(
        args.controlled_local_implementation_rehearsal,
        args.output,
    )
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0 if receipt.status == READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
