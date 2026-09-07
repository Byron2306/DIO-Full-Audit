from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.human_gated_product_capability_dry_run_marketing_proof_pack import (  # noqa: E402
    READY_TOKEN,
    build_human_gated_product_capability_dry_run_marketing_proof_pack,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the T18 human-gated product capability dry-run marketing proof pack."
    )
    parser.add_argument(
        "--human-gated-product-capability-dry-run",
        required=True,
        type=Path,
        help="Path to the T18 human-gated product capability dry-run receipt JSON.",
    )
    parser.add_argument("--output", required=True, type=Path, help="Output directory for the marketing proof pack.")
    args = parser.parse_args()

    receipt = build_human_gated_product_capability_dry_run_marketing_proof_pack(
        args.human_gated_product_capability_dry_run,
        args.output,
    )
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0 if receipt.status == READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
