from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.blind_evaluation_gate import evaluate_blind_fixture_outputs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run DIO metamorphic adaptation blind fixture evaluation."
    )
    parser.add_argument("--executed-receipts", required=True)
    parser.add_argument("--blind-labels", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    receipt = evaluate_blind_fixture_outputs(
        executed_receipts_path=Path(args.executed_receipts),
        blind_labels_path=Path(args.blind_labels),
        output_dir=Path(args.output),
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
