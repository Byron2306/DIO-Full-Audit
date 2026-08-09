import logging
from backend.valinor.light_bridge import LightBridge

logger = logging.getLogger(__name__)

class TirionProcessGovernor:
    """
    Tirion: The City of Shapers (Noldor).
    Role: Process and memory governance. Execution shaping. Lineage enforcement.
    Led by: Feanor.dll, Fingolfin.dll, Finarfin.dll (Conceptual)
    """

    def __init__(self, bridge: LightBridge):
        self.bridge = bridge

    def authorize_spawn(self, child_id: str, parent_id: str, node_id: str) -> tuple[bool, str]:
        """
        Enforces execution shaping and lineage laws.
        A malicious child process must not inherit lawful birth simply because its parent once did.
        """
        parent_state = self.bridge.get_state(parent_id)
        node_state = self.bridge.get_state(node_id)

        inherited = self.bridge.inherit_state(parent_state, node_state)

        # Log lineage tracing
        logger.debug(f"Tirion: Process {child_id} inheriting state [{inherited.constitutional_state.upper()}] from {parent_id}")

        if inherited.constitutional_state in ["muted", "fallen"]:
            logger.warning(f"Tirion: SPAWN DENIED for {child_id}. Lineage is severed ({inherited.constitutional_state}).")
            return False, f"Lineage Denied: Parent/Node is {inherited.constitutional_state}"

        if inherited.constitutional_state == "dissonant":
            logger.warning(f"Tirion: SPAWN RESTRICTED for {child_id}. Parent {parent_id} is dissonant.")
            return True, "Restricted Spawn (Dissonant lineage, no privileges allowed)"
            
        if inherited.constitutional_state == "strained":
             return True, "Strained Spawn (Worker privileges only)"

        return True, "Lawful Spawn (Harmonic lineage)"

    def assign_memory_class(self, entity_id: str) -> str:
        """Determines physical memory protection class based on resonance."""
        state = self.bridge.get_state(entity_id)

        if state.constitutional_state == "harmonic":
            return "protected"

        if state.constitutional_state == "strained":
            return "normal"

        if state.constitutional_state == "dissonant":
            return "restricted"

        return "quarantine"
