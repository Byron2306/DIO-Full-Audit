import logging
import json
import os
import base64
from datetime import datetime
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
try:
    from services.node_identity_service import get_node_identity_service
except Exception:
    from backend.services.node_identity_service import get_node_identity_service

logger = logging.getLogger(__name__)

class SignedManifestValidator:
    """
    Validator for signed constitutional manifests (Phase VI).
    Ensures that the formation policy is signed by a trusted authority.
    """
    
    def __init__(self, db: Any = None):
        self.db = db
        self.identity_svc = get_node_identity_service(db)

    async def validate_signed_manifest(self, manifest_data: Dict[str, Any], signature: str, public_key_pem: str) -> bool:
        """Verifies the RSA signature on a JSON manifest."""
        try:
            # Reconstruct the canonical JSON
            canonical_json = json.dumps(manifest_data, sort_keys=True).encode()
            
            # Load the public key
            public_key = serialization.load_pem_public_key(public_key_pem.encode())
            
            # Verify the signature
            public_key.verify(
                base64.b64decode(signature.encode()),
                canonical_json,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            logger.info("PHASE VI: Constitutional Manifest Signature VERIFIED.")
            return True
        except Exception as e:
            logger.error(f"PHASE VI: Constitutional Manifest Signature FAILED verification: {e}")
            return False

    async def load_and_verify(self, file_path: str, public_key_pem: str) -> Optional[Dict[str, Any]]:
        """Loads a signed manifest file (which contains {manifest: ..., signature: ...}) and verifies it."""
        if not os.path.exists(file_path):
            logger.error(f"Constitutional manifest file not found: {file_path}")
            return None
            
        try:
            with open(file_path, "r") as f:
                envelope = json.load(f)
            
            manifest = envelope.get("manifest")
            signature = envelope.get("signature")
            
            if not manifest or not signature:
                logger.error(f"Invalid signed manifest format at {file_path}")
                return None
                
            if await self.validate_signed_manifest(manifest, signature, public_key_pem):
                return manifest
        except Exception as e:
            logger.error(f"Failed to load/verify signed manifest: {e}")
            
        return None

# Singleton with optional DB dependency
_instance = None
def get_signed_manifest_validator(db: Any = None):
    global _instance
    if _instance is None:
        _instance = SignedManifestValidator(db)
    return _instance
