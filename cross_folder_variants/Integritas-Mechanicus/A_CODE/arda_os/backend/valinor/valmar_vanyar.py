import logging

from backend.valinor.light_bridge import LightBridge

logger = logging.getLogger(__name__)


class GaladrielLightArbiter:
    """Syscall sovereignty and privilege gating."""

    def __init__(self, bridge: LightBridge):
        self.bridge = bridge

    def authorize_syscall(self, entity_id: str, syscall_name: str) -> str:
        state = self.bridge.get_state(entity_id)
        constitutional_state = state.constitutional_state

        logger.debug(
            "Valmar: Evaluating %s for %s [%s]",
            syscall_name,
            entity_id,
            constitutional_state.upper(),
        )

        if constitutional_state == "harmonic":
            return "allow"
        if constitutional_state == "strained":
            return "attenuate"
        if constitutional_state == "dissonant":
            if syscall_name in ["execve", "ptrace", "mount", "setuid"]:
                return "deny"
            return "restrict"
        if constitutional_state in ["muted", "fallen"]:
            return "deny"
        return "deny"

    def authorize_secret_access(self, entity_id: str, secret_name: str) -> bool:
        state = self.bridge.get_state(entity_id)
        allowed = state.constitutional_state == "harmonic"
        if not allowed:
            logger.warning(
                "Valmar: denied secret access (%s) for %s due to [%s]",
                secret_name,
                entity_id,
                state.constitutional_state.upper(),
            )
        return allowed
