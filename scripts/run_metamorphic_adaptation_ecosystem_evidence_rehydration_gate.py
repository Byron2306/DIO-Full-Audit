from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.ecosystem_evidence_rehydration_gate import (
    rehydrate_ecosystem_adaptive_evidence,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rehydrate source-bound ecosystem adaptive evidence from a preserved receipt pack."
    )
    parser.add_argument("--ecosystem-verdict", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    receipt = rehydrate_ecosystem_adaptive_evidence(
        ecosystem_verdict_path=Path(args.ecosystem_verdict),
        output_path=Path(args.output),
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
