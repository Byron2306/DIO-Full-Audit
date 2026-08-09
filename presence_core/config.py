from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "presence.json"

def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = load_json(path)
    cfg["root"] = str(ROOT)
    return cfg

def env_bool(name: str, default: bool=False) -> bool:
    raw=os.getenv(name)
    return default if raw is None else raw.strip().lower() in {"1","true","yes","on"}

def operator_ids() -> set[str]:
    return {x.strip() for x in os.getenv("DIO_OPERATOR_TELEGRAM_IDS", "").split(",") if x.strip()}
