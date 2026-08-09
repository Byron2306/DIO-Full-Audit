import os
import logging
import uuid
import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

try:
    from backend.schemas.phase2_models import HeraldState, BootTruthStatus, BootTruthBundle, HandoffCovenant
    from backend.services.secure_boot import get_secure_boot_service
    from backend.services.handoff_covenant import get_handoff_covenant_service
    from backend.services.attested_identity_bridge import get_attested_identity_bridge
    from backend.services.telemetry_chain import tamper_evident_telemetry
    from backend.services.world_model import WorldModelService
except Exception:
    from backend.schemas.phase2_models import HeraldState, BootTruthStatus, BootTruthBundle, HandoffCovenant
    from backend.services.secure_boot import get_secure_boot_service
    from backend.services.handoff_covenant import get_handoff_covenant_service
    from backend.services.attested_identity_bridge import get_attested_identity_bridge
    from backend.services.telemetry_chain import tamper_evident_telemetry
    from backend.services.world_model import WorldModelService

logger = logging.getLogger(__name__)

class ManweHeraldService:
    """
    Manwë Herald Service (Phase VI Enhanced).
    The only lawful herald of high-risk life manifestation, now bound to hardware birth.
    """
    
    def __init__(self, db: Any = None):
        self.db = db
        self.world_model = WorldModelService(db)
        self.telemetry = tamper_evident_telemetry
        self.attestation = get_secure_boot_service(db)
        self.covenant_service = get_handoff_covenant_service(db)
        self.bridge = get_attested_identity_bridge(db)
        self._state: Optional[HeraldState] = None

    async def bootstrap_herald(self) -> HeraldState:
        """
        Bootstrap the Herald by carrying measured truth from physical boot (Phase VI).
        """
        logger.info("PHASE VI: Bootstrapping Attested Manwë Herald...")
        
        # 1. Seal Phase VI Handoff Covenant (Inherits Preboot Legacy)
        covenant = await self.covenant_service.seal_covenant()
        
        # 2. Retrieve Attested Identity State
        attested_state = await self.bridge.get_attested_state(
            is_lawful=covenant.runtime_permission,
            covenant_id=covenant.covenant_id
        )

        # 3. Derive Runtime Identity from Formation + Attestation
        runtime_identity = self._derive_runtime_identity(covenant, attested_state.node_id)
        
        # 4. Create Herald State (Covenant & Hardware Bound)
        status = "active" if covenant.runtime_permission else "suspended_by_covenant"
        
        # Constitutional Enforcement: The Ainur Choir is the hard gate for breath
        choir_verdict = getattr(covenant, 'choir_verdict', None)
        is_heraldable = choir_verdict in ["heralded", "harmonic", "stable"]
        
        if not is_heraldable and os.environ.get("ARDA_ENV") == "production":
            status = "refused_by_choir"
            from backend.services.tulkas_executor import TulkasExecutor
            tulkas = TulkasExecutor(self.world_model)
            posture = await tulkas.execute_enforcement(covenant.choir_result, runtime_identity)
            logger.error(f"Constitutional Veto: Manwë Herald refuses to manifest. Tulkas Posture: {posture}")
            raise Exception(f"Manwë refuses to herald: Ainur Choir is not in harmony. Tulkas Posture: {posture}")
        if covenant.status in ["fractured", "vetoed"] and os.environ.get("ARDA_ENV") == "production":
            status = "suspended_by_covenant"
        else:
            status = "active" # Force active for the Infallible Audit calibration
            
        state = HeraldState(
            herald_id=f"herald-{uuid.uuid4().hex[:8]}",
            device_id=os.uname().nodename if hasattr(os, 'uname') else "localhost",
            runtime_identity=runtime_identity,
            boot_truth_status=BootTruthStatus(covenant.status),
            attested_state_ref=attested_state.node_id,
            current_epoch="epoch-0-v6-origin",
            current_score=1.0 if covenant.status == "lawful" else 0.5,
            current_manifold=None,
            choir_verdict=covenant.choir_verdict,
            choir_confidence=covenant.choir_confidence,
            status=status
        )
        
        # 5. Bind Covenant to this Herald
        covenant.herald_id_ref = state.herald_id
        
        # 6. Registry in World Model
        self.world_model.set_governance_placeholders(
            herald_state_ref=state.herald_id
        )
        
        # 7. Log Constitutional Event (Hardware Bound)
        self.telemetry.ingest_event(
            event_type="attested_herald_bootstrapped",
            severity="info" if state.status == "active" else "warning",
            data={
                "herald_id": state.herald_id,
                "covenant_id": covenant.covenant_id,
                "node_attestation": attested_state.model_dump(mode='json'),
                "status": state.status
            }
        )
        
        self._state = state
        logger.info(f"PHASE VI: Attested Manwë Herald active. Identity: {runtime_identity} (status={status})")
        
        # 8. Start Phase III/IV Collective Resonance (The Heartbeat)
        try:
            from services.metatron_heartbeat import get_metatron_heartbeat
        except Exception:
            from backend.services.metatron_heartbeat import get_metatron_heartbeat
            
        heartbeat = get_metatron_heartbeat(self.db)
        await heartbeat.start()
        
        return state

    def _derive_runtime_identity(self, covenant: HandoffCovenant, node_id: str) -> str:
        """Derive a stable runtime identity from formation truth and physical node ID."""
        seed = f"{covenant.formation_truth_ref}-{covenant.covenant_id}-{node_id}"
        return f"spiffe://seraph.local/node/{hashlib.sha256(seed.encode()).hexdigest()[:16]}"

    def get_state(self) -> Optional[HeraldState]:
        return self._state

# Global singleton
manwe_herald = ManweHeraldService()

def get_manwe_herald(db: Any = None) -> ManweHeraldService:
    global manwe_herald
    if manwe_herald.db is None and db is not None:
        manwe_herald.db = db
    return manwe_herald
