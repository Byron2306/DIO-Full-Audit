from __future__ import annotations

import os
from pathlib import Path


DEFAULT_MARKET_ENV = Path("/home/byron/.config/dio/market_channels.env")


def load_market_environment() -> Path | None:
    """Load a private channel credential file without shell evaluation."""
    path = Path(os.environ.get("DIO_MARKET_ENV_FILE", str(DEFAULT_MARKET_ENV))).expanduser()
    if not path.is_file():
        return None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not key.replace("_", "").isalnum():
            continue
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))
    return path
