import logging
from typing import Any, Dict, List, Optional
from backend.arda.ainur.dissonance import DissonantStateModel, ResonanceStateModel
from backend.valinor.taniquetil_core import ResonanceEvent

logger = logging.getLogger(__name__)

class HouseOfFinarfin:
    """
    House of Finarfin (The House of Wisdom).
    Manages the Throne of Manwë (Taniquetil) and the gates of Valmar and Alqualondë.
    This house is the brain of Valinor, deciding on the 'Truth' of the substrate.
    """
    def __init__(self, bridge=None, taniquetil=None):
        self.bridge = bridge # The LightBridge
        self.taniquetil = taniquetil # Unified Execution
        
    def evaluate_resonance(self, event: ResonanceEvent) -> Dict[str, Any]:
        """Provides a unified verdict on an entity action."""
        if not self.taniquetil:
             logger.warning("Finarfin: Taniquetil core is not ready to hear the summons.")
             return {"allowed": True, "modifiers": [], "reason": ["Taniquetil Silent"]}
        
        logger.debug(f"Finarfin: Deliberating on {event.action_type.upper()} for {event.entity_id}")
        return self.taniquetil.evaluate(event)

    def reconcile_identity(self, node_id: str) -> Optional[DissonantStateModel]:
        """Uses wisdom to look into the past (Mandos) and decide a node's resonance."""
        if not self.bridge:
             return None
        return self.bridge.get_state(node_id) # Inherits the substrate model

    def herald_verdict(self, verdict: Any):
        """Standardized reporting for governance decisions."""
        logger.info(f"Finarfin: Herald's Report: {verdict}")
        pass

# Instance of the House
finarfin = HouseOfFinarfin()

def get_house_finarfin():
    return finarfin

# Alias for theme alignment
ResonanceGovernor = HouseOfFinarfin
