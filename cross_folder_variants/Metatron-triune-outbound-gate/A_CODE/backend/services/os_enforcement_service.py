"""
ARDA OS Enforcement Service — Ring-0 BPF LSM Guard
====================================================
Uses pre-compiled arda_lsm_loader (libbpf) to attach the LSM hook,
then manages BPF maps via raw ctypes syscalls (no BCC dependency).
"""

import os
import sys
import logging
import struct
import hashlib
import ctypes
import subprocess
import threading
import time
from typing import Dict, Any, Optional, List

try:
    from services.quantum_security import quantum_security
except Exception:
    try:
        from backend.services.quantum_security import quantum_security
    except Exception:
        quantum_security = None

logger = logging.getLogger(__name__)

# ── BPF syscall constants (x86_64) ──────────────────────────────────────────
_BPF_SYSCALL        = 321
_BPF_MAP_LOOKUP_ELEM    = 1
_BPF_MAP_UPDATE_ELEM    = 2
_BPF_MAP_GET_NEXT_ID    = 12
_BPF_MAP_GET_FD_BY_ID   = 14
_BPF_OBJ_GET_INFO_BY_FD = 15
_MAP_ELEM_SIZE       = 4096   # oversized attr union — kernel only reads what it needs

_libc = ctypes.CDLL("libc.so.6", use_errno=True)

def _bpf(cmd: int, attr_buf: ctypes.Array, attr_size: int) -> int:
    """Raw BPF syscall wrapper."""
    return _libc.syscall(_BPF_SYSCALL, cmd, attr_buf, attr_size)


def _map_get_fd_by_id(map_id: int) -> int:
    """Return an fd for the given BPF map ID, or -1 on error."""
    attr = (ctypes.c_uint8 * _MAP_ELEM_SIZE)()
    struct.pack_into("<I", attr, 0, map_id)       # union: map_id at offset 0
    fd = _bpf(_BPF_MAP_GET_FD_BY_ID, attr, _MAP_ELEM_SIZE)
    return fd


def _map_get_name(fd: int) -> str:
    """Return the kernel map name for an open map fd (up to 16 chars)."""
    # struct bpf_map_info layout:
    #   type(4) id(4) key_size(4) val_size(4) max_entries(4) map_flags(4)  ← 24 bytes
    #   name[16]  ← offset 24
    info_buf = (ctypes.c_uint8 * 256)()
    attr = (ctypes.c_uint8 * _MAP_ELEM_SIZE)()
    struct.pack_into("<I", attr, 0, fd)                    # bpf_fd
    struct.pack_into("<I", attr, 4, 256)                   # info_len
    addr = ctypes.addressof(info_buf)
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        struct.pack_into("<Q", attr, 8, addr)              # info ptr (64-bit)
    else:
        struct.pack_into("<I", attr, 8, addr)
    rc = _bpf(_BPF_OBJ_GET_INFO_BY_FD, attr, _MAP_ELEM_SIZE)
    if rc < 0:
        return ""
    # name is at byte 24 (after type/id/key_size/val_size/max_entries/map_flags = 6×4 = 24)
    raw = bytes(info_buf[24:40])
    return raw.rstrip(b"\x00").decode("utf-8", errors="replace")


def _find_map_id_by_name(name: str) -> Optional[int]:
    """Scan all BPF map IDs and return the first one whose name matches."""
    # union bpf_attr for BPF_MAP_GET_NEXT_ID:
    #   offset 0: start_id (input)
    #   offset 4: next_id  (output)
    attr = (ctypes.c_uint8 * _MAP_ELEM_SIZE)()
    current_id = 0
    for _ in range(4096):
        struct.pack_into("<I", attr, 0, current_id)  # start_id
        struct.pack_into("<I", attr, 4, 0)           # next_id (clear output slot)
        rc = _bpf(_BPF_MAP_GET_NEXT_ID, attr, _MAP_ELEM_SIZE)
        if rc < 0:
            break
        next_id = struct.unpack_from("<I", attr, 4)[0]  # read next_id at offset 4
        if next_id == 0 or next_id <= current_id:
            break
        current_id = next_id
        fd = _map_get_fd_by_id(next_id)
        if fd >= 0:
            map_name = _map_get_name(fd)
            os.close(fd)
            if map_name == name:
                return next_id
    return None


