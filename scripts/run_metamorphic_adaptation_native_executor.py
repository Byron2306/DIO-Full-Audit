from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.native_executor import execute_native_plan


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the guarded DIO metamorphic adaptation native executor."
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where the native execution receipt bundle will be written.",
    )
    parser.add_argument(
        "--python-executable",
        default=sys.executable,
        help="Python executable used for planned native DIO commands.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
        help="Timeout per native command when --execute is supplied.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually execute planned native commands. Without this flag, execution is refused.",
    )

    args = parser.parse_args()

    receipt = execute_native_plan(
        output_dir=Path(args.output_dir),
        execute=args.execute,
        python_executable=args.python_executable,
        timeout_seconds=args.timeout_seconds,
    )

    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    print(receipt.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
