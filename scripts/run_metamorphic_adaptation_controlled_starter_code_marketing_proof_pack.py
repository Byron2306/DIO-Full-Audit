from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.controlled_starter_code_marketing_proof_pack import (  # noqa: E402
    READY_TOKEN,
    build_controlled_starter_code_marketing_proof_pack,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the DIO controlled starter-code marketing proof pack."
    )
    parser.add_argument(
        "--controlled-starter-code-generation",
        required=True,
        type=Path,
        help="Path to controlled_starter_code_generation_receipt.json.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output directory for the marketing proof pack.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = build_controlled_starter_code_marketing_proof_pack(
        args.controlled_starter_code_generation,
        args.output,
    )
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0 if receipt.status == READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
