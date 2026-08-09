"""Durable, atomic lifecycle for BEAST capability leases.

The store is deliberately separate from the legacy notation-token cache. It
provides a transactional authority primitive that Metatron can require before
minting notation or opening a consequential edge.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Protocol

from backend.services.arda_trust_contracts import BeastCapabilityLeaseV1, parse_utc


class CapabilityLeaseSignatureVerifier(Protocol):
    def verify(self, lease: BeastCapabilityLeaseV1) -> bool: ...


class CapabilityLeaseError(RuntimeError):
    pass


class CapabilityLeaseUnavailable(CapabilityLeaseError):
    pass


class SqliteCapabilityLeaseStore:
    def __init__(self, path: Path | str, *, signature_verifier: CapabilityLeaseSignatureVerifier):
        self.path = str(path)
        self.signature_verifier = signature_verifier
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS capability_leases (
                    lease_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    used_count INTEGER NOT NULL,
                    maximum_uses INTEGER NOT NULL,
                    expires_at TEXT NOT NULL,
                    revocation_epoch INTEGER NOT NULL,
                    registered_at TEXT NOT NULL,
                    consumed_at TEXT,
                    revoked_at TEXT,
                    revocation_reason TEXT,
                    bound_notation_token_id TEXT,
                    bound_request_digest TEXT,
                    bound_action_digest TEXT,
                    bound_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS authority_state (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    revocation_epoch INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO authority_state(singleton, revocation_epoch) VALUES (1, 0)"
            )
            # Safe forward migration for databases created before notation
            # binding became a separate lifecycle state.
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(capability_leases)")
            }
            for name in (
                "bound_notation_token_id",
                "bound_request_digest",
                "bound_action_digest",
                "bound_at",
            ):
                if name not in columns:
                    connection.execute(f"ALTER TABLE capability_leases ADD COLUMN {name} TEXT")

    def register(self, lease: BeastCapabilityLeaseV1) -> None:
        lease.validate_shape()
        if self.signature_verifier.verify(lease) is not True:
            raise CapabilityLeaseError("capability lease signature is invalid")
        now = datetime.now(timezone.utc)
        if not (parse_utc(lease.issued_at) <= now < parse_utc(lease.expires_at)):
            raise CapabilityLeaseError("capability lease is not currently valid")
        payload = json.dumps(asdict(lease), sort_keys=True, separators=(",", ":"), default=str)
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                current_epoch = int(
                    connection.execute(
                        "SELECT revocation_epoch FROM authority_state WHERE singleton=1"
                    ).fetchone()[0]
                )
                if lease.revocation_epoch < current_epoch:
                    raise CapabilityLeaseError("capability lease was issued before current revocation epoch")
                existing = connection.execute(
                    "SELECT payload_json FROM capability_leases WHERE lease_id=?",
                    (lease.lease_id,),
                ).fetchone()
                if existing is not None:
                    if existing["payload_json"] != payload:
                        raise CapabilityLeaseError("capability lease ID collision")
                    connection.execute("COMMIT")
                    return
                connection.execute(
                    """
                    INSERT INTO capability_leases(
                        lease_id, payload_json, status, used_count, maximum_uses,
                        expires_at, revocation_epoch, registered_at
                    ) VALUES (?, ?, 'active', 0, ?, ?, ?, ?)
                    """,
                    (
                        lease.lease_id,
                        payload,
                        lease.maximum_uses,
                        lease.expires_at,
                        lease.revocation_epoch,
                        now.isoformat(),
                    ),
                )
                connection.execute("COMMIT")
            except Exception:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise

    def consume(
        self,
        lease_id: str,
        *,
        expected_audience: str,
        authority_request_digest: str,
        now: Optional[datetime] = None,
    ) -> BeastCapabilityLeaseV1:
        instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT * FROM capability_leases WHERE lease_id=?", (lease_id,)
                ).fetchone()
                if row is None:
                    raise CapabilityLeaseUnavailable("capability lease does not exist")
                lease = self._decode(row["payload_json"])
                current_epoch = int(
                    connection.execute(
                        "SELECT revocation_epoch FROM authority_state WHERE singleton=1"
                    ).fetchone()[0]
                )
                failures = []
                if row["status"] != "active":
                    failures.append(f"status:{row['status']}")
                if int(row["used_count"]) >= int(row["maximum_uses"]):
                    failures.append("use_limit")
                if parse_utc(row["expires_at"]) <= instant:
                    failures.append("expired")
                if int(row["revocation_epoch"]) < current_epoch:
                    failures.append("revocation_epoch")
                if lease.audience != expected_audience:
                    failures.append("audience")
                if lease.authority_request_digest != authority_request_digest:
                    failures.append("authority_request_digest")
                if self.signature_verifier.verify(lease) is not True:
                    failures.append("signature")
                if failures:
                    raise CapabilityLeaseUnavailable(
                        "capability lease cannot be consumed: " + ",".join(failures)
                    )
                used_count = int(row["used_count"]) + 1
                status = "consumed" if used_count >= int(row["maximum_uses"]) else "active"
                connection.execute(
                    """
                    UPDATE capability_leases
                    SET used_count=?, status=?, consumed_at=?
                    WHERE lease_id=? AND status='active' AND used_count=?
                    """,
                    (used_count, status, instant.isoformat(), lease_id, int(row["used_count"])),
                )
                if connection.total_changes != 1:
                    raise CapabilityLeaseUnavailable("capability lease consumption lost an atomic race")
                connection.execute("COMMIT")
                return lease
            except Exception:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise

    def bind_notation(
        self,
        lease_id: str,
        *,
        notation_token_id: str,
        expected_audience: str,
        authority_request_digest: str,
        action_digest: str,
        now: Optional[datetime] = None,
    ) -> BeastCapabilityLeaseV1:
        """Reserve a lease for one notation token without spending execution.

        The gate cannot call this method to create upstream authority.  It is
        intended for the independent notation issuer after BEAST authority has
        already been registered.
        """
        if not notation_token_id or not action_digest.startswith("sha256:"):
            raise CapabilityLeaseError("notation and action binding are required")
        instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT * FROM capability_leases WHERE lease_id=?", (lease_id,)
                ).fetchone()
                if row is None:
                    raise CapabilityLeaseUnavailable("capability lease does not exist")
                lease = self._decode(row["payload_json"])
                current_epoch = int(connection.execute(
                    "SELECT revocation_epoch FROM authority_state WHERE singleton=1"
                ).fetchone()[0])
                failures = []
                if row["status"] != "active":
                    failures.append(f"status:{row['status']}")
                if parse_utc(row["expires_at"]) <= instant:
                    failures.append("expired")
                if int(row["revocation_epoch"]) < current_epoch:
                    failures.append("revocation_epoch")
                if lease.audience != expected_audience:
                    failures.append("audience")
                if lease.authority_request_digest != authority_request_digest:
                    failures.append("authority_request_digest")
                if self.signature_verifier.verify(lease) is not True:
                    failures.append("signature")
                if failures:
                    raise CapabilityLeaseUnavailable(
                        "capability lease cannot bind notation: " + ",".join(failures)
                    )
                cursor = connection.execute(
                    """
                    UPDATE capability_leases
                    SET status='bound', bound_notation_token_id=?,
                        bound_request_digest=?, bound_action_digest=?, bound_at=?
                    WHERE lease_id=? AND status='active'
                    """,
                    (
                        notation_token_id,
                        authority_request_digest,
                        action_digest,
                        instant.isoformat(),
                        lease_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise CapabilityLeaseUnavailable("capability lease notation binding lost an atomic race")
                connection.execute("COMMIT")
                return lease
            except Exception:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise

    def consume_bound(
        self,
        lease_id: str,
        *,
        notation_token_id: str,
        expected_audience: str,
        authority_request_digest: str,
        action_digest: str,
        now: Optional[datetime] = None,
    ) -> BeastCapabilityLeaseV1:
        """Atomically consume the lease bound to the exact executing action."""
        instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT * FROM capability_leases WHERE lease_id=?", (lease_id,)
                ).fetchone()
                if row is None:
                    raise CapabilityLeaseUnavailable("capability lease does not exist")
                lease = self._decode(row["payload_json"])
                current_epoch = int(connection.execute(
                    "SELECT revocation_epoch FROM authority_state WHERE singleton=1"
                ).fetchone()[0])
                failures = []
                if row["status"] != "bound":
                    failures.append(f"status:{row['status']}")
                if row["bound_notation_token_id"] != notation_token_id:
                    failures.append("notation_token")
                if row["bound_request_digest"] != authority_request_digest:
                    failures.append("bound_request_digest")
                if row["bound_action_digest"] != action_digest:
                    failures.append("action_digest")
                if lease.audience != expected_audience:
                    failures.append("audience")
                if parse_utc(row["expires_at"]) <= instant:
                    failures.append("expired")
                if int(row["revocation_epoch"]) < current_epoch:
                    failures.append("revocation_epoch")
                if self.signature_verifier.verify(lease) is not True:
                    failures.append("signature")
                if failures:
                    raise CapabilityLeaseUnavailable(
                        "bound capability lease cannot be consumed: " + ",".join(failures)
                    )
                cursor = connection.execute(
                    """
                    UPDATE capability_leases
                    SET status='consumed', used_count=used_count+1, consumed_at=?
                    WHERE lease_id=? AND status='bound' AND used_count=0
                    """,
                    (instant.isoformat(), lease_id),
                )
                if cursor.rowcount != 1:
                    raise CapabilityLeaseUnavailable("bound capability consumption lost an atomic race")
                connection.execute("COMMIT")
                return lease
            except Exception:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise

    def revoke(self, lease_id: str, *, reason: str) -> bool:
        if not reason:
            raise ValueError("revocation reason is required")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE capability_leases
                SET status='revoked', revoked_at=?, revocation_reason=?
                WHERE lease_id=? AND status='active'
                """,
                (datetime.now(timezone.utc).isoformat(), reason, lease_id),
            )
            connection.execute("COMMIT")
            return cursor.rowcount == 1

    def advance_revocation_epoch(self, new_epoch: int, *, reason: str) -> int:
        if new_epoch < 0 or not reason:
            raise ValueError("valid revocation epoch and reason are required")
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                current = int(
                    connection.execute(
                        "SELECT revocation_epoch FROM authority_state WHERE singleton=1"
                    ).fetchone()[0]
                )
                if new_epoch <= current:
                    raise ValueError("revocation epoch must advance monotonically")
                connection.execute(
                    "UPDATE authority_state SET revocation_epoch=? WHERE singleton=1",
                    (new_epoch,),
                )
                cursor = connection.execute(
                    """
                    UPDATE capability_leases
                    SET status='revoked', revoked_at=?, revocation_reason=?
                    WHERE status='active' AND revocation_epoch < ?
                    """,
                    (now, reason, new_epoch),
                )
                connection.execute("COMMIT")
                return cursor.rowcount
            except Exception:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise

    def state(self, lease_id: str) -> Mapping[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT lease_id, status, used_count, maximum_uses, expires_at,
                       revocation_epoch, consumed_at, revoked_at, revocation_reason,
                       bound_notation_token_id, bound_request_digest,
                       bound_action_digest, bound_at
                FROM capability_leases WHERE lease_id=?
                """,
                (lease_id,),
            ).fetchone()
            return dict(row) if row is not None else {}

    @staticmethod
    def _decode(payload_json: str) -> BeastCapabilityLeaseV1:
        payload = json.loads(payload_json)
        for field in (
            "data_scope",
            "route_scope",
            "output_scope",
            "approval_receipt_ids",
        ):
            payload[field] = tuple(payload.get(field) or ())
        return BeastCapabilityLeaseV1(**payload)