def _bpf_map_update_u32(map_id: int, key: int, value: int) -> bool:
    """Write a u32 key→u32 value into a BPF map by ID."""
    fd = _map_get_fd_by_id(map_id)
    if fd < 0:
        return False
    try:
        key_buf   = (ctypes.c_uint8 * 4)(*struct.pack("<I", key))
        val_buf   = (ctypes.c_uint8 * 4)(*struct.pack("<I", value))
        attr = (ctypes.c_uint8 * _MAP_ELEM_SIZE)()
        struct.pack_into("<I", attr, 0, fd)
        k_addr = ctypes.addressof(key_buf)
        v_addr = ctypes.addressof(val_buf)
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            struct.pack_into("<Q", attr, 8, k_addr)
            struct.pack_into("<Q", attr, 16, v_addr)
        else:
            struct.pack_into("<I", attr, 8, k_addr)
            struct.pack_into("<I", attr, 12, v_addr)
        # flags = BPF_ANY (0) at offset 24 (already 0)
        rc = _bpf(_BPF_MAP_UPDATE_ELEM, attr, _MAP_ELEM_SIZE)
        return rc == 0
    finally:
        os.close(fd)


def _bpf_map_update_inode(map_id: int, inode: int, dev: int, value: int) -> bool:
    """Write an arda_identity{inode,dev}→u32 entry into the harmony map."""
    fd = _map_get_fd_by_id(map_id)
    if fd < 0:
        return False
    try:
        # struct arda_identity { unsigned long inode; unsigned int dev; }
        # The kernel-side struct is 16 bytes on the supported 64-bit targets
        # because the trailing 4 bytes are alignment padding.
        key_buf = (ctypes.c_uint8 * 16)(*struct.pack("<QI4x", inode, dev))
        val_buf = (ctypes.c_uint8 * 4)(*struct.pack("<I", value))
        attr = (ctypes.c_uint8 * _MAP_ELEM_SIZE)()
        struct.pack_into("<I", attr, 0, fd)
        k_addr = ctypes.addressof(key_buf)
        v_addr = ctypes.addressof(val_buf)
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            struct.pack_into("<Q", attr, 8, k_addr)
            struct.pack_into("<Q", attr, 16, v_addr)
        else:
            struct.pack_into("<I", attr, 8, k_addr)
            struct.pack_into("<I", attr, 12, v_addr)
        rc = _bpf(_BPF_MAP_UPDATE_ELEM, attr, _MAP_ELEM_SIZE)
        return rc == 0
    finally:
        os.close(fd)


# ── Main service ─────────────────────────────────────────────────────────────

