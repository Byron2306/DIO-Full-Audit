from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.t21_human_decision_application_gate import (  # noqa: E402
    apply_t21_human_decision,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply an explicit human decision to a T20 approval decision packet."
    )
    parser.add_argument("--t20-receipt", required=True)
    parser.add_argument(
        "--human-decision",
        required=True,
        choices=["APPROVE_LOCAL_RC", "REQUEST_CHANGES", "REFUSE_RELEASE_CANDIDATE"],
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    receipt = apply_t21_human_decision(
        t20_receipt_path=Path(args.t20_receipt),
        human_decision=args.human_decision,
        output_path=Path(args.output),
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
