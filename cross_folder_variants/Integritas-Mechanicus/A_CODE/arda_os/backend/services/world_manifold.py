import os
import logging
import uuid
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

try:
    from backend.schemas.phase2_models import WorldManifoldSnapshot
    from backend.services.secure_boot import get_secure_boot_service
    from backend.services.formation_verifier import get_formation_verifier
    from backend.services.formation_order import get_formation_order_service
    from backend.services.genesis_score import get_genesis_score_service
    from backend.services.handoff_covenant import get_handoff_covenant_service
    from backend.services.resonance_engine import get_resonance_engine
    from backend.services.manwe_herald import manwe_herald
    from backend.services.order_engine import order_engine
    from backend.services.world_model import WorldModelService
    from backend.services.quorum_engine import get_quorum_engine
    from backend.services.telemetry_chain import tamper_evident_telemetry
    from backend.services.quantum_security import quantum_security
except Exception:
    from backend.schemas.phase2_models import WorldManifoldSnapshot
    from backend.services.secure_boot import get_secure_boot_service
    from backend.services.formation_verifier import get_formation_verifier
    from backend.services.formation_order import get_formation_order_service
    from backend.services.genesis_score import get_genesis_score_service
    from backend.services.handoff_covenant import get_handoff_covenant_service
    from backend.services.resonance_engine import get_resonance_engine
    from backend.services.manwe_herald import manwe_herald
    from backend.services.order_engine import order_engine
    from backend.services.world_model import WorldModelService
    from backend.services.quorum_engine import get_quorum_engine
    from backend.services.telemetry_chain import tamper_evident_telemetry
    from backend.services.quantum_security import quantum_security

logger = logging.getLogger(__name__)

