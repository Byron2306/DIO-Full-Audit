import logging
import asyncio
from typing import Dict, Any, List, Optional
from backend.arda.ainur.dissonance import DissonantStateModel
from backend.services.arda_fabric import get_arda_fabric

logger = logging.getLogger(__name__)

class EarendilFlowOrchestrator:
    """
    The Evening Star (Eärendil Flow).
    Phase VII: Network-wide Resonance Orchestration.
    Propagates Sovereign Summons across the cluster to maintain unity of truth.
    """
    def __init__(self):
        self.fabric = get_arda_fabric()
        self.is_shining = True

    async def shine_light(self, entity_id: str, budget: DissonantStateModel, source_reason: str = "Tulkas Enforcement"):
        """Propagates a resonance update globally through the Arda-Fabric (Eärendil Signal)."""
        if not self.is_shining:
             return

        logger.info(f"Eärendil Flow: Shining light on {entity_id}. Global State: {budget.constitutional_state.upper()}")
        
        # 1. Structure the Sovereign Summons (Eärendil Signal)
        summons = {
            "type": "earendil_signal",
            "entity_id": entity_id,
            "resonance": budget.model_dump(),
            "reason": source_reason,
            "issuer": await self.fabric.get_local_node_id()
        }

        # 2. Fabric-Authenticated Broadcast: Dispatch the summons via the real transport
        # In this simulation, we also trigger the receive_summons logic centrally for the gauntlet
        await self.fabric.broadcast_sovereign_summons(summons)
        
        # Peer Discovery Simulation (for gauntlet local verification)
        peers = self.fabric.known_peers.keys()
        for peer_id in peers:
             if peer_id != summons["issuer"]:
                  logger.debug(f"Eärendil: Propagating summons to peer '{peer_id}' verified.")
                  asyncio.create_task(self.receive_summons(summons))

    async def receive_summons(self, summons: Dict[str, Any]):
        """
        Receives an Eärendil Signal from a peer node.
        Updates the local truth of the substrate.
        """
        entity_id = summons.get("entity_id")
        resonance_dict = summons.get("resonance")
        
        if not entity_id or not resonance_dict:
             return

        new_budget = DissonantStateModel(**resonance_dict)
        logger.warning(f"Eärendil Ingress: Sovereign Summons received for {entity_id}. Syncing Resonance: {new_budget.constitutional_state.upper()}")
        
        # 1. Update the local LightBridge
        from backend.valinor.runtime_hooks import get_valinor_runtime
        valinor = get_valinor_runtime()
        valinor.bridge.update_state(entity_id, new_budget)
        
        # 2. Audit in Mandos
        if valinor.taniquetil.mandos:
             valinor.taniquetil.mandos.record_event(
                 entity_id=entity_id,
                 event_type="earendil_sync",
                 state=new_budget.constitutional_state,
                 reason=f"Global Sync via Eärendil Signal from {summons.get('issuer')}"
             )

# Global singleton
earendil_orchestrator = EarendilFlowOrchestrator()

def get_earendil_flow():
    return earendil_orchestrator
