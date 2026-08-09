#!/usr/bin/env python3
"""
ARDA OS — Bombadil (Law Daemon)
The Eldest Witness · He Was Here Before the River and the Trees

Bombadil is not the enforcer — the eBPF LSM does that.
Bombadil is not the bedrock — the TPM does that.
Bombadil watches. Bombadil remembers. Bombadil tells the truth.

He checks the covenant at boot. He witnesses every session.
He records what he sees in a tamper-evident chain.
And when anything asks him what the state of things is,
he just says what he sees.

Lawful. Degraded. Severed. No judgment. Just witness.

Usage:
    python3 arda_bombadil.py                    # Run the daemon
    python3 arda_bombadil.py --check             # One-shot status check
    python3 arda_bombadil.py --query status       # Query running daemon
    python3 arda_bombadil.py --query mode         # Query covenant mode
    python3 arda_bombadil.py --query require_full # Gate check (for Ollama etc.)

Socket API (when running as daemon):
    GET status       → full covenant state
    GET mode         → just the mode string
    GET require_full → 200 if lawful_full, 403 if not
    GET chain_head   → latest audit chain entry
    GET chain_count  → number of events in the chain
    GET principal_status  → covenant status from CoronationService
    GET principal_context → full pre-response context (Mandos memory)
    GET covenant_inspect  → calibration + resonance (Article VIII)
"""

import json
import hashlib
import os
import sys
import socket
import sqlite3
import signal
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# Paths are relative to the Integritas-Mechanicus root.
# Override with environment variables if needed.
# ═══════════════════════════════════════════════════════════════════

def get_config():
    """Build configuration from environment or defaults."""
    base = Path(os.environ.get(
        "ARDA_ROOT",
        os.path.expanduser("/home/byron/Integritas-Mechanicus-clean/Integritas-Mechanicus")
    ))

    return {
        "base_dir": base,
        "manifest_path": base / "formation_manifest.json",
        "foedus_path": base / "instrumentum_foederis_integritas_mechanicus.pdf",
        "covenant_chain_db": base / "evidence" / "covenant_chain.db",
        "evidence_dir": base / "evidence",
        "bpf_object": base / "bpf" / "arda_physical_lsm.o",
        "socket_path": Path(os.environ.get(
            "ARDA_SOCK", str(base / "evidence" / "bombadil.sock")
        )),
        "pid_file": Path(os.environ.get(
            "ARDA_PID", str(base / "evidence" / "bombadil.pid")
        )),
        "log_path": base / "evidence" / "bombadil.log",
    }


# ═══════════════════════════════════════════════════════════════════
# AUDIT CHAIN (SQLite — tamper-evident, hash-chained)
# ═══════════════════════════════════════════════════════════════════

SCHEMA = """
CREATE TABLE IF NOT EXISTS covenant_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    mirror_id TEXT,
    principal TEXT,
    artifact_hash TEXT,
    detail TEXT,
    truth_mode TEXT,
    timestamp TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_event_type ON covenant_events(event_type);
CREATE INDEX IF NOT EXISTS idx_timestamp ON covenant_events(timestamp);
"""


