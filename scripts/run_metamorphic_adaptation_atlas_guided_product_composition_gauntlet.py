from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.metamorphic_adaptation.atlas_guided_product_composition_gauntlet import (  # noqa: E402
    ATLAS_PRODUCT_COMPOSITION_GAUNTLET_READY_TOKEN,
    run_atlas_guided_product_composition_gauntlet,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ATLAS-guided domain product composition gauntlet.")
    parser.add_argument("--audience-morphology-gauntlet", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    receipt = run_atlas_guided_product_composition_gauntlet(
        audience_morphology_gauntlet_path=args.audience_morphology_gauntlet,
        output_dir=args.output,
        execute=args.execute,
    )
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0 if receipt.status == ATLAS_PRODUCT_COMPOSITION_GAUNTLET_READY_TOKEN else 1


if __name__ == "__main__":
    raise SystemExit(main())
