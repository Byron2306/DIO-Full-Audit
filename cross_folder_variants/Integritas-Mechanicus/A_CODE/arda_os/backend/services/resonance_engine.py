import logging
import uuid
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

try:
    from backend.schemas.phase3_models import ResonanceStatus, HeartbeatProof, HarmonicScore, TriuneHealth, CollectiveResonanceState
    from backend.schemas.phase4_models import HeartbeatEnvelope, VerifiedHeartbeat, SignatureStatus
    from backend.services.heartbeat_verifier import get_heartbeat_verifier
    from backend.services.replay_guard import get_replay_guard
    from backend.services.quorum_engine import get_quorum_engine
    from backend.services.peer_registry import get_peer_registry
    from backend.services.telemetry_chain import tamper_evident_telemetry
except Exception:
    from backend.schemas.phase3_models import ResonanceStatus, HeartbeatProof, HarmonicScore, TriuneHealth, CollectiveResonanceState
    from backend.schemas.phase4_models import HeartbeatEnvelope, VerifiedHeartbeat, SignatureStatus
    from backend.services.heartbeat_verifier import get_heartbeat_verifier
    from backend.services.replay_guard import get_replay_guard
    from backend.services.quorum_engine import get_quorum_engine
    from backend.services.peer_registry import get_peer_registry
    from backend.services.telemetry_chain import tamper_evident_telemetry

logger = logging.getLogger(__name__)

