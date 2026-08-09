#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "microsoft_mirror_routes.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main() -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    created: list[str] = []
    for product in config["products"].values():
        local_root = Path(product["local_root"]).expanduser()
        for folder in product["folders"]:
            path = local_root / folder
            path.mkdir(parents=True, exist_ok=True)
            created.append(str(path))

    receipt = {
        "schema": "knowedge.microsoft_mirror_setup_receipt.v1",
        "created_at": utc_now(),
        "config": str(CONFIG),
        "local_mirror_root": config["local_mirror_root"],
        "created_or_verified": created,
        "note": "Local folders are ready. Cloud sync still needs OneDrive/rclone mapping on the host machine.",
    }
    out = ROOT / "campaigns" / "phase3" / "microsoft_mirror"
    out.mkdir(parents=True, exist_ok=True)
    receipt_path = out / "MICROSOFT_MIRROR_SETUP_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"receipt": str(receipt_path), "folders": len(created)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
