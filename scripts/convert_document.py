#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from adapters.document_studio.conversion import execute_conversion


def main() -> int:
    parser = argparse.ArgumentParser(description="Governed Document Studio format conversion with source/output hash receipts.")
    parser.add_argument("source")
    parser.add_argument("output")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = execute_conversion(Path(args.source), Path(args.output), dry_run=args.dry_run, force=args.force)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
