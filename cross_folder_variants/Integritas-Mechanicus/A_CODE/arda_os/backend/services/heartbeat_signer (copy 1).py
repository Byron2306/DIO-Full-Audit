import logging
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any

try:
    from schemas.phase3_models import HeartbeatProof
    from schemas.phase4_models import HeartbeatEnvelope
    from services.node_identity_service import get_node_identity_service
except Exception:
    from backend.schemas.phase3_models import HeartbeatProof
    from backend.schemas.phase4_models import HeartbeatEnvelope
    from backend.services.node_identity_service import get_node_identity_service

logger = logging.getLogger(__name__)

class HeartbeatSignerService:
    """
    The Voice of the Chorus.
    Envelopes local heartbeats in a signed cryptographic wrapper.
    """
    
    def __init__(self):
        self.identity_service = get_node_identity_service()
        self._seq_counter = 0 # Monotonic counter for replay protection

    async def create_envelope(self, proof: HeartbeatProof) -> HeartbeatEnvelope:
        """
        Sign a heartbeat proof and envelope it for transport.
        """
        self._seq_counter += 1
        
        # 1. Prepare Payload (Canonical Representation)
        # Use raw string values for Enums in the signed payload
        status_str = proof.status.value if hasattr(proof.status, "value") else str(proof.status)
        canonical_payload = f"{proof.node_id}:{proof.manifold_state_hash}:{self._seq_counter}:{status_str}"
        
        # 2. Sign
        signature = self.identity_service.sign_payload(canonical_payload)
        
        # 3. Build Envelope
        envelope = HeartbeatEnvelope(
            envelope_id=f"env-{uuid.uuid4().hex[:12]}",
            signer_node_id=proof.node_id,
            signed_payload=canonical_payload,
            signature=signature,
            nonce=hashlib.sha256(f"{uuid.uuid4().hex}:{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest(),
            timestamp_sent=datetime.now(timezone.utc)
        )
        
        logger.debug(f"PHASE IV: Signed heartbeat envelope {envelope.envelope_id} (seq: {self._seq_counter})")
        return envelope

# Global singleton
heartbeat_signer = HeartbeatSignerService()

def get_heartbeat_signer() -> HeartbeatSignerService:
    global heartbeat_signer
    return heartbeat_signer
