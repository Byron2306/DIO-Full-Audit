from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.metamorphic_adaptation.marketing_proof_boundary_pack import (  # noqa: E402
    MARKETING_PROOF_BOUNDARY_PACK_READY_TOKEN,
    build_marketing_proof_boundary_pack,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a marketing-safe proof boundary pack from T5/T6 evidence.")
    parser.add_argument("--ecosystem-adaptation-digest", required=True, type=Path)
    parser.add_argument("--sequential-retained-gauntlet", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    receipt = build_marketing_proof_boundary_pack(
        ecosystem_adaptation_digest_path=args.ecosystem_adaptation_digest,
        sequential_retained_gauntlet_path=args.sequential_retained_gauntlet,
        output_dir=args.output,
    )
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0 if receipt.status == MARKETING_PROOF_BOUNDARY_PACK_READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
