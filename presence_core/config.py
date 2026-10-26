from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "presence.json"

def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def state_base(
    dio_root: Path = ROOT,
    *,
    configured_root: str | Path | None = None,
) -> Path:
    """Return the canonical durable DIO state root.

    An explicit configured_root wins when supplied. Otherwise Phase 9
    honours DIO_STATE_ROOT, falling back to <dio_root>/state.
    """
    if configured_root is not None:
        configured = str(configured_root).strip()
        if configured:
            return Path(configured).expanduser().resolve()

    configured = os.getenv("DIO_STATE_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()

    return dio_root / "state"

def state_path(
    *parts: str,
    dio_root: Path = ROOT,
    configured_root: str | Path | None = None,
) -> Path:
    return state_base(
        dio_root,
        configured_root=configured_root,
    ).joinpath(*parts)

def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    cfg = load_json(path)
    cfg["root"] = str(ROOT)

    # Phase 9 decouples governed code from durable runtime state.  A live host
    # may run code from /srv/dio/repo while preserving existing state under a
    # separately managed root such as /srv/dio/presence/state.
    state_base = os.getenv("DIO_STATE_ROOT", "").strip()
    if state_base:
        cfg["state_root"] = str(Path(state_base).expanduser().resolve() / "presence")

    event_log = os.getenv("DIO_EVENT_LOG", "").strip()
    if event_log:
        cfg["event_log"] = str(Path(event_log).expanduser().resolve())

    return cfg

def env_bool(name: str, default: bool=False) -> bool:
    raw=os.getenv(name)
    return default if raw is None else raw.strip().lower() in {"1","true","yes","on"}

def operator_ids() -> set[str]:
    return {x.strip() for x in os.getenv("DIO_OPERATOR_TELEGRAM_IDS", "").split(",") if x.strip()}
