from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.t23_html_proof_surface_dossier_linking_gate import (  # noqa: E402
    link_t23_dossiers_into_html_proof_surface,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Link T18 draft dossiers into a local T22 HTML proof surface."
    )
    parser.add_argument("--t22-receipt", required=True)
    parser.add_argument("--t18-dry-run-dir", required=True)
    parser.add_argument("--proof-surface-dir", required=True)
    parser.add_argument("--receipt-output", required=True)
    args = parser.parse_args()

    receipt = link_t23_dossiers_into_html_proof_surface(
        t22_receipt_path=Path(args.t22_receipt),
        t18_dry_run_dir=Path(args.t18_dry_run_dir),
        proof_surface_dir=Path(args.proof_surface_dir),
        receipt_output_path=Path(args.receipt_output),
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
