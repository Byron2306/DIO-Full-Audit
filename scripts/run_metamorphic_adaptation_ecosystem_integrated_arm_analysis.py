from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.metamorphic_adaptation.ecosystem_integrated_arm_analysis import (  # noqa: E402
    ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_READY_TOKEN,
    analyze_ecosystem_integrated_arms,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze ecosystem integrated scores by hidden arm labels.")
    parser.add_argument("--rubric-evaluation-receipt", required=True, type=Path)
    parser.add_argument("--ecosystem-scores", required=True, type=Path)
    parser.add_argument("--label-join", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    receipt = analyze_ecosystem_integrated_arms(
        rubric_evaluation_receipt_path=args.rubric_evaluation_receipt,
        ecosystem_scores_path=args.ecosystem_scores,
        label_join_path=args.label_join,
        output_dir=args.output,
    )
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0 if receipt.status == ECOSYSTEM_INTEGRATED_ARM_ANALYSIS_READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
