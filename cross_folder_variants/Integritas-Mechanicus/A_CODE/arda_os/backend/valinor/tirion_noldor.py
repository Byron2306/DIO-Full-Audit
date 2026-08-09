import logging

from backend.valinor.light_bridge import LightBridge

logger = logging.getLogger(__name__)


class TirionProcessGovernor:
    """Process lineage and memory-class governance."""

    def __init__(self, bridge: LightBridge):
        self.bridge = bridge

    def authorize_spawn(self, child_id: str, parent_id: str, node_id: str) -> tuple[bool, str]:
        parent_state = self.bridge.get_state(parent_id)
        node_state = self.bridge.get_state(node_id)
        inherited = self.bridge.inherit_state(parent_state, node_state)

        logger.debug(
            "Tirion: Process %s inheriting state [%s] from %s",
            child_id,
            inherited.constitutional_state.upper(),
            parent_id,
        )

        if inherited.constitutional_state in ["muted", "fallen"]:
            return False, f"Lineage Denied: Parent/Node is {inherited.constitutional_state}"
        if inherited.constitutional_state == "dissonant":
            return True, "Restricted Spawn (Dissonant lineage, no privileges allowed)"
        if inherited.constitutional_state == "strained":
            return True, "Strained Spawn (Worker privileges only)"
        return True, "Lawful Spawn (Harmonic lineage)"

    def assign_memory_class(self, entity_id: str) -> str:
        state = self.bridge.get_state(entity_id)
        if state.constitutional_state == "harmonic":
            return "protected"
        if state.constitutional_state == "strained":
            return "normal"
        if state.constitutional_state == "dissonant":
            return "restricted"
        return "quarantine"
