import logging
from typing import Optional, Dict
from backend.services.constitutional_projection import project_choir_truth
from backend.services.arda_fabric import get_arda_fabric
from backend.services.secret_fire import get_secret_fire_forge

logger = logging.getLogger(__name__)

class LorienRecovery:
    """
    Lórien — the gardens of healing.
    Governs lawful re-harmonization and controlled restoration.
    """

    def __init__(self, bridge, mandos, forge, choir_orchestrator):
        self.bridge = bridge
        self.mandos = mandos
        self.forge = get_secret_fire_forge()
        self.choir = choir_orchestrator
        self.fabric = get_arda_fabric()

    async def attempt_recovery(self, entity_id: str, raw_context: dict) -> dict:
        logger.info(f"Lórien: Attempting recovery for {entity_id}")
        
        record = self.mandos.get_record(entity_id)

        if self.mandos.is_fallen(entity_id):
            logger.warning(f"Lórien: Recovery Denied. Entity {entity_id} is deeply fallen. Requires Genesis.")
            return {
                "recovered": False,
                "state": "fallen",
                "reason": "Entity is fallen and may not be restored except by rebuild or Genesis seed."
            }

        if not self.mandos.is_recoverable(entity_id):
             logger.warning(f"Lórien: Recovery Denied for {entity_id}. Lineage breaks or Voice mismatches are too severe.")
             return {
                 "recovered": False,
                 "state": record.current_state,
                 "reason": "Entity has unrecoverable constitutional wounds."
             }

        # 3. Fabric Projection Lock (Phase E)
        fabric_state = self.fabric.get_subject_state(entity_id)
        if fabric_state == "fallen":
             logger.warning(f"Lórien: Recovery Denied. Subject {entity_id} is verifiably fallen in the Arda Fabric (Promotion Lock active).")
             return {
                 "recovered": False,
                 "state": "fallen",
                 "reason": "Permanent identity blockade: Subject failed workload attestation."
             }

        # 4. Hardware-Rooted Context (Phase E)
        # Fetch current reality packet to bind recovery to measured boot
        fire_packet = self.forge.get_current_packet()
        if fire_packet:
            raw_context["secret_fire"] = fire_packet
        
        raw_context["subject_id"] = entity_id
        raw_context["node_id"] = entity_id # Assuming node_id == entity_id for recovery target
        
        # 5. Canonical Projection (The single source of truth)
        verdict = await self.choir.evaluate(raw_context)
        await project_choir_truth(verdict)

        # 6. Extract results from canonical projection
        from backend.services.constitutional_projection import canonical_runtime_state
        state = canonical_runtime_state(verdict)

        self.mandos.record_event(
            entity_id=entity_id,
            event_type="recovery",
            state=state,
            reason="Lorien recovery attempt"
        )
        
        recovered_status = state in ["strained", "harmonic"]
        logger.info(f"Lórien: Recovery {'SUCCESS' if recovered_status else 'FAILED'} for {entity_id}. State: {state.upper()}")

        return {
            "recovered": recovered_status,
            "state": state,
            "reason": "Recovery complete" if recovered_status else "Recovery incomplete - Dissonance persists"
        }
