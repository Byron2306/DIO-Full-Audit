from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.real_task_quality_executor import (
    execute_real_task_quality_bundle,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute frozen real task-quality assignments."
    )
    parser.add_argument("--bundle-receipt", required=True)
    parser.add_argument("--blinded-assignments", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    receipt = execute_real_task_quality_bundle(
        bundle_receipt_path=Path(args.bundle_receipt),
        blinded_assignments_path=Path(args.blinded_assignments),
        output_dir=Path(args.output),
        execute=args.execute,
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
