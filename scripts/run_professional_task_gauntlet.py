from __future__ import annotations

import argparse
import json
from pathlib import Path

from products.professional_task_gauntlet import (
    VERIFIED_TOKEN,
    run_professional_task_gauntlet,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the DIO Professional Task Gauntlet against normal, messy and adversarial Studio work packets."
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help="Run only the named case id. May be repeated.",
    )
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="Exit non-zero unless every selected professional task is verified.",
    )
    args = parser.parse_args()

    receipt = run_professional_task_gauntlet(
        output_dir=args.output,
        case_ids=list(args.case) or None,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print(receipt["acceptance_token"])

    if args.require_all and receipt["acceptance_token"] != VERIFIED_TOKEN:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