class OsEnforcementService:
    """
    ARDA OS: Operational Engine.
    Loads the pre-compiled BPF LSM via arda_lsm_loader, then manages
    maps via raw ctypes syscalls.
    """

    # Paths resolved at class level so they work inside the container
    _BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
    _LOADER_BIN   = os.path.join(_BASE_DIR, "bpf", "arda_lsm_loader")
    _OBJ_ENFORCE  = os.path.join(_BASE_DIR, "bpf", "arda_physical_lsm.o")
    _OBJ_AUDIT    = os.path.join(_BASE_DIR, "bpf", "arda_physical_lsm_audit.o")

    def __init__(self, bpf_source: str = None):
        self.lsm_map: Dict[str, Any] = {}
        self.is_authoritative = False
        self.mode = "simulation"
        self._loader_proc: Optional[subprocess.Popen] = None
        self._harmony_map_id: Optional[int] = None
        self._state_map_id:   Optional[int] = None
        self._network_deny_map_id: Optional[int] = None
        # bpf_source kept for API compat
        self.bpf_source = self._OBJ_ENFORCE

        self._arm()

    @staticmethod
    def _host_path(path: str) -> str:
        """Return the host-mounted path when the service runs in a container."""
        host_root = os.environ.get("ARDA_HOST_ROOT", "/host").rstrip("/")
        if host_root and os.path.isdir(host_root) and path.startswith("/"):
            candidate = f"{host_root}{path}"
            if os.path.exists(candidate):
                return candidate
        return path

    def _loader_seed_args(self) -> List[str]:
        """
        Build conservative seed args for the C loader. The loader still defaults
        to AUDIT, but these entries make later enforcement toggles much safer.
        """
        max_seed = int(os.environ.get("ARDA_MAX_SEED", "12000"))
        min_seed = int(os.environ.get("ARDA_MIN_SEED", "64"))
        args: List[str] = ["--max-seed", str(max_seed), "--min-seed", str(min_seed), "--seed-running-procs"]
        pin_root = os.environ.get("ARDA_BPF_PIN_ROOT", "").strip()
        if pin_root:
            args.extend(["--pin-root", pin_root])

        for path in (
            "/bin/sh",
            "/bin/bash",
            "/usr/bin/env",
            "/usr/bin/python3",
            "/usr/bin/docker",
            "/opt/pwsh/pwsh",
        ):
            hp = self._host_path(path)
            if os.path.exists(hp):
                args.extend(["--seed-path", hp])

        for path in (
            "/bin",
            "/sbin",
            "/usr/bin",
            "/usr/sbin",
            "/usr/local/bin",
            "/usr/local/sbin",
        ):
            hp = self._host_path(path)
            if os.path.isdir(hp):
                args.extend(["--seed-exec-dir", hp])

        return args

    def _arm(self):
        """Launch arda_lsm_loader and locate the BPF maps."""
        # Safety kill switch: ARDA_LSM_ENABLED=false prevents loading any BPF
        # program into the host kernel. This MUST be checked first. Loading the
        # LSM hook from a privileged container affects the entire host kernel and
        # will block execve() for all processes not in the harmony allowlist,
        # which can cause a system-wide lockout.
        if os.environ.get("ARDA_LSM_ENABLED", "false").lower() not in ("1", "true", "yes"):
            logger.info("ARDA_LSM: Disabled via ARDA_LSM_ENABLED env var — running in simulation mode.")
            return
        if not os.path.isfile(self._LOADER_BIN):
            logger.error(f"ARDA_LSM: Loader binary not found: {self._LOADER_BIN}")
            return
        if not os.path.isfile(self._OBJ_ENFORCE):
            logger.error(f"ARDA_LSM: BPF object not found: {self._OBJ_ENFORCE}")
            return

        try:
            logger.info("ARDA_LSM: Launching arda_lsm_loader…")
            self._loader_proc = subprocess.Popen(
                [self._LOADER_BIN, self._OBJ_ENFORCE, *self._loader_seed_args()],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Read loader stdout in a background thread so we can wait up to 60 s
            # for bpf_program__attach() without blocking the main init path.
            # The loader calls fflush(stdout) once, right after printing PROG_FD=.
            harmony_map_id_ref = [None]
            map_id_event = threading.Event()

            network_deny_map_id_ref = [None]

            def _read_loader_stdout():
                try:
                    for raw_line in self._loader_proc.stdout:
                        line = raw_line.strip()
                        if line:
                            logger.info(f"ARDA_LSM loader: {line}")
                        if line.startswith("MAP_ID="):
                            try:
                                harmony_map_id_ref[0] = int(line.split("=", 1)[1])
                            except ValueError:
                                pass
                            map_id_event.set()
                        if line.startswith("NETWORK_DENY_MAP_ID="):
                            try:
                                network_deny_map_id_ref[0] = int(line.split("=", 1)[1])
                            except ValueError:
                                pass
                except Exception as exc:
                    logger.warning(f"ARDA_LSM: stdout reader error: {exc}")
                finally:
                    map_id_event.set()  # unblock waiter even on error

            stdout_thread = threading.Thread(target=_read_loader_stdout, daemon=True)
            stdout_thread.start()

            # Wait up to 60 s for MAP_ID= to appear (kernel LSM attachment can be slow)
            if not map_id_event.wait(timeout=60.0):
                logger.error("ARDA_LSM: Timed out waiting for MAP_ID from loader (60s).")
                return

            if self._loader_proc.poll() is not None:
                stderr = self._loader_proc.stderr.read()
                logger.error(f"ARDA_LSM: Loader exited early. stderr={stderr}")
                return

            harmony_map_id = harmony_map_id_ref[0]
            if harmony_map_id is None:
                logger.error("ARDA_LSM: MAP_ID not received despite loader running.")
                return

            self._harmony_map_id = harmony_map_id
            logger.info(f"ARDA_LSM: Harmony map ID = {harmony_map_id}")

            # stdout_thread continues draining output (stays alive after MAP_ID)
            # Find the state and network deny maps by scanning kernel BPF map IDs
            self._state_map_id = _find_map_id_by_name("arda_state_map")
            if not self._state_map_id:
                logger.warning("ARDA_LSM: arda_state_map not found via scan (non-fatal)")

            if network_deny_map_id_ref[0] is not None:
                self._network_deny_map_id = network_deny_map_id_ref[0]
            else:
                self._network_deny_map_id = _find_map_id_by_name("arda_network_deny_map")
            if self._network_deny_map_id:
                logger.info(f"ARDA_LSM: Network deny map ID = {self._network_deny_map_id}")

            self.is_authoritative = True
            self.mode = "ring0_armed"
            logger.info("RING-0: Arda OS Sovereign Guard ARMED. LSM hook: arda_sovereign_ignition. Mode: AUDIT")

            # Auto-enable enforcement if requested via env var
            if os.environ.get("ARDA_ENFORCE_ON_BOOT", "").lower() in ("1", "true", "yes"):
                seeded = self.seed_running_processes()
                min_seed = int(os.environ.get("ARDA_MIN_SEED", "64"))
                if seeded < min_seed:
                    logger.critical(
                        "RING-0: ARDA_ENFORCE_ON_BOOT refused; only %s running-process "
                        "executables seeded (minimum %s). Enforcement remains AUDIT.",
                        seeded,
                        min_seed,
                    )
                elif self.set_enforcement(True):
                    logger.info("RING-0: Enforcement auto-enabled on boot (ARDA_ENFORCE_ON_BOOT=true)")
                else:
                    logger.warning("RING-0: ARDA_ENFORCE_ON_BOOT set but state map not ready — enforcement remains off")

        except Exception as e:
            logger.error(f"ARDA_LSM: Failed to arm: {e}", exc_info=True)
            self._loader_proc = None

    # ── Enforcement toggle ────────────────────────────────────────────────────

    def set_enforcement(self, enabled: bool) -> bool:
        """
        Toggle the BPF state map index 0: 0 = audit/passthrough, 1 = enforce.
        Returns True on success.
        """
        if enabled and os.environ.get("ARDA_ALLOW_UNSAFE_ENFORCEMENT", "").lower() not in ("1", "true", "yes"):
            seeded = self.seed_running_processes()
            min_seed = int(os.environ.get("ARDA_MIN_SEED", "64"))
            if seeded < min_seed:
                logger.critical(
                    "ARDA_LSM: refusing enforcement; only %s running-process executables "
                    "seeded (minimum %s). Set ARDA_ALLOW_UNSAFE_ENFORCEMENT=true to override.",
                    seeded,
                    min_seed,
                )
                return False
        if not self._state_map_id:
            # Try to find it now (in case it appeared after arm)
            self._state_map_id = _find_map_id_by_name("arda_state_map")
        if not self._state_map_id:
            logger.error("ARDA_LSM: Cannot toggle enforcement — state map not found")
            return False
        val = 1 if enabled else 0
        ok = _bpf_map_update_u32(self._state_map_id, 0, val)
        logger.info(f"RING-0: Enforcement {'ENABLED' if enabled else 'DISABLED'} (state map {self._state_map_id})")
        return ok

    def get_enforcement(self) -> Optional[bool]:
        """Read the current enforcement state from BPF state map."""
        if not self._state_map_id:
            self._state_map_id = _find_map_id_by_name("arda_state_map")
        if not self._state_map_id:
            return None
        fd = _map_get_fd_by_id(self._state_map_id)
        if fd < 0:
            return None
        try:
            key_buf = (ctypes.c_uint8 * 4)(*struct.pack("<I", 0))
            val_buf = (ctypes.c_uint8 * 4)(0, 0, 0, 0)
            attr = (ctypes.c_uint8 * _MAP_ELEM_SIZE)()
            struct.pack_into("<I", attr, 0, fd)
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                struct.pack_into("<Q", attr, 8, ctypes.addressof(key_buf))
                struct.pack_into("<Q", attr, 16, ctypes.addressof(val_buf))
            else:
                struct.pack_into("<I", attr, 8, ctypes.addressof(key_buf))
                struct.pack_into("<I", attr, 12, ctypes.addressof(val_buf))
            rc = _bpf(_BPF_MAP_LOOKUP_ELEM, attr, _MAP_ELEM_SIZE)
            if rc == 0:
                return struct.unpack_from("<I", val_buf)[0] == 1
            return None
        finally:
            os.close(fd)

    # ── Workload harmony ──────────────────────────────────────────────────────

    def update_workload_harmony(self, executable_path: str, is_harmonic: bool,
                                quantum_signature: Any = None):
        """
        Synchronizes workload identity into the Ring-0 BPF harmony map.
        Falls back to in-memory dict when not authoritative (simulation).
        """
        if is_harmonic and os.getenv("ARDA_SOVEREIGN_MODE") == "1":
            if not quantum_security:
                logger.error("ARDA_LSM: Quantum Security Service unavailable at Ring-1.")
                return False
            if not quantum_signature:
                logger.error(f"ARDA_LSM: Ignition VETOED. Missing PQC signature for {executable_path}")
                return False
            # Verify manifest integrity
            try:
                with open(executable_path, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                if not self._verify_manifest_integrity(executable_path, file_hash):
                    logger.critical(f"ARDA_LSM: [MANIFEST VETO] {executable_path} not in manifest.")
                    return False
            except Exception as e:
                logger.error(f"ARDA_LSM: Manifest check failed: {e}")
                return False

        if not self.is_authoritative or self._harmony_map_id is None:
            self.lsm_map[executable_path] = 1 if is_harmonic else 0
            logger.warning(f"RING-0 SIM: {executable_path} -> {'HARMONIC' if is_harmonic else 'FALLEN'}")
            return True

        try:
            st = os.stat(executable_path)
            ok = _bpf_map_update_inode(
                self._harmony_map_id, st.st_ino, st.st_dev, 1 if is_harmonic else 0
            )
            if ok:
                logger.info(f"RING-0 SYNC: {executable_path} (ino={st.st_ino} dev={st.st_dev}) -> {'HARMONIC' if is_harmonic else 'FALLEN'}")
            else:
                logger.error(f"RING-0: BPF map update failed for {executable_path}")
            return ok
        except FileNotFoundError:
            logger.warning(f"RING-0: Path not found — using in-memory fallback: {executable_path}")
            self.lsm_map[executable_path] = 1 if is_harmonic else 0
            return True
        except Exception as e:
            logger.error(f"ARDA_LSM: Map synchronization failure: {e}")
            return False

    # ── Network enforcement ───────────────────────────────────────────────────

    def deny_network_for_pid(self, pid: int, denied: bool) -> bool:
        """
        Write a PID into arda_network_deny_map (value=1 deny, value=0 allow).
        Called by Tulkas on CONTAIN/PURGE/EXILE to close the network gate at
        ring-0 for fallen nodes, independent of whether the process is killed.
        """
        if not self._network_deny_map_id:
            self._network_deny_map_id = _find_map_id_by_name("arda_network_deny_map")
        if not self._network_deny_map_id:
            self.lsm_map[f"net_deny_pid_{pid}"] = 1 if denied else 0
            logger.warning(f"RING-0 SIM: network {'deny' if denied else 'allow'} for PID {pid}")
            return True
        ok = _bpf_map_update_u32(self._network_deny_map_id, pid, 1 if denied else 0)
        if ok:
            logger.info(f"RING-0 NET: PID {pid} -> {'DENY' if denied else 'ALLOW'}")
        else:
            logger.error(f"RING-0: network deny map update failed for PID {pid}")
        return ok

    # ── Running process seeding (anti-lockout) ────────────────────────────────

    def seed_running_processes(self) -> int:
        """
        Seed all currently running process executables into the harmony map.
        Call this before enabling permanent enforcement to ensure no running
        process has its next exec attempt blocked.
        Returns the number of new entries seeded.
        """
        if not self.is_authoritative or self._harmony_map_id is None:
            logger.warning("RING-0 SIM: seed_running_processes — not authoritative, no-op")
            return 0

        seeded = 0
        proc_dirs = ["/host/proc", "/proc"] if os.path.isdir("/host/proc") else ["/proc"]
        for proc_dir in proc_dirs:
            try:
                for entry in os.listdir(proc_dir):
                    try:
                        int(entry)
                    except ValueError:
                        continue
                    exe_link = os.path.join(proc_dir, entry, "exe")
                    try:
                        target = os.readlink(exe_link)
                    except OSError:
                        continue
                    target = target.split(" (deleted)")[0]
                    if proc_dir == "/host/proc":
                        target = self._host_path(target)
                    try:
                        st = os.stat(target)
                        ok = _bpf_map_update_inode(self._harmony_map_id, st.st_ino, st.st_dev, 1)
                        if ok:
                            seeded += 1
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"RING-0: seed_running_processes scan error: {e}")
        logger.info(f"RING-0: seeded {seeded} running-process executables into harmony map")
        return seeded

    def _verify_manifest_integrity(self, path: str, current_hash: str) -> bool:
        """Verify binary hash against the Sovereign Manifest."""
        import json
        for mp in ["/etc/arda/sovereign_manifest.json",
                   os.path.join(os.getcwd(), "sovereign_manifest.json")]:
            if os.path.exists(mp):
                try:
                    with open(mp) as f:
                        manifest = json.load(f)
                    norm = os.path.abspath(path).lower().replace("\\", "/")
                    norm_manifest = {k.lower().replace("\\", "/"): v for k, v in manifest.items()}
                    return current_hash == norm_manifest.get(norm)
                except Exception as e:
                    logger.error(f"ARDA_LSM: Manifest read error: {e}")
        logger.warning("ARDA_LSM: Sovereign Manifest missing — fail-closed")
        return False

    def sovereign_exec(self, executable_path: str, command: list):
        """Sole authorized execution path."""
        if self.is_authoritative:
            return subprocess.run(command)
        if os.environ.get("ARDA_SOVEREIGN_MODE") == "1":
            raise PermissionError("ARDA_VETO: Sovereign Path Compromised (No Ring-0 Guard)")
        logger.warning(f"ARDA_SIMULATED_EXEC: {command[0]} (no BPF guard)")
        return subprocess.run(command)

    def __del__(self):
        if self._loader_proc and self._loader_proc.poll() is None:
            try:
                self._loader_proc.terminate()
            except Exception:
                pass


# ── Singleton ─────────────────────────────────────────────────────────────────

_os_service: Optional[OsEnforcementService] = None

def get_os_enforcement_service() -> OsEnforcementService:
    global _os_service
    if _os_service is None:
        _os_service = OsEnforcementService()
    return _os_service
