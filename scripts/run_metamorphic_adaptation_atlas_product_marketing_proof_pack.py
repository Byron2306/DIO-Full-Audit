from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.metamorphic_adaptation.atlas_product_marketing_proof_pack import (  # noqa: E402
    ATLAS_PRODUCT_MARKETING_PROOF_PACK_READY_TOKEN,
    build_atlas_product_marketing_proof_pack,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ATLAS-guided product composition marketing proof pack.")
    parser.add_argument("--audience-morphology-gauntlet", required=True, type=Path)
    parser.add_argument("--atlas-product-composition", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    receipt = build_atlas_product_marketing_proof_pack(
        audience_morphology_gauntlet_path=args.audience_morphology_gauntlet,
        atlas_product_composition_path=args.atlas_product_composition,
        output_dir=args.output,
    )
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0 if receipt.status == ATLAS_PRODUCT_MARKETING_PROOF_PACK_READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
