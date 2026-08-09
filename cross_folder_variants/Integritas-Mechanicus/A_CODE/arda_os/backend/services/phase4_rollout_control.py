"""Verifier-driven rollout and recovery control for ARDA Phase 4."""

from __future__ import annotations

import base64
import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from backend.services.arda_trust_contracts import parse_utc


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":")).encode("utf-8")


class RolloutControlError(RuntimeError):
    pass


def _load_serialization_module():
    try:
        from cryptography.hazmat.primitives import serialization
    except ModuleNotFoundError as exc:
        raise RolloutControlError(
            "cryptography dependency is required for verifier-signed rollout control; "
            "install it in the active Python environment"
        ) from exc
    return serialization


class VerifiedVerdictReplayStore:
    def __init__(self, database_path: str) -> None:
        parent = Path(database_path).expanduser().resolve().parent
        parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(database_path, isolation_level=None, check_same_thread=False)
        self._lock = threading.RLock()
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS verifier_verdict_replay("
            "verdict_id TEXT PRIMARY KEY, consumed_at TEXT NOT NULL)"
        )

    def consume(self, verdict_id: str, now: datetime) -> None:
        with self._lock:
            try:
                self._db.execute("BEGIN IMMEDIATE")
                self._db.execute(
                    "INSERT INTO verifier_verdict_replay(verdict_id, consumed_at) VALUES(?,?)",
                    (verdict_id, now.isoformat()),
                )
                self._db.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                self._db.execute("ROLLBACK")
                raise RolloutControlError("verifier verdict already consumed") from exc


class TrustedVerifierVerdict:
    def __init__(self, public_key_path: str, *, key_id: str) -> None:
        serialization = _load_serialization_module()
        self.key_id = key_id
        self._public_key = serialization.load_pem_public_key(Path(public_key_path).read_bytes())

    def verify(self, verdict: Mapping[str, Any]) -> Dict[str, Any]:
        if isinstance(verdict.get("signed_verdict"), Mapping):
            verdict = verdict["signed_verdict"]
        signature = str(verdict.get("signature") or "")
        algorithm = str(verdict.get("signature_algorithm") or "")
        material = dict(verdict.get("verification_material") or {})
        if algorithm != "ed25519" or material.get("key_id") != self.key_id:
            raise RolloutControlError("verifier verdict signature metadata is invalid")
        unsigned = {
            key: value
            for key, value in verdict.items()
            if key not in {"signature", "signature_algorithm", "verification_material"}
        }
        try:
            self._public_key.verify(
                base64.b64decode(signature, validate=True),
                _canonical_json_bytes(unsigned),
            )
        except Exception as exc:
            raise RolloutControlError("verifier verdict signature is invalid") from exc
        return unsigned


@dataclass(frozen=True)
class RolloutDecision:
    requested_state: str
    allowed: bool
    target_enforcement_mode: str
    enable_lockdown: bool
    reasons: tuple[str, ...]


class Phase4RolloutController:
    def __init__(self, verdict_verifier: TrustedVerifierVerdict, replay_store: VerifiedVerdictReplayStore) -> None:
        self._verifier = verdict_verifier
        self._replay = replay_store

    def evaluate(self, signed_verdict: Mapping[str, Any], requested_state: str, *, now: Optional[datetime] = None) -> RolloutDecision:
        instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        verdict = self._verifier.verify(signed_verdict)
        verdict_id = str(verdict.get("verdict_id") or verdict.get("request_digest") or "")
        if not verdict_id:
            raise RolloutControlError("verifier verdict id is missing")
        issued_at = parse_utc(str(verdict.get("issued_at")))
        if (instant - issued_at).total_seconds() > 600:
            raise RolloutControlError("verifier verdict is stale")
        self._replay.consume(verdict_id, instant)

        requested_state = requested_state.strip().lower()
        ok = bool(verdict.get("ok"))
        production_ready = bool(verdict.get("production_ready"))
        failures = tuple(str(item) for item in (verdict.get("failures") or ()))
        authorized_states = {str(item).strip().lower() for item in (verdict.get("authorized_states") or ()) if str(item).strip()}
        if requested_state == "observe":
            if authorized_states and "observe" not in authorized_states:
                raise RolloutControlError("observe not authorized by verifier verdict")
            return RolloutDecision("observe", True, "audit", False, failures)
        if requested_state == "enforce":
            if authorized_states and "enforce" not in authorized_states:
                raise RolloutControlError("enforce not authorized by verifier verdict")
            if not (ok and production_ready):
                raise RolloutControlError("enforce requires a fresh production-ready verifier verdict")
            return RolloutDecision("enforce", True, "fsverity_strict", False, ())
        if requested_state == "lockdown":
            if authorized_states and "lockdown" not in authorized_states:
                raise RolloutControlError("lockdown not authorized by verifier verdict")
            if ok and production_ready:
                raise RolloutControlError("lockdown denied while verifier reports production-ready state")
            return RolloutDecision("lockdown", True, "audit", True, failures or ("verifier_refusal",))
        if requested_state == "rescue":
            if authorized_states and "rescue" not in authorized_states:
                raise RolloutControlError("rescue not authorized by verifier verdict")
            if ok and production_ready:
                raise RolloutControlError("rescue denied while verifier reports production-ready state")
            return RolloutDecision("rescue", True, "audit", False, failures or ("verifier_refusal",))
        raise RolloutControlError(f"unsupported rollout state: {requested_state}")
