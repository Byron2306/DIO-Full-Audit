import logging
import base64
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.exceptions import InvalidSignature
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

try:
    from schemas.phase4_models import HeartbeatEnvelope, VerifiedHeartbeat, SignatureStatus
    from services.node_identity_service import get_node_identity_service
    from services.peer_registry import get_peer_registry
except Exception:
    from backend.schemas.phase4_models import HeartbeatEnvelope, VerifiedHeartbeat, SignatureStatus
    from backend.services.node_identity_service import get_node_identity_service
    from backend.services.peer_registry import get_peer_registry

logger = logging.getLogger(__name__)

class HeartbeatVerifierService:
    """
    The Auditor of the Chorus.
    Ensures every incoming heartbeat is cryptographically valid and timely.
    """
    
    def __init__(self):
        self.peer_registry = None # Lazy load to prevent circular imports

    async def verify_envelope(self, envelope: HeartbeatEnvelope) -> VerifiedHeartbeat:
        """
        Verify the signature and temporal validity of an envelope.
        """
        if self.peer_registry is None:
            self.peer_registry = get_peer_registry()
            
        start_time = time.time()
        
        # 1. Fetch Peer Identity
        node_id = envelope.signer_node_id
        peer = self.peer_registry.get_peer(node_id)
        
        # 1b. Check if this is the Local Node
        local_identity = get_node_identity_service().get_identity()
        if node_id == local_identity.node_id:
            logger.debug(f"PHASE IV: Verifying local heartbeat from {node_id}")
            peer = local_identity
        
        signature_status = SignatureStatus.UNKNOWN
        
        if not peer:
            logger.warning(f"PHASE IV: Received heartbeat from unknown node {node_id}. Auditing for new identity...")
            # In Phase IV, we might allow auto-discovery if the cert is valid
            # For now, we rejection if not in registry
            signature_status = SignatureStatus.UNKNOWN
        else:
            # 2. Verify Cryptographic Signature
            is_valid = self._verify_cryptographic_signature(
                payload=envelope.signed_payload,
                signature=envelope.signature,
                public_key_pem=peer.public_key_pem
            )
            
            if is_valid:
                # 3. Check Freshness
                now = datetime.now(timezone.utc)
                age = (now - envelope.timestamp_sent).total_seconds()
                
                if age > 60: # 1 minute max age for resonance
                    signature_status = SignatureStatus.EXPIRED
                else:
                    signature_status = SignatureStatus.VERIFIED
            else:
                signature_status = SignatureStatus.INVALID

        # 4. Extract metrics for verified state
        # Parsing payload "node_id:hash:seq:status"
        parts = envelope.signed_payload.split(':')
        m_hash = parts[1] if len(parts) > 1 else "unknown"
        seq = int(parts[2]) if len(parts) > 2 else 0
        h_status = parts[3] if len(parts) > 3 else "unknown"
        
        lag_ms = (time.time() - start_time) * 1000
        
        verified = VerifiedHeartbeat(
            proof_id=envelope.envelope_id,
            node_id=node_id,
            received_at=datetime.now(timezone.utc),
            signature_status=signature_status,
            verification_lag_ms=lag_ms,
            original_timestamp=envelope.timestamp_sent,
            manifold_state_hash=m_hash,
            status=h_status,
            sequence_number=seq
        )
        
        if signature_status != SignatureStatus.VERIFIED:
            logger.error(f"PHASE IV: Heartbeat rejected from {node_id}. Reason: {signature_status.value}")
        else:
            logger.debug(f"PHASE IV: Heartbeat verified from {node_id} (seq: {seq})")
            
        return verified

    def _verify_cryptographic_signature(self, payload: str, signature: str, public_key_pem: str) -> bool:
        """Helper to verify RSA PSS signature."""
        if not HAS_CRYPTO:
            return False # Mock behavior for non-crypto environment

        try:
            public_key = serialization.load_pem_public_key(public_key_pem.encode())
            decoded_sig = base64.b64decode(signature)
            
            public_key.verify(
                decoded_sig,
                payload.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except (InvalidSignature, Exception) as e:
            logger.debug(f"PHASE IV: Cryptographic verification failed: {e}")
            return False

# Global singleton
heartbeat_verifier = HeartbeatVerifierService()

def get_heartbeat_verifier() -> HeartbeatVerifierService:
    global heartbeat_verifier
    return heartbeat_verifier
