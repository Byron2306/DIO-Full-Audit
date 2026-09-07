from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from experiments.metamorphic_adaptation.native_execution_plan import write_native_execution_plan


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit the DIO metamorphic adaptation native execution plan."
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where the native execution plan bundle will be written.",
    )
    parser.add_argument(
        "--python-executable",
        default="python",
        help="Python executable to place into planned command argv.",
    )
    args = parser.parse_args()

    plan = write_native_execution_plan(
        Path(args.output_dir),
        python_executable=args.python_executable,
    )

    print(json.dumps(asdict(plan), indent=2, sort_keys=True))
    print(plan.status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
