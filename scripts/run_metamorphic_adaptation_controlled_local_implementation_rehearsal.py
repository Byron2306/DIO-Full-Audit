from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.controlled_local_implementation_rehearsal import (  # noqa: E402
    READY_TOKEN,
    run_controlled_local_implementation_rehearsal,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the DIO controlled local implementation rehearsal gauntlet.")
    parser.add_argument(
        "--selected-product-sprint-marketing-pack",
        required=True,
        type=Path,
        help="Path to the T13 selected product sprint marketing proof pack receipt JSON.",
    )
    parser.add_argument("--output", required=True, type=Path, help="Output directory for the rehearsal packet.")
    parser.add_argument("--execute", action="store_true", help="Write the controlled local rehearsal packet.")
    args = parser.parse_args()

    receipt = run_controlled_local_implementation_rehearsal(
        selected_product_sprint_marketing_pack_path=args.selected_product_sprint_marketing_pack,
        output_dir=args.output,
        execute=args.execute,
    )
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0 if receipt.status == READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
