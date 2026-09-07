from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.t22_html_proof_surface_generation_gate import (
    build_t22_html_proof_surface,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a local static HTML proof surface from a T21 human decision application receipt."
    )
    parser.add_argument("--t21-receipt", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--receipt-output", required=True)
    args = parser.parse_args()

    receipt = build_t22_html_proof_surface(
        t21_receipt_path=Path(args.t21_receipt),
        output_dir=Path(args.output_dir),
        receipt_output_path=Path(args.receipt_output),
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
