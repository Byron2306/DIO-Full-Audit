from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class SourceHealthLedger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.rows: dict[str, dict[str, Any]] = {}
        if self.path.is_file():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                self.rows = dict(payload.get("sources") or {})
            except (OSError, json.JSONDecodeError):
                self.rows = {}

    def record(self, source_id: str, state: str, *, observations: int = 0, error: str | None = None) -> dict[str, Any]:
        previous = dict(self.rows.get(source_id) or {})
        row = {
            "source_id": source_id,
            "state": state,
            "checked_at": _now(),
            "observations": int(observations),
            "error": error,
            "success_count": int(previous.get("success_count") or 0) + (1 if state == "READY" else 0),
            "failure_count": int(previous.get("failure_count") or 0) + (0 if state == "READY" else 1),
            "authority_created": False,
        }
        self.rows[source_id] = row
        return row

    def write(self) -> dict[str, Any]:
        payload = {
            "schema": "dio.market_capital.source_health.v1",
            "generated_at": _now(),
            "sources": self.rows,
            "authority_created": False,
            "external_effects": False,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return payload
