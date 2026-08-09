import logging
import asyncio
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional, Any
from backend.schemas.phase3_models import HeartbeatProof, ResonanceStatus
from backend.schemas.phase4_models import HeartbeatEnvelope
from backend.services.resonance_engine import get_resonance_engine
from backend.services.node_identity_service import get_node_identity_service
from backend.services.heartbeat_signer import get_heartbeat_signer
from backend.services.chorus_transport import get_chorus_transport
from backend.services.telemetry_chain import tamper_evident_telemetry

logger = logging.getLogger(__name__)

class MetatronHeartbeatService:
    """
    The Voice of the Constitutional Node (Phase VI Enhanced).
    Periodically emits signed proofs of local liveness, order integrity, and hardware birth.
    """
    
    def __init__(self, db: Any = None):
        self.db = db
        self.resonance = get_resonance_engine(db)
        self.telemetry = tamper_evident_telemetry
        self._is_running = False
        self._task: Optional[asyncio.Task] = None
        self._interval = 10 
        
        self.identity_service = get_node_identity_service()
        self.signer = get_heartbeat_signer()
        self.transport = get_chorus_transport()
        
    async def start(self):
        """Start the heartbeat emission loop."""
        if self._is_running:
            return
            
        logger.info(f"PHASE IV: Starting Metatron Heartbeat (Interval: {self._interval}s)")
        await self.transport.start()
        self._is_running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        
    async def stop(self):
        """Stop the heartbeat emission loop."""
        self._is_running = False
        await self.transport.stop()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("PHASE III: Metatron Heartbeat stopped.")

    async def emit_now(self) -> HeartbeatProof:
        """Manually trigger and emit a single heartbeat proof."""
        proof = await self._generate_proof()
        envelope = await self.signer.create_envelope(proof)
        
        # Phase 26: Polyphonic Resonance Integration
        from .resonance_service import get_resonance_service
        res_svc = get_resonance_service()
        score = 1.0 if proof.status == ResonanceStatus.RESONANT else 0.0
        res_svc.sing_in_choir("macro", "seraph_heartbeat", score, [f"Kernel Integrity: {proof.kernel_integrity}"])

        await self.resonance.record_envelope(envelope)
        await self.transport.broadcast_envelope(envelope)
        return proof

    async def _heartbeat_loop(self):
        """Main loop that generates and broadcasts heartbeats."""
        while self._is_running:
            try:
                await self.emit_now()
            except Exception as e:
                logger.error(f"PHASE III: Heartbeat emission failure: {e}")
            await asyncio.sleep(self._interval)

    async def _generate_proof(self) -> HeartbeatProof:
        """
        Synthesize the current local state into a signed proof (Phase VI).
        The heartbeat is only as valid as its hardware-attested origin.
        """
        try:
            from backend.services.manwe_herald import manwe_herald
            from backend.services.world_manifold import world_manifold
            from backend.services.process_lineage_service import get_process_lineage_service
        except Exception:
            from backend.services.manwe_herald import manwe_herald
            from backend.services.world_manifold import world_manifold
            from backend.services.process_lineage_service import get_process_lineage_service
            
        identity = self.identity_service.get_identity()
        node_id = identity.node_id if identity else "unborn-node"
        
        # 1. High-dimensional state from the manifold
        manifold = world_manifold.get_current_manifold() or await world_manifold.build_manifold_snapshot()
        
        # 2. Kernel/Lineage Metrics (Phase V)
        lineage_svc = get_process_lineage_service(self.db)
        integrity = await lineage_svc.audit_lineage_integrity()
        pids = lineage_svc.get_active_protected_count()

        # 3. Hardware Birth Proof (Phase VI)
        herald_state = manwe_herald.get_state()
        attestation_ref = herald_state.attested_state_ref if herald_state else None
        
        # 4. Construct the Proof
        proof = HeartbeatProof(
            proof_id=f"proof-{datetime.now(timezone.utc).timestamp()}",
            node_id=node_id,
            manifold_state_hash=manifold.world_state_hash,
            order_pulse_ref="v6-heartbeat",
            signature=identity.fingerprint if identity else "nosig",
            status=ResonanceStatus.RESONANT if manifold.kernel_bridge_status == "connected" else ResonanceStatus.FRACTURED,
            kernel_integrity=integrity,
            manifested_pids=pids,
            attestation_ref=attestation_ref,
            measured_formation_hash=manifold.world_state_hash[:16] # Derived from manifold
        )
        return proof

# Global singleton
metatron_heartbeat = MetatronHeartbeatService()

def get_metatron_heartbeat(db: Any = None) -> MetatronHeartbeatService:
    global metatron_heartbeat
    if metatron_heartbeat.db is None and db is not None:
        metatron_heartbeat.db = db
    return metatron_heartbeat
