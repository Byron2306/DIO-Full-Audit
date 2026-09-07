from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.sequential_retained_ecosystem_gauntlet import (  # noqa: E402
    SEQUENTIAL_RETAINED_ECOSYSTEM_GAUNTLET_READY_TOKEN,
    run_sequential_retained_ecosystem_gauntlet,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the sequential retained ecosystem adaptation gauntlet.")
    parser.add_argument("--ecosystem-adaptation-digest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    receipt = run_sequential_retained_ecosystem_gauntlet(
        ecosystem_adaptation_digest_path=args.ecosystem_adaptation_digest,
        output_dir=args.output,
        execute=args.execute,
    )
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0 if receipt.status == SEQUENTIAL_RETAINED_ECOSYSTEM_GAUNTLET_READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
