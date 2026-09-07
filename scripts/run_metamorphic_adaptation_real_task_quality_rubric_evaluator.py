from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.real_task_quality_rubric_evaluator import (
    evaluate_real_task_quality_rubrics,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate blinded real task-quality outputs against frozen rubrics."
    )
    parser.add_argument("--execution-receipt", required=True)
    parser.add_argument("--task-outputs", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    receipt = evaluate_real_task_quality_rubrics(
        execution_receipt_path=Path(args.execution_receipt),
        task_outputs_path=Path(args.task_outputs),
        output_dir=Path(args.output),
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
