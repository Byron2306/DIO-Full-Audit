import logging
import base64
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
try:
    from services.node_identity_service import get_node_identity_service
    from services.tpm_attestation_service import get_tpm_service
    from schemas.phase6_models import AttestedNodeState
except Exception:
    from backend.services.node_identity_service import get_node_identity_service
    from backend.services.tpm_attestation_service import get_tpm_service
    from backend.schemas.phase6_models import AttestedNodeState

logger = logging.getLogger(__name__)

class AttestedIdentityBridge:
    """
    Binds the cryptographic node identity to the physical, measured birth of the machine.
    Enforces the 'Not just who I am, but how I was born' principle.
    """
    
    def __init__(self, db: Any = None):
        self.db = db
        self.identity_svc = get_node_identity_service(db)
        self.tpm_svc = get_tpm_service()

    async def get_attested_state(self, is_lawful: bool, covenant_id: str) -> AttestedNodeState:
        """Retrieves an attested state for the local node."""
        identity = await self.identity_svc.get_node_identity()
        pcrs = await self.tpm_svc.get_pcr_snapshot()
        
        pcr_dict = {p.index: p.value for p in pcrs}
        
        return AttestedNodeState(
            node_id=identity.node_id,
            is_attested=is_lawful,
            status="attested" if is_lawful else "fractured",
            preboot_covenant_id=covenant_id,
            last_attestation_timestamp=datetime.utcnow(),
            pcr_values=pcr_dict
        )

    async def verify_remote_attestation(self, state: AttestedNodeState) -> bool:
        """Reject legacy self-reported remote state.

        ``AttestedNodeState`` contains claims, not nonce-bound quote evidence.
        Remote callers must use ``StrictArdaAttestationVerifier`` and present
        its signed ``ArdaAttestationResultV1`` to the relying party.
        """
        logger.error(
            "PHASE VI: Remote node %s supplied self-reported attestation state; "
            "strict verifier appraisal is required.",
            getattr(state, "node_id", "unknown"),
        )
        return False

# Singleton
_instance = None
def get_attested_identity_bridge(db: Any = None):
    global _instance
    if _instance is None:
        _instance = AttestedIdentityBridge(db)
    return _instance
