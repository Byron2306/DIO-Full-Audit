"""
WindowsEvidenceProvider
========================
Implements EvidenceProvider for Windows using native telemetry sources:

  • Varda  (file/registry integrity)  — Sysmon Event IDs 11/12/13 via Get-WinEvent
  • Ulmo   (network flow)             — Windows Firewall log + netstat ETW
  • Manwë  (process lineage)          — Sysmon Event IDs 1/5 + WMI Win32_Process
  • Mandos (threat/AV verdicts)       — Windows Defender via MSFT_MpThreatDetection WMI

All collectors degrade gracefully: if the required Windows API is absent
(e.g. running on Linux in dev), confidence is set to 0.0 and the evidence
dict contains a 'stub': True marker so consumers can filter.
"""
from __future__ import annotations

import json
import logging
import platform
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models import EvidencePacket

logger = logging.getLogger(__name__)

_IS_WINDOWS = platform.system() == "Windows"


def _run_ps(script: str, timeout: int = 20) -> Optional[str]:
    try:
        result = subprocess.run(
            ["powershell.exe", "-NonInteractive", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        logger.debug("PS exit %d stderr: %s", result.returncode, result.stderr[:200])
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.debug("PowerShell unavailable: %s", exc)
    return None


def _new_sweep_id() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Helper: query Windows Event Log via Get-WinEvent
# ---------------------------------------------------------------------------

def _get_win_events(log_name: str, event_ids: List[int], max_events: int = 100) -> List[Dict[str, Any]]:
    id_filter = " -or ".join(f"$_.Id -eq {i}" for i in event_ids)
    script = (
        f"try {{ "
        f"  Get-WinEvent -LogName '{log_name}' -MaxEvents {max_events} "
        f"  -ErrorAction Stop "
        f"  | Where-Object {{ {id_filter} }} "
        f"  | Select-Object TimeCreated, Id, Message "
        f"  | ConvertTo-Json -Depth 2 "
        f"}} catch {{ Write-Output '[]' }}"
    )
    raw = _run_ps(script)
    if not raw or raw == "[]":
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        return []


# ---------------------------------------------------------------------------
# WindowsEvidenceProvider
# ---------------------------------------------------------------------------

class WindowsEvidenceProvider:
    """
    Collects evidence from four Ainur-aligned Windows telemetry sources.
    Each collect_* method returns an EvidencePacket with:
      - source:     collector name
      - confidence: 1.0 = live Windows data, 0.0 = stub
      - evidence:   structured payload consumed by constitutional layer
    """

    # -----------------------------------------------------------------------
    # Varda — file & registry integrity (Sysmon channels 11, 12, 13)
    # -----------------------------------------------------------------------

    def collect_varda_evidence(self, context: Dict[str, object]) -> EvidencePacket:
        """
        Varda watches what was *created* and *changed*.
        On Windows: Sysmon Event 11 (FileCreate), 12/13 (RegistryEvent).
        """
        sweep_id = _new_sweep_id()
        if not _IS_WINDOWS:
            return self._stub_packet("varda_windows", sweep_id)

        file_events = _get_win_events(
            "Microsoft-Windows-Sysmon/Operational", [11], max_events=50
        )
        reg_events = _get_win_events(
            "Microsoft-Windows-Sysmon/Operational", [12, 13], max_events=50
        )

        confidence = 1.0 if (file_events or reg_events) else 0.5
        return EvidencePacket(
            source="varda_windows",
            confidence=confidence,
            sweep_id=sweep_id,
            evidence={
                "collected_at": _now_iso(),
                "file_creation_events": self._parse_sysmon_events(file_events),
                "registry_events": self._parse_sysmon_events(reg_events),
                "event_counts": {
                    "file_create": len(file_events),
                    "registry_modify": len(reg_events),
                },
                "sysmon_operational": bool(file_events or reg_events),
            },
        )

    # -----------------------------------------------------------------------
    # Ulmo — network flow (Windows Firewall log + netstat)
    # -----------------------------------------------------------------------

    def collect_ulmo_evidence(self, context: Dict[str, object]) -> EvidencePacket:
        """
        Ulmo watches what flows across boundaries.
        On Windows: Firewall log + live netstat ETW snapshot.
        """
        sweep_id = _new_sweep_id()
        if not _IS_WINDOWS:
            return self._stub_packet("ulmo_windows", sweep_id)

        connections = self._read_netstat()
        firewall_events = _get_win_events(
            "Security", [5156, 5157, 5158], max_events=100  # Filtering Platform Connection
        )

        confidence = 1.0 if connections else 0.5
        return EvidencePacket(
            source="ulmo_windows",
            confidence=confidence,
            sweep_id=sweep_id,
            evidence={
                "collected_at": _now_iso(),
                "active_connections": connections,
                "firewall_allow_events": len([e for e in firewall_events if e.get("Id") == 5156]),
                "firewall_block_events": len([e for e in firewall_events if e.get("Id") == 5157]),
                "raw_firewall_sample": self._parse_sysmon_events(firewall_events[:10]),
            },
        )

    def _read_netstat(self) -> List[Dict[str, str]]:
        script = (
            "Get-NetTCPConnection | "
            "Select-Object LocalAddress,LocalPort,RemoteAddress,RemotePort,State,OwningProcess | "
            "ConvertTo-Json -Depth 2"
        )
        raw = _run_ps(script)
        if not raw:
            return []
        try:
            data = json.loads(raw)
            rows = data if isinstance(data, list) else [data]
            return [
                {
                    "local": f"{r.get('LocalAddress')}:{r.get('LocalPort')}",
                    "remote": f"{r.get('RemoteAddress')}:{r.get('RemotePort')}",
                    "state": str(r.get("State", "")),
                    "pid": str(r.get("OwningProcess", "")),
                }
                for r in rows
            ]
        except (json.JSONDecodeError, TypeError):
            return []

    # -----------------------------------------------------------------------
    # Manwë — process lineage (Sysmon 1/5 + WMI Win32_Process)
    # -----------------------------------------------------------------------

    def collect_manwe_evidence(self, context: Dict[str, object]) -> EvidencePacket:
        """
        Manwë knows what was created in the wind — process spawning chains.
        On Windows: Sysmon Event 1 (ProcessCreate), Event 5 (ProcessTerminate)
        + live Win32_Process snapshot for parent-child resolution.
        """
        sweep_id = _new_sweep_id()
        if not _IS_WINDOWS:
            return self._stub_packet("manwe_windows", sweep_id)

        create_events = _get_win_events(
            "Microsoft-Windows-Sysmon/Operational", [1], max_events=100
        )
        terminate_events = _get_win_events(
            "Microsoft-Windows-Sysmon/Operational", [5], max_events=50
        )
        live_procs = self._read_live_processes()

        confidence = 1.0 if create_events else (0.7 if live_procs else 0.0)
        return EvidencePacket(
            source="manwe_windows",
            confidence=confidence,
            sweep_id=sweep_id,
            evidence={
                "collected_at": _now_iso(),
                "process_create_events": self._parse_sysmon_events(create_events[:25]),
                "process_terminate_count": len(terminate_events),
                "live_process_snapshot": live_procs[:50],
                "sysmon_operational": bool(create_events),
            },
        )

    def _read_live_processes(self) -> List[Dict[str, Any]]:
        script = (
            "Get-WmiObject Win32_Process | "
            "Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine | "
            "ConvertTo-Json -Depth 2"
        )
        raw = _run_ps(script, timeout=25)
        if not raw:
            return []
        try:
            data = json.loads(raw)
            rows = data if isinstance(data, list) else [data]
            return [
                {
                    "pid": r.get("ProcessId"),
                    "ppid": r.get("ParentProcessId"),
                    "name": r.get("Name"),
                    "path": r.get("ExecutablePath"),
                    # CommandLine can be long; truncate to avoid packet bloat
                    "cmdline": str(r.get("CommandLine", ""))[:256],
                }
                for r in rows
            ]
        except (json.JSONDecodeError, TypeError):
            return []

    # -----------------------------------------------------------------------
    # Mandos — threat verdicts (Windows Defender via MSFT_MpThreatDetection)
    # -----------------------------------------------------------------------

    def collect_mandos_evidence(self, context: Dict[str, object]) -> EvidencePacket:
        """
        Mandos judges the dead — what Defender has condemned.
        On Windows: MSFT_MpThreatDetection WMI class (Defender namespace)
        + recent Security Event Log entries (4624/4625/4688).
        """
        sweep_id = _new_sweep_id()
        if not _IS_WINDOWS:
            return self._stub_packet("mandos_windows", sweep_id)

        threats = self._read_defender_threats()
        auth_events = _get_win_events("Security", [4624, 4625], max_events=50)  # Logon/Logon-fail
        process_events = _get_win_events("Security", [4688], max_events=50)     # Process creation

        confidence = 1.0 if threats is not None else 0.5
        return EvidencePacket(
            source="mandos_windows",
            confidence=confidence,
            sweep_id=sweep_id,
            evidence={
                "collected_at": _now_iso(),
                "defender_threats": threats or [],
                "threat_count": len(threats) if threats else 0,
                "logon_success_count": len([e for e in auth_events if e.get("Id") == 4624]),
                "logon_failure_count": len([e for e in auth_events if e.get("Id") == 4625]),
                "privileged_process_events": self._parse_sysmon_events(process_events[:20]),
            },
        )

    def _read_defender_threats(self) -> Optional[List[Dict[str, Any]]]:
        script = (
            "try { "
            "  Get-WmiObject -Namespace 'root\\Microsoft\\Windows\\Defender' "
            "    -Class MSFT_MpThreatDetection | "
            "  Select-Object ThreatName, DetectionTime, ActionSuccess, "
            "    RemediationTime, Resources | "
            "  ConvertTo-Json -Depth 3 "
            "} catch { Write-Output 'UNAVAILABLE' }"
        )
        raw = _run_ps(script, timeout=25)
        if not raw or raw == "UNAVAILABLE":
            return None
        try:
            data = json.loads(raw)
            rows = data if isinstance(data, list) else [data]
            return [
                {
                    "threat_name": r.get("ThreatName", "unknown"),
                    "detected_at": str(r.get("DetectionTime", "")),
                    "action_success": bool(r.get("ActionSuccess", False)),
                    "resources": r.get("Resources", []),
                }
                for r in rows
            ]
        except (json.JSONDecodeError, TypeError):
            return None

    # -----------------------------------------------------------------------
    # Shared helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _parse_sysmon_events(events: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Flatten raw Get-WinEvent dicts to a minimal structured form."""
        out = []
        for ev in events:
            out.append(
                {
                    "id": str(ev.get("Id", "")),
                    "time": str(ev.get("TimeCreated", "")),
                    "message_snippet": str(ev.get("Message", ""))[:300],
                }
            )
        return out

    @staticmethod
    def _stub_packet(source: str, sweep_id: str) -> EvidencePacket:
        return EvidencePacket(
            source=source,
            confidence=0.0,
            sweep_id=sweep_id,
            evidence={
                "stub": True,
                "reason": "Non-Windows host; live telemetry unavailable",
                "collected_at": _now_iso(),
            },
        )
