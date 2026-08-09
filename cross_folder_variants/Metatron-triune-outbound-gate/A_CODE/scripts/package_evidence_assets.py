#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def zip_path(src: Path, zip_path: Path, arc_prefix: Path | None = None) -> None:
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED, compresslevel=6) as zf:
        if src.is_file():
            arcname = src.name if arc_prefix is None else str(arc_prefix / src.name)
            zf.write(src, arcname=arcname)
            return
        prefix = arc_prefix or Path(src.name)
        for path in sorted(src.rglob("*")):
            if path.is_dir():
                continue
            zf.write(path, arcname=str(prefix / path.relative_to(src)))


def split_file(path: Path, max_bytes: int) -> list[Path]:
    if path.stat().st_size <= max_bytes:
        return [path]
    parts = []
    with path.open("rb") as src:
        idx = 1
        while True:
            chunk = src.read(max_bytes)
            if not chunk:
                break
            part = path.with_suffix(path.suffix + f".part{idx:03d}")
            with part.open("wb") as dst:
                dst.write(chunk)
            parts.append(part)
            idx += 1
    path.unlink()
    return parts


def main() -> int:
    parser = argparse.ArgumentParser(description="Create segmented zip assets from a full evidence package directory.")
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--max-part-mb", type=int, default=1900)
    args = parser.parse_args()

    bundle_root = Path(args.bundle_root).resolve()
    assets_dir = bundle_root.parent / f"{bundle_root.name}_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    targets: list[tuple[Path, str, Path | None]] = []
    meta_files = [p for p in [bundle_root / "manifest.json", bundle_root / "promotion_report.txt"] if p.exists()]
    for file_path in meta_files:
        targets.append((file_path, f"{bundle_root.name}__meta__{file_path.name}.zip", None))

    for path in sorted((bundle_root / "host").iterdir()) if (bundle_root / "host").exists() else []:
        targets.append((path, f"{bundle_root.name}__host__{path.name}.zip", Path("host") / path.name))

    for path in sorted((bundle_root / "containers").iterdir()) if (bundle_root / "containers").exists() else []:
        targets.append((path, f"{bundle_root.name}__containers__{path.name}.zip", Path("containers") / path.name))

    max_bytes = args.max_part_mb * 1024 * 1024
    written: list[str] = []
    for src, zip_name, arc_prefix in targets:
        zip_file = assets_dir / zip_name
        zip_path(src, zip_file, arc_prefix=arc_prefix)
        for part in split_file(zip_file, max_bytes):
            written.append(str(part))

    index_path = assets_dir / "ASSET_INDEX.txt"
    index_path.write_text("\n".join(written) + "\n", encoding="utf-8")
    print(index_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
