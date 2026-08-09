#!/usr/bin/env python3
"""Apply the generated ARDA overlay onto a prepared rootfs tree."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DISTRIBUTION_DIR = SCRIPT_DIR.parent
DEFAULT_OVERLAY = DISTRIBUTION_DIR / "build" / "overlay" / "rootfs"


def _copy_tree(src: Path, dest: Path) -> list[dict]:
    copied: list[dict] = []
    for path in sorted(src.rglob("*")):
        relative = path.relative_to(src)
        target = dest / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if path.is_symlink():
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() or target.is_symlink():
                if target.is_dir() and not target.is_symlink():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            target.symlink_to(path.readlink())
            copied.append(
                {
                    "source": str(path),
                    "destination": str(target),
                    "type": "symlink",
                    "target": str(path.readlink()),
                }
            )
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        if os.access(path, os.X_OK):
            mode = target.stat().st_mode
            target.chmod(mode | 0o111)
        copied.append(
            {
                "source": str(path),
                "destination": str(target),
                "size": path.stat().st_size,
            }
        )
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply the ARDA overlay to a rootfs tree")
    parser.add_argument("--overlay-root", default=str(DEFAULT_OVERLAY))
    parser.add_argument("--rootfs-dir", required=True)
    args = parser.parse_args()

    overlay_root = Path(args.overlay_root)
    rootfs_dir = Path(args.rootfs_dir)
    if not overlay_root.is_dir():
        raise SystemExit(f"overlay root missing: {overlay_root}")

    rootfs_dir.mkdir(parents=True, exist_ok=True)
    copied = _copy_tree(overlay_root, rootfs_dir)
    print(
        json.dumps(
            {
                "ok": True,
                "overlay_root": str(overlay_root),
                "rootfs_dir": str(rootfs_dir),
                "copied_file_count": len(copied),
                "copied_files": copied,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
