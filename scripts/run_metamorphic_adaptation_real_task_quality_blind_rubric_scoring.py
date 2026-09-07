from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.real_task_quality_blind_rubric_scoring import (
    score_real_task_quality_outputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Score real task-quality outputs while still blind to arm labels."
    )
    parser.add_argument("--execution-receipt", required=True)
    parser.add_argument("--blinded-assignments", required=True)
    parser.add_argument("--task-outputs", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    receipt = score_real_task_quality_outputs(
        execution_receipt_path=Path(args.execution_receipt),
        blinded_assignments_path=Path(args.blinded_assignments),
        task_outputs_path=Path(args.task_outputs),
        output_dir=Path(args.output),
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
