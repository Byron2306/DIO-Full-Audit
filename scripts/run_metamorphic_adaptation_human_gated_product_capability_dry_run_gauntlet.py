from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.human_gated_product_capability_dry_run_gauntlet import (  # noqa: E402
    READY_TOKEN,
    build_human_gated_product_capability_dry_run_gauntlet,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the DIO human-gated product capability dry-run gauntlet."
    )
    parser.add_argument(
        "--local-starter-code-acceptance-marketing-pack",
        required=True,
        type=Path,
        help="Path to the T17 local starter-code acceptance marketing proof pack receipt.",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    receipt = build_human_gated_product_capability_dry_run_gauntlet(
        args.local_starter_code_acceptance_marketing_pack,
        args.output,
        execute=args.execute,
    )
    payload = asdict(receipt)
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(receipt.status)
    return 0 if receipt.status == READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
