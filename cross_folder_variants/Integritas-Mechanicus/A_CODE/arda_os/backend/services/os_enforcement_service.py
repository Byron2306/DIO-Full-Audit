import hashlib
import json
import logging
import os
import re
import resource
import shutil
import ctypes
import struct
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

try:
    from services.measured_identity import (
        MeasuredIdentityVerifier,
        MeasuredProjectionGenerationStore,
    )
except Exception:
    from backend.services.measured_identity import (  # type: ignore
        MeasuredIdentityVerifier,
        MeasuredProjectionGenerationStore,
    )

try:
    from services.phase4_attestation_gate import Phase4AttestationGate
except Exception:
    from backend.services.phase4_attestation_gate import Phase4AttestationGate  # type: ignore

try:
    from services.phase4_secret_release import Phase4SecretReleaseService
except Exception:
    from backend.services.phase4_secret_release import Phase4SecretReleaseService  # type: ignore

try:
    from services.phase4_live_attestation import Phase4LiveAttestationService
except Exception:
    from backend.services.phase4_live_attestation import Phase4LiveAttestationService  # type: ignore

try:
    from services.harmonic_engine import HarmonicEngine
except Exception:
    from backend.services.harmonic_engine import HarmonicEngine  # type: ignore

try:
    from services.quantum_security import quantum_security
except Exception:
    try:
        from backend.services.quantum_security import quantum_security
    except Exception:
        quantum_security = None

logger = logging.getLogger(__name__)

_BPF_SYSCALL = 321
_BPF_MAP_LOOKUP_ELEM = 1
_BPF_MAP_UPDATE_ELEM = 2
_BPF_OBJ_GET = 7
_BPF_MAP_DELETE_ELEM = 3
_MAP_ELEM_SIZE = 4096
_libc = ctypes.CDLL("libc.so.6", use_errno=True)


def _bpf(cmd: int, attr_buf: ctypes.Array, attr_size: int) -> int:
    return _libc.syscall(_BPF_SYSCALL, cmd, attr_buf, attr_size)


class _ArdaPolicyState(ctypes.Structure):
    _fields_ = [
        ("generation_hash_prefix", ctypes.c_uint64),
        ("redline_rule_count", ctypes.c_uint32),
        ("projection_flags", ctypes.c_uint32),
    ]


class _ArdaLastDenyEvent(ctypes.Structure):
    _fields_ = [
        ("cgroup_id", ctypes.c_uint64),
        ("active_generation", ctypes.c_uint64),
        ("inode", ctypes.c_uint64),
        ("dev", ctypes.c_uint32),
        ("enforcement_mode", ctypes.c_uint32),
        ("deny_reason", ctypes.c_uint32),
    ]


