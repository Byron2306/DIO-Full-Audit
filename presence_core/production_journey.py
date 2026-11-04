"""Durable command boundary for canonical Vesper production journeys.

The ledger gives caller commands stable idempotency and deliberately fails
closed after an interrupted handler. It cannot make an arbitrary downstream
handler transactional; an IN_PROGRESS command after process death requires
reconciliation before an operator retries it.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .vesper_journey_runtime import execute_vesper_action


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _connect(path: Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=FULL")
    con.execute("""CREATE TABLE IF NOT EXISTS journey_commands (
        command_id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL,
        action TEXT NOT NULL,
        request_sha256 TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('IN_PROGRESS','COMPLETED','NEEDS_RECONCILIATION')),
        result_json TEXT,
        error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")
    return con


def advance_production_journey(
    state_root: Path,
    *,
    command_id: str,
    case_id: str,
    action: str,
    action_ref: str,
    actor_id: str,
    actor_class: str,
    handlers: Mapping[str, Any],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute one approved Vesper action at most once per command ID.

    Reusing a command ID with changed inputs is rejected. Interrupted commands
    are never replayed automatically because a handler may have performed an
    external effect before the interruption.
    """
    command_id = str(command_id or "").strip()
    case_id = str(case_id or "").strip()
    action = str(action or "").strip().upper()
    actor_id = str(actor_id or "").strip()
    actor_class = str(actor_class or "").strip().lower()
    if not all((command_id, case_id, action, action_ref, actor_id, actor_class)):
        raise ValueError("command_id, case_id, action, action_ref, actor_id and actor_class are required")
    request = {"case_id": case_id, "action": action, "action_ref": action_ref,
               "actor_id": actor_id, "actor_class": actor_class, "payload": payload or {}}
    request_hash = _digest(request)
    ledger_path = Path(state_root) / "production_journey.sqlite"
    con = _connect(ledger_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM journey_commands WHERE command_id=?", (command_id,)).fetchone()
        if row:
            if row["request_sha256"] != request_hash:
                con.rollback()
                raise ValueError("command_id was already used with different journey inputs")
            if row["state"] == "COMPLETED":
                con.commit()
                return json.loads(row["result_json"])
            con.commit()
            return {"schema": "dio.production_journey_command.v1", "command_id": command_id,
                    "case_id": case_id, "state": row["state"], "replay_blocked": True,
                    "reason": row["error"] or "A previous attempt has no reconciled completion receipt."}
        con.execute("INSERT INTO journey_commands VALUES (?,?,?,?,?,?,?,?,?)",
                    (command_id, case_id, action, request_hash, "IN_PROGRESS", None, None, _now(), _now()))
        con.commit()
    finally:
        con.close()

    try:
        result = execute_vesper_action(Path(state_root), case_id, action=action,
                                       action_ref=action_ref, actor_class=actor_class,
                                       handlers=handlers, payload=payload or {})
        result = {**result, "command_id": command_id, "actor_id": actor_id,
                  "command_state": "COMPLETED"}
    except Exception as exc:
        con = _connect(ledger_path)
        try:
            with con:
                con.execute("UPDATE journey_commands SET state='NEEDS_RECONCILIATION',error=?,updated_at=? WHERE command_id=? AND state='IN_PROGRESS'",
                            (f"{type(exc).__name__}: {exc}"[:1000], _now(), command_id))
        finally:
            con.close()
        raise

    con = _connect(ledger_path)
    try:
        with con:
            con.execute("UPDATE journey_commands SET state='COMPLETED',result_json=?,updated_at=? WHERE command_id=? AND state='IN_PROGRESS'",
                        (json.dumps(result, sort_keys=True, ensure_ascii=False), _now(), command_id))
            if con.total_changes != 1:
                raise RuntimeError("journey command completion lost its ledger claim")
    finally:
        con.close()
    return result


def reconcile_production_journey_command(state_root: Path, command_id: str, *, resolution: str,
                                         actor_id: str, evidence_ref: str) -> dict[str, Any]:
    """Close an interrupted command only after explicit, referenced review.

    This records a reconciliation decision; it does not rerun the handler.
    """
    resolution = str(resolution or "").strip().upper()
    if resolution not in {"CONFIRM_EFFECT_COMPLETED", "CONFIRM_NO_EFFECT"}:
        raise ValueError("resolution must confirm completed effect or confirm no effect")
    if not str(actor_id or "").strip() or not str(evidence_ref or "").strip():
        raise ValueError("actor_id and evidence_ref are required")
    con = _connect(Path(state_root) / "production_journey.sqlite")
    try:
        with con:
            row = con.execute("SELECT * FROM journey_commands WHERE command_id=?", (command_id,)).fetchone()
            if row is None:
                raise ValueError("journey command not found")
            if row["state"] not in {"IN_PROGRESS", "NEEDS_RECONCILIATION"}:
                raise ValueError("only interrupted journey commands can be reconciled")
            note = json.dumps({"resolution": resolution, "actor_id": actor_id,
                               "evidence_ref": evidence_ref}, sort_keys=True)
            state = "NEEDS_RECONCILIATION" if resolution == "CONFIRM_NO_EFFECT" else "COMPLETED"
            result = None
            if resolution == "CONFIRM_EFFECT_COMPLETED":
                result = json.dumps({"schema": "dio.production_journey_command.v1",
                                     "command_id": command_id, "case_id": row["case_id"],
                                     "action": row["action"], "command_state": "COMPLETED",
                                     "reconciled": True, "reconciliation": json.loads(note)},
                                    sort_keys=True, ensure_ascii=False)
            # Confirm-no-effect remains held: a fresh command ID is required after
            # reconciliation, preserving the original attempt's immutable history.
            con.execute("UPDATE journey_commands SET state=?,error=?,result_json=COALESCE(?,result_json),updated_at=? WHERE command_id=?",
                        (state, note, result, _now(), command_id))
            return {"schema": "dio.production_journey_reconciliation.v1", "command_id": command_id,
                    "state": state, "resolution": resolution, "actor_id": actor_id,
                    "evidence_ref": evidence_ref, "new_command_required": resolution == "CONFIRM_NO_EFFECT"}
    finally:
        con.close()
