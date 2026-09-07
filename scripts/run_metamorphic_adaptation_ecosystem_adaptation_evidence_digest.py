from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.ecosystem_adaptation_evidence_digest import (  # noqa: E402
    ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_READY_TOKEN,
    write_ecosystem_adaptation_evidence_digest,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bind the ecosystem adaptive evidence chain into a final digest.")
    parser.add_argument("--organ-registry-receipt", required=True, type=Path)
    parser.add_argument("--ecosystem-plan-receipt", required=True, type=Path)
    parser.add_argument("--ecosystem-execution-receipt", required=True, type=Path)
    parser.add_argument("--ecosystem-rubric-evaluation-receipt", required=True, type=Path)
    parser.add_argument("--ecosystem-arm-analysis-receipt", required=True, type=Path)
    parser.add_argument("--ecosystem-adaptive-verdict", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    digest = write_ecosystem_adaptation_evidence_digest(
        organ_registry_receipt_path=args.organ_registry_receipt,
        ecosystem_plan_receipt_path=args.ecosystem_plan_receipt,
        ecosystem_execution_receipt_path=args.ecosystem_execution_receipt,
        ecosystem_rubric_evaluation_receipt_path=args.ecosystem_rubric_evaluation_receipt,
        ecosystem_arm_analysis_receipt_path=args.ecosystem_arm_analysis_receipt,
        ecosystem_adaptive_verdict_path=args.ecosystem_adaptive_verdict,
        output_path=args.output,
    )
    print(json.dumps(asdict(digest), indent=2, sort_keys=True))
    print(digest.status)
    return 0 if digest.status == ECOSYSTEM_ADAPTATION_EVIDENCE_DIGEST_READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
