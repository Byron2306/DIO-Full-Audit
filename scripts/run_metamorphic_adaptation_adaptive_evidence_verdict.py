from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.adaptive_evidence_verdict import (  # noqa: E402
    write_adaptive_evidence_verdict,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate DIO adaptive evidence thresholds from the real task-quality digest."
    )
    parser.add_argument("--real-task-quality-digest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--minimum-mean-quality-score", type=float, default=0.6)
    parser.add_argument("--minimum-full-minus-baseline-effect", type=float, default=0.15)
    args = parser.parse_args()

    receipt = write_adaptive_evidence_verdict(
        real_task_quality_digest_path=Path(args.real_task_quality_digest),
        output_path=Path(args.output),
        minimum_mean_quality_score=args.minimum_mean_quality_score,
        minimum_full_minus_baseline_effect=args.minimum_full_minus_baseline_effect,
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