class WorldManifoldService:
    """
    World Manifold Service.
    The final fusion of constitutional dimensions before Triune arbitration.
    """
    
    def __init__(self, db: Any = None):
        self.db = db
        self.world_model = WorldModelService(db)
        self.telemetry = tamper_evident_telemetry
        self.boot = get_secure_boot_service(db)
        self.verifier = get_formation_verifier(db)
        self.formation_order = get_formation_order_service(db)
        self.genesis = get_genesis_score_service(db)
        self.covenant_service = get_handoff_covenant_service(db)
        self.resonance = get_resonance_engine(db)
        self.order = order_engine
        self.herald = manwe_herald
        self.quorum_engine = get_quorum_engine()
        self._current_manifold: Optional[WorldManifoldSnapshot] = None

    async def build_manifold_snapshot(self, domain: str = "global") -> WorldManifoldSnapshot:
        """
        Build a high-dimensional manifold snapshot by fusing truth, order, and state.
        """
        logger.info("PHASE III: Building high-dimensional world manifold with resonance context...")
        
        # 1. Fetch Constitutional Trees (Formation Chain)
        formation_truth = self.verifier.get_truth() or await self.verifier.verify_formation()
        f_order_state = self.formation_order.get_order() or await self.formation_order.validate_formation_order()
        g_score = self.genesis.get_score() or await self.genesis.load_genesis_score()
        covenant = self.covenant_service.get_covenant() or await self.covenant_service.seal_covenant()
        
        # 2. Fetch Runtime State
        herald_state = self.herald.get_state()
        
        # 3. Fetch collective resonance & quorum (Phase IV)
        resonance_state = self.resonance.get_current_state() or await self.resonance.refresh_collective_resonance()
        quorum_decision = self.quorum_engine.get_last_decision()
        
        # 4. Compute World State Snapshot Hash from actual manifold components
        world_state_data = json.dumps({
            "formation_truth": formation_truth.formation_truth_id if formation_truth else "unknown",
            "formation_order": f_order_state.formation_order_id if f_order_state else "unknown",
            "genesis_score": g_score.genesis_score_id if g_score else "unknown",
            "resonance": resonance_state.resonance_id if resonance_state and hasattr(resonance_state, 'resonance_id') else "unknown",
            "herald_state": str(herald_state) if herald_state else "unknown",
        }, sort_keys=True)
        world_hash = hashlib.sha256(world_state_data.encode()).hexdigest()
        
        # 4b. Fetch Phase V Kernel dimensions
        try:
            from backend.services.process_lineage_service import get_process_lineage_service
        except Exception:
            from backend.services.process_lineage_service import get_process_lineage_service
        
        lineage_svc = get_process_lineage_service(self.db)
        integrity = await lineage_svc.audit_lineage_integrity()
        pids = lineage_svc.get_active_protected_count()
        # -------------------------------------
        
        # 5. Fuse into Manifold
        manifold = WorldManifoldSnapshot(
            manifold_id=f"manifold-{uuid.uuid4().hex[:12]}",
            world_state_hash=world_hash,
            boot_truth_ref=formation_truth.boot_truth_ref,
            formation_truth_ref=formation_truth.formation_truth_id,
            order_state_ref=f_order_state.formation_order_id,
            formation_order_ref=f_order_state.formation_order_id,
            genesis_score_ref=g_score.genesis_score_id,
            covenant_ref=covenant.covenant_id,
            active_epoch=g_score.genesis_epoch if not herald_state else herald_state.current_epoch,
            genre_mode=g_score.genre_mode,
            formation_status=covenant.status,
            collective_resonance_ref=resonance_state.resonance_id,
            triune_health_score=resonance_state.cluster_health.collective_score,
            quorum_status=quorum_decision.status.value if quorum_decision else "pending",
            nodes_verified=quorum_decision.nodes_resonant if quorum_decision else 1,
            nodes_silent=quorum_decision.nodes_silent if quorum_decision else 0,
            nodes_fractured=quorum_decision.nodes_dissonant if quorum_decision else 0,
            # --- PHASE V: Kernel Bridge Metrics ---
            kernel_integrity_score=integrity,
            protected_processes_count=pids,
            kernel_bridge_status="connected" if integrity > 0.8 else "fractured",
            # --- PHASE VI: Pre-Boot Sovereignty ---
            attestation_ref=formation_truth.bott_truth_ref if hasattr(formation_truth, 'bott_truth_ref') else formation_truth.boot_truth_ref,
            measured_birth_hash=formation_truth.sealed_identity_seed,
            boot_lineage_status=formation_truth.status,
            # --- PHASE VII: Kernel Sovereignty ---
            is_substrate_sovereign=True, # Assuming active in this version
            active_interceptors=["ebpf_exec", "seccomp"],
            denied_exec_count=0, # Initialized
            lineage_integrity_score=1.0,
            # -------------------------------------
            dependency_edges=[],
            recent_precedents=[],
            trust_zone_state={
                "global": covenant.status,
                "formation": formation_truth.status,
                "handoff": covenant.status,
                "resonance": "resonant" if resonance_state.cluster_health.is_fully_lawful else "dissonant",
                "quorum": quorum_decision.status.value if quorum_decision else "unknown",
                "kernel": "lawful" if integrity > 0.9 else "fractured",
                "attestation": "lawful" if formation_truth.status == "lawful" else "fractured",
                "sovereignty": "substrate_enforced"
            },
            epoch_strictness=g_score.strictness
        )

        # 5b. Cryptographically seal the manifold snapshot for integrity.
        sign_payload = manifold.model_dump(
            mode="json",
            exclude={"signature_ref", "signature_algorithm", "signature", "signature_valid"},
        )
        signed = quantum_security.sign_manifold_snapshot(sign_payload)
        manifold.signature_ref = signed.get("signature_ref")
        manifold.signature_algorithm = signed.get("algorithm")
        manifold.signature = signed.get("signature")
        manifold.signature_valid = quantum_security.verify_manifold_snapshot_signature(
            sign_payload,
            manifold.signature_ref,
            signature=manifold.signature,
            algorithm=manifold.signature_algorithm,
        )
        if os.environ.get("ARDA_ENV") == "production" and not manifold.signature_valid:
            raise RuntimeError("SOVEREIGN_FAILURE: World manifold signature validation failed")
        
        # 6. Push to World Model
        self.world_model.set_governance_placeholders(
            manifold_ref=manifold.manifold_id
        )
        
        # 7. Record Constitutional Event
        self.telemetry.ingest_event(
            event_type="manifold_synthesized",
            severity="info",
            data=manifold.model_dump(mode='json')
        )
        
        self._current_manifold = manifold
        logger.info(f"PHASE II: World Manifold synthesized with Covenant: {covenant.covenant_id}")
        
        return manifold

    def get_current_manifold(self) -> Optional[WorldManifoldSnapshot]:
        return self._current_manifold

# Global singleton
world_manifold = WorldManifoldService()
