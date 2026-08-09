import logging
import uuid
import os
from typing import Optional, Dict, Any, List

from backend.schemas.phase2_models import HandoffCovenant
from backend.services.formation_verifier import get_formation_verifier
from backend.services.formation_order import get_formation_order_service
from backend.services.genesis_score import get_genesis_score_service
from backend.services.preboot_state_sealer import get_preboot_state_sealer
from backend.services.telemetry_chain import tamper_evident_telemetry
from backend.services.secret_fire import get_secret_fire_forge

from backend.arda.ainur import AinurChoir, ConstitutionalMode
from backend.services.constitutional_projection import project_choir_truth

logger = logging.getLogger(__name__)

class HandoffCovenantService:
    """
    The Contract between Pre-runtime Formation and Runtime Governance (Phase VI).
    Seals the herald activation and inherits the preboot legacy.
    """
    
    def __init__(self, db: Any = None):
        self.db = db
        self.verifier = get_formation_verifier(db)
        self.order = get_formation_order_service(db)
        self.genesis = get_genesis_score_service(db)
        self.sealer = get_preboot_state_sealer()
        self.telemetry = tamper_evident_telemetry
        self._choir: Optional[AinurChoir] = None
        self._current_covenant: Optional[HandoffCovenant] = None

    @property
    def choir(self) -> AinurChoir:
        if self._choir is None:
            self._choir = AinurChoir()
        return self._choir

    async def seal_covenant(self) -> HandoffCovenant:
        """
        Binds truth + order + genesis + preboot legacy into runtime permission.
        """
        logger.info("PHASE VI: Sealing Handoff Covenant with Preboot Legacy...")
        
        # 1. Fetch current pre-runtime artifacts
        formation_truth = await self.verifier.verify_formation()
        formation_order = await self.order.validate_formation_order()
        genesis_score = await self.genesis.load_genesis_score()
        
        # 2. Inherit Preboot Legacy
        preboot_covenant = await self.sealer.unseal_covenant()
        preboot_ref = preboot_covenant.covenant_id if preboot_covenant else "orphan-boot-v6"

        # Prepare ID for the new covenant (Law VI binding)
        new_covenant_id = f"cov-{uuid.uuid4().hex[:12]}"

        # 3. Consult the Ainur Choir
        fire_service = get_secret_fire_forge()
        # For the Genesis boot, we assume we can pull/forge the current packet
        secret_fire = fire_service.get_current_packet() 
        
        choir_context = {
            "covenant_id": new_covenant_id,
            "covenant_valid": True, # Placeholder for self-reference
            "formation_truth": formation_truth,
            "formation_order": formation_order,
            "preboot_legacy": preboot_covenant,
            "secret_fire": secret_fire,
            "expected_entities": ["herald-svc", "quorum-engine", "auth-gateway"],
            "protected_manifestations_count": 3,
            "runtime_identity": "handoff-service",
            "node_id": "local-substrate",
            "entity_id": "local-substrate"
        }
        choir_verdict = await self.choir.evaluate(choir_context)
        await project_choir_truth(choir_verdict)

        # 4. Determine Outcome
        runtime_permission = True
        status = "lawful"
        reason = "Formation verified lawful; sequence complete; preboot legacy inherited."
        
        if formation_truth.status != "lawful":
            runtime_permission = False
            status = "unlawful"
            reason = "UNLAWFUL FORMATION: Boot truth inconsistent with manifest."
        elif formation_order.status != "lawful":
            runtime_permission = False 
            status = "fractured"
            reason = "FRACTURED FORMATION: Sequence of birth violated invariants."
        elif preboot_covenant and not preboot_covenant.formation_verdict.is_lawful:
             runtime_permission = False
             status = "vetoed"
             reason = "PHASE VI VETO: Preboot environment failed formation check."
        elif not choir_verdict.heralding_allowed:
             runtime_permission = False
             status = choir_verdict.overall_state
             reason = f"AINUR CHOIR {choir_verdict.overall_state.upper()}: {'; '.join(choir_verdict.reasons)}"
            
        # 4. Create HandoffCovenant
        covenant = HandoffCovenant(
            covenant_id=new_covenant_id,
            formation_truth_ref=formation_truth.formation_truth_id,
            formation_order_ref=formation_order.formation_order_id,
            genesis_score_ref=genesis_score.genesis_score_id,
            herald_id_ref="awaiting_herald",
            preboot_covenant_ref=preboot_ref,
            status=status.value if hasattr(status, "value") else status,
            runtime_permission=runtime_permission,
            choir_verdict=choir_verdict.overall_state,
            choir_result=choir_verdict,
            choir_confidence=choir_verdict.confidence,
            reason=reason
        )
        
        # 5. Log Constitutional Event
        self.telemetry.ingest_event(
            event_type="handoff_covenant_sealed",
            severity="info" if runtime_permission else "critical",
            data={
                "covenant": covenant.model_dump(mode='json'),
                "preboot_inherited": preboot_covenant is not None
            }
        )
        
        self._current_covenant = covenant
        logger.info(f"PHASE VI: Handoff Covenant Sealed. Permission: {runtime_permission} ({status})")
        
        return covenant

    def get_covenant(self) -> Optional[HandoffCovenant]:
        return self._current_covenant

# Global singleton
_handoff_covenant_service: Optional[HandoffCovenantService] = None

def get_handoff_covenant_service(db: Any = None) -> HandoffCovenantService:
    global _handoff_covenant_service
    if _handoff_covenant_service is None:
        _handoff_covenant_service = HandoffCovenantService(db)
    elif _handoff_covenant_service.db is None and db is not None:
        _handoff_covenant_service.db = db
    return _handoff_covenant_service
