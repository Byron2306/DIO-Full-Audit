from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_profiles import PROFILE_CLASS_DIRS, load_json, sha256_file, validate


def build_index(root: Path) -> dict:
    validate(root)
    profile_root = root / "config" / "profiles"
    entries: list[dict] = []
    for dirname, expected_class in PROFILE_CLASS_DIRS.items():
        for path in sorted((profile_root / dirname).glob("*.json")):
            profile = load_json(path)
            entries.append(
                {
                    "profile_id": profile["profile_id"],
                    "profile_class": expected_class,
                    "profile_version": profile["profile_version"],
                    "path": str(path.relative_to(root)),
                    "content_hash": f"sha256:{sha256_file(path)}",
                    "status": profile["status"],
                }
            )
    entries.sort(key=lambda item: item["profile_id"])
    return {"schema": "dio.profile_index.v1", "index_version": "1.0.0", "profiles": entries}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the canonical DIO Phase 1 profile index.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    payload = build_index(root)
    target = root / "config" / "profiles" / "index.json"
    temp = target.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(target)
    print(f"WROTE {target}")
    print("DIO_PROFILE_INDEX_READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
