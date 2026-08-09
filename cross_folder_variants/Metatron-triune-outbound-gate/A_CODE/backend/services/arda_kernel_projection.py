"""Strict, content-bound projection of ARDA law into the kernel LSM.

The legacy loader can seed inode/device coordinates for lockout-safe laboratory
use.  This module defines the production boundary: only a signed, fresh
manifest bound to an accepted verifier result may project fs-verity identities.
It never signs manifests, mints authority, or treats filesystem coordinates as
proof of content identity.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import struct
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Mapping, Optional, Protocol, Sequence, Tuple

from .arda_trust_contracts import (
    ArdaAttestationResultV1,
    BeastCapabilityLeaseV1,
    canonical_json_bytes,
    parse_utc,
)


class KernelProjectionError(RuntimeError):
    """A hard veto raised before kernel state may be changed."""


class DetachedSignatureVerifier(Protocol):
    def verify(
        self,
        payload: bytes,
        signature: str,
        algorithm: str,
        verification_material: Mapping[str, Any],
    ) -> bool: ...


class VerityDigestMeasurer(Protocol):
    def measure(self, path: str) -> Tuple[int, str]:
        """Return the kernel-enforced (algorithm id, lowercase hex digest)."""


@dataclass(frozen=True)
class VerityManifestEntryV1:
    path: str
    algorithm_id: int
    fsverity_digest: str
    workload_digest: str

    def validate(self) -> None:
        if not PurePosixPath(self.path).is_absolute():
            raise KernelProjectionError("manifest executable path must be absolute")
        if self.algorithm_id <= 0 or self.algorithm_id > 0xFFFF:
            raise KernelProjectionError("invalid fs-verity algorithm id")
        digest = self.fsverity_digest.lower()
        if len(digest) not in (64, 128):
            raise KernelProjectionError("fs-verity digest must be SHA-256 or SHA-512 sized")
        try:
            bytes.fromhex(digest)
        except ValueError as exc:
            raise KernelProjectionError("fs-verity digest is not hexadecimal") from exc
        if not self.workload_digest.startswith("sha256:"):
            raise KernelProjectionError("entry lacks a content-addressed workload identity")

    @property
    def loader_spec(self) -> str:
        return f"{self.algorithm_id}:{self.fsverity_digest.lower()}"


@dataclass(frozen=True)
class SignedVerityManifestV1:
    manifest_id: str
    generation: int
    environment: str
    audience: str
    node_id: str
    attestation_result_id: str
    attestation_evidence_digest: str
    capability_lease_id: str
    capability_lease_digest: str
    policy_digest: str
    policy_generation: str
    cgroup_id: str
    cgroup_kernel_id: int
    pid_namespace_inode: int
    mount_namespace_inode: int
    issued_at: str
    expires_at: str
    entries: Tuple[VerityManifestEntryV1, ...]
    signature_algorithm: str
    signature: str
    verification_material: Mapping[str, Any]
    schema_version: str = "1.0"

    def unsigned_payload(self) -> Mapping[str, Any]:
        return {
            "schema_version": self.schema_version,
            "manifest_id": self.manifest_id,
            "generation": self.generation,
            "environment": self.environment,
            "audience": self.audience,
            "node_id": self.node_id,
            "attestation_result_id": self.attestation_result_id,
            "attestation_evidence_digest": self.attestation_evidence_digest,
            "capability_lease_id": self.capability_lease_id,
            "capability_lease_digest": self.capability_lease_digest,
            "policy_digest": self.policy_digest,
            "policy_generation": self.policy_generation,
            "cgroup_id": self.cgroup_id,
            "cgroup_kernel_id": self.cgroup_kernel_id,
            "pid_namespace_inode": self.pid_namespace_inode,
            "mount_namespace_inode": self.mount_namespace_inode,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "entries": [entry.__dict__ for entry in self.entries],
            "signature_algorithm": self.signature_algorithm,
            "verification_material": dict(self.verification_material),
        }

    @property
    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(
            canonical_json_bytes(self.unsigned_payload())
        ).hexdigest()


@dataclass(frozen=True)
class VerifiedKernelProjectionV1:
    manifest_id: str
    manifest_digest: str
    generation: int
    node_id: str
    attestation_result_id: str
    capability_lease_id: str
    policy_generation: str
    cgroup_id: str
    cgroup_kernel_id: int
    pid_namespace_inode: int
    mount_namespace_inode: int
    expires_at: str
    loader_digest_specs: Tuple[str, ...]
    verified_paths: Tuple[str, ...]
    enforcement_mode: str = "fsverity_strict"


class ProjectionGenerationStore:
    """Atomic monotonic-generation guard against rollback and split projection."""

    def __init__(self, database_path: str) -> None:
        self._lock = threading.Lock()
        self._db = sqlite3.connect(database_path, check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS arda_kernel_generation ("
            "node_id TEXT PRIMARY KEY, generation INTEGER NOT NULL, "
            "manifest_digest TEXT NOT NULL)"
        )

    def assert_newer(self, node_id: str, generation: int) -> None:
        row = self._db.execute(
            "SELECT generation FROM arda_kernel_generation WHERE node_id = ?",
            (node_id,),
        ).fetchone()
        if row is not None and generation <= int(row[0]):
            raise KernelProjectionError("manifest generation is stale or replayed")

    def commit(self, projection: VerifiedKernelProjectionV1) -> None:
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self.assert_newer(projection.node_id, projection.generation)
                self._db.execute(
                    "INSERT INTO arda_kernel_generation(node_id,generation,manifest_digest) "
                    "VALUES(?,?,?) ON CONFLICT(node_id) DO UPDATE SET "
                    "generation=excluded.generation, manifest_digest=excluded.manifest_digest",
                    (projection.node_id, projection.generation, projection.manifest_digest),
                )
                self._db.execute("COMMIT")
            except Exception:
                self._db.execute("ROLLBACK")
                raise


class StrictArdaKernelProjector:
    def __init__(
        self,
        *,
        signature_verifier: DetachedSignatureVerifier,
        attestation_signature_verifier: DetachedSignatureVerifier,
        capability_signature_verifier: DetachedSignatureVerifier,
        digest_measurer: VerityDigestMeasurer,
        generation_store: ProjectionGenerationStore,
        environment: str,
        audience: str = "arda-kernel-projector",
        maximum_manifest_age_seconds: int = 300,
    ) -> None:
        self._signatures = signature_verifier
        self._attestation_signatures = attestation_signature_verifier
        self._capability_signatures = capability_signature_verifier
        self._measurer = digest_measurer
        self._generations = generation_store
        self._environment = environment
        self._audience = audience
        self._maximum_age = maximum_manifest_age_seconds

    def verify(
        self,
        manifest: SignedVerityManifestV1,
        attestation: ArdaAttestationResultV1,
        capability: BeastCapabilityLeaseV1,
        *,
        now: datetime | None = None,
    ) -> VerifiedKernelProjectionV1:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        failures = []
        if manifest.schema_version != "1.0" or not manifest.manifest_id:
            failures.append("manifest_shape")
        if manifest.generation <= 0 or not manifest.entries:
            failures.append("manifest_generation_or_entries")
        if (
            not manifest.cgroup_id
            or manifest.cgroup_kernel_id <= 0
            or manifest.pid_namespace_inode <= 0
            or manifest.mount_namespace_inode <= 0
        ):
            failures.append("runtime_capsule_binding")
        if manifest.environment != self._environment or manifest.audience != self._audience:
            failures.append("manifest_environment_or_audience")
        issued, expires = parse_utc(manifest.issued_at), parse_utc(manifest.expires_at)
        if issued >= expires or now < issued or now >= expires:
            failures.append("manifest_freshness")
        if (now - issued).total_seconds() > self._maximum_age:
            failures.append("manifest_age")
        if not attestation.accepted:
            failures.append("attestation_rejected")
        if attestation.environment != self._environment or attestation.audience != self._audience:
            failures.append("attestation_environment_or_audience")
        if now >= parse_utc(attestation.expires_at):
            failures.append("attestation_expired")
        if manifest.node_id != attestation.subject_node_id:
            failures.append("node_binding")
        if manifest.attestation_result_id != attestation.result_id:
            failures.append("attestation_result_binding")
        if manifest.attestation_evidence_digest != attestation.evidence_digest:
            failures.append("attestation_evidence_binding")
        try:
            capability.validate_shape()
        except ValueError:
            failures.append("capability_shape")
        capability_digest = "sha256:" + hashlib.sha256(
            canonical_json_bytes(capability.unsigned_payload())
        ).hexdigest()
        if manifest.capability_lease_id != capability.lease_id:
            failures.append("capability_lease_binding")
        if manifest.capability_lease_digest != capability_digest:
            failures.append("capability_digest_binding")
        if capability.node_id != manifest.node_id:
            failures.append("capability_node_binding")
        if capability.attestation_result_id != attestation.result_id:
            failures.append("capability_attestation_binding")
        if capability.attestation_evidence_digest != attestation.evidence_digest:
            failures.append("capability_evidence_binding")
        if capability.policy_generation != manifest.policy_generation:
            failures.append("capability_policy_generation")
        if capability.audience != self._audience:
            failures.append("capability_audience")
        if now >= parse_utc(capability.expires_at):
            failures.append("capability_expired")
        if parse_utc(manifest.expires_at) > parse_utc(capability.expires_at):
            failures.append("projection_outlives_capability")
        if not self._attestation_signatures.verify(
            canonical_json_bytes(attestation.unsigned_payload()),
            attestation.signature,
            attestation.signature_algorithm,
            attestation.verification_material,
        ):
            failures.append("attestation_signature")
        if not self._signatures.verify(
            canonical_json_bytes(manifest.unsigned_payload()),
            manifest.signature,
            manifest.signature_algorithm,
            manifest.verification_material,
        ):
            failures.append("manifest_signature")
        if not self._capability_signatures.verify(
            canonical_json_bytes(capability.unsigned_payload()),
            capability.signature,
            capability.signature_algorithm,
            capability.verification_material,
        ):
            failures.append("capability_signature")
        if failures:
            raise KernelProjectionError("kernel projection veto: " + ",".join(failures))

        self._generations.assert_newer(manifest.node_id, manifest.generation)
        seen_paths, seen_identities = set(), set()
        for entry in manifest.entries:
            entry.validate()
            identity = (entry.algorithm_id, entry.fsverity_digest.lower())
            if entry.path in seen_paths or identity in seen_identities:
                raise KernelProjectionError("duplicate path or digest identity in manifest")
            seen_paths.add(entry.path)
            seen_identities.add(identity)
            actual_algorithm, actual_digest = self._measurer.measure(entry.path)
            if (actual_algorithm, actual_digest.lower()) != identity:
                raise KernelProjectionError("kernel-measured fs-verity digest mismatch")

        return VerifiedKernelProjectionV1(
            manifest_id=manifest.manifest_id,
            manifest_digest=manifest.digest,
            generation=manifest.generation,
            node_id=manifest.node_id,
            attestation_result_id=attestation.result_id,
            capability_lease_id=capability.lease_id,
            policy_generation=manifest.policy_generation,
            cgroup_id=manifest.cgroup_id,
            cgroup_kernel_id=manifest.cgroup_kernel_id,
            pid_namespace_inode=manifest.pid_namespace_inode,
            mount_namespace_inode=manifest.mount_namespace_inode,
            expires_at=manifest.expires_at,
            loader_digest_specs=tuple(entry.loader_spec for entry in manifest.entries),
            verified_paths=tuple(entry.path for entry in manifest.entries),
        )

    def commit(self, projection: VerifiedKernelProjectionV1) -> None:
        """Commit only after the kernel map swap and mode transition succeed."""
        self._generations.commit(projection)


class KernelProjectionSink(Protocol):
    def stage(self, projection: VerifiedKernelProjectionV1) -> None: ...
    def activate(self, generation: int) -> None: ...
    def deactivate(self, generation: int, reason: str) -> None: ...
    def remove(self, generation: int) -> None: ...


class BpftoolPinnedProjectionSink:
    """Live sink for loader-pinned generation maps; never invokes a shell."""

    def __init__(self, pin_root: str = "/sys/fs/bpf/arda", bpftool: str = "/usr/sbin/bpftool"):
        root = os.path.realpath(pin_root)
        if not root.startswith("/sys/fs/bpf/"):
            raise KernelProjectionError("BPF pin root must be beneath /sys/fs/bpf")
        self._generation_map = os.path.join(root, "arda_verity_generation_map")
        self._active_map = os.path.join(root, "arda_active_generation_map")
        self._bpftool = bpftool
        self._staged: dict[int, VerifiedKernelProjectionV1] = {}

    @staticmethod
    def _hex(data: bytes) -> list[str]:
        return [f"{byte:02x}" for byte in data]

    def _run(self, *args: str, json_output: bool = False) -> Any:
        if not os.path.isfile(self._bpftool):
            raise KernelProjectionError("bpftool executable is unavailable")
        command = [self._bpftool]
        if json_output:
            command.append("-j")
        command.extend(args)
        result = subprocess.run(
            command,
            check=False, capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            raise KernelProjectionError("BPF map operation failed: " + result.stderr.strip()[:300])
        return json.loads(result.stdout) if json_output else None

    def stage(self, projection: VerifiedKernelProjectionV1) -> None:
        if projection.generation in self._staged or projection.cgroup_kernel_id <= 0:
            raise KernelProjectionError("invalid or duplicate staged BPF generation")
        try:
            for spec in projection.loader_digest_specs:
                algorithm_text, digest_text = spec.split(":", 1)
                digest = bytes.fromhex(digest_text)
                if len(digest) not in (32, 64):
                    raise ValueError("digest length")
                key = struct.pack(
                    "<QQHH64s4x", projection.cgroup_kernel_id, projection.generation,
                    int(algorithm_text), len(digest), digest.ljust(64, b"\0"),
                )
                self._run("map", "update", "pinned", self._generation_map,
                          "key", "hex", *self._hex(key), "value", "hex", "01", "00", "00", "00", "noexist")
            self._staged[projection.generation] = projection
        except Exception:
            self.remove(projection.generation)
            raise

    def activate(self, generation: int) -> None:
        projection = self._staged.get(generation)
        if projection is None:
            raise KernelProjectionError("BPF generation was not staged")
        self._run("map", "update", "pinned", self._active_map,
                  "key", "hex", *self._hex(struct.pack("<Q", projection.cgroup_kernel_id)),
                  "value", "hex", *self._hex(struct.pack("<Q", generation)), "any")

    def deactivate(self, generation: int, reason: str) -> None:
        projection = self._staged.get(generation)
        if projection is not None:
            self._run("map", "delete", "pinned", self._active_map,
                      "key", "hex", *self._hex(struct.pack("<Q", projection.cgroup_kernel_id)))
            return
        # Reconciliation must survive a userspace restart. Discover any
        # per-cgroup activation pointer that still references this generation.
        entries = self._run("map", "dump", "pinned", self._active_map, json_output=True) or []
        for entry in entries:
            value = bytes(int(part, 16) for part in entry.get("value", []))
            key = bytes(int(part, 16) for part in entry.get("key", []))
            if len(value) == 8 and struct.unpack("<Q", value)[0] == generation:
                self._run("map", "delete", "pinned", self._active_map,
                          "key", "hex", *self._hex(key))

    def remove(self, generation: int) -> None:
        # bpftool JSON supplies exact raw key bytes; delete only the requested generation.
        try:
            entries = self._run("map", "dump", "pinned", self._generation_map, json_output=True) or []
            for entry in entries:
                raw = bytes(int(part, 16) for part in entry.get("key", []))
                if len(raw) >= 16 and struct.unpack_from("<Q", raw, 8)[0] == generation:
                    self._run("map", "delete", "pinned", self._generation_map,
                              "key", "hex", *self._hex(raw))
        finally:
            self._staged.pop(generation, None)


class KernelProjectionReconciler:
    """Two-phase kernel generation activation plus continuous revocation."""

    def __init__(
        self,
        database_path: str,
        *,
        sink: KernelProjectionSink,
        generation_store: ProjectionGenerationStore,
    ) -> None:
        self._sink = sink
        self._generations = generation_store
        self._lock = threading.Lock()
        self._db = sqlite3.connect(database_path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS arda_kernel_projections (
                manifest_digest TEXT PRIMARY KEY,
                generation INTEGER NOT NULL UNIQUE,
                node_id TEXT NOT NULL,
                capability_lease_id TEXT NOT NULL,
                cgroup_id TEXT NOT NULL,
                cgroup_kernel_id INTEGER NOT NULL,
                pid_namespace_inode INTEGER NOT NULL,
                mount_namespace_inode INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                status TEXT NOT NULL,
                activated_at TEXT,
                deactivated_at TEXT,
                deactivation_reason TEXT
            )
            """
        )
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(arda_kernel_projections)")}
        if "cgroup_kernel_id" not in columns:
            self._db.execute(
                "ALTER TABLE arda_kernel_projections ADD COLUMN cgroup_kernel_id INTEGER NOT NULL DEFAULT 0"
            )

    def apply(self, projection: VerifiedKernelProjectionV1) -> None:
        """Stage completely, persist monotonicity, then flip active generation."""
        with self._lock:
            self._generations.assert_newer(projection.node_id, projection.generation)
            previous_generations = tuple(
                int(row[0])
                for row in self._db.execute(
                    "SELECT generation FROM arda_kernel_projections "
                    "WHERE node_id=? AND status='active'",
                    (projection.node_id,),
                ).fetchall()
            )
            self._sink.stage(projection)
            try:
                # Burning a generation before activation is fail-closed: a
                # failed flip must use a fresh generation rather than replay.
                self._generations.commit(projection)
                self._sink.activate(projection.generation)
                now = datetime.now(timezone.utc).isoformat()
                self._db.execute("BEGIN IMMEDIATE")
                self._db.execute(
                    "UPDATE arda_kernel_projections SET status='superseded', "
                    "deactivated_at=?, deactivation_reason='new_generation' "
                    "WHERE node_id=? AND status='active'",
                    (now, projection.node_id),
                )
                self._db.execute(
                    """
                    INSERT INTO arda_kernel_projections(
                        manifest_digest,generation,node_id,capability_lease_id,
                        cgroup_id,cgroup_kernel_id,pid_namespace_inode,mount_namespace_inode,
                        expires_at,status,activated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?, 'active', ?)
                    """,
                    (
                        projection.manifest_digest,
                        projection.generation,
                        projection.node_id,
                        projection.capability_lease_id,
                        projection.cgroup_id,
                        projection.cgroup_kernel_id,
                        projection.pid_namespace_inode,
                        projection.mount_namespace_inode,
                        projection.expires_at,
                        now,
                    ),
                )
                self._db.execute("COMMIT")
                for previous in previous_generations:
                    try:
                        self._sink.remove(previous)
                    except Exception:
                        # The active-generation flip already makes old entries
                        # unreachable; reconciliation can retry physical GC.
                        pass
            except Exception:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                try:
                    self._sink.deactivate(projection.generation, "activation_failed")
                    self._sink.remove(projection.generation)
                finally:
                    pass
                raise

    def reconcile(
        self,
        *,
        now: Optional[datetime] = None,
        revoked_lease_ids: Sequence[str] = (),
        runtime_bindings: Optional[Mapping[str, Tuple[str, int, int]]] = None,
    ) -> Tuple[Mapping[str, Any], ...]:
        instant = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        revoked = set(revoked_lease_ids)
        runtime_bindings = runtime_bindings or {}
        actions = []
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM arda_kernel_projections WHERE status='active'"
            ).fetchall()
            for row in rows:
                reason = None
                if parse_utc(row["expires_at"]) <= instant:
                    reason = "expired"
                elif row["capability_lease_id"] in revoked:
                    reason = "capability_revoked"
                elif row["node_id"] in runtime_bindings:
                    observed = runtime_bindings[row["node_id"]]
                    expected = (
                        row["cgroup_id"],
                        int(row["pid_namespace_inode"]),
                        int(row["mount_namespace_inode"]),
                    )
                    if tuple(observed) != expected:
                        reason = "runtime_binding_drift"
                if reason is None:
                    continue
                generation = int(row["generation"])
                self._sink.deactivate(generation, reason)
                self._sink.remove(generation)
                self._db.execute(
                    "UPDATE arda_kernel_projections SET status='revoked', "
                    "deactivated_at=?, deactivation_reason=? WHERE generation=?",
                    (instant.isoformat(), reason, generation),
                )
                actions.append({"generation": generation, "reason": reason})
        return tuple(actions)

    def active(self, node_id: str) -> Mapping[str, Any]:
        row = self._db.execute(
            "SELECT * FROM arda_kernel_projections WHERE node_id=? AND status='active'",
            (node_id,),
        ).fetchone()
        return dict(row) if row else {}


def create_live_kernel_projection_reconciler(
    state_directory: str,
    *,
    pin_root: str = "/sys/fs/bpf/arda",
    bpftool: str = "/usr/sbin/bpftool",
) -> KernelProjectionReconciler:
    """Construct the production reconciler over loader-pinned BPF maps."""
    os.makedirs(state_directory, mode=0o700, exist_ok=True)
    generations = ProjectionGenerationStore(
        os.path.join(state_directory, "kernel-generations.sqlite3")
    )
    return KernelProjectionReconciler(
        os.path.join(state_directory, "kernel-projections.sqlite3"),
        sink=BpftoolPinnedProjectionSink(pin_root=pin_root, bpftool=bpftool),
        generation_store=generations,
    )
