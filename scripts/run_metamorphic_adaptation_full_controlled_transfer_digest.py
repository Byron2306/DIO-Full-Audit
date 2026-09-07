from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.full_controlled_transfer_digest import (
    write_full_controlled_transfer_digest,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit DIO full controlled transfer digest."
    )
    parser.add_argument("--plan", required=True)
    parser.add_argument("--scaffold-receipt", required=True)
    parser.add_argument("--execution-receipt", required=True)
    parser.add_argument("--compatibility-verdict", required=True)
    parser.add_argument("--blind-evaluation-receipt", required=True)
    parser.add_argument("--factorial-analysis-receipt", required=True)
    parser.add_argument("--claim-gate", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    digest = write_full_controlled_transfer_digest(
        plan_path=Path(args.plan),
        scaffold_receipt_path=Path(args.scaffold_receipt),
        execution_receipt_path=Path(args.execution_receipt),
        compatibility_verdict_path=Path(args.compatibility_verdict),
        blind_evaluation_receipt_path=Path(args.blind_evaluation_receipt),
        factorial_analysis_receipt_path=Path(args.factorial_analysis_receipt),
        claim_gate_path=Path(args.claim_gate),
        output_path=Path(args.output),
    )

    print(json.dumps(asdict(digest), indent=2, sort_keys=True))
    print(digest.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
