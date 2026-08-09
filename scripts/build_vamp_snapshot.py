#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.vamp import build_snapshot  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a calibrated, Evidex-backed VAMP evidence snapshot.")
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "deliverables" / "vamp_snapshots")
    parser.add_argument("--no-evidex", action="store_true")
    args = parser.parse_args()
    output = build_snapshot(args.request.resolve(), args.out.resolve(), run_evidex=not args.no_evidex)
    print(json.dumps({"status": "completed", "output": str(output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
