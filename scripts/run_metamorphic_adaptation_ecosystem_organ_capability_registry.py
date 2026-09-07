from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.ecosystem_organ_capability_registry import (
    build_ecosystem_organ_capability_registry,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit DIO ecosystem organ capability registry.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    receipt = build_ecosystem_organ_capability_registry(output_dir=Path(args.output))
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
