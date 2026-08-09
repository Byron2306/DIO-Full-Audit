from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_catalogs(root: Path) -> dict[str, Any]:
    return {
        "channels": load_json(root / "config" / "marketing_channels.json"),
        "sa_media": load_json(root / "config" / "sa_media_marketplace.json"),
        "agencies": load_json(root / "config" / "agency_partner_registry.json"),
        "policy": load_json(root / "config" / "market_command.json"),
    }
