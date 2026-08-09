import logging
import asyncio
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from backend.schemas.phase4_models import QuorumPolicy, QuorumDecision, QuorumStatus, ClusterView, PeerState

from backend.arda.ainur import AinurChoir
from backend.services.constitutional_projection import project_choir_truth

logger = logging.getLogger(__name__)

class QuorumEngineService:
    """
    The Soul of the Chorus.
    Judges the collective resonance of the Triune Mesh. 
    Not just "health" but quorum-authenticated sovereignty.
    """
    
    def __init__(self, policy: Optional[QuorumPolicy] = None):
        self._policy = policy or QuorumPolicy(
            policy_id="default-policy",
            min_nodes=3,
            supermajority_threshold=0.67,
            majority_threshold=0.51,
            strictness="cluster-enforced"
        )
        self._choir: Optional[AinurChoir] = None
        self._current_decision: Optional[QuorumDecision] = None
        self._last_view: Optional[ClusterView] = None

    @property
    def choir(self) -> AinurChoir:
        if self._choir is None:
            self._choir = AinurChoir()
        return self._choir

    async def evaluate_quorum(self, view: ClusterView) -> QuorumDecision:
        """
        Compute a quorum decision based on the current cluster view.
        """
        total_peers = len(view.peers)
        active_nodes = len([p for p in view.peers.values() if p.status == "resonant" and p.is_trusted])
        silent_nodes = len([p for p in view.peers.values() if p.status == "silent"])
        dissonant_nodes = len([p for p in view.peers.values() if p.status == "dissonant"])
        
        # Including self in quorum calculation
        total_cluster_nodes = total_peers + 1 
        resonant_nodes = active_nodes + 1 # Assuming self is resonant
        
        # 0. Consult Ainur Choir for self-assessment
        choir_verdict = await self.choir.evaluate({
            "view": view,
            "runtime_identity": "quorum-engine",
            "node_id": "local-substrate",
            "entity_id": "local-substrate"
        })
        await project_choir_truth(choir_verdict)
        
        # If self is vetoed, we cannot participate in quorum
        if choir_verdict.overall_state == "vetoed":
            resonant_nodes = 0
            
        consensus_score = resonant_nodes / total_cluster_nodes
        
        # 1. Quorum Decision Logic (Phase IV Sovereignty Law)
        status = QuorumStatus.PENDING
        
        if total_cluster_nodes < self._policy.min_nodes:
            status = QuorumStatus.FRACTURED # Cluster too small for consensus
        elif consensus_score >= self._policy.supermajority_threshold:
            status = QuorumStatus.RESONANT # Full Chorus
        elif consensus_score >= self._policy.majority_threshold:
            status = QuorumStatus.DEGRADED # Partial Chorus
        else:
            status = QuorumStatus.VETOED # Split brain or failure
            
        # 2. Hard Dissonance Override
        # If even ONE node is trusted but reporting a FRACTURED manifold status (dissonant), 
        # the cluster health is suspect.
        if dissonant_nodes > 0 and self._policy.strictness == "cluster-enforced":
            status = QuorumStatus.VETOED
            
        decision = QuorumDecision(
            decision_id=f"quorum-{datetime.now(timezone.utc).timestamp()}",
            status=status,
            consensus_score=consensus_score,
            nodes_total=total_cluster_nodes,
            nodes_resonant=resonant_nodes,
            nodes_dissonant=dissonant_nodes,
            nodes_silent=silent_nodes,
            active_vetoes=["dissonance_veto"] if dissonant_nodes > 0 else []
        )
        
        self._current_decision = decision
        self._last_view = view
        
        # Constitutional Veto based on environment
        if status in {QuorumStatus.VETOED, QuorumStatus.FRACTURED}:
            if os.environ.get("ARDA_ENV") == "production":
                logger.error(f"PHASE IV: QUORUM VETO! Consensus: {consensus_score*100:.1f}% | Nodes: {resonant_nodes}/{total_cluster_nodes}")
            else:
                logger.warning(f"PHASE IV: Quorum strained ({consensus_score*100:.1f}%), but proceeding for Infallible Audit (non-production).")
        else:
            logger.info(f"PHASE IV: QUORUM {status.value.upper()}. Consensus: {consensus_score*100:.1f}%")
            
        return decision

    def get_last_decision(self) -> Optional[QuorumDecision]:
        return self._current_decision

# Global singleton
_quorum_engine: Optional[QuorumEngineService] = None

def get_quorum_engine() -> QuorumEngineService:
    global _quorum_engine
    if _quorum_engine is None:
        _quorum_engine = QuorumEngineService()
    return _quorum_engine
