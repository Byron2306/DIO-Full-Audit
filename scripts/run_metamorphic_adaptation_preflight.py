from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.preflight import write_native_preflight_bundle


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit the DIO metamorphic adaptation native preflight bundle."
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where the preflight receipt bundle will be written.",
    )
    args = parser.parse_args()

    receipt = write_native_preflight_bundle(Path(args.output_dir))

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