class ResonanceEngineService:
    """
    The Soul of the Triune Chorus.
    Orchestrates distributed trust, cryptographic verification, and quorum consensus.
    """
    
    def __init__(self, db: Any = None):
        self.db = db
        self.telemetry = tamper_evident_telemetry
        self._node_heartbeats: Dict[str, HeartbeatProof] = {}
        self._current_resonance: Optional[CollectiveResonanceState] = None
        
        # Phase IV Components
        self.verifier = get_heartbeat_verifier()
        self.replay_guard = get_replay_guard()
        self.quorum_engine = get_quorum_engine()
        self.registry = get_peer_registry()
        
    async def record_envelope(self, envelope: HeartbeatEnvelope) -> bool:
        """
        PHASE IV: Ingest a signed cryptographic envelope from a peer.
        This is the primary entry point for distributed cluster resonance.
        """
        logger.info(f"PHASE IV: Ingesting Signed Envelope from node {envelope.signer_node_id}")
        
        # 1. Cryptographic Verification
        verified = await self.verifier.verify_envelope(envelope)
        
        if verified.signature_status != SignatureStatus.VERIFIED:
            logger.error(f"PHASE IV: Dropping envelope from {envelope.signer_node_id}: {verified.signature_status.value}")
            return False
            
        # 2. Replay Protection
        if not self.replay_guard.check_and_record(verified):
            return False
            
        # 3. Update Peer Registry State
        self.registry.update_peer_state(
            node_id=verified.node_id, 
            status=verified.status,
            latency_ms=verified.verification_lag_ms
        )
        
        # 4. Canonical State Update
        # Prepare a Phase III back-compat proof for the score calculation
        # In a full Phase IV refactor, we would map VerifiedHeartbeat directly.
        legacy_proof = HeartbeatProof(
            proof_id=verified.proof_id,
            node_id=verified.node_id,
            manifold_state_hash=verified.manifold_state_hash,
            order_pulse_ref="v4-ref",
            signature=envelope.signature[:16],
            status=verified.status
        )
        self._node_heartbeats[verified.node_id] = legacy_proof
        
        # 5. Refresh Consensus
        await self.refresh_collective_resonance()
        return True

    async def record_heartbeat(self, proof: HeartbeatProof) -> HarmonicScore:
        """
        Ingest a node's constitutional heartbeat and recalculate its resonance.
        """
        logger.info(f"PHASE III: Ingesting Heartbeat from node {proof.node_id}")
        self._node_heartbeats[proof.node_id] = proof
        
        # Calculate current harmonic score for this node
        score = self._calculate_node_score(proof)
        
        # Record event in telemetry
        self.telemetry.ingest_event(
            event_type="heartbeat_ingested",
            severity="info" if score.composite_score > 0.8 else "warning",
            data=score.model_dump(mode='json')
        )
        
        # Trigger an immediate recalculation of the cluster resonance
        await self.refresh_collective_resonance()
        
        return score

    async def refresh_collective_resonance(self) -> CollectiveResonanceState:
        """
        Aggregates all known heartbeats into a unified Triune health state.
        This provides the final 'Truth' for multi-node consensus.
        """
        logger.info("PHASE III: Refreshing Collective Resonance...")
        
        node_scores: Dict[str, HarmonicScore] = {}
        active_count = 0
        resonant_count = 0
        total_score = 0.0
        active_vetoes = []
        
        for node_id, proof in self._node_heartbeats.items():
            score = self._calculate_node_score(proof)
            node_scores[node_id] = score
            active_count += 1
            if score.composite_score >= 0.8:
                resonant_count += 1
            else:
                active_vetoes.append(f"Vetoed node {node_id} (Dissonance Detected)")
            total_score += score.composite_score
            
        avg_score = total_score / active_count if active_count > 0 else 0.0
        is_fully_lawful = (resonant_count == active_count) and (active_count >= 1)
        
        health = TriuneHealth(
            cluster_id="triune-consensus-root",
            nodes_active=active_count,
            nodes_resonant=resonant_count,
            collective_score=avg_score,
            is_fully_lawful=is_fully_lawful,
            active_vetoes=active_vetoes
        )
        
        # --- PHASE IV: QUORUM EVALUATION ---
        # Build the cluster view from the current registry state
        try:
            from schemas.phase4_models import ClusterView, PeerState
        except Exception:
            from backend.schemas.phase4_models import ClusterView, PeerState
            
        peer_states = {p.node_id: self.registry.get_peer_state(p.node_id) for p in self.registry.get_all_peers()}
        # Filter out None states
        peer_states = {k: v for k, v in peer_states.items() if v}
        
        view = ClusterView(
            cluster_id="triune-consensus-view",
            active_nodes=list(self._node_heartbeats.keys()),
            peers=peer_states,
            total_quorum_score=avg_score,
            last_unison_at=datetime.now(timezone.utc) if is_fully_lawful else None
        )
        # Final Quorum Decision
        await self.quorum_engine.evaluate_quorum(view)
        # --- END PHASE IV ---
        
        state = CollectiveResonanceState(
            resonance_id=f"res-{uuid.uuid4().hex[:8]}",
            epoch_id="origin-v4-resonance",
            node_scores=node_scores,
            cluster_health=health
        )
        
        self._current_resonance = state
        return state

    def _calculate_node_score(self, proof: HeartbeatProof) -> HarmonicScore:
        """
        Judges a node's legality based on liveness and its self-reported status.
        In production, this would also verify cryptographic signatures.
        """
        # Simulated scoring logic
        order_score = 1.0
        truth_score = 1.0
        
        truth_score = 1.0 if proof.status == ResonanceStatus.RESONANT else 0.0
        
        # Apply penalties based on status
        if proof.status == ResonanceStatus.DISSONANT:
            order_score = 0.5
        elif proof.status == ResonanceStatus.FRACTURED:
            order_score = 0.1
            truth_score = 0.0
            
        # Phase V: Kernel-Bridge Integrity
        kernel_score = proof.kernel_integrity
        
        # Composite calculation
        composite = (order_score * 0.3) + (truth_score * 0.4) + (kernel_score * 0.3)
        
        return HarmonicScore(
            node_id=proof.node_id,
            liveness=1.0, # Placeholder
            order_consistency=order_score,
            truth_integrity=truth_score,
            composite_score=composite
        )

    def get_current_state(self) -> Optional[CollectiveResonanceState]:
        return self._current_resonance

# Global singleton
resonance_engine = ResonanceEngineService()

def get_resonance_engine(db: Any = None) -> ResonanceEngineService:
    global resonance_engine
    if resonance_engine.db is None and db is not None:
        resonance_engine.db = db
    return resonance_engine
