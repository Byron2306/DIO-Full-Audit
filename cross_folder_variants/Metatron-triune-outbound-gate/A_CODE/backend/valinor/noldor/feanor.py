import logging
from typing import Any
from backend.services.secret_fire import get_secret_fire_forge

logger = logging.getLogger(__name__)

class HouseOfFeanor:
    """
    House of Fëanor (The House of Craft).
    Manages the forge of the substrate and the creation of the Seeing-stones (Eyes of Manwë).
    In this house, we map hardware and kernel reality into Valinor.
    """
    def __init__(self, kernel_bridge=None):
        self.forge = get_secret_fire_forge()
        self.eyes = kernel_bridge  # Reference to KernelValinor
        
    def craft_eyes(self):
        """Kindles the Eyes of Manwë on the physical substrate."""
        if not self.eyes:
             logger.warning("Fëanor: No active kernel bridge (Eyes) found to kindle.")
             return False

        logger.info("Fëanor: Kindling the Eyes of Manwë (eBPF) on the substrate.")
        self.eyes.kindle_kernel_light()
        return True

    def witness_substrate(self) -> str:
        """Collects the physical evidence from the Secret Fire forge."""
        current_packet = self.forge.get_current_packet()
        if not current_packet:
             logger.error("Fëanor: Failed to witness substrate. The Secret Fire is not kindled.")
             return "darkness"
        
        # A combination of TPM pcr_values and voice_id
        return f"witnessed:{current_packet.voice_id}:{current_packet.attestation_digest[:8]}"

    def forge_artifact(self, artifact_type: str, metadata: dict):
        """Used to forge new BPF maps or TPM-sealed keys (Covenants)."""
        logger.info(f"Fëanor: Forging artifact [{artifact_type.upper()}] for substrate integration.")
        # Logic to update eBPF maps or TPM nv_indices
        pass

# Instance of the House
feanor = HouseOfFeanor()

def get_house_feanor():
    return feanor