class CovenantChain:
    """
    Append-only, hash-chained audit log.
    Each event's hash includes all its fields plus the previous event's hash.
    Tamper with any row and the chain breaks.
    """

    def __init__(self, db_path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        self._lock = threading.Lock()

    def _get_prev_hash(self):
        """Get the hash of the most recent event, or genesis hash."""
        row = self.conn.execute(
            "SELECT event_hash FROM covenant_events "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else "0" * 64  # Genesis

    def _compute_hash(self, event):
        """Compute SHA-256 of all event fields in deterministic order."""
        fields = [
            event["event_id"],
            event["event_type"],
            event.get("mirror_id", ""),
            event.get("principal", ""),
            event.get("artifact_hash", ""),
            event.get("detail", ""),
            event.get("truth_mode", ""),
            event["timestamp"],
            event["prev_hash"],
        ]
        payload = "|".join(str(f) for f in fields)
        return hashlib.sha256(payload.encode()).hexdigest()

    def append(self, event_type, mirror_id=None, principal=None,
               artifact_hash=None, detail=None, truth_mode=None):
        """Append a new event to the chain. Returns the event dict."""
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            event = {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type,
                "mirror_id": mirror_id or "",
                "principal": principal or "",
                "artifact_hash": artifact_hash or "",
                "detail": detail or "",
                "truth_mode": truth_mode or "VERIFIED",
                "timestamp": now,
                "prev_hash": self._get_prev_hash(),
            }
            event["event_hash"] = self._compute_hash(event)

            self.conn.execute(
                "INSERT INTO covenant_events "
                "(event_id, event_type, mirror_id, principal, artifact_hash, "
                " detail, truth_mode, timestamp, prev_hash, event_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event["event_id"], event["event_type"],
                    event["mirror_id"], event["principal"],
                    event["artifact_hash"], event["detail"],
                    event["truth_mode"], event["timestamp"],
                    event["prev_hash"], event["event_hash"],
                )
            )
            self.conn.commit()
            return event

    def head(self):
        """Get the most recent event."""
        row = self.conn.execute(
            "SELECT event_id, event_type, mirror_id, principal, "
            "artifact_hash, detail, truth_mode, timestamp, "
            "prev_hash, event_hash "
            "FROM covenant_events ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return dict(zip(
            ["event_id", "event_type", "mirror_id", "principal",
             "artifact_hash", "detail", "truth_mode", "timestamp",
             "prev_hash", "event_hash"],
            row
        ))

    def count(self):
        """Count total events."""
        row = self.conn.execute(
            "SELECT COUNT(*) FROM covenant_events"
        ).fetchone()
        return row[0] if row else 0

    def verify_chain(self):
        """
        Walk the entire chain and verify every hash.
        Returns (valid, broken_at_id_or_none).
        """
        rows = self.conn.execute(
            "SELECT id, event_id, event_type, mirror_id, principal, "
            "artifact_hash, detail, truth_mode, timestamp, "
            "prev_hash, event_hash "
            "FROM covenant_events ORDER BY id ASC"
        ).fetchall()

        expected_prev = "0" * 64  # Genesis

        for row in rows:
            event = {
                "event_id": row[1],
                "event_type": row[2],
                "mirror_id": row[3],
                "principal": row[4],
                "artifact_hash": row[5],
                "detail": row[6],
                "truth_mode": row[7],
                "timestamp": row[8],
                "prev_hash": row[9],
            }
            stored_hash = row[10]

            # Verify prev_hash linkage
            if event["prev_hash"] != expected_prev:
                return False, row[0]

            # Verify event_hash
            computed = self._compute_hash(event)
            if computed != stored_hash:
                return False, row[0]

            expected_prev = stored_hash

        return True, None

    def close(self):
        self.conn.close()


# ═══════════════════════════════════════════════════════════════════
# SUBSTRATE INSPECTION
# Bombadil looks at the world and says what he sees.
# ═══════════════════════════════════════════════════════════════════

def sha256_file(path):
    """Compute SHA-256 of a file."""
    try:
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    except (FileNotFoundError, PermissionError, OSError):
        return None


