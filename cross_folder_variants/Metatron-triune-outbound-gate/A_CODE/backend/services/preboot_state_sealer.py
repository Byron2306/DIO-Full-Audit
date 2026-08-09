import logging
import json
import hmac
import hashlib
import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
try:
    from schemas.phase6_models import PrebootCovenant
except Exception:
    from backend.schemas.phase6_models import PrebootCovenant

logger = logging.getLogger(__name__)

class PrebootStateSealer:
    """
    Seals and persists the pre-boot verdict for the runtime to inherit.
    Handles the 'Sealed Handoff' from initramfs to the full OS.
    """
    
    def __init__(self, key: str = "seraph_internal_secret_key"):
        self.key = key.encode()
        self.seal_path = os.environ.get("PREBOOT_COVENANT_PATH", "/run/seraph/preboot_covenant.sealed")
        if os.name == 'nt': # Windows development override
            self.seal_path = os.path.join(os.getcwd(), "tmp", "preboot_covenant.sealed")

    async def generate_lawful_covenant(self) -> str:
        """
        Simulates the initramfs action of measuring the rootfs and sealing the covenant.
        This is the 'Birth of Arda' as an OS.
        """
        logger.info("PHASE VI (Preboot): Measuring the Kingdom and sealing the Covenant...")
        
        # 1. Measure the 'Rootfs' (simulated)
        # We use the same logic as the handoff verifier to establish the baseline
        from backend.services.lawful_handoff import get_lawful_handoff
        handoff = get_lawful_handoff()
        rootfs_hash = await handoff._calculate_runtime_rootfs_hash()
        
        # 2. Form the Preboot Covenant
        from backend.schemas.phase6_models import PrebootCovenant, FormationVerdict
        covenant = PrebootCovenant(
            covenant_id=f"cov-{uuid.uuid4().hex[:8]}",
            formation_verdict=FormationVerdict(is_lawful=True, confidence_score=1.0),
            boot_id=uuid.uuid4().hex,
            manifest_hash=hashlib.sha256(b"arda-genesis-manifest").hexdigest(),
            rootfs_hash=rootfs_hash,
            reaction_mode=os.environ.get("ARDA_REACTION_MODE", "guarded"),
            sealed_data="protected_init_key_0xdeadbeef"
        )
        
        # 3. Seal it
        return await self.seal_covenant(covenant)

    async def seal_covenant(self, covenant: PrebootCovenant) -> str:
        """Serializes and seals a covenant with an HMAC."""
        data = covenant.model_dump_json().encode()
        sig = hmac.new(self.key, data, hashlib.sha256).hexdigest()
        
        sealed_data = f"{sig}:{base64.b64encode(data).decode()}"
        
        # Save to /run (volatile, suitable for boot handoff)
        os.makedirs(os.path.dirname(self.seal_path), exist_ok=True)
        with open(self.seal_path, "w") as f:
            f.write(sealed_data)
        
        logger.info(f"PHASE VI: Preboot Covenant SEALED at {self.seal_path}.")
        return sealed_data

    async def unseal_covenant(self) -> Optional[PrebootCovenant]:
        """Loads and verifies a sealed covenant from the substrate."""
        if not os.path.exists(self.seal_path):
            logger.warning(f"No sealed preboot covenant found at {self.seal_path}.")
            return None
            
        try:
            with open(self.seal_path, "r") as f:
                sealed_data = f.read()
                
            sig, b64_data = sealed_data.split(":", 1)
            data = base64.b64decode(b64_data.encode())
            
            # Verify HMAC
            expected_sig = hmac.new(self.key, data, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected_sig):
                logger.error("Sealed covenant HMAC verification FAILED.")
                return None
            
            # Reconstruct model
            return PrebootCovenant.model_validate_json(data.decode())
        except Exception as e:
            logger.error(f"Failed to unseal preboot covenant: {e}")
            
        return None

import base64
# Singleton
_instance = None
def get_preboot_state_sealer():
    global _instance
    if _instance is None:
        _instance = PrebootStateSealer()
    return _instance
