from typing import Optional, Dict
from dataclasses import dataclass
import logging
from backend.arda.ainur.dissonance import ResonanceStateModel, ResonanceMapper

logger = logging.getLogger(__name__)

@dataclass
class EntityContext:
    entity_id: str
    parent_id: Optional[str]
    node_id: Optional[str]

class LightBridge:
    """
    Bridge between Ainur truth (Ilmarin/Taniquetil)
    and Calaquendi enforcement (Valinor).
    This acts as the state registry for the Calaquendi.
    """

    def __init__(self, state_registry: Dict[str, ResonanceStateModel] = None):
        # Maps entity_id (process/session/packet) to its Resonance Amplitude
        self.state_registry = state_registry if state_registry is not None else {}

    def get_state(self, entity_id: str) -> ResonanceStateModel:
        """Returns the constitutional state of an entity. Defaults to Strained (Hardened) if unknown."""
        state = self.state_registry.get(entity_id)
        if state:
            return state
        # PHASE VIII HARDENING: Unknown entities must not be assumed harmonic.
        # They default to STRAINED until the choir projects explicit truth.
        return ResonanceMapper.from_choir_state(entity_id, "strained", reason="Implicitly Strained (Unknown / Unheralded)")

    def update_state(self, entity_id: str, state: ResonanceStateModel):
        """Updates the resonance amplitude for an entity based on a Choir Verdict via Tulkas."""
        self.state_registry[entity_id] = state
        logger.info(f"Valinor LightBridge: Entity {entity_id} amplitude updated to [{state.constitutional_state.upper()}]")

    def inherit_state(self, parent_state: ResonanceStateModel, node_state: ResonanceStateModel) -> ResonanceStateModel:
        """
        Enforces the Law of Inheritance:
        A child cannot exceed the resonant amplitude of its parent or host node.
        """
        return ResonanceMapper.resolve_inheritance(parent_state, node_state)
