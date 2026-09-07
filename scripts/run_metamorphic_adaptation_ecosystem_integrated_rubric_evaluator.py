from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.metamorphic_adaptation.ecosystem_integrated_rubric_evaluator import (
    ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATOR_READY_TOKEN,
    evaluate_ecosystem_integrated_outputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Score blinded ecosystem integrated outputs.")
    parser.add_argument("--execution-receipt", required=True, type=Path)
    parser.add_argument("--ecosystem-outputs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    receipt = evaluate_ecosystem_integrated_outputs(
        execution_receipt_path=args.execution_receipt,
        ecosystem_outputs_path=args.ecosystem_outputs,
        output_dir=args.output,
    )
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0 if receipt.status == ECOSYSTEM_INTEGRATED_RUBRIC_EVALUATOR_READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
