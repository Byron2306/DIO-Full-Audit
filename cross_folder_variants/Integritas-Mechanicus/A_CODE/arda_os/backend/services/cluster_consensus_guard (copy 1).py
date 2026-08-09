import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

# (Imports moved to local scopes to prevent Phase IV structural deadlocks)

logger = logging.getLogger(__name__)

class ClusterConsensusGuardService:
    """
    The Sentinel of the Mesh.
    Provides the final authoritative verdict on whether the cluster's consensus 
    is legitimate enough for high-sensitivity actions.
    """
    
    def __init__(self):
        self._quorum_engine = None

    def _get_engine(self):
        if self._quorum_engine is None:
            try:
                from services.quorum_engine import get_quorum_engine
            except Exception:
                from backend.services.quorum_engine import get_quorum_engine
            self._quorum_engine = get_quorum_engine()
        return self._quorum_engine

    async def get_cluster_verdict(self, action_sensitivity: str = "medium") -> str:
        """
        Determines the cluster-wide consensus verdict for a specific action.
        Returns: 'permit', 'caution', or 'veto'.
        """
        try:
            from schemas.phase4_models import QuorumStatus
        except Exception:
            from backend.schemas.phase4_models import QuorumStatus
            
        engine = self._get_engine()
        decision = engine.get_last_decision()
        
        if not decision:
            # Cold start logic: Caution until first quorum is established
            logger.warning("PHASE IV: No quorum decision available (Cold Start).")
            return "caution"
            
        # 1. Action Sensitivity Mapping
        # High-sensitivity (e.g. quarantine, token rotation) requires supermajority resonance.
        # Medium-sensitivity (e.g. metadata updates) requires majority resonance.
        # Low-sensitivity (e.g. read-only audits) requires only local belief.
        
        status = decision.status
        consensus = decision.consensus_score
        
        if status == QuorumStatus.VETOED:
            # Any collective veto is a total block
            return "veto"
            
        if action_sensitivity == "high":
            if status == QuorumStatus.RESONANT and consensus >= 0.67:
                 return "permit"
            return "veto" if status == QuorumStatus.FRACTURED else "caution"
            
        if action_sensitivity == "medium":
            if status in {QuorumStatus.RESONANT, QuorumStatus.DEGRADED} and consensus >= 0.51:
                return "permit"
            return "caution"
            
        # Default safety for low-risk actions
        return "permit"

# Global singleton
cluster_consensus_guard = ClusterConsensusGuardService()

def get_cluster_consensus_guard() -> ClusterConsensusGuardService:
    global cluster_consensus_guard
    return cluster_consensus_guard
