import logging
import asyncio
from typing import Dict, Any, Optional
from backend.services.arda_fabric import get_arda_fabric
try:
    from backend.valinor.runtime_hooks import get_valinor_runtime
except Exception:
    from backend.services.runtime_hooks import get_valinor_runtime  # type: ignore
from backend.services.outbound_policy_hardening import (
    OutboundPolicyError,
    canonicalize_target,
    host_matches_allowlist,
)

logger = logging.getLogger(__name__)

class GatesOfNight:
    """
    The Doors of Night — Boundary Bound.
    Phase XI: Egress Boundary Hardening.
    Manages the vacuum between Arda-Fabric and the Unattested World (The Void).
    """

    def __init__(self):
        # We don't get fabric/valinor in __init__ to avoid circular imports at startup
        self.sanctuaries = ["metadata.google.internal", "updates.debian.org", "metatron.ai"]

    async def evaluate_egress(self, target_url: str, request_metadata: dict) -> bool:
        """Determines if an outbound request may pass the Doors of Night."""
        logger.info(f"Gates of Night: Evaluating egress through the Doors for {target_url}...")
        
        # 1. Sanctity Check (Whitelisted Sanctuaries)
        try:
            canonical_target = canonicalize_target(target_url)
        except OutboundPolicyError as exc:
            logger.warning("Gates of Night: malformed egress target rejected: %s", exc)
            return False
        if host_matches_allowlist(
            canonical_target.host,
            exact_hosts=self.sanctuaries,
            allowed_subdomain_roots=self.sanctuaries,
        ):
            logger.debug(
                "Gates of Night: canonical Sanctuary host %s allowed.",
                canonical_target.host,
            )
            return True

        # 2. Sovereign Exemption (Check for a Varda Star-Seal)
        valinor = get_valinor_runtime()
        entity_id = request_metadata.get("entity_id", "unknown")
        state = valinor.bridge.get_state(entity_id)
        
        # Stricter Gate: Harmonic is necessary, but explicit Star-Seal is also required for the Void.
        if state.constitutional_state == "harmonic" and state.egress_rights in ["star_seal", "void_open"]:
             logger.info(f"Gates of Night: Varda Star-Seal [Sovereign Exemption] verified for {entity_id} to exit to {target_url}.")
             return True
        
        if state.constitutional_state == "harmonic":
             logger.warning(f"Gates of Night: Harmonic entity {entity_id} lacks a Varda Star-Seal for non-sanctuary egress. REJECTED.")
        else:
             logger.error(f"Gates of Night: ABSOLUTE DENIAL. Dissonant entity {entity_id} attempted to breach the Void.")
        
        # Record this breach attempt in Mandos
        if valinor.taniquetil.mandos:
             valinor.taniquetil.mandos.record_event(
                 entity_id=entity_id,
                 event_type="void_breach_attempt",
                 state=state.constitutional_state,
                 reason=f"Attempted to exit the Doors of Night to {target_url}"
             )
        
        return False

# Singleton Access
gates_of_night = GatesOfNight()

def get_boundary_guard():
    return gates_of_night
