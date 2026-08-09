import asyncio
import os
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class KernelAuditTailer:
    """
    [PHASE V] VM Machine Bridge: Audit Log Tailer
    Tails /var/log/audit/audit.log or a specified path.
    Parses 'SYSCALL' and 'EXECVE' events into Seraph observations.
    """
    
    def __init__(self, log_path: str = "/var/log/audit/audit.log"):
        self.log_path = log_path
        self._callback = None
        self._stop_event = asyncio.Event()

    async def start_tailing(self, callback: Any):
        """
        Stream events from the machine's audit log.
        """
        self._callback = callback
        self._last_real_event_at = time.time()
        self._silence_threshold = 120.0 # 2 minutes
        
        logger.info(f"PHASE V: Machine Integration Bridge active on {self.log_path}")
        
        # Divergence from mock: if log is missing, it's a critical dissonance
        if not os.path.exists(self.log_path):
            logger.error(f"PHASE V: CRITICAL: Audit log {self.log_path} missing. Target may be blinded.")
            await self._raise_silence_dissonance("Audit log file missing on disk")
            # We still run the mock stream for testing, but the alert is fired
            await self._run_mock_stream()
            return

        # Simple file tailing loop
        with open(self.log_path, "r") as f:
            f.seek(0, os.SEEK_END)
            while not self._stop_event.is_set():
                line = f.readline()
                if not line:
                    # Check for suspicious silence
                    silence_duration = time.time() - self._last_real_event_at
                    if silence_duration > self._silence_threshold:
                        await self._raise_silence_dissonance(f"Suspicious silence: no audit events for {silence_duration:.0f}s")
                    
                    await asyncio.sleep(0.5)
                    continue
                
                self._last_real_event_at = time.time()
                await self._parse_and_dispatch(line)

    async def _raise_silence_dissonance(self, reason: str):
        """
        The Silence of Morgoth: Detects the absence of kernel signals.
        Ingests a critical dissonance event into the telemetry chain.
        """
        try:
            from backend.services.telemetry_chain import tamper_evident_telemetry
            tamper_evident_telemetry.ingest_event(
                event_type="morgoth_silence_detected",
                severity="critical",
                data={
                    "reason": reason,
                    "last_real_event_at": getattr(self, "_last_real_event_at", 0),
                    "audit_path": self.log_path
                },
                agent_id="kernel-watchdog"
            )
        except Exception as e:
            logger.error(f"Failed to raise silence dissonance: {e}")

    async def _parse_and_dispatch(self, line: str):
        """
        Parse auditd line: type=SYSCALL msg=audit(timestamp:id): arch=... syscall=59 exe="/bin/bash"
        """
        if "type=SYSCALL" not in line and "type=EXECVE" not in line:
            return
            
        # Basic parsing logic
        try:
            # Simple extraction for demo/bridge purposes
            event_type = "exec" if "syscall=59" in line else "syscall"
            pid = self._extract_field(line, "pid=")
            exe = self._extract_field(line, 'exe="', '"')
            cmdline = self._extract_field(line, 'cmdline="', '"') # Depends on audit rules
            
            payload = {
                "source": "auditd",
                "path": exe,
                "cmdline": cmdline,
                "raw": line.strip()
            }
            
            if self._callback:
                # Signature: node_id, event_type, pid, payload
                await self._callback("local-node", "REAL_TIME_AUDIT", int(pid) if pid else 0, payload)
                
        except Exception as e:
            logger.error(f"PHASE V: Audit parse error: {e}")

    def _extract_field(self, line: str, prefix: str, suffix: str = " ") -> Optional[str]:
        if prefix not in line: return None
        start = line.find(prefix) + len(prefix)
        end = line.find(suffix, start)
        return line[start:end] if end != -1 else line[start:]

    async def _run_mock_stream(self):
        """
        If the VM/WSL doesn't have auditd yet, we supply a rigorous synthetic stream
        to keep the Triune alive while the machine is being provisioned.
        """
        while not self._stop_event.is_set():
            await asyncio.sleep(30.0) # Periodic mock signals
            # Simulated suspicious activity for gauntlet testing
            mock_line = f'type=SYSCALL msg=audit({datetime.now(timezone.utc).timestamp()}): arch=c000003e syscall=59 success=yes exit=0 a0=7ffec3 pid=8888 ppid=1 auid=0 uid=0 gid=0 euid=0 suid=0 fsuid=0 exe="/usr/bin/sudo"'
            await self._parse_and_dispatch(mock_line)

    def stop(self):
        self._stop_event.set()
