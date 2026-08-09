import os
import logging
import hashlib
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timezone

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.exceptions import InvalidSignature
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

try:
    from schemas.phase4_models import NodeIdentity
    from services.telemetry_chain import tamper_evident_telemetry
except Exception:
    from backend.schemas.phase4_models import NodeIdentity
    from backend.services.telemetry_chain import tamper_evident_telemetry

logger = logging.getLogger(__name__)


class NodeIdentityUnavailable(RuntimeError):
    """Raised when cryptographic node identity cannot be established."""


class NodeIdentityService:
    """
    The Foundation of Distributed Trust.
    Issues and manages the cryptographic identity of the local node.
    """
    
    def __init__(self, key_path: str = "config/node_identity.key"):
        self.key_path = key_path
        self._private_key = None
        self._identity: Optional[NodeIdentity] = None
        
    def initialize(self):
        """Load or create the node's cryptographic keys."""
        if not HAS_CRYPTO:
            logger.critical("PHASE IV: 'cryptography' library missing; node identity unavailable.")
            raise NodeIdentityUnavailable(
                "cryptographic node identity cannot fall back to an unkeyed digest"
            )

        if os.path.exists(self.key_path):
            self._load_keys()
        else:
            self._generate_keys()
            
        self._build_identity()
        logger.info(f"PHASE IV: Node Identity initialized. Node ID: {self._identity.node_id}")

    def get_identity(self) -> NodeIdentity:
        """Return the public identity of this node."""
        if not self._identity:
            self.initialize()
        return self._identity

    async def get_node_identity(self) -> NodeIdentity:
        """Async wrapper for identity retrieval."""
        return self.get_identity()

    def sign_payload(self, payload: str) -> str:
        """Sign a string payload using the node's private key."""
        if not HAS_CRYPTO or not self._private_key:
            raise NodeIdentityUnavailable(
                "node private key is unavailable; an unkeyed hash is not a signature"
            )

        signature = self._private_key.sign(
            payload.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        import base64
        return base64.b64encode(signature).decode('utf-8')

    def _generate_keys(self):
        """Generate a new RSA 4096-bit keypair."""
        logger.info("PHASE IV: Generating fresh node keypair (RSA-4096)...")
        self._private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096
        )
        
        # Ensure config dir exists
        os.makedirs(os.path.dirname(self.key_path), exist_ok=True)
        
        # Save private key (securely in production, but here we just write it)
        with open(self.key_path, "wb") as f:
            f.write(self._private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        os.chmod(self.key_path, 0o600)

    def _load_keys(self):
        """Load the private key from disk."""
        logger.info(f"PHASE IV: Loading node keypair from {self.key_path}...")
        with open(self.key_path, "rb") as f:
            self._private_key = serialization.load_pem_private_key(
                f.read(),
                password=None
            )
        try:
            os.chmod(self.key_path, 0o600)
        except OSError as exc:
            if str(os.environ.get("ARDA_ENV") or "").lower() == "production":
                raise NodeIdentityUnavailable(
                    "cannot enforce private-key filesystem permissions"
                ) from exc

    def _build_identity(self):
        """Derive the node's identity from its public key."""
        public_key = self._private_key.public_key()
        pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        # Derive Node ID (SHA256 of public key)
        fingerprint = hashlib.sha256(pem.encode()).hexdigest()
        node_id = f"node-{fingerprint[:16]}"
        
        # Bind to Herald if active (Late binding to prevent circular import)
        try:
            from services.manwe_herald import manwe_herald
        except Exception:
            from backend.services.manwe_herald import manwe_herald
            
        herald_state = manwe_herald.get_state()
        metadata = {
            "herald_id": herald_state.herald_id if herald_state else "unbound",
            "boot_epoch": herald_state.current_epoch if herald_state else "unknown",
            "hostname": os.uname().nodename if hasattr(os, 'uname') else "localhost"
        }
        
        self._identity = NodeIdentity(
            node_id=node_id,
            public_key_pem=pem,
            fingerprint=fingerprint,
            metadata=metadata
        )

# Global singleton
node_identity = NodeIdentityService()

def get_node_identity_service(db: Any = None) -> NodeIdentityService:
    global node_identity
    return node_identity
