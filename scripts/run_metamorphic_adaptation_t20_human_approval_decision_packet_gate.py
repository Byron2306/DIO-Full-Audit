from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.t20_human_approval_decision_packet_gate import (  # noqa: E402
    build_t20_human_approval_decision_packet,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a T20 human approval decision packet from a T19 local release-candidate receipt."
    )
    parser.add_argument("--t19-receipt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    receipt = build_t20_human_approval_decision_packet(
        t19_receipt_path=Path(args.t19_receipt),
        output_path=Path(args.output),
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
