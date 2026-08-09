import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class MeasuredIdentityError(RuntimeError):
    """Raised when measured-identity preflight must fail closed."""


def _parse_utc(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _canonical_json_bytes(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


class MeasuredProjectionGenerationStore:
    """Monotonic generation guard and userspace lifecycle ledger for measured identity."""

    def __init__(self, database_path: str) -> None:
        self._lock = threading.Lock()
        parent = os.path.dirname(os.path.abspath(database_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._db = sqlite3.connect(database_path, check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS arda_measured_generation ("
            "node_id TEXT PRIMARY KEY, generation INTEGER NOT NULL, "
            "manifest_digest TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS arda_measured_staging ("
            "manifest_id TEXT PRIMARY KEY, node_id TEXT NOT NULL, generation INTEGER NOT NULL, "
            "cgroup_id TEXT NOT NULL, manifest_digest TEXT NOT NULL, enforcement_mode TEXT NOT NULL, "
            "state TEXT NOT NULL, staged_at TEXT NOT NULL, activated_at TEXT NULL, "
            "deactivated_at TEXT NULL, removed_at TEXT NULL, failure_reason TEXT NULL, payload_json TEXT NOT NULL)"
        )

    def assert_newer(self, node_id: str, generation: int) -> None:
        row = self._db.execute(
            "SELECT generation FROM arda_measured_generation WHERE node_id = ?",
            (node_id,),
        ).fetchone()
        if row is not None and generation <= int(row[0]):
            raise MeasuredIdentityError("manifest generation is stale or replayed")

    def next_generation(self, node_id: str) -> int:
        row = self._db.execute(
            "SELECT generation FROM arda_measured_generation WHERE node_id = ?",
            (node_id,),
        ).fetchone()
        return 1 if row is None else int(row[0]) + 1

    def commit(self, node_id: str, generation: int, manifest_digest: str) -> None:
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self.assert_newer(node_id, generation)
                self._db.execute(
                    "INSERT INTO arda_measured_generation(node_id,generation,manifest_digest,updated_at) "
                    "VALUES(?,?,?,?) ON CONFLICT(node_id) DO UPDATE SET "
                    "generation=excluded.generation, manifest_digest=excluded.manifest_digest, updated_at=excluded.updated_at",
                    (
                        node_id,
                        generation,
                        manifest_digest,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def stage(self, projection: Dict[str, Any]) -> None:
        payload_json = json.dumps(projection, sort_keys=True)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                existing = self._db.execute(
                    "SELECT state FROM arda_measured_staging WHERE manifest_id = ?",
                    (projection["manifest_id"],),
                ).fetchone()
                if existing is not None and existing[0] not in ("removed", "deactivated"):
                    raise MeasuredIdentityError("manifest is already staged or active")
                self._db.execute(
                    "INSERT INTO arda_measured_staging("
                    "manifest_id,node_id,generation,cgroup_id,manifest_digest,enforcement_mode,state,"
                    "staged_at,activated_at,deactivated_at,removed_at,failure_reason,payload_json"
                    ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(manifest_id) DO UPDATE SET "
                    "node_id=excluded.node_id, generation=excluded.generation, cgroup_id=excluded.cgroup_id, "
                    "manifest_digest=excluded.manifest_digest, enforcement_mode=excluded.enforcement_mode, "
                    "state=excluded.state, staged_at=excluded.staged_at, activated_at=NULL, "
                    "deactivated_at=NULL, removed_at=NULL, failure_reason=NULL, payload_json=excluded.payload_json",
                    (
                        projection["manifest_id"],
                        projection["node_id"],
                        projection["generation"],
                        projection["cgroup_id"],
                        projection["manifest_digest"],
                        projection["enforcement_mode"],
                        "staged",
                        now,
                        None,
                        None,
                        None,
                        None,
                        payload_json,
                    ),
                )
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def activate(self, manifest_id: str) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                row = self._db.execute(
                    "SELECT manifest_id,node_id,generation,cgroup_id,manifest_digest,enforcement_mode,state,payload_json "
                    "FROM arda_measured_staging WHERE manifest_id = ?",
                    (manifest_id,),
                ).fetchone()
                if row is None:
                    raise MeasuredIdentityError("staged manifest not found")
                if row[6] != "staged":
                    raise MeasuredIdentityError("manifest is not in staged state")
                self.assert_newer(row[1], int(row[2]))
                self._db.execute(
                    "UPDATE arda_measured_staging SET state = ?, deactivated_at = ?, failure_reason = ? "
                    "WHERE node_id = ? AND cgroup_id = ? AND state = ? AND manifest_id != ?",
                    (
                        "deactivated",
                        now,
                        "superseded_by_newer_generation",
                        row[1],
                        row[3],
                        "active",
                        manifest_id,
                    ),
                )
                self._db.execute(
                    "UPDATE arda_measured_staging SET state = ?, activated_at = ?, failure_reason = NULL WHERE manifest_id = ?",
                    ("active", now, manifest_id),
                )
                self._db.execute(
                    "INSERT INTO arda_measured_generation(node_id,generation,manifest_digest,updated_at) "
                    "VALUES(?,?,?,?) ON CONFLICT(node_id) DO UPDATE SET "
                    "generation=excluded.generation, manifest_digest=excluded.manifest_digest, updated_at=excluded.updated_at",
                    (row[1], int(row[2]), row[4], now),
                )
                self._db.execute("COMMIT")
                return json.loads(row[7])
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def deactivate(self, manifest_id: str, reason: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                row = self._db.execute(
                    "SELECT state FROM arda_measured_staging WHERE manifest_id = ?",
                    (manifest_id,),
                ).fetchone()
                if row is None:
                    raise MeasuredIdentityError("staged manifest not found")
                if row[0] not in ("staged", "active"):
                    raise MeasuredIdentityError("manifest is not staged or active")
                self._db.execute(
                    "UPDATE arda_measured_staging SET state = ?, deactivated_at = ?, failure_reason = ? WHERE manifest_id = ?",
                    ("deactivated", now, reason, manifest_id),
                )
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def remove(self, manifest_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                row = self._db.execute(
                    "SELECT state FROM arda_measured_staging WHERE manifest_id = ?",
                    (manifest_id,),
                ).fetchone()
                if row is None:
                    raise MeasuredIdentityError("staged manifest not found")
                self._db.execute(
                    "UPDATE arda_measured_staging SET state = ?, removed_at = ? WHERE manifest_id = ?",
                    ("removed", now, manifest_id),
                )
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def get_record(self, manifest_id: str) -> Optional[Dict[str, Any]]:
        row = self._db.execute(
            "SELECT manifest_id,node_id,generation,cgroup_id,manifest_digest,enforcement_mode,state,"
            "staged_at,activated_at,deactivated_at,removed_at,failure_reason,payload_json "
            "FROM arda_measured_staging WHERE manifest_id = ?",
            (manifest_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "manifest_id": row[0],
            "node_id": row[1],
            "generation": int(row[2]),
            "cgroup_id": row[3],
            "manifest_digest": row[4],
            "enforcement_mode": row[5],
            "state": row[6],
            "staged_at": row[7],
            "activated_at": row[8],
            "deactivated_at": row[9],
            "removed_at": row[10],
            "failure_reason": row[11],
            "payload": json.loads(row[12]),
        }

    def list_records(self, states: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        query = (
            "SELECT manifest_id FROM arda_measured_staging"
            if not states
            else "SELECT manifest_id FROM arda_measured_staging WHERE state IN (%s)"
            % ",".join("?" for _ in states)
        )
        rows = self._db.execute(query, tuple(states or [])).fetchall()
        records: List[Dict[str, Any]] = []
        for row in rows:
            record = self.get_record(row[0])
            if record is not None:
                records.append(record)
        return records

    def compact_active_records(
        self,
        *,
        node_id: Optional[str] = None,
        cgroup_id: Optional[str] = None,
        keep_manifest_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                clauses = ["state = 'active'"]
                params: list[Any] = []
                if node_id:
                    clauses.append("node_id = ?")
                    params.append(node_id)
                if cgroup_id:
                    clauses.append("cgroup_id = ?")
                    params.append(cgroup_id)
                rows = self._db.execute(
                    "SELECT manifest_id,node_id,generation,cgroup_id FROM arda_measured_staging WHERE "
                    + " AND ".join(clauses),
                    tuple(params),
                ).fetchall()
                if not rows:
                    self._db.execute("COMMIT")
                    return {
                        "ok": True,
                        "compacted_count": 0,
                        "kept_manifest_id": keep_manifest_id,
                    }

                if not keep_manifest_id:
                    latest = max(rows, key=lambda row: int(row[2]))
                    keep_manifest_id = str(latest[0])
                compacted: list[str] = []
                for manifest_id, _, _, _ in rows:
                    if str(manifest_id) == keep_manifest_id:
                        continue
                    self._db.execute(
                        "UPDATE arda_measured_staging SET state = ?, deactivated_at = ?, failure_reason = ? "
                        "WHERE manifest_id = ? AND state = 'active'",
                        ("deactivated", now, "compacted_older_active_generation", manifest_id),
                    )
                    compacted.append(str(manifest_id))
                self._db.execute("COMMIT")
                return {
                    "ok": True,
                    "compacted_count": len(compacted),
                    "compacted_manifest_ids": compacted,
                    "kept_manifest_id": keep_manifest_id,
                }
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def close(self) -> None:
        try:
            self._db.close()
        except Exception:
            pass


class MeasuredIdentityVerifier:
    """Userspace preflight verifier for Arda Phase 3 measured manifests."""

    SCHEMA_VERSION = "arda.measured_manifest.v1"
    AUDIENCE = "arda-measured-preflight"

    def __init__(self, generation_store: MeasuredProjectionGenerationStore, maximum_age_seconds: int = 300):
        self._generation_store = generation_store
        self._maximum_age_seconds = maximum_age_seconds

    @staticmethod
    def _entry_loader_spec(entry: Dict[str, Any]) -> str:
        return f"{entry['fs_verity_algorithm_id']}:{entry['fs_verity_digest'].lower()}"

    def _validate_signature_shape(self, signature_block: Dict[str, Any]) -> List[str]:
        failures = []
        if not isinstance(signature_block, dict):
            return ["signature_block_missing"]
        for field in ("algorithm", "keyid", "signature"):
            if not signature_block.get(field):
                failures.append(f"signature_{field}")
        return failures

    def _validate_entry(self, entry: Dict[str, Any], seen_paths: set[str], seen_identities: set[tuple[int, str]]) -> List[str]:
        failures = []
        path = entry.get("path")
        algorithm_id = entry.get("fs_verity_algorithm_id")
        digest = str(entry.get("fs_verity_digest", "")).lower()
        workload_digest = str(entry.get("workload_digest", ""))

        if not path or not os.path.isabs(path):
            failures.append("entry_path")
        if not isinstance(algorithm_id, int) or algorithm_id <= 0:
            failures.append("entry_fsverity_algorithm_id")
        if len(digest) not in (64, 128):
            failures.append("entry_fsverity_digest_length")
        else:
            try:
                bytes.fromhex(digest)
            except ValueError:
                failures.append("entry_fsverity_digest_hex")
        if not workload_digest.startswith("sha256:"):
            failures.append("entry_workload_digest")

        identity = (algorithm_id, digest)
        if path in seen_paths:
            failures.append("entry_duplicate_path")
        if identity in seen_identities:
            failures.append("entry_duplicate_identity")

        seen_paths.add(path)
        seen_identities.add(identity)
        return failures

    def preflight(
        self,
        manifest: Dict[str, Any],
        attestation: Optional[Dict[str, Any]] = None,
        *,
        commit_generation: bool = False,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        failures: List[str] = []

        if manifest.get("schema_version") != self.SCHEMA_VERSION:
            failures.append("manifest_schema_version")
        if not manifest.get("manifest_id"):
            failures.append("manifest_id")
        if not isinstance(manifest.get("generation"), int) or manifest["generation"] <= 0:
            failures.append("manifest_generation")
        if not manifest.get("node_id"):
            failures.append("manifest_node_id")
        if not manifest.get("policy_generation"):
            failures.append("manifest_policy_generation")
        if manifest.get("audience") != self.AUDIENCE:
            failures.append("manifest_audience")

        issued_at = manifest.get("issued_at")
        expires_at = manifest.get("expires_at")
        try:
            issued = _parse_utc(issued_at)
            expires = _parse_utc(expires_at)
            if issued >= expires or current_time < issued or current_time >= expires:
                failures.append("manifest_freshness")
            if (current_time - issued).total_seconds() > self._maximum_age_seconds:
                failures.append("manifest_age")
        except Exception:
            failures.append("manifest_timestamps")
            issued = current_time
            expires = current_time

        entries = manifest.get("entries")
        if not isinstance(entries, list) or not entries:
            failures.append("manifest_entries")
            entries = []

        failures.extend(self._validate_signature_shape(manifest.get("signature", {})))

        seen_paths: set[str] = set()
        seen_identities: set[tuple[int, str]] = set()
        loader_specs: List[str] = []
        verified_paths: List[str] = []
        for entry in entries:
            if not isinstance(entry, dict):
                failures.append("entry_shape")
                continue
            failures.extend(self._validate_entry(entry, seen_paths, seen_identities))
            loader_specs.append(self._entry_loader_spec(entry))
            verified_paths.append(entry.get("path"))

        if attestation is not None:
            if not attestation.get("result_id"):
                failures.append("attestation_result_id")
            if attestation.get("accepted") is not True:
                failures.append("attestation_not_accepted")
            if manifest.get("node_id") != attestation.get("subject_node_id"):
                failures.append("attestation_node_binding")
            if manifest.get("attestation_result_id") != attestation.get("result_id"):
                failures.append("attestation_result_binding")
            if manifest.get("attestation_evidence_digest") != attestation.get("evidence_digest"):
                failures.append("attestation_evidence_binding")
            try:
                attestation_expires = _parse_utc(attestation["expires_at"])
                if current_time >= attestation_expires:
                    failures.append("attestation_expired")
            except Exception:
                failures.append("attestation_expiry")

        unsigned_payload = {
            "schema_version": manifest.get("schema_version"),
            "manifest_id": manifest.get("manifest_id"),
            "generation": manifest.get("generation"),
            "node_id": manifest.get("node_id"),
            "policy_generation": manifest.get("policy_generation"),
            "audience": manifest.get("audience"),
            "attestation_result_id": manifest.get("attestation_result_id"),
            "attestation_evidence_digest": manifest.get("attestation_evidence_digest"),
            "issued_at": issued_at,
            "expires_at": expires_at,
            "entries": entries,
        }
        manifest_digest = "sha256:" + hashlib.sha256(_canonical_json_bytes(unsigned_payload)).hexdigest()

        if not failures:
            try:
                self._generation_store.assert_newer(manifest["node_id"], manifest["generation"])
                if commit_generation:
                    self._generation_store.commit(
                        manifest["node_id"],
                        manifest["generation"],
                        manifest_digest,
                    )
            except MeasuredIdentityError as error:
                failures.append("manifest_generation_replay")
                failures.append(str(error))

        return {
            "ok": not failures,
            "timestamp": current_time.isoformat(),
            "manifest_id": manifest.get("manifest_id"),
            "manifest_digest": manifest_digest,
            "generation": manifest.get("generation"),
            "node_id": manifest.get("node_id"),
            "policy_generation": manifest.get("policy_generation"),
            "enforcement_mode": "fsverity_strict",
            "checked_paths": verified_paths,
            "loader_digest_specs": loader_specs,
            "would_stage_entry_count": len(loader_specs),
            "commit_generation": commit_generation,
            "failures": failures,
        }

    def stage_projection(
        self,
        preflight_result: Dict[str, Any],
        manifest: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not preflight_result.get("ok"):
            failures = ",".join(str(failure) for failure in preflight_result.get("failures", []))
            raise MeasuredIdentityError(
                "cannot stage measured projection from failed preflight"
                + (f": {failures}" if failures else "")
            )
        cgroup_id = manifest.get("cgroup_id")
        cgroup_kernel_id = manifest.get("cgroup_kernel_id")
        if not cgroup_id or not isinstance(cgroup_kernel_id, int) or cgroup_kernel_id <= 0:
            raise MeasuredIdentityError("manifest lacks runtime capsule binding for staging")
        projection = {
            "manifest_id": preflight_result["manifest_id"],
            "manifest_digest": preflight_result["manifest_digest"],
            "generation": preflight_result["generation"],
            "node_id": preflight_result["node_id"],
            "policy_generation": preflight_result["policy_generation"],
            "enforcement_mode": preflight_result["enforcement_mode"],
            "loader_digest_specs": preflight_result["loader_digest_specs"],
            "checked_paths": preflight_result["checked_paths"],
            "cgroup_id": cgroup_id,
            "cgroup_kernel_id": cgroup_kernel_id,
            "pid_namespace_inode": manifest.get("pid_namespace_inode"),
            "mount_namespace_inode": manifest.get("mount_namespace_inode"),
            "expires_at": manifest.get("expires_at"),
        }
        self._generation_store.stage(projection)
        record = self._generation_store.get_record(preflight_result["manifest_id"])
        return {
            "ok": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "stage",
            "record": record,
        }

    def activate_staged_projection(self, manifest_id: str) -> Dict[str, Any]:
        projection = self._generation_store.activate(manifest_id)
        record = self._generation_store.get_record(manifest_id)
        return {
            "ok": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "activate",
            "projection": projection,
            "record": record,
        }

    def deactivate_staged_projection(self, manifest_id: str, reason: str) -> Dict[str, Any]:
        self._generation_store.deactivate(manifest_id, reason)
        return {
            "ok": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "deactivate",
            "record": self._generation_store.get_record(manifest_id),
        }

    def remove_staged_projection(self, manifest_id: str) -> Dict[str, Any]:
        self._generation_store.remove(manifest_id)
        return {
            "ok": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "remove",
            "record": self._generation_store.get_record(manifest_id),
        }
