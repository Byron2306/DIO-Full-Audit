from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from experiments.metamorphic_adaptation.t25_stage_source_purification_breakthrough_ledger_gate import (
    build_t25_stage_source_purification_breakthrough_ledger,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the T25 purified stage-source map and breakthrough ledger."
    )
    parser.add_argument("--t24-receipt", required=True)
    parser.add_argument("--receipt-output", required=True)
    parser.add_argument("--markdown-output", required=True)
    args = parser.parse_args()

    receipt = build_t25_stage_source_purification_breakthrough_ledger(
        t24_receipt_path=Path(args.t24_receipt),
        receipt_output_path=Path(args.receipt_output),
        markdown_output_path=Path(args.markdown_output),
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0 if receipt.stage_sources_purified else 1


if __name__ == "__main__":
    raise SystemExit(main())
