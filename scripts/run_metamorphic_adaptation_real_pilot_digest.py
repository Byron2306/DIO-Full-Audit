from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.real_pilot_digest import write_real_pilot_digest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit DIO metamorphic adaptation real pilot digest."
    )
    parser.add_argument("--real-plan", required=True)
    parser.add_argument("--scaffold-receipt", required=True)
    parser.add_argument("--execution-receipt", required=True)
    parser.add_argument("--compatibility-verdict", required=True)
    parser.add_argument("--blind-evaluation-receipt", required=True)
    parser.add_argument("--claim-gate", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    digest = write_real_pilot_digest(
        real_plan_path=Path(args.real_plan),
        scaffold_receipt_path=Path(args.scaffold_receipt),
        execution_receipt_path=Path(args.execution_receipt),
        compatibility_verdict_path=Path(args.compatibility_verdict),
        blind_evaluation_receipt_path=Path(args.blind_evaluation_receipt),
        claim_gate_path=Path(args.claim_gate),
        output_path=Path(args.output),
    )

    print(json.dumps(asdict(digest), indent=2, sort_keys=True))
    print(digest.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
