from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.local_starter_code_acceptance_verification_gauntlet import (  # noqa: E402
    READY_TOKEN,
    build_local_starter_code_acceptance_verification_gauntlet,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the DIO T17 local starter-code acceptance verification gauntlet.")
    parser.add_argument("--controlled-starter-code-generation", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    receipt = build_local_starter_code_acceptance_verification_gauntlet(
        args.controlled_starter_code_generation,
        args.output,
        execute=args.execute,
    )
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0 if receipt.status == READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
