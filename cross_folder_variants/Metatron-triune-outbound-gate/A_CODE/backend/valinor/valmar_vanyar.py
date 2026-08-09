import logging
from backend.valinor.light_bridge import LightBridge

logger = logging.getLogger(__name__)

class GaladrielLightArbiter:
    """
    Valmar: The City of Light and Law (Vanyar).
    Role: Syscall Sovereignty & Privilege Purity.
    Led by: Galadriel (Kernel Light Arbiter)
    """

    def __init__(self, bridge: LightBridge):
        self.bridge = bridge

    def authorize_syscall(self, entity_id: str, syscall_name: str) -> str:
        """
        Determines the execution authority of a process trying to make a sensitive call.
        Rather than a static RBAC list, authority decays over the Resonance ladder.
        """
        state = self.bridge.get_state(entity_id)

        s = state.constitutional_state

        logger.debug(f"Valmar (Galadriel): Evaluating {syscall_name} for {entity_id} [{s.upper()}]")

        if s == "harmonic":
            return "allow"

        if s == "strained":
            return "attenuate" # e.g., allowed but tracked/throttled or delayed

        if s == "dissonant":
            # For dissonant, only non-privileged syscalls are allowed.
            if syscall_name in ["execve", "ptrace", "mount", "setuid"]:
                 logger.warning(f"Valmar: DENIED privileged syscall {syscall_name} for dissonant entity {entity_id}.")
                 return "deny"
            return "restrict" # Read-only, or strictly sandbox enforced

        if s in ["muted", "fallen"]:
            logger.error(f"Valmar: ABSOLUTE DENIAL for {syscall_name}. Entity {entity_id} is {s.upper()}.")
            return "deny"

    def authorize_secret_access(self, entity_id: str, secret_name: str) -> bool:
        """
        Only entities holding the Flame Imperishable (Harmonic state) may access keys.
        """
        state = self.bridge.get_state(entity_id)

        if state.constitutional_state == "harmonic":
            logger.info(f"Valmar: Authorized secret access for {entity_id}.")
            return True
            
        logger.warning(f"Valmar: DENIED secret access ({secret_name}) for {entity_id} due to Resonance State [{state.constitutional_state.upper()}].")
        return False
