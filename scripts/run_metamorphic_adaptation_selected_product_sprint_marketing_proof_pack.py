from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.selected_product_sprint_marketing_proof_pack import (  # noqa: E402
    READY_TOKEN,
    build_selected_product_sprint_marketing_proof_pack,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the DIO T13 selected product sprint marketing proof pack."
    )
    parser.add_argument(
        "--selected-product-sprint-planning",
        required=True,
        type=Path,
        help="Path to selected_product_sprint_planning_gauntlet_receipt.json",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output directory for the T13 selected product sprint marketing proof pack.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = build_selected_product_sprint_marketing_proof_pack(
        selected_product_sprint_planning=args.selected_product_sprint_planning,
        output_dir=args.output,
    )
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    copy_path = Path(receipt.sprint_marketing_copy_path)
    if copy_path.exists():
        print(copy_path.read_text(encoding="utf-8"))
    return 0 if receipt.status == READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
