import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

try:
    from schemas.phase4_models import QuorumStatus
    from services.quorum_engine import get_quorum_engine
    from services.cluster_consensus_guard import get_cluster_consensus_guard
except Exception:
    from backend.schemas.phase4_models import QuorumStatus
    from backend.services.quorum_engine import get_quorum_engine
    from backend.services.cluster_consensus_guard import get_cluster_consensus_guard

logger = logging.getLogger(__name__)

class KernelConsensusGuardService:
    """
    The Sentinel of Creation.
    Binds the Cluster Chorus (Phase IV) to local Process Birth (Phase V).
    """
    
    def __init__(self, db: Any = None):
        self.db = db
        self.consensus_guard = get_cluster_consensus_guard()
        self.quorum_engine = get_quorum_engine()

    async def get_birth_verdict(self, binary_path: str, execution_class: str = "protected") -> str:
        """
        Final authoritative verdict on whether a process may be born based on cluster-wide reality.
        Returns: 'permit', 'caution', or 'veto'.
        """
        # Mapping Execution Classes to Cluster Sensitivity
        sensitivity = "high" if execution_class == "protected" else "medium"
        
        # Consult the Chorus (Phase IV)
        verdict = await self.consensus_guard.get_cluster_verdict(action_sensitivity=sensitivity)
        
        # Log the crossing of the Fourth and Fifth Phases
        if verdict == "veto":
            logger.error(f"PHASE IV/V VETO: Prohibiting birth of {binary_path} due to Cluster Dissonance.")
        elif verdict == "caution":
            logger.warning(f"PHASE IV/V CAUTION: Birth permitted but sandboxed for {binary_path}.")
            
        return verdict

    async def is_node_fractured(self) -> bool:
        """
        Determine if the current node is in a local temporal fracture.
        """
        decision = self.quorum_engine.get_last_decision()
        if decision and decision.status == QuorumStatus.FRACTURED:
            return True
        return False

# Global singleton
kernel_consensus_guard = KernelConsensusGuardService()

def get_kernel_consensus_guard(db: Any = None) -> KernelConsensusGuardService:
    global kernel_consensus_guard
    if db: kernel_consensus_guard.db = db
    return kernel_consensus_guard
