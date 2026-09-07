from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.real_controlled_transfer_plan import (
    write_real_controlled_transfer_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan a limited real native DIO controlled transfer pilot."
    )
    parser.add_argument("--fixture-digest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    plan = write_real_controlled_transfer_plan(
        fixture_digest_path=Path(args.fixture_digest),
        output_path=Path(args.output),
    )

    print(json.dumps(asdict(plan), indent=2, sort_keys=True))
    print(plan.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
