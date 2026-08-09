"""
LinuxEvidenceProvider
======================
Implements EvidenceProvider using Linux-native telemetry sources:

  • Varda  (file/registry integrity)  — auditd syscall log (ausearch -sc open/write/unlink)
                                         + inotifywait where available
  • Ulmo   (network flow)             — ss -tunap + /proc/net/tcp{,6} + nftables log
  • Manwë  (process lineage)          — /proc enumeration + auditd execve events
  • Mandos (threat/AV verdicts)       — rkhunter summary + ClamAV clamscan log
                                         + /var/log/auth.log anomaly scan

All collectors degrade gracefully when tools or logs are absent.
"""
from __future__ import annotations

import glob
import json
import logging
import os
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import EvidencePacket

logger = logging.getLogger(__name__)


def _run(cmd: List[str], timeout: int = 15) -> Optional[str]:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        logger.debug("cmd %s exit %d: %s", cmd[0], result.returncode, result.stderr[:200])
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError) as exc:
        logger.debug("cmd %s unavailable: %s", cmd[0], exc)
    return None


def _new_sweep_id() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stub_packet(source: str, sweep_id: str) -> EvidencePacket:
    return EvidencePacket(
        source=source,
        confidence=0.0,
        sweep_id=sweep_id,
        evidence={"stub": True, "collected_at": _now_iso()},
    )


# ---------------------------------------------------------------------------
# LinuxEvidenceProvider
# ---------------------------------------------------------------------------

