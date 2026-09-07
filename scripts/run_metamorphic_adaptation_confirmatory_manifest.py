from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.confirmatory_manifest import write_confirmatory_manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit the DIO metamorphic adaptation confirmatory preflight manifest."
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output JSON manifest path.",
    )
    parser.add_argument(
        "--run-output",
        default="/tmp/dio-metamorphic-adaptation-confirmatory",
        help="Custody root used for dry-run placeholder validation.",
    )
    args = parser.parse_args()

    manifest = write_confirmatory_manifest(
        Path(args.output),
        run_output=Path(args.run_output),
    )

    print(json.dumps(asdict(manifest), indent=2, sort_keys=True))
    print("DIO_METAMORPHIC_ADAPTATION_CONFIRMATORY_MANIFEST_READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
