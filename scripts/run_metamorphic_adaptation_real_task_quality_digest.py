from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.real_task_quality_digest import (
    write_real_task_quality_digest,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit DIO real task-quality digest."
    )
    parser.add_argument("--bundle-receipt", required=True)
    parser.add_argument("--execution-receipt", required=True)
    parser.add_argument("--rubric-evaluation-receipt", required=True)
    parser.add_argument("--arm-analysis-receipt", required=True)
    parser.add_argument("--claim-gate", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    digest = write_real_task_quality_digest(
        bundle_receipt_path=Path(args.bundle_receipt),
        execution_receipt_path=Path(args.execution_receipt),
        rubric_evaluation_receipt_path=Path(args.rubric_evaluation_receipt),
        arm_analysis_receipt_path=Path(args.arm_analysis_receipt),
        claim_gate_path=Path(args.claim_gate),
        output_path=Path(args.output),
    )

    print(json.dumps(asdict(digest), indent=2, sort_keys=True))
    print(digest.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
