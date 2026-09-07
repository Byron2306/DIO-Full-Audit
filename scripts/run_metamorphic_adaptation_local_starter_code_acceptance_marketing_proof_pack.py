from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.local_starter_code_acceptance_marketing_proof_pack import (  # noqa: E402
    READY_TOKEN,
    build_local_starter_code_acceptance_marketing_proof_pack,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the T17 local starter-code acceptance marketing proof pack."
    )
    parser.add_argument(
        "--local-starter-code-acceptance-verification",
        required=True,
        type=Path,
        help="Path to the T17 local starter-code acceptance verification receipt.",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    receipt = build_local_starter_code_acceptance_marketing_proof_pack(
        args.local_starter_code_acceptance_verification,
        args.output,
    )
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0 if receipt.status == READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
