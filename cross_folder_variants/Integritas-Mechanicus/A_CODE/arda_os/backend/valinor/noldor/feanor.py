import logging

from backend.services.secret_fire import get_secret_fire_forge

logger = logging.getLogger(__name__)


class HouseOfFeanor:
    """Substrate witnessing and kernel-eye craft."""

    def __init__(self, kernel_bridge=None):
        self.forge = get_secret_fire_forge()
        self.eyes = kernel_bridge

    def craft_eyes(self) -> bool:
        if not self.eyes:
            logger.warning("Feanor: no active kernel bridge found to kindle.")
            return False
        self.eyes.kindle_kernel_light()
        return True

    def witness_substrate(self) -> str:
        current_packet = self.forge.get_current_packet()
        if not current_packet:
            return "darkness"
        return f"witnessed:{current_packet.voice_id}:{current_packet.attestation_digest[:8]}"

    def forge_artifact(self, artifact_type: str, metadata: dict) -> None:
        logger.info("Feanor: forging artifact [%s] metadata=%s", artifact_type.upper(), metadata)


feanor = HouseOfFeanor()


def get_house_feanor() -> HouseOfFeanor:
    return feanor
