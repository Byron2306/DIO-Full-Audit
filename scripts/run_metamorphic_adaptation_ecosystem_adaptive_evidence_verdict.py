from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.metamorphic_adaptation.ecosystem_adaptive_evidence_verdict import (  # noqa: E402
    ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_READY_TOKEN,
    write_ecosystem_adaptive_evidence_verdict,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate ecosystem adaptive evidence threshold verdict.")
    parser.add_argument("--arm-analysis", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--minimum-mean-ecosystem-quality-score", type=float, default=0.6)
    parser.add_argument("--minimum-full-minus-baseline-effect", type=float, default=0.15)
    args = parser.parse_args()

    verdict = write_ecosystem_adaptive_evidence_verdict(
        arm_analysis_path=args.arm_analysis,
        output_path=args.output,
        minimum_mean_ecosystem_quality_score=args.minimum_mean_ecosystem_quality_score,
        minimum_full_minus_baseline_effect=args.minimum_full_minus_baseline_effect,
    )
    print(json.dumps(asdict(verdict), indent=2, sort_keys=True))
    print(verdict.status)
    return 0 if verdict.status == ECOSYSTEM_ADAPTIVE_EVIDENCE_VERDICT_READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
