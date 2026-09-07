from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.t24_canonical_continuity_digest_gate import (  # noqa: E402
    build_t24_canonical_continuity_digest,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the canonical T1-T23 continuity digest from receipt roots."
    )
    parser.add_argument("--receipt-pack-dir", required=True)
    parser.add_argument("--extra-receipt-dir", action="append", default=[])
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    receipt = build_t24_canonical_continuity_digest(
        receipt_pack_dir=Path(args.receipt_pack_dir),
        extra_receipt_dirs=[Path(path) for path in args.extra_receipt_dir],
        output_path=Path(args.output),
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
