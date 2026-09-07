from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.capability_execution_readiness_marketing_proof_pack import (  # noqa: E402
    READY_TOKEN,
    build_capability_execution_readiness_marketing_proof_pack,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the DIO capability execution readiness marketing proof pack."
    )
    parser.add_argument(
        "--capability-execution-readiness-map",
        required=True,
        type=Path,
        help="Path to capability_execution_readiness_map_receipt.json",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    receipt = build_capability_execution_readiness_marketing_proof_pack(
        capability_execution_readiness_map=args.capability_execution_readiness_map,
        output_dir=args.output,
    )
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0 if receipt.status == READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
