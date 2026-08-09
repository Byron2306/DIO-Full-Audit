from dataclasses import dataclass
import logging
from typing import Dict, Optional

try:
    from backend.arda.ainur.dissonance import ResonanceMapper, ResonanceStateModel
except Exception:
    from backend.services.ainur.dissonance import ResonanceMapper, ResonanceStateModel  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class EntityContext:
    entity_id: str
    parent_id: Optional[str]
    node_id: Optional[str]


class LightBridge:
    """
    Bridge between Ainur truth and Valinor enforcement.
    Unknown entities default to strained rather than harmonic.
    """

    def __init__(self, state_registry: Dict[str, ResonanceStateModel] | None = None):
        self.state_registry = state_registry if state_registry is not None else {}

    def get_state(self, entity_id: str) -> ResonanceStateModel:
        state = self.state_registry.get(entity_id)
        if state:
            return state
        return ResonanceMapper.from_choir_state(
            entity_id,
            "strained",
            reason="Implicitly Strained (Unknown / Unheralded)",
        )

    def update_state(self, entity_id: str, state: ResonanceStateModel) -> None:
        self.state_registry[entity_id] = state
        logger.info(
            "Valinor LightBridge: Entity %s amplitude updated to [%s]",
            entity_id,
            state.constitutional_state.upper(),
        )

    def inherit_state(self, parent_state: ResonanceStateModel, node_state: ResonanceStateModel) -> ResonanceStateModel:
        return ResonanceMapper.resolve_inheritance(parent_state, node_state)
