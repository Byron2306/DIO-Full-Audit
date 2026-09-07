from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.real_task_quality_arm_analysis import (
    analyze_real_task_quality_by_arm,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze real task-quality rubric scores by arm.")
    parser.add_argument("--rubric-evaluation-receipt", required=True)
    parser.add_argument("--rubric-scores", required=True)
    parser.add_argument("--label-join", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    receipt = analyze_real_task_quality_by_arm(
        rubric_evaluation_receipt_path=Path(args.rubric_evaluation_receipt),
        rubric_scores_path=Path(args.rubric_scores),
        label_join_path=Path(args.label_join),
        output_dir=Path(args.output),
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