class LinuxEvidenceProvider:
    """
    Collects evidence from four Ainur-aligned Linux telemetry sources.
    Each collect_* method returns an EvidencePacket with confidence 0.0–1.0.
    """

    # -----------------------------------------------------------------------
    # Varda — file integrity (auditd file access events)
    # -----------------------------------------------------------------------

    def collect_varda_evidence(self, context: Dict[str, object]) -> EvidencePacket:
        """
        Varda watches what was created and changed.
        Linux: auditd file-write/create syscalls via ausearch.
        """
        sweep_id = _new_sweep_id()

        events = self._ausearch_events(["-sc", "open,openat,creat,unlink,rename"])
        ima_violations = self._read_ima_violations()

        confidence = 1.0 if events else (0.5 if ima_violations else 0.0)
        return EvidencePacket(
            source="varda_linux",
            confidence=confidence,
            sweep_id=sweep_id,
            evidence={
                "collected_at": _now_iso(),
                "audit_file_events": events[:100],
                "ima_violations": ima_violations[:50],
                "event_counts": {
                    "file_events": len(events),
                    "ima_violations": len(ima_violations),
                },
                "auditd_operational": len(events) > 0,
            },
        )

    def _ausearch_events(self, extra_args: List[str]) -> List[Dict[str, str]]:
        """Run ausearch and parse key=value pairs from each event."""
        raw = _run(["ausearch", "--start", "today"] + extra_args + ["-i"], timeout=10)
        if not raw:
            return []
        events: List[Dict[str, str]] = []
        current: Dict[str, str] = {}
        for line in raw.splitlines():
            if line.startswith("----"):
                if current:
                    events.append(current)
                    current = {}
            else:
                for kv in re.findall(r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)', line):
                    key, val = kv
                    current[key] = val.strip('"')
        if current:
            events.append(current)
        return events

    def _read_ima_violations(self) -> List[str]:
        """Scan IMA runtime measurements for policy violations."""
        path = "/sys/kernel/security/ima/violations"
        try:
            count = int(Path(path).read_text().strip())
            if count > 0:
                return [f"ima_violation_count={count}"]
        except Exception:
            pass
        return []

    # -----------------------------------------------------------------------
    # Ulmo — network flow (ss + /proc/net)
    # -----------------------------------------------------------------------

    def collect_ulmo_evidence(self, context: Dict[str, object]) -> EvidencePacket:
        """
        Ulmo watches what flows across boundaries.
        Linux: ss -tunap socket snapshot + /proc/net/nf_conntrack if available.
        """
        sweep_id = _new_sweep_id()

        connections = self._read_ss()
        conntrack = self._read_conntrack()

        confidence = 1.0 if connections else (0.6 if conntrack else 0.0)
        return EvidencePacket(
            source="ulmo_linux",
            confidence=confidence,
            sweep_id=sweep_id,
            evidence={
                "collected_at": _now_iso(),
                "active_connections": connections[:200],
                "conntrack_entries": len(conntrack),
                "connection_count": len(connections),
                "listening_ports": self._listening_ports(connections),
            },
        )

    def _read_ss(self) -> List[Dict[str, str]]:
        raw = _run(["ss", "-tunap", "--no-header"])
        if not raw:
            return []
        rows: List[Dict[str, str]] = []
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            rows.append({
                "netid": parts[0],
                "state": parts[1],
                "local": parts[4] if len(parts) > 4 else "",
                "peer": parts[5] if len(parts) > 5 else "",
                "process": parts[6] if len(parts) > 6 else "",
            })
        return rows

    def _read_conntrack(self) -> List[str]:
        path = "/proc/net/nf_conntrack"
        try:
            lines = Path(path).read_text(errors="replace").splitlines()
            return [l for l in lines if l.strip()]
        except Exception:
            return []

    def _listening_ports(self, connections: List[Dict[str, str]]) -> List[str]:
        ports = set()
        for c in connections:
            if c.get("state") == "LISTEN":
                addr = c.get("local", "")
                if ":" in addr:
                    ports.add(addr.rsplit(":", 1)[-1])
        return sorted(ports)

    # -----------------------------------------------------------------------
    # Manwë — process lineage (/proc + auditd execve)
    # -----------------------------------------------------------------------

    def collect_manwe_evidence(self, context: Dict[str, object]) -> EvidencePacket:
        """
        Manwë watches what was spawned.
        Linux: /proc enumeration + auditd execve events.
        """
        sweep_id = _new_sweep_id()

        processes = self._enumerate_processes()
        execve_events = self._ausearch_events(["-sc", "execve"])

        confidence = 1.0 if execve_events else (0.7 if processes else 0.0)
        return EvidencePacket(
            source="manwe_linux",
            confidence=confidence,
            sweep_id=sweep_id,
            evidence={
                "collected_at": _now_iso(),
                "process_count": len(processes),
                "processes": processes[:100],
                "execve_event_count": len(execve_events),
                "recent_execve": execve_events[:50],
            },
        )

    def _enumerate_processes(self) -> List[Dict[str, str]]:
        procs: List[Dict[str, str]] = []
        for pid_dir in glob.glob("/proc/[0-9]*"):
            try:
                pid = os.path.basename(pid_dir)
                cmdline = Path(f"{pid_dir}/cmdline").read_bytes().replace(b"\x00", b" ").decode(errors="replace").strip()
                comm = Path(f"{pid_dir}/comm").read_text().strip()
                status_text = Path(f"{pid_dir}/status").read_text()
                ppid = ""
                for line in status_text.splitlines():
                    if line.startswith("PPid:"):
                        ppid = line.split(":", 1)[1].strip()
                        break
                procs.append({"pid": pid, "ppid": ppid, "comm": comm, "cmdline": cmdline[:200]})
            except Exception:
                continue
        return procs

    # -----------------------------------------------------------------------
    # Mandos — threat verdicts (rkhunter + clamav + auth.log anomalies)
    # -----------------------------------------------------------------------

    def collect_mandos_evidence(self, context: Dict[str, object]) -> EvidencePacket:
        """
        Mandos watches for verdicts from AV/rootkit scanners.
        Linux: rkhunter log summary + ClamAV log + auth.log failed-auth scan.
        """
        sweep_id = _new_sweep_id()

        rkhunter_findings = self._read_rkhunter_log()
        clam_findings = self._read_clamav_log()
        auth_anomalies = self._scan_auth_log()

        has_data = bool(rkhunter_findings or clam_findings or auth_anomalies)
        confidence = 1.0 if has_data else 0.3  # low base even without findings
        return EvidencePacket(
            source="mandos_linux",
            confidence=confidence,
            sweep_id=sweep_id,
            evidence={
                "collected_at": _now_iso(),
                "rkhunter_findings": rkhunter_findings,
                "clamav_findings": clam_findings,
                "auth_anomalies": auth_anomalies[:50],
                "threat_count": len(rkhunter_findings) + len(clam_findings),
                "clean": not bool(rkhunter_findings or clam_findings),
            },
        )

    def _read_rkhunter_log(self) -> List[str]:
        candidates = [
            "/var/log/rkhunter.log",
            "/var/log/rkhunter/rkhunter.log",
        ]
        for path in candidates:
            try:
                lines = Path(path).read_text(errors="replace").splitlines()
                # Return lines that indicate warnings or infections
                return [
                    l.strip() for l in lines
                    if any(kw in l.lower() for kw in ["warning", "infected", "rootkit", "suspicious"])
                ][:30]
            except Exception:
                continue
        return []

    def _read_clamav_log(self) -> List[str]:
        candidates = [
            "/var/log/clamav/clamav.log",
            "/var/log/clamav/freshclam.log",
        ]
        findings = []
        for path in candidates:
            try:
                lines = Path(path).read_text(errors="replace").splitlines()
                findings += [
                    l.strip() for l in lines
                    if "found" in l.lower() or "infected" in l.lower()
                ]
            except Exception:
                continue
        return findings[:30]

    def _scan_auth_log(self) -> List[str]:
        candidates = [
            "/var/log/auth.log",
            "/var/log/secure",
        ]
        for path in candidates:
            try:
                lines = Path(path).read_text(errors="replace").splitlines()
                return [
                    l.strip() for l in lines[-500:]
                    if any(kw in l.lower() for kw in [
                        "failed password", "invalid user", "authentication failure",
                        "sudo:", "su:", "pam_unix(su"
                    ])
                ][:50]
            except Exception:
                continue
        return []
