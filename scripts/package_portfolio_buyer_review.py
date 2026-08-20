#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PREFERENCE = {
    ".html": 0,
    ".pdf": 1,
    ".docx": 2,
    ".pptx": 3,
    ".xlsx": 4,
    ".md": 5,
    ".txt": 6,
    ".csv": 7,
    ".svg": 8,
    ".png": 9,
    ".jpg": 10,
    ".jpeg": 10,
    ".webp": 11,
    ".mp4": 12,
    ".webm": 13,
    ".zip": 14,
}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Package representative human-facing artifacts from a DIO portfolio production gauntlet for blind buyer review.")
    parser.add_argument("--gauntlet-root", type=Path, required=True)
    parser.add_argument("--max-per-product", type=int, default=3)
    parser.add_argument("--max-file-mb", type=int, default=25)
    args = parser.parse_args()

    root = args.gauntlet_root.resolve()
    queue_path = root / "CANONICAL_BLIND_BUYER_REVIEW_QUEUE.json"
    canonical_root = root / "canonical_53_x3"
    if not queue_path.is_file():
        raise FileNotFoundError(queue_path)
    if not canonical_root.is_dir():
        raise FileNotFoundError(canonical_root)

    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    max_bytes = max(1, args.max_file_mb) * 1024 * 1024

    for item in queue.get("items") or []:
        surface = str(item.get("surface") or "unknown")
        candidates = sorted(
            list(item.get("candidate_artifacts") or []),
            key=lambda row: (
                PREFERENCE.get(str(row.get("suffix") or "").casefold(), 99),
                int(row.get("bytes") or 0),
                str(row.get("path") or ""),
            ),
        )
        accepted = 0
        for candidate in candidates:
            relative = Path(str(candidate.get("path") or ""))
            source = (canonical_root / relative).resolve()
            if not source.is_relative_to(canonical_root) or not source.is_file():
                skipped.append({"surface": surface, "path": str(relative), "reason": "missing_or_unsafe"})
                continue
            if source.stat().st_size > max_bytes:
                skipped.append({"surface": surface, "path": str(relative), "reason": "over_size_cap", "bytes": source.stat().st_size})
                continue
            selected.append(
                {
                    "surface": surface,
                    "source": source,
                    "source_relative": str(relative),
                    "bytes": source.stat().st_size,
                    "suffix": source.suffix.casefold(),
                }
            )
            accepted += 1
            if accepted >= max(1, args.max_per_product):
                break

    bundle = root / "CANONICAL_BLIND_BUYER_REVIEW_BUNDLE.zip"
    manifest = {
        "schema": "dio.portfolio.canonical_blind_buyer_review_bundle.v1",
        "gauntlet_root": str(root),
        "product_count": len({row["surface"] for row in selected}),
        "artifact_count": len(selected),
        "max_per_product": args.max_per_product,
        "max_file_mb": args.max_file_mb,
        "selected": [
            {key: value for key, value in row.items() if key != "source"}
            for row in selected
        ],
        "skipped": skipped,
        "review_rule": "Review customer-facing artifacts, not receipts. A bundle presence is not an approval or production verdict.",
    }
    manifest_path = root / "CANONICAL_BLIND_BUYER_REVIEW_BUNDLE_MANIFEST.json"
    write_json(manifest_path, manifest)

    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(queue_path, "REVIEW_QUEUE.json")
        archive.write(manifest_path, "BUNDLE_MANIFEST.json")
        for row in selected:
            source = row["source"]
            suffix_path = Path(row["source_relative"])
            try:
                tail = suffix_path.relative_to(Path("normal") / slug(row["surface"]) / "EXECUTION")
            except ValueError:
                tail = Path(source.name)
            archive.write(source, str(Path("products") / slug(row["surface"]) / tail))

    print(json.dumps({
        "bundle": str(bundle),
        "product_count": manifest["product_count"],
        "artifact_count": manifest["artifact_count"],
        "skipped_count": len(skipped),
        "manifest": str(manifest_path),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