class OsEnforcementService:
    """
    ARDA OS: Operational Engine.
    Enforces the Hardware-Userspace Contract via the BPF map interface.

    Phase 1 hardening goals:
    - sovereign mode cannot silently degrade into simulation
    - the arming path is inspectable
    - callers can run a focused sovereignty self-test
    """

    BPF_MAP_NAME = "arda_harmony_map"
    MAP_SCHEMA_VERSION = "phase5-policy-v1"
    ENFORCEMENT_MODE_AUDIT = "audit"
    ENFORCEMENT_MODE_LEGACY_INODE = "legacy_inode"
    ENFORCEMENT_MODE_FSVERITY_STRICT = "fsverity_strict"
    LOCKDOWN_DISABLED = 0
    LOCKDOWN_DENY_ALL = 1
    DEFAULT_PIN_ROOT = "/sys/fs/bpf/arda"
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    CANONICAL_BPF_SOURCE = os.path.join(BASE_DIR, "bpf", "arda_physical_lsm.c")
    CANONICAL_BPF_OBJECT = os.path.join(BASE_DIR, "bpf", "arda_physical_lsm.o")
    CANONICAL_LOADER_SOURCE = os.path.join(BASE_DIR, "bpf", "arda_lsm_loader.c")
    CANONICAL_LOADER_BINARY = os.path.join(BASE_DIR, "bpf", "arda_lsm_loader")
    CANONICAL_PIN_ROOT = os.environ.get("ARDA_BPF_PIN_ROOT", DEFAULT_PIN_ROOT)
    REQUIRED_MAPS = {
        "arda_harmony_map": {
            "pin_name": "harmony_map",
            "required": True,
            "purpose": "authoritative harmonic executable allowlist",
            "key_shape": "struct arda_identity { inode, dev }",
            "value_shape": "__u32 harmonic flag",
        },
        "arda_state_map": {
            "pin_name": "state_map",
            "required": True,
            "purpose": "authoritative enforcement mode selector",
            "key_shape": "__u32 index 0",
            "value_shape": "__u32 mode (0=audit, 1=legacy_inode)",
        },
        "arda_deny_count": {
            "pin_name": "deny_count",
            "required": True,
            "purpose": "authoritative cumulative denial telemetry",
            "key_shape": "__u32 index 0",
            "value_shape": "__u64 total denials",
        },
        "arda_policy_state_map": {
            "pin_name": "policy_state_map",
            "required": True,
            "purpose": "constitutional policy generation and red-line projection state",
            "key_shape": "__u32 index 0",
            "value_shape": "struct { __u64 generation_hash_prefix; __u32 redline_rule_count; __u32 projection_flags; }",
        },
        "arda_lockdown_map": {
            "pin_name": "lockdown_map",
            "required": True,
            "purpose": "emergency deny-all control for fail-closed host posture",
            "key_shape": "__u32 index 0",
            "value_shape": "__u32 lockdown mode (0=disabled, 1=deny_all)",
        },
        "arda_last_deny_event_map": {
            "pin_name": "last_deny_event_map",
            "required": True,
            "purpose": "last kernel veto forensic record for measured-exec debugging",
            "key_shape": "__u32 index 0",
            "value_shape": "struct { __u64 cgroup_id; __u64 active_generation; unsigned long inode; unsigned int dev; __u32 enforcement_mode; __u32 deny_reason; }",
        },
    }
    PHASE3_REQUIRED_MAPS = {
        "arda_verity_identity_map": {
            "pin_name": "verity_identity_map",
            "required": True,
            "purpose": "measured executable identity staging keyed by cgroup, generation, and fs-verity digest",
            "key_shape": "struct { __u64 cgroup_id; __u64 generation; __u16 algorithm_id; __u16 digest_size; __u8 digest[64]; }",
            "value_shape": "__u32 allow flag",
        },
        "arda_active_generation_map": {
            "pin_name": "active_generation_map",
            "required": True,
            "purpose": "active measured-generation pointer keyed by cgroup kernel id",
            "key_shape": "__u64 cgroup kernel id",
            "value_shape": "__u64 active generation",
        },
        "arda_measured_exec_map": {
            "pin_name": "measured_exec_map",
            "required": True,
            "purpose": "strict measured executable allowlist keyed by cgroup, generation, inode, and dev",
            "key_shape": "struct { __u64 cgroup_id; __u64 generation; unsigned long inode; unsigned int dev; }",
            "value_shape": "__u32 allow flag",
        },
    }
    DEFAULT_PROJECTION_SEED_PATHS = (
        "/bin/sh",
        "/bin/bash",
        "/usr/bin/bash",
        "/usr/bin/env",
        "/usr/bin/python3",
        "/usr/bin/sudo",
        "/usr/bin/systemctl",
        "/usr/sbin/bpftool",
        "/usr/bin/bpftool",
        "/usr/bin/findmnt",
        "/usr/bin/mokutil",
        "/usr/bin/cat",
        "/usr/bin/ls",
        "/usr/bin/sed",
        "/usr/bin/rg",
    )
    POLICY_PROJECTION_FLAG_REDLINE = 1 << 0
    DENY_REASON_NAMES = {
        0: "none",
        1: "lockdown",
        2: "redline",
        3: "missing_active_generation",
        4: "zero_active_generation",
        5: "measured_exec_miss",
        6: "invalid_mode",
        7: "harmony_miss",
    }
    MEASURED_MANIFEST_SCHEMA_VERSION = "arda.measured_manifest.v1"
    MEASURED_AUDIENCE = "arda-measured-preflight"
    DEFAULT_MEASURED_GENERATION_DB = "/var/lib/arda/projection/arda_measured_generation.sqlite3"

    def __init__(self, bpf_source: str = None, *, arm: bool = True):
        self.sovereign_mode = os.getenv("ARDA_SOVEREIGN_MODE") == "1"
        self.read_only_status = not arm
        self.bpf_source = bpf_source or self._find_bpf_source()
        self.lsm_map = {}
        self.bpf = None
        self.is_authoritative = False
        self.is_simulation = False
        self.attach_verified = False
        self.pin_path = None
        self.last_error = None
        self.last_self_test: Optional[Dict[str, Any]] = None
        self.armed_at: Optional[str] = None
        self.arm_mode = "unarmed"
        self.loader_process: Optional[subprocess.Popen] = None
        self.loader_attempted = False
        self.loader_last_error: Optional[str] = None
        self.fallback_last_error: Optional[str] = None
        self.loader_timeout_seconds = int(os.environ.get("ARDA_LOADER_TIMEOUT_SECONDS", "20"))
        self.enforcement_mode = os.environ.get(
            "ARDA_ENFORCEMENT_MODE",
            self.ENFORCEMENT_MODE_AUDIT,
        ).strip() or self.ENFORCEMENT_MODE_AUDIT
        self.measured_generation_db = os.environ.get(
            "ARDA_MEASURED_GENERATION_DB",
            self.DEFAULT_MEASURED_GENERATION_DB if os.geteuid() == 0 else os.path.join(tempfile.gettempdir(), "arda_measured_generation.sqlite3"),
        )
        self._measured_generation_store = MeasuredProjectionGenerationStore(self.measured_generation_db)
        self._measured_identity_verifier = MeasuredIdentityVerifier(self._measured_generation_store)
        self._phase4_attestation_gate = Phase4AttestationGate()
        self._phase4_secret_release = Phase4SecretReleaseService()
        self._phase4_live_attestation = Phase4LiveAttestationService()
        self._harmonic_engine = HarmonicEngine()

        if not self.bpf_source:
            self._fail_or_degrade("ARDA_LSM: Failed to find physical LSM source file.")
            return

        if arm:
            self._arm_ring0_guard()
        else:
            self._attach_read_only_status()

    def _attach_read_only_status(self) -> None:
        self.is_authoritative = os.path.exists(
            os.path.join(self.CANONICAL_PIN_ROOT, self.REQUIRED_MAPS[self.BPF_MAP_NAME]["pin_name"])
        )
        self.is_simulation = False
        self.attach_verified = self.is_authoritative
        self.arm_mode = "read_only_pinned_maps" if self.is_authoritative else "read_only_unpinned"
        self.pin_path = (
            f"{self.CANONICAL_PIN_ROOT}/harmony_map"
            if self.is_authoritative
            else None
        )

    def _find_bpf_source(self) -> Optional[str]:
        potential_paths = [
            self.CANONICAL_BPF_SOURCE,
            os.path.join(os.getcwd(), "arda_physical_lsm.c"),
            os.path.join(os.getcwd(), "backend", "services", "bpf", "arda_physical_lsm.c"),
        ]
        for path in potential_paths:
            if os.path.exists(path):
                return path
        return None

    def _fail_or_degrade(self, message: str, error: Exception = None):
        self.last_error = f"{message}{': ' + str(error) if error else ''}"
        logger.error(self.last_error)
        if self.sovereign_mode:
            sys.exit(f"FATAL: {self.last_error}")
        self.is_authoritative = False
        self.is_simulation = True
        self.arm_mode = "simulation"

    def _arm_ring0_guard(self):
        if self._can_attempt_loader():
            if self._arm_with_loader():
                return
        try:
            from bcc import BPF

            include_path = os.path.join(os.path.dirname(self.bpf_source), "include")
            cflags = [f"-I{include_path}", "-DARDA_SOVEREIGN_HEADERS"]

            self.bpf = BPF(src_file=self.bpf_source, cflags=cflags)
            self.lsm_map = self.bpf.get_table(self.BPF_MAP_NAME)

            try:
                self.bpf.attach_lsm()
                self.attach_verified = True
                logger.info("RING-0: BPF LSM hook verifiably bound.")
            except Exception as attach_error:
                raise RuntimeError("Authoritative LSM attachment failed") from attach_error

            self._apply_initial_runtime_state()
            self._handle_pinning()

            self.is_authoritative = True
            self.is_simulation = False
            self.arm_mode = "ring0"
            self.armed_at = datetime.now(timezone.utc).isoformat()
            logger.info("RING-0: Arda OS Sovereign Guard Armed.")
        except Exception as error:
            self.bpf = None
            self.lsm_map = {}
            if self.sovereign_mode:
                self._fail_or_degrade("ARDA_LSM: Ring-0 Guard failed to arm", error)
                return

            descriptive_error = f"ARDA_LSM: Ring-0 Guard failed to arm: {error}"
            logger.warning(descriptive_error)
            logger.warning("RING-0 MOCK: Operating in High-Fidelity Sovereign Simulation mode.")
            self.is_authoritative = False
            self.is_simulation = True
            self.arm_mode = "simulation"
            self.fallback_last_error = descriptive_error
            self.last_error = self.loader_last_error or descriptive_error

    def _can_attempt_loader(self) -> bool:
        loader = self.CANONICAL_LOADER_BINARY
        obj = self.CANONICAL_BPF_OBJECT
        return os.path.exists(loader) and os.access(loader, os.X_OK) and os.path.exists(obj)

    def _arm_with_loader(self) -> bool:
        self.loader_attempted = True
        command = [
            self.CANONICAL_LOADER_BINARY,
            self.CANONICAL_BPF_OBJECT,
            "--timeout-seconds",
            str(self.loader_timeout_seconds),
            "--pin-root",
            self.CANONICAL_PIN_ROOT,
            "--enforcement-mode",
            self.enforcement_mode,
        ]
        try:
            self.loader_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            time.sleep(0.2)
            rc = self.loader_process.poll()
            if rc is not None:
                stderr = ""
                if self.loader_process.stderr:
                    stderr = self.loader_process.stderr.read().strip()
                self.loader_last_error = stderr or f"loader exited with code {rc}"
                raise RuntimeError(self.loader_last_error)

            self.is_authoritative = True
            self.is_simulation = False
            self.attach_verified = True
            self.arm_mode = "ring0_loader"
            self.armed_at = datetime.now(timezone.utc).isoformat()
            self.pin_path = f"{self.CANONICAL_PIN_ROOT}/harmony_map"
            logger.info("RING-0: Arda loader path armed.")
            return True
        except Exception as error:
            self.loader_last_error = str(error)
            if self.loader_process and self.loader_process.poll() is None:
                self.loader_process.terminate()
                try:
                    self.loader_process.wait(timeout=1)
                except Exception:
                    self.loader_process.kill()
            if self.loader_process:
                if self.loader_process.stdout:
                    self.loader_process.stdout.close()
                if self.loader_process.stderr:
                    self.loader_process.stderr.close()
            self.loader_process = None
            logger.warning(f"ARDA_LSM: canonical loader arming failed: {error}")
            return False

    def _handle_pinning(self):
        if not os.path.exists("/sys/fs/bpf"):
            logger.warning("RING-0: bpffs not available; skipping pinning.")
            return

        try:
            os.makedirs(self.DEFAULT_PIN_ROOT, exist_ok=True)
            map_pin = f"{self.DEFAULT_PIN_ROOT}/harmony_map"
            if not os.path.exists(map_pin):
                self.lsm_map.pin(map_pin)
            self.pin_path = map_pin
            logger.info(f"RING-0: Persistent map pinned to {map_pin}")
        except Exception as error:
            if self.sovereign_mode:
                raise RuntimeError("Persistent BPF pinning failed in sovereign mode") from error
            logger.warning(f"RING-0: Pinning failed (non-critical in development): {error}")

    def get_status(self) -> Dict[str, Any]:
        live_enforcement_mode = self._get_live_enforcement_mode()
        loader_status = self.get_loader_status()
        map_status = self.get_required_map_status()
        deny_count = self.get_deny_count()
        last_deny_event = self.get_last_deny_event()
        harmonic_runtime = self._build_harmonic_runtime_status(
            live_enforcement_mode=live_enforcement_mode,
            deny_count=deny_count,
        )
        try:
            policy_state = self._read_policy_state()
        except Exception:
            policy_state = None
        try:
            lockdown_mode = self._read_lockdown_mode()
        except Exception:
            lockdown_mode = None
        phase4_secret_release = getattr(self, "_phase4_secret_release", None)
        secret_release_map = (
            phase4_secret_release.SECRET_BUNDLE_ENV_MAP if phase4_secret_release is not None else {}
        )
        return {
            "sovereign_mode": self.sovereign_mode,
            "is_authoritative": self.is_authoritative,
            "is_simulation": self.is_simulation,
            "attach_verified": self.attach_verified,
            "arm_mode": self.arm_mode,
            "enforcement_mode": live_enforcement_mode,
            "map_schema_version": self.MAP_SCHEMA_VERSION,
            "bpf_source": self.bpf_source,
            "map_name": self.BPF_MAP_NAME,
            "pin_path": self.pin_path,
            "armed_at": self.armed_at,
            "last_error": self.last_error,
            "last_self_test": self.last_self_test,
            "loader_attempted": self.loader_attempted,
            "loader_last_error": self.loader_last_error,
            "fallback_last_error": self.fallback_last_error,
            "loader_status": loader_status,
            "required_maps": map_status,
            "policy_projection_state": policy_state,
            "lockdown_mode": lockdown_mode,
            "deny_count": deny_count,
            "last_deny_event": last_deny_event,
            "harmonic_runtime": harmonic_runtime,
            "readiness": self.assess_phase1_readiness(),
            "phase3_measured_identity": {
                "schema_version": self.MEASURED_MANIFEST_SCHEMA_VERSION,
                "audience": self.MEASURED_AUDIENCE,
                "generation_db": self.measured_generation_db,
                "next_mode": self.ENFORCEMENT_MODE_FSVERITY_STRICT,
                "required_map_names": list(self.PHASE3_REQUIRED_MAPS.keys()),
                "required_maps": self.get_phase3_map_status(),
            },
            "phase4_attestation_gate": {
                "audience": self._phase4_attestation_gate.AUDIENCE,
                "release_gate_ready": True,
            },
            "phase4_secret_release": {
                "purposes": list(secret_release_map.keys()),
                "sealed_bundle_env_vars": secret_release_map,
                "seal_key_env": getattr(phase4_secret_release, "SEAL_KEY_ENV", "ARDA_PHASE4_SEAL_KEY"),
            },
            "phase4_live_attestation": {
                "pcr_selection": self._phase4_live_attestation.PCR_SELECTION if hasattr(self, "_phase4_live_attestation") else "sha256:0,1,7,11",
                "required_tools": list(self._phase4_live_attestation.REQUIRED_TOOLS) if hasattr(self, "_phase4_live_attestation") else [],
            },
        }

    def _build_harmonic_runtime_status(
        self,
        *,
        live_enforcement_mode: str,
        deny_count: Optional[int],
    ) -> Dict[str, Any]:
        harmonic_engine = getattr(self, "_harmonic_engine", None)
        if harmonic_engine is None:
            harmonic_engine = HarmonicEngine()
            self._harmonic_engine = harmonic_engine

        actor_id = "root" if os.geteuid() == 0 else "operator"
        target_domain = "kernel.authority" if self.is_authoritative else "userspace.simulation"
        context = {
            "scope_type": "arda_runtime",
            "enforcement_mode": live_enforcement_mode,
            "lockdown_mode": self._read_lockdown_mode(),
            "loader_attempted": self.loader_attempted,
            "attach_verified": self.attach_verified,
            "deny_count": int(deny_count or 0),
            "required_maps_present": bool(self.get_required_map_status().get("all_required_present")),
        }

        harmonic_observation = harmonic_engine.observe(
            actor_id=actor_id,
            tool_name=self.arm_mode,
            target_domain=target_domain,
            operation=self.arm_mode,
            environment="host",
            stage="runtime_status",
            context=context,
            timestamp_ms=time.time() * 1000.0,
        )
        harmonic_state = harmonic_observation["harmonic_state"]
        return {
            "scope": "arda_runtime",
            "baseline_ref": harmonic_observation["baseline_ref"],
            "timing_features": harmonic_observation["timing_features"],
            "resonance_score": harmonic_state["resonance_score"],
            "discord_score": harmonic_state["discord_score"],
            "confidence": harmonic_state["confidence"],
            "drift_norm": harmonic_state["drift_norm"],
            "jitter_norm": harmonic_state["jitter_norm"],
            "burstiness": harmonic_state["burstiness"],
            "entropy_signature": harmonic_state["entropy_signature"],
            "mode_recommendation": harmonic_state["mode_recommendation"],
            "rationale": harmonic_state["rationale"],
            "observation": {
                "arm_mode": self.arm_mode,
                "target_domain": target_domain,
                "enforcement_mode": live_enforcement_mode,
                "attach_verified": self.attach_verified,
                "loader_attempted": self.loader_attempted,
                "deny_count": int(deny_count or 0),
            },
        }

    def get_loader_status(self) -> Dict[str, Any]:
        return {
            "canonical_bpf_source": self.CANONICAL_BPF_SOURCE,
            "canonical_bpf_source_exists": os.path.exists(self.CANONICAL_BPF_SOURCE),
            "canonical_bpf_object": self.CANONICAL_BPF_OBJECT,
            "canonical_bpf_object_exists": os.path.exists(self.CANONICAL_BPF_OBJECT),
            "canonical_loader_source": self.CANONICAL_LOADER_SOURCE,
            "canonical_loader_source_exists": os.path.exists(self.CANONICAL_LOADER_SOURCE),
            "canonical_loader_binary": self.CANONICAL_LOADER_BINARY,
            "canonical_loader_binary_exists": os.path.exists(self.CANONICAL_LOADER_BINARY),
            "preferred_loader_mode": "libbpf_loader" if os.path.exists(self.CANONICAL_LOADER_BINARY) else "bcc_attach",
            "canonical_loader_command": [
                self.CANONICAL_LOADER_BINARY,
                self.CANONICAL_BPF_OBJECT,
                "--timeout-seconds",
                str(self.loader_timeout_seconds),
                "--pin-root",
                self.CANONICAL_PIN_ROOT,
                "--enforcement-mode",
                self.enforcement_mode,
            ],
            "loader_timeout_seconds": self.loader_timeout_seconds,
            "canonical_pin_root": self.CANONICAL_PIN_ROOT,
            "map_schema_version": self.MAP_SCHEMA_VERSION,
            "enforcement_mode": self.enforcement_mode,
            "required_map_names": list(self.REQUIRED_MAPS.keys()),
            "phase3_required_map_names": list(self.PHASE3_REQUIRED_MAPS.keys()),
        }

    def get_required_map_status(self) -> Dict[str, Any]:
        maps: Dict[str, Any] = {}
        all_required_present = True
        enforcement_mode = self._get_live_enforcement_mode()
        declared_source_maps = self._inspect_declared_bpf_maps()
        compiled_object_maps = self._inspect_compiled_bpf_maps()

        for map_name, spec in self.REQUIRED_MAPS.items():
            pin_name = spec.get("pin_name", map_name)
            pin_path = os.path.join(self.CANONICAL_PIN_ROOT, pin_name)
            pin_exists = os.path.exists(pin_path)
            in_process_handle = self._has_runtime_map_handle(map_name)
            source_declared = map_name in declared_source_maps
            object_declared = map_name in compiled_object_maps or pin_name in compiled_object_maps
            present = pin_exists or in_process_handle
            if spec.get("required", False) and not present:
                all_required_present = False

            maps[map_name] = {
                "required": spec.get("required", False),
                "purpose": spec.get("purpose"),
                "key_shape": spec.get("key_shape"),
                "value_shape": spec.get("value_shape"),
                "pin_name": pin_name,
                "pin_path": pin_path,
                "pin_exists": pin_exists,
                "in_process_handle": in_process_handle,
                "source_declared": source_declared,
                "object_declared": object_declared,
                "present": present,
                "runtime_mode_value": self._read_state_map_mode() if map_name == "arda_state_map" else None,
                "lockdown_mode_value": self._read_lockdown_mode() if map_name == "arda_lockdown_map" else None,
            }

        return {
            "schema_version": self.MAP_SCHEMA_VERSION,
            "enforcement_mode": enforcement_mode,
            "all_required_present": all_required_present,
            "declared_source_maps": declared_source_maps,
            "compiled_object_maps": compiled_object_maps,
            "maps": maps,
        }

    def get_phase3_map_status(self) -> Dict[str, Any]:
        maps: Dict[str, Any] = {}
        all_required_present = True
        declared_source_maps = self._inspect_declared_bpf_maps()
        compiled_object_maps = self._inspect_compiled_bpf_maps()

        for map_name, spec in self.PHASE3_REQUIRED_MAPS.items():
            pin_name = spec.get("pin_name", map_name)
            pin_path = os.path.join(self.CANONICAL_PIN_ROOT, pin_name)
            pin_exists = os.path.exists(pin_path)
            in_process_handle = self._has_runtime_map_handle(map_name)
            source_declared = map_name in declared_source_maps
            object_declared = map_name in compiled_object_maps or pin_name in compiled_object_maps
            present = pin_exists or in_process_handle
            if spec.get("required", False) and not present:
                all_required_present = False
            maps[map_name] = {
                "required": spec.get("required", False),
                "purpose": spec.get("purpose"),
                "key_shape": spec.get("key_shape"),
                "value_shape": spec.get("value_shape"),
                "pin_name": pin_name,
                "pin_path": pin_path,
                "pin_exists": pin_exists,
                "in_process_handle": in_process_handle,
                "source_declared": source_declared,
                "object_declared": object_declared,
                "present": present,
            }

        return {
            "schema_version": self.MEASURED_MANIFEST_SCHEMA_VERSION,
            "next_mode": self.ENFORCEMENT_MODE_FSVERITY_STRICT,
            "all_required_present": all_required_present,
            "declared_source_maps": declared_source_maps,
            "compiled_object_maps": compiled_object_maps,
            "active_records": self._measured_generation_store.list_records(states=["active"]),
            "maps": maps,
        }

    def shutdown(self) -> None:
        if self.loader_process and self.loader_process.poll() is None:
            self.loader_process.terminate()
            try:
                self.loader_process.wait(timeout=2)
            except Exception:
                self.loader_process.kill()
                self.loader_process.wait(timeout=2)
        if self.loader_process:
            if self.loader_process.stdout:
                self.loader_process.stdout.close()
            if self.loader_process.stderr:
                self.loader_process.stderr.close()
        self.loader_process = None
        generation_store = getattr(self, "_measured_generation_store", None)
        if generation_store is not None:
            generation_store.close()

    def assess_phase1_readiness(self) -> Dict[str, Any]:
        memlock_soft, memlock_hard = resource.getrlimit(resource.RLIMIT_MEMLOCK)
        unprivileged_bpf_disabled = None
        try:
            with open("/proc/sys/kernel/unprivileged_bpf_disabled", "r", encoding="utf-8") as handle:
                unprivileged_bpf_disabled = handle.read().strip()
        except Exception:
            pass

        blockers = []
        recommendations = []
        ready_for_authoritative_attempt = True

        if not os.path.exists(self.CANONICAL_LOADER_BINARY):
            blockers.append("canonical_loader_binary_missing")
            recommendations.append("Build the canonical loader with sh bin/build_arda_loader.sh")
            ready_for_authoritative_attempt = False

        if not os.path.exists(self.CANONICAL_BPF_OBJECT):
            blockers.append("canonical_bpf_object_missing")
            recommendations.append("Build the canonical BPF object with sh bin/build_arda_bpf.sh")
            ready_for_authoritative_attempt = False

        if os.geteuid() != 0:
            blockers.append("not_running_as_root")
            recommendations.append("Run the authoritative loader path under a host privilege context permitted to load BPF programs")
            ready_for_authoritative_attempt = False

        if memlock_soft != resource.RLIM_INFINITY and memlock_soft < 1024 * 1024:
            blockers.append("memlock_soft_limit_low")
            recommendations.append("Increase RLIMIT_MEMLOCK or run in a context where the loader can raise it")
            ready_for_authoritative_attempt = False

        if os.geteuid() != 0 and unprivileged_bpf_disabled == "2":
            blockers.append("unprivileged_bpf_disabled_strict")
            recommendations.append("Use a privileged host context because unprivileged BPF is disabled by kernel policy")
            ready_for_authoritative_attempt = False

        if self.loader_last_error and "operation not permitted" in self.loader_last_error.lower():
            blockers.append("bpf_load_operation_not_permitted")
            recommendations.append("Verify kernel BPF load permissions, memlock policy, and host execution context")
            ready_for_authoritative_attempt = False

        if self.loader_last_error and "rlimit_memlock" in self.loader_last_error.lower():
            blockers.append("loader_memlock_failure")
            recommendations.append("Run the loader where RLIMIT_MEMLOCK can be raised or is already sufficient")
            ready_for_authoritative_attempt = False

        if self.is_authoritative and not self.pin_path:
            blockers.append("bpffs_pin_not_verified")
            recommendations.append("Verify harmony-map pinning under the intended privileged deployment mode")
            ready_for_authoritative_attempt = False

        map_status = self.get_required_map_status()
        if self.is_authoritative and not map_status["all_required_present"]:
            blockers.append("required_map_contract_incomplete")
            recommendations.append("Verify each required pinned map is present and matches the canonical Arda substrate contract")
            ready_for_authoritative_attempt = False

        return {
            "ready_for_authoritative_attempt": ready_for_authoritative_attempt,
            "blockers": blockers,
            "recommendations": recommendations,
            "context": {
                "euid": os.geteuid(),
                "memlock_soft": memlock_soft,
                "memlock_hard": memlock_hard,
                "unprivileged_bpf_disabled": unprivileged_bpf_disabled,
                "enforcement_mode": self.enforcement_mode,
                "map_schema_version": self.MAP_SCHEMA_VERSION,
                "lockdown_mode": self._read_lockdown_mode(),
            },
        }

    def run_self_test(self, test_executable: Optional[str] = None) -> Dict[str, Any]:
        """
        Phase 1 self-test:
        proves whether Arda is truly armed enough to claim sovereign mode.

        In sovereign mode:
        - the guard must be authoritative
        - the LSM attachment must be verified
        - a test executable path must be supplied so Arda can prove it can
          seed an executable identity into the map without falling back
        """
        result: Dict[str, Any] = {
            "ok": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {
                "authoritative": self.is_authoritative,
                "attach_verified": self.attach_verified,
                "simulation_disabled": not self.is_simulation,
                "map_ready": bool(self.lsm_map),
                "required_maps_ready": self.get_required_map_status()["all_required_present"],
            },
            "details": {},
        }

        if self.sovereign_mode and not self.is_authoritative:
            result["details"]["failure"] = "ring0_guard_not_authoritative"
            self.last_self_test = result
            return result

        if test_executable:
            if not os.path.exists(test_executable):
                result["details"]["failure"] = f"test_executable_missing:{test_executable}"
                self.last_self_test = result
                return result
            map_sync_ok = self.update_workload_harmony(test_executable, is_harmonic=False)
            result["checks"]["map_sync"] = map_sync_ok
        else:
            result["checks"]["map_sync"] = not self.sovereign_mode

        result["ok"] = all(result["checks"].values())
        if not result["ok"] and "failure" not in result["details"]:
            result["details"]["failure"] = "one_or_more_checks_failed"
        self.last_self_test = result
        return result

    def run_native_denial_self_test(self) -> Dict[str, Any]:
        """
        Attempts the strongest Phase 1 proof available in the current environment:
        execute an unharmonic temporary binary and observe whether the kernel vetoes it.

        Honest result model:
        - ok=True only when native denial is directly observed
        - ok=False with a specific failure reason when Arda is unarmed or the
          binary is allowed to run
        - ok=False with a precondition reason when the environment cannot support
          the test yet
        """
        result: Dict[str, Any] = {
            "ok": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {
                "authoritative": self.is_authoritative,
                "attach_verified": self.attach_verified,
                "simulation_disabled": not self.is_simulation,
            },
            "details": {},
        }

        if not self.is_authoritative:
            result["details"]["failure"] = "ring0_guard_not_authoritative"
            return result
        if not self.attach_verified:
            result["details"]["failure"] = "lsm_attach_not_verified"
            return result
        if self.is_simulation:
            result["details"]["failure"] = "simulation_mode_active"
            return result

        with tempfile.TemporaryDirectory(prefix="arda-phase1-") as temp_dir:
            probe_path = os.path.join(temp_dir, "unharmonic_probe")
            source_probe = shutil.which("true") or "/bin/true"
            if not os.path.exists(source_probe):
                result["details"]["failure"] = "missing_probe_source_binary"
                result["details"]["probe_source"] = source_probe
                return result

            shutil.copy2(source_probe, probe_path)
            os.chmod(probe_path, 0o755)

            command = [probe_path]
            try:
                completed = subprocess.run(command, capture_output=True, text=True, check=False)
                result["details"]["returncode"] = completed.returncode
                result["details"]["stdout"] = completed.stdout.strip()
                result["details"]["stderr"] = completed.stderr.strip()

                if completed.returncode != 0:
                    result["checks"]["native_denial_observed"] = True
                    result["ok"] = True
                else:
                    result["checks"]["native_denial_observed"] = False
                    result["details"]["failure"] = "unharmonic_binary_executed"
            except PermissionError as error:
                result["checks"]["native_denial_observed"] = True
                result["details"]["exception"] = f"PermissionError: {error}"
                result["ok"] = True
            except OSError as error:
                result["details"]["exception"] = f"OSError: {error}"
                result["details"]["errno"] = getattr(error, "errno", None)
                native_deny = getattr(error, "errno", None) in (1, 13)
                result["checks"]["native_denial_observed"] = native_deny
                result["ok"] = native_deny
                if not native_deny:
                    result["details"]["failure"] = "unexpected_oserror"

        return result

    def update_workload_harmony(
        self,
        executable_path: str,
        is_harmonic: bool,
        quantum_signature: Any = None,
    ) -> bool:
        """
        Synchronizes workload identity into the Ring-0 BPF map.
        If ARDA_SOVEREIGN_MODE is 1, a valid PQC signature is REQUIRED for
        harmonic transition.
        """
        if is_harmonic and self.sovereign_mode:
            if not quantum_security:
                logger.error("ARDA_LSM: Quantum Security Service unavailable at Ring-1.")
                return False

            if not quantum_signature:
                logger.error(f"ARDA_LSM: Ignition VETOED. Missing PQC signature for {executable_path}")
                return False

            try:
                with open(executable_path, "rb") as handle:
                    file_hash = hashlib.sha256(handle.read()).hexdigest()

                if not self._verify_manifest_integrity(executable_path, file_hash):
                    logger.critical(
                        f"ARDA_LSM: [MANIFEST VETO] {executable_path} hash {file_hash} not found in manifest."
                    )
                    return False

                red_lines = ["crontab", "shadow", "sudoers", "passwd"]
                consensus = quantum_signature.get("consensus", {})
                action = consensus.get("action", "ESCALATE_TO_COUNCIL")

                if any(rl in executable_path.lower() for rl in red_lines) and action == "AUTONOMOUS_GRANT":
                    logger.critical(
                        f"ARDA_RED_LINE_VETO: Council attempted autonomous grant for CRITICAL path {executable_path}. VETOED."
                    )
                    return False

                harmony_index = consensus.get("harmony_index", 0.0)
                logger.info(
                    "ARDA_LSM: [CHORAL AUDIT] Action=%s Harmony=%.2f Lawful=%s/%s",
                    action,
                    harmony_index,
                    consensus.get("lawful_count", 0),
                    consensus.get("total_witnesses", 0),
                )

                if action == "AUTONOMOUS_GRANT" and harmony_index < 0.6:
                    logger.critical(
                        f"ARDA_LSM: [DISSONANCE VETO] Choral Harmony too weak for autonomous grant ({harmony_index:.2f})."
                    )
                    return False
                if harmony_index < 0.5:
                    logger.critical(f"ARDA_LSM: [MELKOR VETO] High dissonance ({harmony_index:.2f}). Gate closed.")
                    return False

                norm_path = os.path.abspath(executable_path).lower()
                consensus_reached = consensus.get("consensus_reached", False)
                lawful_count = consensus.get("lawful_count", 0)
                consensus_summary = (
                    f"Consensus:{consensus_reached}:Lawful:{lawful_count}:Action:{action}:Harmony:{harmony_index:.2f}"
                )
                payload = f"{norm_path}:True:{consensus_summary}".encode("utf-8")

                pqc_mode = getattr(quantum_security, "mode", "simulation")
                sig_valid = quantum_security.dilithium_verify(
                    public_key=quantum_signature.get("public_key"),
                    data=payload,
                    signature=quantum_signature.get("signature"),
                )
                if pqc_mode != "simulation" and not sig_valid:
                    logger.critical(f"ARDA_LSM: [SIGNATURE VETO] Production PQC seal broken for {executable_path}")
                    return False
                logger.info(
                    "ARDA_LSM: [SIM-PQC] Advisory seal check: %s",
                    "valid" if sig_valid else "advisory-only (key drift in simulation)",
                )
            except Exception as error:
                logger.error(f"ARDA_LSM: [FRACTURE] Semantic Downgrade failed: {error}")
                return False

        if not self.bpf:
            if self.sovereign_mode:
                logger.critical("ARDA_LSM: Sovereign map sync attempted without an armed Ring-0 guard.")
                return False
            self.lsm_map[executable_path] = 1 if is_harmonic else 0
            logger.warning(
                f"RING-0 MOCK: Syncing {executable_path} -> {'HARMONIC' if is_harmonic else 'FALLEN'}"
            )
            return True

        try:
            self._set_runtime_enforcement_mode(self.ENFORCEMENT_MODE_LEGACY_INODE)
            stat = os.stat(executable_path)
            key = self.lsm_map.Key(stat.st_ino, stat.st_dev)
            self.lsm_map[key] = self.lsm_map.Leaf(1 if is_harmonic else 0)
            logger.info(
                "RING-0 SYNC: %s (Inode:%s Dev:%s) -> %s",
                executable_path,
                stat.st_ino,
                stat.st_dev,
                "HARMONIC" if is_harmonic else "FALLEN",
            )
            return True
        except Exception as error:
            logger.error(f"ARDA_LSM: Map synchronization failure: {error}")
            return False

    def _has_runtime_map_handle(self, map_name: str) -> bool:
        bpf_handle = getattr(self, "bpf", None)
        if bpf_handle:
            try:
                return bpf_handle.get_table(map_name) is not None
            except Exception:
                return False
        if map_name == self.BPF_MAP_NAME:
            return bool(getattr(self, "lsm_map", {})) or (
                getattr(self, "is_authoritative", False) and getattr(self, "arm_mode", None) == "ring0_loader"
            )
        if getattr(self, "is_authoritative", False) and getattr(self, "arm_mode", None) == "ring0_loader":
            return True
        return False

    def _set_runtime_enforcement_mode(self, mode: str) -> bool:
        bpf_handle = getattr(self, "bpf", None)
        if not bpf_handle:
            return True
        if mode == self.ENFORCEMENT_MODE_AUDIT:
            numeric_mode = 0
        elif mode == self.ENFORCEMENT_MODE_LEGACY_INODE:
            numeric_mode = 1
        else:
            numeric_mode = 2
        try:
            state_map = bpf_handle.get_table("arda_state_map")
            state_map[state_map.Key(0)] = state_map.Leaf(numeric_mode)
            self.enforcement_mode = mode
            return True
        except Exception as error:
            logger.warning(f"ARDA_LSM: Failed to set runtime enforcement mode {mode}: {error}")
            return False

    def _read_state_map_mode(self) -> Optional[int]:
        bpf_handle = getattr(self, "bpf", None)
        if bpf_handle:
            try:
                state_map = bpf_handle.get_table("arda_state_map")
                return int(state_map[state_map.Key(0)].value)
            except Exception:
                pass
        try:
            return self._read_pinned_u32_scalar(self.REQUIRED_MAPS["arda_state_map"]["pin_name"])
        except Exception:
            return None

    def _read_lockdown_mode(self) -> Optional[int]:
        bpf_handle = getattr(self, "bpf", None)
        if bpf_handle:
            try:
                lockdown_map = bpf_handle.get_table("arda_lockdown_map")
                return int(lockdown_map[lockdown_map.Key(0)].value)
            except Exception:
                pass
        try:
            return self._read_pinned_u32_scalar(self.REQUIRED_MAPS["arda_lockdown_map"]["pin_name"])
        except Exception:
            return None

    def set_emergency_lockdown(self, enabled: bool) -> bool:
        mode = self.LOCKDOWN_DENY_ALL if enabled else self.LOCKDOWN_DISABLED
        bpf_handle = getattr(self, "bpf", None)
        if bpf_handle:
            try:
                lockdown_map = bpf_handle.get_table("arda_lockdown_map")
                lockdown_map[lockdown_map.Key(0)] = lockdown_map.Leaf(mode)
                return True
            except Exception as error:
                logger.warning(f"ARDA_LSM: Failed to set in-process lockdown mode: {error}")
                return False
        try:
            self._project_lockdown_mode(mode)
            return True
        except Exception as error:
            logger.warning(f"ARDA_LSM: Failed to set pinned lockdown mode: {error}")
            return False

    def _map_numeric_mode_to_name(self, numeric_mode: Optional[int]) -> str:
        if numeric_mode == 0:
            return self.ENFORCEMENT_MODE_AUDIT
        if numeric_mode == 1:
            return self.ENFORCEMENT_MODE_LEGACY_INODE
        if numeric_mode == 2:
            return self.ENFORCEMENT_MODE_FSVERITY_STRICT
        return getattr(self, "enforcement_mode", self.ENFORCEMENT_MODE_LEGACY_INODE)

    def _get_live_enforcement_mode(self) -> str:
        return self._map_numeric_mode_to_name(self._read_state_map_mode())

    def _apply_initial_runtime_state(self) -> None:
        target_mode = self.enforcement_mode
        if target_mode not in {
            self.ENFORCEMENT_MODE_AUDIT,
            self.ENFORCEMENT_MODE_LEGACY_INODE,
            self.ENFORCEMENT_MODE_FSVERITY_STRICT,
        }:
            target_mode = self.ENFORCEMENT_MODE_LEGACY_INODE
        self._set_runtime_enforcement_mode(target_mode)

    def _verify_manifest_integrity(self, path: str, current_hash: str) -> bool:
        potential_manifests = [
            "/etc/arda/sovereign_manifest.json",
            os.path.join(os.getcwd(), "sovereign_manifest.json"),
        ]
        manifest_path = next((candidate for candidate in potential_manifests if os.path.exists(candidate)), None)
        if not manifest_path:
            logger.warning("ARDA_LSM: Sovereign Manifest missing.")
            return False

        try:
            with open(manifest_path, "r") as handle:
                manifest = json.load(handle)

            norm_path = os.path.abspath(path).lower().replace("\\", "/")
            normalized_manifest = {k.lower().replace("\\", "/"): v for k, v in manifest.items()}
            expected_hash = normalized_manifest.get(norm_path)
            return current_hash == expected_hash
        except Exception as error:
            logger.error(f"ARDA_LSM: Manifest verification failure: {error}")
            return False

    def _inspect_declared_bpf_maps(self) -> list[str]:
        bpf_source = getattr(self, "bpf_source", None)
        if not bpf_source or not os.path.exists(bpf_source):
            return []
        try:
            with open(bpf_source, "r", encoding="utf-8") as handle:
                source = handle.read()
        except Exception:
            return []

        pattern = re.compile(r"}\s+([a-zA-Z0-9_]+)\s+SEC\(\"\.maps\"\);")
        declared = pattern.findall(source)
        return sorted(set(declared))

    def _inspect_compiled_bpf_maps(self) -> list[str]:
        bpf_object = self.CANONICAL_BPF_OBJECT
        if not bpf_object or not os.path.exists(bpf_object):
            return []
        if shutil.which("bpftool") is None:
            return []
        try:
            result = subprocess.run(
                ["bpftool", "btf", "dump", "file", bpf_object, "format", "raw"],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            return []
        if result.returncode != 0:
            return []
        pattern = re.compile(r"VAR '([^']+)'")
        return sorted(set(pattern.findall(result.stdout)))

    def _open_pinned_map_fd(self, pin_path: str) -> int:
        path_bytes = os.fsencode(pin_path) + b"\x00"
        path_buf = ctypes.create_string_buffer(path_bytes)
        attr = (ctypes.c_uint8 * _MAP_ELEM_SIZE)()
        path_addr = ctypes.addressof(path_buf)
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            struct.pack_into("<Q", attr, 0, path_addr)
        else:
            struct.pack_into("<I", attr, 0, path_addr)
        fd = _bpf(_BPF_OBJ_GET, attr, _MAP_ELEM_SIZE)
        if fd < 0:
            errno_value = ctypes.get_errno()
            raise OSError(errno_value, f"Failed to open pinned BPF map {pin_path}")
        return fd

    def _update_pinned_harmony_entry(self, executable_path: str, is_harmonic: bool) -> Dict[str, Any]:
        stat = os.stat(executable_path)
        pin_path = os.path.join(self.CANONICAL_PIN_ROOT, self.REQUIRED_MAPS[self.BPF_MAP_NAME]["pin_name"])
        fd = self._open_pinned_map_fd(pin_path)
        try:
            kernel_dev = self._kernel_device_value(stat.st_dev)
            key_buf = (ctypes.c_uint8 * 16)(*struct.pack("<QI4x", stat.st_ino, kernel_dev))
            value_buf = (ctypes.c_uint8 * 4)(*struct.pack("<I", 1 if is_harmonic else 0))
            attr = (ctypes.c_uint8 * _MAP_ELEM_SIZE)()
            struct.pack_into("<I", attr, 0, fd)
            key_addr = ctypes.addressof(key_buf)
            value_addr = ctypes.addressof(value_buf)
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                struct.pack_into("<Q", attr, 8, key_addr)
                struct.pack_into("<Q", attr, 16, value_addr)
            else:
                struct.pack_into("<I", attr, 8, key_addr)
                struct.pack_into("<I", attr, 12, value_addr)
            rc = _bpf(_BPF_MAP_UPDATE_ELEM, attr, _MAP_ELEM_SIZE)
            if rc != 0:
                errno_value = ctypes.get_errno()
                raise OSError(errno_value, f"Failed to project harmony entry for {executable_path}")
            return {
                "path": executable_path,
                "inode": stat.st_ino,
                "dev": kernel_dev,
                "raw_dev": stat.st_dev,
                "harmonic": is_harmonic,
            }
        finally:
            os.close(fd)

    def _project_state_mode(self, mode: str) -> str:
        if mode == self.ENFORCEMENT_MODE_AUDIT:
            numeric_mode = 0
        elif mode == self.ENFORCEMENT_MODE_LEGACY_INODE:
            numeric_mode = 1
        else:
            numeric_mode = 2
        pin_path = os.path.join(self.CANONICAL_PIN_ROOT, self.REQUIRED_MAPS["arda_state_map"]["pin_name"])
        fd = self._open_pinned_map_fd(pin_path)
        try:
            key_buf = (ctypes.c_uint8 * 4)(*struct.pack("<I", 0))
            value_buf = (ctypes.c_uint8 * 4)(*struct.pack("<I", numeric_mode))
            attr = (ctypes.c_uint8 * _MAP_ELEM_SIZE)()
            struct.pack_into("<I", attr, 0, fd)
            key_addr = ctypes.addressof(key_buf)
            value_addr = ctypes.addressof(value_buf)
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                struct.pack_into("<Q", attr, 8, key_addr)
                struct.pack_into("<Q", attr, 16, value_addr)
            else:
                struct.pack_into("<I", attr, 8, key_addr)
                struct.pack_into("<I", attr, 12, value_addr)
            rc = _bpf(_BPF_MAP_UPDATE_ELEM, attr, _MAP_ELEM_SIZE)
            if rc != 0:
                errno_value = ctypes.get_errno()
                raise OSError(errno_value, f"Failed to project state mode {mode}")
            self.enforcement_mode = mode
            return mode
        finally:
            os.close(fd)

    def _project_lockdown_mode(self, mode: int) -> int:
        pin_path = os.path.join(self.CANONICAL_PIN_ROOT, self.REQUIRED_MAPS["arda_lockdown_map"]["pin_name"])
        fd = self._open_pinned_map_fd(pin_path)
        try:
            key_buf = (ctypes.c_uint8 * 4)(*struct.pack("<I", 0))
            value_buf = (ctypes.c_uint8 * 4)(*struct.pack("<I", mode))
            attr = (ctypes.c_uint8 * _MAP_ELEM_SIZE)()
            struct.pack_into("<I", attr, 0, fd)
            key_addr = ctypes.addressof(key_buf)
            value_addr = ctypes.addressof(value_buf)
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                struct.pack_into("<Q", attr, 8, key_addr)
                struct.pack_into("<Q", attr, 16, value_addr)
            else:
                struct.pack_into("<I", attr, 8, key_addr)
                struct.pack_into("<I", attr, 12, value_addr)
            rc = _bpf(_BPF_MAP_UPDATE_ELEM, attr, _MAP_ELEM_SIZE)
            if rc != 0:
                errno_value = ctypes.get_errno()
                raise OSError(errno_value, f"Failed to project lockdown mode {mode}")
            return mode
        finally:
            os.close(fd)

    def _read_pinned_u64_scalar(self, map_pin_name: str) -> Optional[int]:
        pin_path = os.path.join(self.CANONICAL_PIN_ROOT, map_pin_name)
        fd = self._open_pinned_map_fd(pin_path)
        try:
            key_buf = (ctypes.c_uint8 * 4)(*struct.pack("<I", 0))
            value_buf = (ctypes.c_uint8 * 8)()
            attr = (ctypes.c_uint8 * _MAP_ELEM_SIZE)()
            struct.pack_into("<I", attr, 0, fd)
            key_addr = ctypes.addressof(key_buf)
            value_addr = ctypes.addressof(value_buf)
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                struct.pack_into("<Q", attr, 8, key_addr)
                struct.pack_into("<Q", attr, 16, value_addr)
            else:
                struct.pack_into("<I", attr, 8, key_addr)
                struct.pack_into("<I", attr, 12, value_addr)
            rc = _bpf(_BPF_MAP_LOOKUP_ELEM, attr, _MAP_ELEM_SIZE)
            if rc != 0:
                errno_value = ctypes.get_errno()
                if errno_value in (2,):
                    return None
                raise OSError(errno_value, f"Failed to read scalar map {pin_path}")
            return int(struct.unpack("<Q", bytes(value_buf))[0])
        finally:
            os.close(fd)

    def _read_pinned_u32_scalar(self, map_pin_name: str) -> Optional[int]:
        pin_path = os.path.join(self.CANONICAL_PIN_ROOT, map_pin_name)
        fd = self._open_pinned_map_fd(pin_path)
        try:
            key_buf = (ctypes.c_uint8 * 4)(*struct.pack("<I", 0))
            value_buf = (ctypes.c_uint8 * 4)()
            attr = (ctypes.c_uint8 * _MAP_ELEM_SIZE)()
            struct.pack_into("<I", attr, 0, fd)
            key_addr = ctypes.addressof(key_buf)
            value_addr = ctypes.addressof(value_buf)
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                struct.pack_into("<Q", attr, 8, key_addr)
                struct.pack_into("<Q", attr, 16, value_addr)
            else:
                struct.pack_into("<I", attr, 8, key_addr)
                struct.pack_into("<I", attr, 12, value_addr)
            rc = _bpf(_BPF_MAP_LOOKUP_ELEM, attr, _MAP_ELEM_SIZE)
            if rc != 0:
                errno_value = ctypes.get_errno()
                if errno_value in (2,):
                    return None
                raise OSError(errno_value, f"Failed to read scalar map {pin_path}")
            return int(struct.unpack("<I", bytes(value_buf))[0])
        finally:
            os.close(fd)

    def _project_policy_state(self, policy_generation: str, redline_rule_count: int) -> Dict[str, Any]:
        pin_path = os.path.join(self.CANONICAL_PIN_ROOT, self.REQUIRED_MAPS["arda_policy_state_map"]["pin_name"])
        fd = self._open_pinned_map_fd(pin_path)
        try:
            generation_hash_prefix = struct.unpack(
                "<Q",
                hashlib.sha256(policy_generation.encode("utf-8")).digest()[:8],
            )[0]
            projection_flags = self.POLICY_PROJECTION_FLAG_REDLINE if redline_rule_count > 0 else 0
            key_buf = (ctypes.c_uint8 * 4)(*struct.pack("<I", 0))
            value_struct = _ArdaPolicyState(
                generation_hash_prefix=generation_hash_prefix,
                redline_rule_count=redline_rule_count,
                projection_flags=projection_flags,
            )
            value_addr = ctypes.addressof(value_struct)
            attr = (ctypes.c_uint8 * _MAP_ELEM_SIZE)()
            struct.pack_into("<I", attr, 0, fd)
            key_addr = ctypes.addressof(key_buf)
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                struct.pack_into("<Q", attr, 8, key_addr)
                struct.pack_into("<Q", attr, 16, value_addr)
            else:
                struct.pack_into("<I", attr, 8, key_addr)
                struct.pack_into("<I", attr, 12, value_addr)
            rc = _bpf(_BPF_MAP_UPDATE_ELEM, attr, _MAP_ELEM_SIZE)
            if rc != 0:
                errno_value = ctypes.get_errno()
                raise OSError(errno_value, f"Failed to project policy state {policy_generation}")
            return {
                "policy_generation": policy_generation,
                "generation_hash_prefix": generation_hash_prefix,
                "redline_rule_count": redline_rule_count,
                "projection_flags": projection_flags,
            }
        finally:
            os.close(fd)

    def _read_policy_state(self) -> Optional[Dict[str, int]]:
        pin_path = os.path.join(self.CANONICAL_PIN_ROOT, self.REQUIRED_MAPS["arda_policy_state_map"]["pin_name"])
        fd = self._open_pinned_map_fd(pin_path)
        try:
            key_buf = (ctypes.c_uint8 * 4)(*struct.pack("<I", 0))
            value_struct = _ArdaPolicyState()
            attr = (ctypes.c_uint8 * _MAP_ELEM_SIZE)()
            struct.pack_into("<I", attr, 0, fd)
            key_addr = ctypes.addressof(key_buf)
            value_addr = ctypes.addressof(value_struct)
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                struct.pack_into("<Q", attr, 8, key_addr)
                struct.pack_into("<Q", attr, 16, value_addr)
            else:
                struct.pack_into("<I", attr, 8, key_addr)
                struct.pack_into("<I", attr, 12, value_addr)
            rc = _bpf(_BPF_MAP_LOOKUP_ELEM, attr, _MAP_ELEM_SIZE)
            if rc != 0:
                errno_value = ctypes.get_errno()
                if errno_value in (2,):
                    return None
                raise OSError(errno_value, f"Failed to read policy state map {pin_path}")
            return {
                "generation_hash_prefix": int(value_struct.generation_hash_prefix),
                "redline_rule_count": int(value_struct.redline_rule_count),
                "projection_flags": int(value_struct.projection_flags),
            }
        finally:
            os.close(fd)

    def get_deny_count(self) -> Optional[int]:
        try:
            return self._read_pinned_u64_scalar(self.REQUIRED_MAPS["arda_deny_count"]["pin_name"])
        except Exception:
            return None

    def get_last_deny_event(self) -> Optional[Dict[str, Any]]:
        pin_path = os.path.join(self.CANONICAL_PIN_ROOT, self.REQUIRED_MAPS["arda_last_deny_event_map"]["pin_name"])
        try:
            fd = self._open_pinned_map_fd(pin_path)
        except Exception:
            return None
        try:
            key_buf = (ctypes.c_uint8 * 4)(*struct.pack("<I", 0))
            value_struct = _ArdaLastDenyEvent()
            attr = (ctypes.c_uint8 * _MAP_ELEM_SIZE)()
            struct.pack_into("<I", attr, 0, fd)
            key_addr = ctypes.addressof(key_buf)
            value_addr = ctypes.addressof(value_struct)
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                struct.pack_into("<Q", attr, 8, key_addr)
                struct.pack_into("<Q", attr, 16, value_addr)
            else:
                struct.pack_into("<I", attr, 8, key_addr)
                struct.pack_into("<I", attr, 12, value_addr)
            rc = _bpf(_BPF_MAP_LOOKUP_ELEM, attr, _MAP_ELEM_SIZE)
            if rc != 0:
                errno_value = ctypes.get_errno()
                if errno_value in (2,):
                    return None
                raise OSError(errno_value, f"Failed to read last deny event map {pin_path}")
            deny_reason = int(value_struct.deny_reason)
            return {
                "cgroup_id": int(value_struct.cgroup_id),
                "active_generation": int(value_struct.active_generation),
                "inode": int(value_struct.inode),
                "dev": int(value_struct.dev),
                "enforcement_mode_value": int(value_struct.enforcement_mode),
                "enforcement_mode": self._mode_value_to_name(int(value_struct.enforcement_mode)),
                "deny_reason_value": deny_reason,
                "deny_reason": self.DENY_REASON_NAMES.get(deny_reason, f"unknown_{deny_reason}"),
            }
        finally:
            os.close(fd)

    def _mode_value_to_name(self, mode_value: int) -> str:
        if mode_value == 0:
            return self.ENFORCEMENT_MODE_AUDIT
        if mode_value == 1:
            return self.ENFORCEMENT_MODE_LEGACY_INODE
        if mode_value == 2:
            return self.ENFORCEMENT_MODE_FSVERITY_STRICT
        return f"unknown_{mode_value}"

    @staticmethod
    def _parse_loader_digest_spec(loader_spec: str) -> tuple[int, bytes]:
        algorithm_text, digest_text = loader_spec.split(":", 1)
        digest_bytes = bytes.fromhex(digest_text)
        if len(digest_bytes) not in (32, 64):
            raise ValueError(f"unsupported digest size in loader spec: {loader_spec}")
        return int(algorithm_text), digest_bytes

    @staticmethod
    def _kernel_device_value(device: int) -> int:
        major_value = os.major(device)
        minor_value = os.minor(device)
        return ((major_value & 0xFFF) << 20) | (minor_value & 0xFFFFF)

    @staticmethod
    def _build_verity_identity_key(
        cgroup_kernel_id: int,
        generation: int,
        algorithm_id: int,
        digest_bytes: bytes,
    ) -> bytes:
        return struct.pack(
            "<QQHH64s4x",
            cgroup_kernel_id,
            generation,
            algorithm_id,
            len(digest_bytes),
            digest_bytes.ljust(64, b"\0"),
        )

    @staticmethod
    def _build_measured_exec_key(cgroup_kernel_id: int, generation: int, path: str) -> bytes:
        stat_result = os.stat(path)
        return struct.pack(
            "<QQQI4x",
            cgroup_kernel_id,
            generation,
            stat_result.st_ino,
            OsEnforcementService._kernel_device_value(stat_result.st_dev),
        )

    def _stage_pinned_measured_exec(
        self,
        *,
        cgroup_kernel_id: int,
        generation: int,
        path: str,
    ) -> Dict[str, Any]:
        pin_path = os.path.join(self.CANONICAL_PIN_ROOT, self.PHASE3_REQUIRED_MAPS["arda_measured_exec_map"]["pin_name"])
        fd = self._open_pinned_map_fd(pin_path)
        try:
            key_bytes = self._build_measured_exec_key(cgroup_kernel_id, generation, path)
            key_buf = (ctypes.c_uint8 * len(key_bytes))(*key_bytes)
            value_buf = (ctypes.c_uint8 * 4)(*struct.pack("<I", 1))
            attr = (ctypes.c_uint8 * _MAP_ELEM_SIZE)()
            struct.pack_into("<I", attr, 0, fd)
            key_addr = ctypes.addressof(key_buf)
            value_addr = ctypes.addressof(value_buf)
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                struct.pack_into("<Q", attr, 8, key_addr)
                struct.pack_into("<Q", attr, 16, value_addr)
            else:
                struct.pack_into("<I", attr, 8, key_addr)
                struct.pack_into("<I", attr, 12, value_addr)
            rc = _bpf(_BPF_MAP_UPDATE_ELEM, attr, _MAP_ELEM_SIZE)
            if rc != 0:
                errno_value = ctypes.get_errno()
                raise OSError(errno_value, f"Failed to stage measured executable {path}")
            stat_result = os.stat(path)
            kernel_dev = self._kernel_device_value(stat_result.st_dev)
            return {
                "cgroup_kernel_id": cgroup_kernel_id,
                "generation": generation,
                "path": path,
                "inode": stat_result.st_ino,
                "dev": kernel_dev,
                "raw_dev": stat_result.st_dev,
            }
        finally:
            os.close(fd)

    def _delete_pinned_measured_exec(
        self,
        *,
        cgroup_kernel_id: int,
        generation: int,
        path: str,
    ) -> Dict[str, Any]:
        pin_path = os.path.join(self.CANONICAL_PIN_ROOT, self.PHASE3_REQUIRED_MAPS["arda_measured_exec_map"]["pin_name"])
        fd = self._open_pinned_map_fd(pin_path)
        try:
            key_bytes = self._build_measured_exec_key(cgroup_kernel_id, generation, path)
            key_buf = (ctypes.c_uint8 * len(key_bytes))(*key_bytes)
            attr = (ctypes.c_uint8 * _MAP_ELEM_SIZE)()
            struct.pack_into("<I", attr, 0, fd)
            key_addr = ctypes.addressof(key_buf)
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                struct.pack_into("<Q", attr, 8, key_addr)
            else:
                struct.pack_into("<I", attr, 8, key_addr)
            rc = _bpf(_BPF_MAP_DELETE_ELEM, attr, _MAP_ELEM_SIZE)
            if rc != 0:
                errno_value = ctypes.get_errno()
                raise OSError(errno_value, f"Failed to delete measured executable {path}")
            return {"cgroup_kernel_id": cgroup_kernel_id, "generation": generation, "path": path}
        finally:
            os.close(fd)

    def _stage_pinned_verity_identity(
        self,
        *,
        cgroup_kernel_id: int,
        generation: int,
        loader_spec: str,
    ) -> Dict[str, Any]:
        algorithm_id, digest_bytes = self._parse_loader_digest_spec(loader_spec)
        pin_path = os.path.join(self.CANONICAL_PIN_ROOT, self.PHASE3_REQUIRED_MAPS["arda_verity_identity_map"]["pin_name"])
        fd = self._open_pinned_map_fd(pin_path)
        try:
            key_bytes = self._build_verity_identity_key(
                cgroup_kernel_id,
                generation,
                algorithm_id,
                digest_bytes,
            )
            key_buf = (ctypes.c_uint8 * len(key_bytes))(*key_bytes)
            value_buf = (ctypes.c_uint8 * 4)(*struct.pack("<I", 1))
            attr = (ctypes.c_uint8 * _MAP_ELEM_SIZE)()
            struct.pack_into("<I", attr, 0, fd)
            key_addr = ctypes.addressof(key_buf)
            value_addr = ctypes.addressof(value_buf)
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                struct.pack_into("<Q", attr, 8, key_addr)
                struct.pack_into("<Q", attr, 16, value_addr)
            else:
                struct.pack_into("<I", attr, 8, key_addr)
                struct.pack_into("<I", attr, 12, value_addr)
            rc = _bpf(_BPF_MAP_UPDATE_ELEM, attr, _MAP_ELEM_SIZE)
            if rc != 0:
                errno_value = ctypes.get_errno()
                raise OSError(errno_value, f"Failed to stage verity identity {loader_spec}")
            return {
                "cgroup_kernel_id": cgroup_kernel_id,
                "generation": generation,
                "algorithm_id": algorithm_id,
                "digest_hex": digest_bytes.hex(),
            }
        finally:
            os.close(fd)

    def _project_active_generation(self, *, cgroup_kernel_id: int, generation: int) -> Dict[str, Any]:
        pin_path = os.path.join(self.CANONICAL_PIN_ROOT, self.PHASE3_REQUIRED_MAPS["arda_active_generation_map"]["pin_name"])
        fd = self._open_pinned_map_fd(pin_path)
        try:
            key_buf = (ctypes.c_uint8 * 8)(*struct.pack("<Q", cgroup_kernel_id))
            value_buf = (ctypes.c_uint8 * 8)(*struct.pack("<Q", generation))
            attr = (ctypes.c_uint8 * _MAP_ELEM_SIZE)()
            struct.pack_into("<I", attr, 0, fd)
            key_addr = ctypes.addressof(key_buf)
            value_addr = ctypes.addressof(value_buf)
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                struct.pack_into("<Q", attr, 8, key_addr)
                struct.pack_into("<Q", attr, 16, value_addr)
            else:
                struct.pack_into("<I", attr, 8, key_addr)
                struct.pack_into("<I", attr, 12, value_addr)
            rc = _bpf(_BPF_MAP_UPDATE_ELEM, attr, _MAP_ELEM_SIZE)
            if rc != 0:
                errno_value = ctypes.get_errno()
                raise OSError(errno_value, f"Failed to project active generation {generation}")
            return {"cgroup_kernel_id": cgroup_kernel_id, "generation": generation}
        finally:
            os.close(fd)

    def _delete_pinned_verity_identity(
        self,
        *,
        cgroup_kernel_id: int,
        generation: int,
        loader_spec: str,
    ) -> Dict[str, Any]:
        algorithm_id, digest_bytes = self._parse_loader_digest_spec(loader_spec)
        pin_path = os.path.join(self.CANONICAL_PIN_ROOT, self.PHASE3_REQUIRED_MAPS["arda_verity_identity_map"]["pin_name"])
        fd = self._open_pinned_map_fd(pin_path)
        try:
            key_bytes = self._build_verity_identity_key(
                cgroup_kernel_id,
                generation,
                algorithm_id,
                digest_bytes,
            )
            key_buf = (ctypes.c_uint8 * len(key_bytes))(*key_bytes)
            attr = (ctypes.c_uint8 * _MAP_ELEM_SIZE)()
            struct.pack_into("<I", attr, 0, fd)
            key_addr = ctypes.addressof(key_buf)
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                struct.pack_into("<Q", attr, 8, key_addr)
            else:
                struct.pack_into("<I", attr, 8, key_addr)
            rc = _bpf(_BPF_MAP_DELETE_ELEM, attr, _MAP_ELEM_SIZE)
            if rc != 0:
                errno_value = ctypes.get_errno()
                raise OSError(errno_value, f"Failed to delete verity identity {loader_spec}")
            return {
                "cgroup_kernel_id": cgroup_kernel_id,
                "generation": generation,
                "algorithm_id": algorithm_id,
                "digest_hex": digest_bytes.hex(),
            }
        finally:
            os.close(fd)

    def _delete_active_generation(self, cgroup_kernel_id: int) -> Dict[str, Any]:
        pin_path = os.path.join(self.CANONICAL_PIN_ROOT, self.PHASE3_REQUIRED_MAPS["arda_active_generation_map"]["pin_name"])
        fd = self._open_pinned_map_fd(pin_path)
        try:
            key_buf = (ctypes.c_uint8 * 8)(*struct.pack("<Q", cgroup_kernel_id))
            attr = (ctypes.c_uint8 * _MAP_ELEM_SIZE)()
            struct.pack_into("<I", attr, 0, fd)
            key_addr = ctypes.addressof(key_buf)
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                struct.pack_into("<Q", attr, 8, key_addr)
            else:
                struct.pack_into("<I", attr, 8, key_addr)
            rc = _bpf(_BPF_MAP_DELETE_ELEM, attr, _MAP_ELEM_SIZE)
            if rc != 0:
                errno_value = ctypes.get_errno()
                raise OSError(errno_value, f"Failed to delete active generation for cgroup {cgroup_kernel_id}")
            return {"cgroup_kernel_id": cgroup_kernel_id}
        finally:
            os.close(fd)

    def project_pinned_policy(
        self,
        harmonic_paths: List[str],
        enforcement_mode: Optional[str] = None,
        constitutional_state: Optional[Dict[str, Any]] = None,
        seed_running_processes: bool = False,
        max_running_processes: int = 64,
        verify_native_denial_after: bool = False,
    ) -> Dict[str, Any]:
        mode = enforcement_mode or self.enforcement_mode
        if mode not in {
            self.ENFORCEMENT_MODE_AUDIT,
            self.ENFORCEMENT_MODE_LEGACY_INODE,
            self.ENFORCEMENT_MODE_FSVERITY_STRICT,
        }:
            raise ValueError(f"unsupported enforcement mode: {mode}")
        if not self.is_authoritative:
            raise RuntimeError("cannot project pinned policy without authoritative Ring-0 arming")
        if not self.get_required_map_status()["all_required_present"]:
            raise RuntimeError("cannot project pinned policy while required map contract is incomplete")

        deny_count_before = self.get_deny_count()
        projected_entries: List[Dict[str, Any]] = []
        seen_paths = set()

        def add_path(path: str) -> None:
            normalized = os.path.abspath(path)
            if normalized in seen_paths or not os.path.exists(normalized) or not os.access(normalized, os.X_OK):
                return
            projected_entries.append(self._update_pinned_harmony_entry(normalized, True))
            seen_paths.add(normalized)

        for path in harmonic_paths:
            add_path(path)

        if seed_running_processes:
            proc_root = "/proc"
            for entry in sorted(os.listdir(proc_root)):
                if len(projected_entries) >= len(harmonic_paths) + max_running_processes:
                    break
                if not entry.isdigit():
                    continue
                exe_link = os.path.join(proc_root, entry, "exe")
                try:
                    target = os.readlink(exe_link)
                except OSError:
                    continue
                deleted_suffix = " (deleted)"
                if target.endswith(deleted_suffix):
                    target = target[: -len(deleted_suffix)]
                add_path(target)

        applied_mode = self._project_state_mode(mode)
        projected_policy_state = None
        if constitutional_state:
            projected_policy_state = self._project_policy_state(
                constitutional_state["policy_generation"],
                int(constitutional_state.get("redline_rule_count", 0)),
            )
        deny_count_after = self.get_deny_count()
        native_denial_verification = None
        if verify_native_denial_after:
            native_denial_verification = self.run_native_denial_self_test()

        return {
            "ok": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "enforcement_mode": applied_mode,
            "seed_running_processes": seed_running_processes,
            "projected_entries": projected_entries,
            "projected_count": len(projected_entries),
            "projected_policy_state": projected_policy_state,
            "default_seed_paths": list(self.DEFAULT_PROJECTION_SEED_PATHS),
            "audit": {
                "requested_seed_count": len(harmonic_paths),
                "unique_projected_count": len(projected_entries),
                "deny_count_before": deny_count_before,
                "deny_count_after": deny_count_after,
                "deny_count_delta": None
                if deny_count_before is None or deny_count_after is None
                else deny_count_after - deny_count_before,
            },
            "native_denial_verification": native_denial_verification,
        }

    def preflight_measured_manifest(
        self,
        manifest: Dict[str, Any],
        attestation: Optional[Dict[str, Any]] = None,
        *,
        commit_generation: bool = False,
    ) -> Dict[str, Any]:
        return self._measured_identity_verifier.preflight(
            manifest,
            attestation,
            commit_generation=commit_generation,
        )

    def stage_measured_manifest(
        self,
        manifest: Dict[str, Any],
        attestation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        preflight = self.preflight_measured_manifest(manifest, attestation, commit_generation=False)
        return self._measured_identity_verifier.stage_projection(preflight, manifest)

    def activate_staged_measured_manifest(self, manifest_id: str) -> Dict[str, Any]:
        return self._measured_identity_verifier.activate_staged_projection(manifest_id)

    def deactivate_staged_measured_manifest(self, manifest_id: str, reason: str) -> Dict[str, Any]:
        return self._measured_identity_verifier.deactivate_staged_projection(manifest_id, reason)

    def remove_staged_measured_manifest(self, manifest_id: str) -> Dict[str, Any]:
        return self._measured_identity_verifier.remove_staged_projection(manifest_id)

    def evaluate_phase4_attestation_gate(
        self,
        manifest: Dict[str, Any],
        attestation_envelope: Dict[str, Any],
        cloud_witness: Optional[Dict[str, Any]] = None,
        local_evidence: Optional[Dict[str, Any]] = None,
        pcr_baseline: Optional[Dict[str, Any]] = None,
        require_tpm_quote_verification: bool = False,
        allow_attested_only_boot: bool = False,
        allow_missing_boot_measurement_for_live_proof: bool = False,
        require_verifier_nonce: bool = False,
        require_nonlocal_attestation_signature: bool = False,
    ) -> Dict[str, Any]:
        return self._phase4_attestation_gate.evaluate(
            manifest,
            attestation_envelope,
            cloud_witness,
            local_evidence,
            pcr_baseline,
            require_tpm_quote_verification,
            allow_attested_only_boot,
            allow_missing_boot_measurement_for_live_proof,
            require_verifier_nonce,
            require_nonlocal_attestation_signature,
        )

    def release_phase4_secret(
        self,
        purpose: str,
        gate_result: Dict[str, Any],
        *,
        requester: str,
    ) -> Dict[str, Any]:
        return self._phase4_secret_release.release(
            purpose,
            gate_result,
            requester=requester,
        )

    def capture_phase4_live_attestation(
        self,
        output_dir: str,
        *,
        nonce: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._phase4_live_attestation.capture(output_dir, nonce=nonce)

    def project_staged_measured_manifest(self, manifest_id: str) -> Dict[str, Any]:
        if not self.is_authoritative:
            raise RuntimeError("cannot project measured manifest without authoritative Ring-0 arming")
        phase3_status = self.get_phase3_map_status()
        if not phase3_status["all_required_present"]:
            raise RuntimeError("cannot project measured manifest while Phase 3 map contract is incomplete")

        record = self._measured_generation_store.get_record(manifest_id)
        if not record:
            raise RuntimeError(f"staged measured manifest not found: {manifest_id}")
        if record["state"] not in {"staged", "active"}:
            raise RuntimeError(f"measured manifest is not stageable: {record['state']}")

        projection = record["payload"]
        staged_entries = []
        for loader_spec in projection.get("loader_digest_specs", []):
            staged_entries.append(
                self._stage_pinned_verity_identity(
                    cgroup_kernel_id=int(projection["cgroup_kernel_id"]),
                    generation=int(projection["generation"]),
                    loader_spec=loader_spec,
                )
            )
        staged_exec_entries = []
        for path in projection.get("checked_paths", []):
            staged_exec_entries.append(
                self._stage_pinned_measured_exec(
                    cgroup_kernel_id=int(projection["cgroup_kernel_id"]),
                    generation=int(projection["generation"]),
                    path=path,
                )
            )
        active_pointer = self._project_active_generation(
            cgroup_kernel_id=int(projection["cgroup_kernel_id"]),
            generation=int(projection["generation"]),
        )
        applied_mode = self._project_state_mode(self.ENFORCEMENT_MODE_FSVERITY_STRICT)
        return {
            "ok": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "manifest_id": manifest_id,
            "enforcement_mode": applied_mode,
            "projected_entry_count": len(staged_entries),
            "projected_entries": staged_entries,
            "projected_exec_entry_count": len(staged_exec_entries),
            "projected_exec_entries": staged_exec_entries,
            "active_generation": active_pointer,
        }

    def unproject_staged_measured_manifest(self, manifest_id: str) -> Dict[str, Any]:
        if not self.is_authoritative:
            raise RuntimeError("cannot unproject measured manifest without authoritative Ring-0 arming")
        record = self._measured_generation_store.get_record(manifest_id)
        if not record:
            raise RuntimeError(f"staged measured manifest not found: {manifest_id}")
        projection = record["payload"]
        removed_entries = []
        for loader_spec in projection.get("loader_digest_specs", []):
            removed_entries.append(
                self._delete_pinned_verity_identity(
                    cgroup_kernel_id=int(projection["cgroup_kernel_id"]),
                    generation=int(projection["generation"]),
                    loader_spec=loader_spec,
                )
            )
        removed_exec_entries = []
        for path in projection.get("checked_paths", []):
            removed_exec_entries.append(
                self._delete_pinned_measured_exec(
                    cgroup_kernel_id=int(projection["cgroup_kernel_id"]),
                    generation=int(projection["generation"]),
                    path=path,
                )
            )
        removed_pointer = self._delete_active_generation(int(projection["cgroup_kernel_id"]))
        return {
            "ok": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "manifest_id": manifest_id,
            "removed_entry_count": len(removed_entries),
            "removed_entries": removed_entries,
            "removed_exec_entry_count": len(removed_exec_entries),
            "removed_exec_entries": removed_exec_entries,
            "active_generation_removed": removed_pointer,
        }

    def sovereign_exec(self, executable_path: str, command: list):
        """
        The sole authorized execution path.
        """
        if self.sovereign_mode and not self.is_authoritative:
            raise PermissionError("ARDA_VETO: Sovereign Path Compromised (No Ring-0 Guard)")

        if self.is_authoritative:
            return subprocess.run(command)

        if os.environ.get("ARDA_SIMULATE_DENY") == "1":
            logger.critical(f"ARDA_VETO: Simulated Proactive Denial for {command[0]}")
            raise PermissionError(f"Arda OS Veto (Simulated Ring-0): {command[0]}")

        return subprocess.run(command)


_os_service = None


def get_os_enforcement_service():
    global _os_service
    if _os_service is None:
        _os_service = OsEnforcementService()
    return _os_service
