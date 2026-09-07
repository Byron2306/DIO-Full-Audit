from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.fixture_experiment_digest import write_fixture_experiment_digest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit DIO metamorphic adaptation fixture experiment digest."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--run-receipt", required=True)
    parser.add_argument("--execution-receipt", required=True)
    parser.add_argument("--blind-evaluation-receipt", required=True)
    parser.add_argument("--factorial-analysis-receipt", required=True)
    parser.add_argument("--transfer-claim-gate", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    digest = write_fixture_experiment_digest(
        controlled_transfer_manifest_path=Path(args.manifest),
        controlled_transfer_run_receipt_path=Path(args.run_receipt),
        controlled_transfer_execution_receipt_path=Path(args.execution_receipt),
        blind_evaluation_receipt_path=Path(args.blind_evaluation_receipt),
        factorial_analysis_receipt_path=Path(args.factorial_analysis_receipt),
        transfer_claim_gate_path=Path(args.transfer_claim_gate),
        output_path=Path(args.output),
    )

    print(json.dumps(asdict(digest), indent=2, sort_keys=True))
    print(digest.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
