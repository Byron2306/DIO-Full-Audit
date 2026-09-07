from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.controlled_starter_code_generation_gauntlet import (  # noqa: E402
    READY_TOKEN,
    build_controlled_starter_code_generation_gauntlet,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the DIO controlled local starter-code generation gauntlet."
    )
    parser.add_argument(
        "--capability-execution-readiness-marketing-pack",
        required=True,
        type=Path,
        help="Path to the T15 capability execution readiness marketing proof pack receipt.",
    )
    parser.add_argument("--output", required=True, type=Path, help="Output directory.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write local starter-code files. Without this flag, only a locked plan receipt is emitted.",
    )
    args = parser.parse_args()

    receipt = build_controlled_starter_code_generation_gauntlet(
        args.capability_execution_readiness_marketing_pack,
        args.output,
        execute=args.execute,
    )
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0 if receipt.status == READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
