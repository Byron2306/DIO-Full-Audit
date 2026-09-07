from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.transfer_claim_gate import write_transfer_claim_gate


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate DIO metamorphic adaptation transfer claim gate."
    )
    parser.add_argument("--execution-receipt", required=True)
    parser.add_argument("--blind-evaluation-receipt", required=True)
    parser.add_argument("--factorial-analysis-receipt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    receipt = write_transfer_claim_gate(
        execution_receipt_path=Path(args.execution_receipt),
        blind_evaluation_receipt_path=Path(args.blind_evaluation_receipt),
        factorial_analysis_receipt_path=Path(args.factorial_analysis_receipt),
        output_path=Path(args.output),
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
