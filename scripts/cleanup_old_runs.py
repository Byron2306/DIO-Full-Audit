#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def age_days(path: Path) -> float:
    return (time.time() - path.stat().st_mtime) / 86400


def collect_old_dirs(root: Path, keep_days: float, keep_names: set[str]) -> list[Path]:
    if not root.exists():
        return []
    old = []
    for path in root.iterdir():
        if not path.is_dir():
            continue
        if path.name in keep_names:
            continue
        if age_days(path) >= keep_days:
            old.append(path)
    return sorted(old)


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean old AutoRelease run and deliverable folders.")
    parser.add_argument("--keep-days", type=float, default=14, help="Delete folders older than this many days.")
    parser.add_argument("--keep", action="append", default=["latest", "phase2_demo"], help="Run/deliverable folder name to keep. Can be repeated.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be removed without deleting.")
    args = parser.parse_args()

    keep_names = set(args.keep or [])
    targets = []
    targets.extend(collect_old_dirs(ROOT / "runs", args.keep_days, keep_names))
    targets.extend(collect_old_dirs(ROOT / "deliverables", args.keep_days, keep_names))

    if not targets:
        print("No old run/deliverable folders matched cleanup criteria.")
        return 0

    for path in targets:
        print(("Would remove: " if args.dry_run else "Removing: ") + str(path))
        if not args.dry_run:
            shutil.rmtree(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

