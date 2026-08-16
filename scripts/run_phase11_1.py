#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from products.phase11_1_gauntlet import ACCEPTANCE_TOKEN, run_phase11_1_gauntlet


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DIO Phase 11.1 Vesper attachment-delivery gauntlet.")
    parser.add_argument("--output", default="/tmp/dio-phase11-1")
    args = parser.parse_args()
    receipt = run_phase11_1_gauntlet(output_dir=Path(args.output), root=ROOT)
    print(json.dumps({key: receipt[key] for key in ("deterministic_execution", "vesper_intake", "source_binding", "proof_integrity", "outlook_draft", "external_delivery", "human_release")}, indent=2, sort_keys=True))
    print(ACCEPTANCE_TOKEN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
