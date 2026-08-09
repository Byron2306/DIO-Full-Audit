import os
import signal
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

try:
    from schemas.phase5_models import ExecLineage, ExecutionClass, ProcessBirthDecision
except Exception:
    from backend.schemas.phase5_models import ExecLineage, ExecutionClass, ProcessBirthDecision

logger = logging.getLogger(__name__)

class ProcessLineageService:
    """
    The Ancestry of Truth.
    Tracks the constitutional lineage of manifested processes.
    """
    
    def __init__(self, db: Any = None):
        self.db = db
        self._lineage: Dict[int, ExecLineage] = {} # Active process lineage

    def record_manifestation(self, pid: int, ppid: int, node_id: str, herald_id: str, covenant_id: str, 
                             decision: ProcessBirthDecision, execution_class: ExecutionClass) -> ExecLineage:
        """
        Seal the constitutional record of a manifested process.
        """
        lineage = ExecLineage(
            pid=pid,
            ppid=ppid,
            node_id=node_id,
            herald_identity=herald_id,
            covenant_ref=covenant_id,
            token_id=decision.request_ref, # Assuming request ID as token ref for lineage
            manifested_at=datetime.now(timezone.utc),
            execution_class=execution_class,
            status="active"
        )
        
        self._lineage[pid] = lineage
        logger.info(f"PHASE V: Lineage recorded for PID {pid} (Parent: {ppid}). Lawful manifest confirmed.")
        return lineage

    def get_lineage(self, pid: int) -> Optional[ExecLineage]:
        return self._lineage.get(pid)

    def prune_lineage(self, pid: int):
        if pid in self._lineage:
            logger.debug(f"PHASE V: Pruning lineage for exited PID {pid}")
            del self._lineage[pid]

    def terminate_unlawful_process(self, pid: int, reason: str = "Unknown"):
        """
        [PHASE V] ENFORCEMENT: Kill a process that has lost its constitutional right to exist.
        """
        if pid in self._lineage:
            logger.error(f"PHASE V: ENFORCEMENT KILL for PID {pid}. Reason: {reason}")
            try:
                # Use 9 (SIGKILL) on POSIX, TerminateProcess on Windows
                os.kill(pid, getattr(signal, "SIGKILL", 9))
                self._lineage[pid].status = "terminated"
                logger.warning(f"PHASE V: Process {pid} purged from machine domain.")
            except ProcessLookupError:
                logger.warning(f"PHASE V: PID {pid} already dead - purging lineage records.")
                self.prune_lineage(pid)
            except Exception as e:
                logger.error(f"PHASE V: Failed to terminate {pid}: {e}")

    def get_active_protected_count(self) -> int:
        return len([l for l in self._lineage.values() if l.execution_class == ExecutionClass.PROTECTED and l.status == "active"])

    async def audit_lineage_integrity(self) -> float:
        """
        Re-verify that all active protected processes still hold lawful covenants.
        If any are found without valid lineage, they are terminated immediately.
        """
        total_lineages = len(self._lineage)
        if total_lineages == 0: return 1.0
        
        valid_count = 0
        pids_to_kill = []
        
        for pid, lineage in self._lineage.items():
            # Check if process is actually alive
            is_alive = False
            try:
                os.kill(pid, 0) # Test signal
                is_alive = True
            except ProcessLookupError:
                is_alive = False
            
            if not is_alive:
                pids_to_kill.append((pid, "Process disappeared from kernel table."))
                continue
                
            # Verification logic (In production, would re-verify with HandoffCovenantService)
            if lineage.status != "active":
                pids_to_kill.append((pid, "Status is no longer active."))
                continue
            
            valid_count += 1
            
        # Perform cleanup/enforcement
        for pid, reason in pids_to_kill:
            if pid in self._lineage:
                self.terminate_unlawful_process(pid, reason)
                
        return valid_count / total_lineages if total_lineages > 0 else 1.0

# Global singleton
lineage_service = ProcessLineageService()

def get_process_lineage_service(db: Any = None) -> ProcessLineageService:
    global lineage_service
    if db: lineage_service.db = db
    return lineage_service