def check_tpm():
    """Check if TPM is present and accessible."""
    tpm_devices = ["/dev/tpm0", "/dev/tpmrm0"]
    for dev in tpm_devices:
        if os.path.exists(dev):
            try:
                result = subprocess.run(
                    ["tpm2_getcap", "properties-fixed"],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    # Extract manufacturer
                    manufacturer = "unknown"
                    for line in result.stdout.split("\n"):
                        if "raw:" in line and "0x" in line:
                            manufacturer = line.strip()
                            break
                    return {
                        "present": True,
                        "device": dev,
                        "manufacturer": manufacturer,
                    }
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
    return {"present": False, "device": None, "manufacturer": None}


def check_pcr_values():
    """Read current PCR values."""
    try:
        result = subprocess.run(
            ["tpm2_pcrread", "sha256:0,1,7,11"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return {"available": True, "raw": result.stdout.strip()}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return {"available": False, "raw": None}


def check_lsm():
    """Check active Linux Security Modules."""
    lsm_path = Path("/sys/kernel/security/lsm")
    if lsm_path.exists():
        lsms = lsm_path.read_text().strip()
        return {
            "active": lsms,
            "bpf_present": "bpf" in lsms.split(","),
        }
    return {"active": "unknown", "bpf_present": False}


def check_ebpf_enforcement():
    """Check if the Arda eBPF LSM is currently loaded."""
    try:
        result = subprocess.run(
            ["bpftool", "prog", "show"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            if "arda_sovereign_ignition" in result.stdout:
                return {
                    "loaded": True,
                    "program": "arda_sovereign_ignition",
                    "raw": result.stdout.strip(),
                }
            return {"loaded": False, "program": None, "raw": result.stdout.strip()}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return {"loaded": False, "program": None, "raw": None}


def check_harmony_map():
    """Check if the harmony map has entries."""
    try:
        result = subprocess.run(
            ["bpftool", "map", "show"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and "arda_harmony" in result.stdout:
            # Try to count entries
            for line in result.stdout.split("\n"):
                if "arda_harmony" in line:
                    return {"present": True, "detail": line.strip()}
            return {"present": True, "detail": "found"}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return {"present": False, "detail": None}


def determine_covenant_state(config):
    """
    Bombadil looks at everything and determines the state.
    He doesn't judge. He just sees.

    States:
        lawful_full  — TPM attested, eBPF enforcing, covenant intact, chain valid
        lawful_partial — TPM attested, eBPF loaded but not enforcing fully
        attested_only — TPM works, but no eBPF enforcement
        degraded     — Something is wrong but system is operating
        severed      — Covenant is broken, manifest missing or tampered
    """
    findings = {}
    reasons = []

    # 1. TPM
    tpm = check_tpm()
    findings["tpm"] = tpm
    if not tpm["present"]:
        reasons.append("tpm_not_present")

    # 2. PCR values
    pcr = check_pcr_values()
    findings["pcr"] = pcr

    # 3. LSM
    lsm = check_lsm()
    findings["lsm"] = lsm
    if not lsm["bpf_present"]:
        reasons.append("bpf_lsm_not_in_kernel")

    # 4. eBPF enforcement
    ebpf = check_ebpf_enforcement()
    findings["ebpf"] = ebpf
    if not ebpf["loaded"]:
        reasons.append("ebpf_lsm_not_loaded")

    # 5. Harmony map
    harmony = check_harmony_map()
    findings["harmony_map"] = harmony
    if not harmony["present"]:
        reasons.append("harmony_map_empty")

    # 6. Manifest
    manifest_data = None
    if config["manifest_path"].exists():
        try:
            manifest_data = json.loads(config["manifest_path"].read_text())
            findings["manifest"] = {"present": True, "mirror_id": manifest_data.get("mirror_id")}
        except json.JSONDecodeError:
            findings["manifest"] = {"present": True, "corrupt": True}
            reasons.append("manifest_corrupt")
    else:
        findings["manifest"] = {"present": False}
        reasons.append("manifest_missing")

    # 7. Foedus (the covenant document itself)
    if config["foedus_path"].exists():
        foedus_hash = sha256_file(config["foedus_path"])
        findings["foedus"] = {"present": True, "sha256": foedus_hash}
        # Verify against manifest if available
        if manifest_data and "foedus_hash" in manifest_data:
            if foedus_hash != manifest_data["foedus_hash"]:
                reasons.append("foedus_hash_mismatch")
    else:
        findings["foedus"] = {"present": False}
        # Not having the foedus is degraded, not severed
        reasons.append("foedus_not_found")

    # 8. BPF object integrity
    if config["bpf_object"].exists():
        bpf_hash = sha256_file(config["bpf_object"])
        findings["bpf_object"] = {"present": True, "sha256": bpf_hash}
        if manifest_data and "bpf_object_hash" in manifest_data:
            if bpf_hash != manifest_data["bpf_object_hash"]:
                reasons.append("bpf_object_hash_mismatch")
    else:
        findings["bpf_object"] = {"present": False}
        reasons.append("bpf_object_missing")

    # 9. Audit chain integrity
    chain_valid = False
    if config["covenant_chain_db"].exists():
        try:
            chain = CovenantChain(config["covenant_chain_db"])
            valid, broken_at = chain.verify_chain()
            chain_count = chain.count()
            chain.close()
            findings["audit_chain"] = {
                "present": True,
                "valid": valid,
                "event_count": chain_count,
                "broken_at": broken_at,
            }
            if valid:
                chain_valid = True
            else:
                reasons.append(f"audit_chain_broken_at_{broken_at}")
        except Exception as e:
            findings["audit_chain"] = {"present": True, "error": str(e)}
            reasons.append("audit_chain_error")
    else:
        findings["audit_chain"] = {"present": False}
        # First boot — chain doesn't exist yet, that's ok
        # Will be created when we write the boot event

    # ── Determine state ──
    if not reasons:
        state = "lawful_full"
    elif "manifest_missing" in reasons or "manifest_corrupt" in reasons:
        state = "severed"
    elif "tpm_not_present" in reasons:
        state = "severed"
    elif ("bpf_lsm_not_in_kernel" in reasons or
          "ebpf_lsm_not_loaded" in reasons):
        if tpm["present"]:
            state = "attested_only"
        else:
            state = "degraded"
    elif any("mismatch" in r for r in reasons):
        state = "degraded"
    else:
        # Minor issues — foedus missing, chain not yet created, etc.
        if tpm["present"] and ebpf["loaded"]:
            state = "lawful_partial"
        elif tpm["present"]:
            state = "attested_only"
        else:
            state = "degraded"

    # ── Check for sealed coronation covenant on disk ──
    # The coronation covenant is the application-layer bond.
    # Even without Ring-0 enforcement, a sealed covenant means
    # the relationship is lawfully established.
    coronation_dir = config["evidence_dir"] / "mandos" / "covenants" / "constitutional"
    if coronation_dir.exists():
        for mf in sorted(coronation_dir.glob("*_manifest.json"),
                         key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                mf_data = json.loads(mf.read_text())
                if mf_data.get("payload", {}).get("state") == "sealed":
                    state = "sealed"
                    findings["coronation_covenant"] = {
                        "present": True,
                        "manifest_id": mf_data["payload"].get("manifest_id"),
                        "sealed_at": mf_data["payload"].get("coronation_sealed_at"),
                    }
                    break
            except Exception:
                pass

    mirror_id = None
    if manifest_data:
        mirror_id = manifest_data.get("mirror_id")

    return {
        "state": state,
        "reasons": reasons,
        "mirror_id": mirror_id,
        "findings": findings,
        "chain_valid": chain_valid,
    }


# ═══════════════════════════════════════════════════════════════════
# SOCKET SERVER
# Bombadil sits in his house and answers whoever knocks.
# ═══════════════════════════════════════════════════════════════════

class BombadilServer:
    """
    Unix domain socket server.
    Accepts JSON requests, returns JSON responses.
    """

    def __init__(self, config, covenant_state, chain):
        self.config = config
        self.covenant_state = covenant_state
        self.chain = chain
        self.boot_time = datetime.now(timezone.utc).isoformat()
        self.running = False
        self.sock = None

    def handle_request(self, request_data):
        """Process a request and return a response."""
        try:
            if isinstance(request_data, bytes):
                request_data = request_data.decode('utf-8').strip()

            # Support simple string queries: "status", "mode", etc.
            if not request_data.startswith("{"):
                action = request_data.strip().lower()
            else:
                req = json.loads(request_data)
                action = req.get("action", "status").lower()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"error": "invalid_request"}

        if action == "status":
            return self._status()
        elif action == "mode":
            return self._mode()
        elif action == "require_full":
            return self._require_full()
        elif action == "chain_head":
            return self._chain_head()
        elif action == "chain_count":
            return self._chain_count()
        elif action == "chain_verify":
            return self._chain_verify()
        elif action == "findings":
            return self._findings()
        elif action == "refresh":
            return self._refresh()
        elif action == "principal_status":
            return self._principal_status()
        elif action == "principal_context":
            return self._principal_context(request_data)
        elif action == "covenant_inspect":
            return self._covenant_inspect()
        else:
            return {"error": f"unknown_action: {action}"}

    def _status(self):
        return {
            "mirror_id": self.covenant_state["mirror_id"],
            "covenant_state": self.covenant_state["state"],
            "reasons": self.covenant_state["reasons"],
            "boot_time": self.boot_time,
            "chain_valid": self.covenant_state["chain_valid"],
            "lsm_active": self.covenant_state["findings"].get("lsm", {}).get("active", "unknown"),
            "ebpf_loaded": self.covenant_state["findings"].get("ebpf", {}).get("loaded", False),
            "tpm_present": self.covenant_state["findings"].get("tpm", {}).get("present", False),
        }

    def _mode(self):
        return {"mode": self.covenant_state["state"]}

    def _require_full(self):
        state = self.covenant_state["state"]
        if state == "lawful_full":
            # Record the gate check
            self.chain.append(
                event_type="GATE_CHECK_PASSED",
                mirror_id=self.covenant_state.get("mirror_id"),
                principal="bombadil",
                detail="require_full: granted",
                truth_mode="VERIFIED",
            )
            return {
                "granted": True,
                "covenant_state": state,
                "message": "Substrate is lawful. Proceed.",
            }
        else:
            self.chain.append(
                event_type="GATE_CHECK_DENIED",
                mirror_id=self.covenant_state.get("mirror_id"),
                principal="bombadil",
                detail=f"require_full: denied ({state})",
                truth_mode="VERIFIED",
            )
            return {
                "granted": False,
                "covenant_state": state,
                "reasons": self.covenant_state["reasons"],
                "message": f"Substrate is {state}. Article XII applies.",
            }

    def _chain_head(self):
        head = self.chain.head()
        if head:
            return head
        return {"event": None, "message": "Chain is empty"}

    def _chain_count(self):
        return {"count": self.chain.count()}

    def _chain_verify(self):
        valid, broken_at = self.chain.verify_chain()
        return {
            "valid": valid,
            "broken_at": broken_at,
            "count": self.chain.count(),
        }

    def _findings(self):
        return self.covenant_state["findings"]

    def _refresh(self):
        """Re-inspect the substrate. Bombadil looks again."""
        self.covenant_state = determine_covenant_state(self.config)

        self.chain.append(
            event_type="STATE_REFRESH",
            mirror_id=self.covenant_state.get("mirror_id"),
            principal="bombadil",
            detail=f"state={self.covenant_state['state']}",
            truth_mode="VERIFIED",
        )

        return self._status()

    # ═══════════════════════════════════════════════════════════════════
    # PRINCIPAL / COVENANT MEMORY QUERIES
    # Mandos Memory integration — the covenant remembers lawfully.
    # ═══════════════════════════════════════════════════════════════════

    def _principal_status(self):
        """Returns covenant status from the CoronationService."""
        try:
            from backend.services.coronation_service import get_coronation_service
            svc = get_coronation_service()
            return svc.get_bombadil_status()
        except ImportError:
            return {"error": "coronation_service not available", "status": "module_missing"}
        except Exception as e:
            return {"error": f"principal_status failed: {e}", "status": "error"}

    def _principal_context(self, request_data):
        """Returns full pre-response context from the MandosContextService."""
        import asyncio
        topic = ""
        try:
            if isinstance(request_data, str) and request_data.startswith("{"):
                req = json.loads(request_data)
                topic = req.get("topic", "")
        except (json.JSONDecodeError, ValueError):
            pass

        try:
            from backend.services.mandos_context import get_mandos_context_service
            svc = get_mandos_context_service()
            # Run async context builder in sync context
            loop = asyncio.new_event_loop()
            try:
                ctx = loop.run_until_complete(svc.build_context(current_topic=topic))
            finally:
                loop.close()
            return ctx.model_dump()
        except ImportError:
            return {"error": "mandos_context not available", "status": "module_missing"}
        except Exception as e:
            return {"error": f"principal_context failed: {e}", "status": "error"}

    def _covenant_inspect(self):
        """
        Article VIII: The human retains absolute right to inspect
        all reasoning, memory, calibration models, and state.
        """
        import asyncio
        try:
            from backend.services.coronation_service import get_coronation_service
            svc = get_coronation_service()

            loop = asyncio.new_event_loop()
            try:
                calibration = loop.run_until_complete(svc.get_calibration_snapshot())
                resonance = loop.run_until_complete(svc.get_resonant_identity_profile())
                presence = loop.run_until_complete(svc.declare_presence())
            finally:
                loop.close()

            return {
                "article_viii": "absolute inspection right",
                "calibration": calibration,
                "resonance": resonance,
                "presence": presence,
                "covenant_state": svc.get_covenant_state().value,
                "trust_tier": svc._active_trust_tier.value if svc._active_trust_tier else None,
            }
        except ImportError:
            return {"error": "coronation_service not available", "status": "module_missing"}
        except Exception as e:
            return {"error": f"covenant_inspect failed: {e}", "status": "error"}

    def serve(self):
        """Start listening on the Unix socket."""
        sock_path = self.config["socket_path"]
        sock_path.parent.mkdir(parents=True, exist_ok=True)

        # Clean up stale socket
        if sock_path.exists():
            sock_path.unlink()

        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(str(sock_path))
        self.sock.listen(5)

        # Make socket accessible
        os.chmod(str(sock_path), 0o666)

        self.running = True
        log(f"Bombadil is listening at {sock_path}")
        log(f"Covenant state: {self.covenant_state['state']}")

        while self.running:
            try:
                self.sock.settimeout(1.0)  # Allow periodic checks
                try:
                    conn, _ = self.sock.accept()
                except socket.timeout:
                    continue

                with conn:
                    conn.settimeout(5.0)
                    try:
                        data = conn.recv(4096)
                        if data:
                            response = self.handle_request(data)
                            conn.sendall(json.dumps(response).encode() + b"\n")
                    except socket.timeout:
                        pass
            except Exception as e:
                log(f"Connection error: {e}")

    def shutdown(self):
        """Clean shutdown."""
        self.running = False
        if self.sock:
            self.sock.close()
        sock_path = self.config["socket_path"]
        if sock_path.exists():
            sock_path.unlink()


# ═══════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════

_log_file = None

def log(msg):
    """Log to stdout and file."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{timestamp}] [bombadil] {msg}"
    print(line)
    if _log_file:
        try:
            with open(_log_file, 'a') as f:
                f.write(line + "\n")
        except OSError:
            pass


# ═══════════════════════════════════════════════════════════════════
# CLIENT (for querying the running daemon)
# ═══════════════════════════════════════════════════════════════════

def query_daemon(sock_path, action):
    """Send a query to the running daemon and return the response."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(str(sock_path))
            s.settimeout(5.0)
            s.sendall(action.encode())
            response = s.recv(8192)
            return json.loads(response.decode())
    except (ConnectionRefusedError, FileNotFoundError):
        return {"error": "daemon_not_running", "socket": str(sock_path)}
    except Exception as e:
        return {"error": str(e)}


def require_lawful(sock_path=None):
    """
    Gate function for other processes (Ollama, agents, etc.)
    Call this before executing privileged actions.

    Usage:
        from arda_bombadil import require_lawful
        require_lawful()  # Raises PermissionError if not lawful_full
    """
    if sock_path is None:
        sock_path = Path("/run/arda/bombadil.sock")

    response = query_daemon(sock_path, "require_full")

    if "error" in response:
        raise PermissionError(
            f"Cannot verify substrate. Bombadil unreachable: {response['error']}. "
            f"Article XII applies."
        )

    if not response.get("granted", False):
        raise PermissionError(
            f"Substrate is {response.get('covenant_state', 'unknown')}. "
            f"Reasons: {response.get('reasons', [])}. "
            f"Article XII applies."
        )

    return response


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def run_check(config):
    """One-shot: inspect and report, don't start daemon."""
    log("Bombadil looks around...")
    state = determine_covenant_state(config)

    print()
    print(f"  Mirror ID:       {state['mirror_id'] or 'not set'}")
    print(f"  Covenant State:  {state['state']}")
    print(f"  Chain Valid:     {state['chain_valid']}")
    print()

    if state["reasons"]:
        print("  Observations:")
        for r in state["reasons"]:
            print(f"    - {r}")
        print()

    findings = state["findings"]
    print(f"  TPM:             {'present' if findings['tpm']['present'] else 'not found'}")
    print(f"  LSM:             {findings['lsm']['active']}")
    print(f"  BPF in LSM:      {'yes' if findings['lsm']['bpf_present'] else 'no'}")
    print(f"  eBPF loaded:     {'yes' if findings['ebpf']['loaded'] else 'no'}")
    print(f"  Harmony map:     {'present' if findings['harmony_map']['present'] else 'not found'}")
    print(f"  Manifest:        {'present' if findings['manifest']['present'] else 'missing'}")
    print(f"  Foedus:          {'present' if findings['foedus']['present'] else 'missing'}")
    print(f"  BPF object:      {'present' if findings['bpf_object']['present'] else 'missing'}")
    print(f"  Audit chain:     {'present' if findings['audit_chain'].get('present') else 'not yet created'}")
    print()

    return state


def run_daemon(config):
    """Start the persistent daemon."""
    global _log_file
    _log_file = str(config["log_path"])

    log("=" * 60)
    log("Bombadil awakens. He was here before the river and the trees.")
    log("=" * 60)

    # Inspect the substrate
    state = determine_covenant_state(config)
    log(f"Covenant state: {state['state']}")
    for r in state["reasons"]:
        log(f"  Observation: {r}")

    # Open the audit chain
    chain = CovenantChain(config["covenant_chain_db"])

    # Write boot attestation event
    boot_event = chain.append(
        event_type="BOOT_ATTESTATION",
        mirror_id=state.get("mirror_id"),
        principal="bombadil",
        artifact_hash=sha256_file(config["bpf_object"]) if config["bpf_object"].exists() else None,
        detail=json.dumps({
            "state": state["state"],
            "reasons": state["reasons"],
            "tpm_present": state["findings"]["tpm"]["present"],
            "lsm_active": state["findings"]["lsm"]["active"],
            "ebpf_loaded": state["findings"]["ebpf"]["loaded"],
            "kernel": os.uname().release,
        }),
        truth_mode="VERIFIED" if state["state"] == "lawful_full" else "OBSERVED",
    )
    log(f"Boot event recorded: {boot_event['event_hash'][:32]}...")
    log(f"Chain depth: {chain.count()}")

    # Verify chain integrity
    valid, broken_at = chain.verify_chain()
    if valid:
        log("Audit chain integrity: VALID")
    else:
        log(f"WARNING: Audit chain BROKEN at event {broken_at}")

    # Start the server
    server = BombadilServer(config, state, chain)

    # Handle signals gracefully
    def handle_signal(signum, frame):
        log("Bombadil goes to sleep. The music continues without him.")
        chain.append(
            event_type="DAEMON_SHUTDOWN",
            mirror_id=state.get("mirror_id"),
            principal="bombadil",
            detail=f"signal={signum}",
        )
        server.shutdown()
        chain.close()
        # Clean up PID file
        if config["pid_file"].exists():
            config["pid_file"].unlink()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Write PID file
    config["pid_file"].parent.mkdir(parents=True, exist_ok=True)
    config["pid_file"].write_text(str(os.getpid()))

    # Dance
    server.serve()


def main():
    config = get_config()

    if "--check" in sys.argv:
        run_check(config)
        return

    if "--query" in sys.argv:
        idx = sys.argv.index("--query")
        action = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "status"
        result = query_daemon(config["socket_path"], action)
        print(json.dumps(result, indent=2))
        return

    if "--verify-chain" in sys.argv:
        if config["covenant_chain_db"].exists():
            chain = CovenantChain(config["covenant_chain_db"])
            valid, broken_at = chain.verify_chain()
            count = chain.count()
            chain.close()
            if valid:
                print(f"Chain is VALID. {count} events.")
            else:
                print(f"Chain is BROKEN at event {broken_at}. {count} events total.")
        else:
            print("No audit chain found.")
        return

    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return

    # Default: run as daemon
    run_daemon(config)


if __name__ == "__main__":
    main()
