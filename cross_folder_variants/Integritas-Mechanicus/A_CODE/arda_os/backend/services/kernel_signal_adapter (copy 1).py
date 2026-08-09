import psutil
import os
import logging
import asyncio
import uuid
import random
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from backend.schemas.phase5_models import KernelObservation, PrivilegeTransition, SyscallRiskEvent
from backend.schemas.phase7_models import KernelExecVerdict, KernelSovereigntySnapshot
from backend.services.telemetry_chain import tamper_evident_telemetry
from backend.services.kernel_audit_tailer import KernelAuditTailer
from backend.services.process_lineage_service import get_process_lineage_service

logger = logging.getLogger(__name__)

class KernelSignalAdapterService:
    """
    The Machine Voice.
    Normalizes low-level kernel signals into Seraph-grade law.
    """
    
    def __init__(self, db: Any = None):
        self.db = db
        self.telemetry = tamper_evident_telemetry
        self._risk_buffer: List[KernelObservation] = []

    async def start_observer(self):
        """
        [PHASE V] VM INTEGRATION BRIDGE
        Launches both the Audit Log Tailer and the Process Tree delta monitor.
        This provides the final 'Gatekeeper' link between the machine and the Triune.
        """
        logger.info("PHASE V: Starting Unified Machine Integration Bridge...")
        
        try:
            from services.kernel_audit_tailer import KernelAuditTailer
        except Exception:
            from backend.services.kernel_audit_tailer import KernelAuditTailer
            
        self.tailer = KernelAuditTailer()
        
        # 1. Start the Real-time Audit Stream (Background Task)
        asyncio.create_task(self.tailer.start_tailing(self.ingest_event))
        
        # 2. Start the Machine Process Delta Monitor (Live psutil)
        seen_pids = set(psutil.pids())
        while True:
            await asyncio.sleep(2.0) # Faster Machine Pulse for VM integration
            current_pids = set(psutil.pids())
            new_pids = current_pids - seen_pids
            exited_pids = seen_pids - current_pids
            
            try:
                from services.process_lineage_service import get_process_lineage_service
            except Exception:
                from backend.services.process_lineage_service import get_process_lineage_service
            
            lineage_svc = get_process_lineage_service(self.db)
            [lineage_svc.prune_lineage(p) for p in exited_pids]
            
            # Inspect new manifestations (Auditd catches exec, psutil catches what auditd missed)
            for pid in new_pids:
                try:
                    p = psutil.Process(pid)
                    await self._audit_new_process(p, lineage_svc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            seen_pids = current_pids

    async def _audit_new_process(self, proc: psutil.Process, lineage_svc: Any):
        """
        Assess if a new machine-level manifestation is LAWFUL or FRACTURED.
        """
        pid = proc.pid
        lineage = lineage_svc.get_lineage(pid)
        
        if lineage:
            # Lawful birth - registered by ProtectedExecWrapper
            logger.debug(f"PHASE V: Verified Lawful Lineage for PID {pid} ({proc.name()})")
            return
            
        # Potentially unauthorized manifestation
        # In a real Triune, we'd check if the binary is in a 'PROTECTED' path
        # For now, we score based on 'sudo' or 'admin' strings in name or cmdline
        risk = 0.1
        cmdline = " ".join(proc.cmdline())
        if "sudo" in cmdline.lower() or "admin" in cmdline.lower():
            risk = 0.95
            
        await self.ingest_event(
            node_id="local-node", # Placeholder
            event_type="UNHERALDED_MANIFESTATION",
            pid=pid,
            payload={
                "name": proc.name(),
                "cmdline": cmdline,
                "created": datetime.fromtimestamp(proc.create_time(), tz=timezone.utc).isoformat()
            }
        )

    async def ingest_event(self, node_id: str, event_type: str, pid: int, payload: Dict[str, Any]):
        """
        Direct entry point for eBPF or Audit probes.
        """
        risk_score = self._evaluate_risk(event_type, pid, payload)
        
        observation = KernelObservation(
            node_id=node_id,
            event_type=event_type,
            source_pid=pid,
            raw_payload=payload,
            risk_score=risk_score
        )
        
        self._risk_buffer.append(observation)
        if len(self._risk_buffer) > 100: self._risk_buffer.pop(0)

        # Record to telemetry
        try:
            self.telemetry.ingest_event(
                event_type=f"kernel:{event_type}",
                severity="info" if risk_score < 0.5 else "warning",
                data=observation.model_dump(mode='json')
            )
        except Exception as e:
            logger.error(f"PHASE VII: Telemetry ingestion failed: {e}")
        
        # --- PHASE VII: EXECUTION INTERCEPTION FEEDBACK ---
        if event_type == "EXEC_INTERCEPT":
            if payload.get("verdict") in ["deny", "kill"]:
                logger.error(f"PHASE VII: SUBSTRATE SOVEREIGNTY VETO! {payload.get('path')} blocked.")
        # ---------------------------------------------------

        if risk_score >= 0.8 and event_type != "EXEC_INTERCEPT":
            logger.error(f"PHASE VII: HIGH RISK KERNEL EVENT! {event_type} from PID {pid} (score: {risk_score:.2f})")
            try:
                from services.process_lineage_service import get_process_lineage_service
            except Exception:
                from backend.services.process_lineage_service import get_process_lineage_service
            
            lineage_svc = get_process_lineage_service(self.db)
            lineage_svc.terminate_unlawful_process(pid, f"Extreme Risk Event: {event_type}")
            
        return observation

    def _evaluate_risk(self, etype: str, pid: int, payload: Dict[str, Any]) -> float:
        """
        Assess risk of a kernel signal based on constitution.
        """
        # (Mock logic)
        if etype == "setuid" and payload.get("new_uid") == 0:
            return 0.95 # Sudo-like escalation
        if etype == "exec" and "/tmp" in payload.get("path", ""):
            return 0.7 # Suspicious path execution
        return 0.1

    def get_recent_anomalies(self) -> List[KernelObservation]:
        return [o for o in self._risk_buffer if o.risk_score >= 0.5]

    async def _run_simulated_audit(self):
        """
        Periodically audit local process tree manifest.
        """
        logger.debug("PHASE V: Performing kernel-adjacent manifesting audit...")
        # (Mock logic - scan PIDs etc.)
        pass

# Global singleton
kernel_adapter = KernelSignalAdapterService()

def get_kernel_signal_adapter(db: Any = None) -> KernelSignalAdapterService:
    global kernel_adapter
    if db: kernel_adapter.db = db
    return kernel_adapter
