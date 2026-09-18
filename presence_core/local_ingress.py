from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS ingress_receipts (
  event_key TEXT PRIMARY KEY,
  body_sha256 TEXT NOT NULL,
  state TEXT NOT NULL,
  response_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


class LocalIngressLedger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.executescript(SCHEMA)
        return connection

    def cached_response(
        self,
        event_key: str,
        body: bytes,
    ) -> dict[str, Any] | None:
        key = str(event_key or "").strip()
        if not key:
            return None
        digest = _hash(body)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT body_sha256,state,response_json FROM ingress_receipts WHERE event_key=?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        if row["body_sha256"] != digest:
            raise ValueError(
                "local ingress event key was reused with different bytes"
            )
        if row["state"] != "completed" or not row["response_json"]:
            return None
        return json.loads(row["response_json"])

    def begin(self, event_key: str, body: bytes) -> None:
        key = str(event_key or "").strip()
        if not key:
            return
        digest = _hash(body)
        now = _now()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT body_sha256 FROM ingress_receipts WHERE event_key=?",
                (key,),
            ).fetchone()
            if existing is not None and existing["body_sha256"] != digest:
                raise ValueError(
                    "local ingress event key was reused with different bytes"
                )
            connection.execute(
                """INSERT INTO ingress_receipts(event_key,body_sha256,state,response_json,created_at,updated_at)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(event_key) DO UPDATE SET updated_at=excluded.updated_at""",
                (key, digest, "received", None, now, now),
            )
            connection.commit()

    def complete(
        self,
        event_key: str,
        body: bytes,
        response: dict[str, Any],
    ) -> None:
        key = str(event_key or "").strip()
        if not key:
            return
        digest = _hash(body)
        encoded = json.dumps(
            response,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        now = _now()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT body_sha256 FROM ingress_receipts WHERE event_key=?",
                (key,),
            ).fetchone()
            if row is not None and row["body_sha256"] != digest:
                raise ValueError(
                    "local ingress event key was reused with different bytes"
                )
            connection.execute(
                """INSERT INTO ingress_receipts(event_key,body_sha256,state,response_json,created_at,updated_at)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(event_key) DO UPDATE SET
                     state='completed',
                     response_json=excluded.response_json,
                     updated_at=excluded.updated_at""",
                (key, digest, "completed", encoded, now, now),
            )
            connection.commit()
