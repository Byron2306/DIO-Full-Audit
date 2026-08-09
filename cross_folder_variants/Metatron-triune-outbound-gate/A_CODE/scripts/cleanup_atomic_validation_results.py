#!/usr/bin/env python3
"""
cleanup_atomic_validation_results.py
===================================
Removes invalid/empty atomic validation `run_*.json` artifacts that inflate counts.

We only delete records that are clearly unusable:
- missing both `techniques` and `techniques_executed`
- missing `command`
- empty `stdout` and `stderr`

Usage:
  python3 scripts/cleanup_atomic_validation_results.py
  python3 scripts/cleanup_atomic_validation_results.py --dir artifacts/atomic-validation --dry-run
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Tuple


def _load_json(path: Path) -> Tuple[Dict[str, Any] | None, str]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except Exception as exc:
        return None, str(exc)


def _is_clearly_invalid(row: Dict[str, Any]) -> bool:
    techniques = row.get("techniques") or []
    techniques_executed = row.get("techniques_executed") or []
    command = row.get("command")
    stdout = row.get("stdout") or ""
    stderr = row.get("stderr") or ""
    return (not techniques and not techniques_executed) and (not command) and (not str(stdout).strip()) and (not str(stderr).strip())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="artifacts/atomic-validation")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(args.dir)
    if not root.exists():
        print(f"[WARN] results dir not found: {root}")
        return 0

    deleted = 0
    unreadable = 0
    total = 0

    for path in sorted(root.glob("run_*.json")):
        total += 1
        row, err = _load_json(path)
        if row is None:
            unreadable += 1
            continue

        if _is_clearly_invalid(row):
            if args.dry_run:
                print(f"[DRY] delete {path}")
            else:
                path.unlink(missing_ok=True)
            deleted += 1

    print(f"Scanned: {total}")
    print(f"Deleted invalid: {deleted}")
    print(f"Unreadable: {unreadable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

