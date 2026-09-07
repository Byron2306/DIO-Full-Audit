from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.real_pilot_claim_gate import write_real_pilot_claim_gate


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate DIO real pilot claim gate."
    )
    parser.add_argument("--compatibility-verdict", required=True)
    parser.add_argument("--blind-evaluation-receipt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    receipt = write_real_pilot_claim_gate(
        compatibility_verdict_path=Path(args.compatibility_verdict),
        blind_evaluation_receipt_path=Path(args.blind_evaluation_receipt),
        output_path=Path(args.output),
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
