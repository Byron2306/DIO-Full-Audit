#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from products.paid_reference_gauntlet import ACCEPTANCE_TOKEN, run_paid_reference_gauntlet


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Phase 11 Paid Reference Products gauntlet.")
    parser.add_argument("--output", default="/tmp/dio-phase11-paid-reference")
    args = parser.parse_args()
    receipt = run_paid_reference_gauntlet(output_dir=Path(args.output))
    print(json.dumps({key: receipt[key] for key in (
        "deterministic_execution", "external_delivery", "market_validation",
        "phase10_controlled_payment_binding", "proof_integrity", "resolution",
    )}, indent=2, sort_keys=True))
    print(ACCEPTANCE_TOKEN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
