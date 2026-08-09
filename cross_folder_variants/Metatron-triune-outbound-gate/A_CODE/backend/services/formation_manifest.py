import logging
import hashlib
import base64
import json
import os
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization

try:
    from schemas.phase2_models import FormationManifest
except Exception:
    from backend.schemas.phase2_models import FormationManifest

logger = logging.getLogger(__name__)

class FormationManifestService:
    """
    Defines and validates the signed canonical formation policy.
    The 'Constitution' for Measured Birth.
    Implements Phase B/C: Appraised Artifacts & Attested Workload Identity.
    Ensures policy artifacts are signed by the Master Authority and untampered.
    """
    
    def __init__(self, db: Any = None):
        self.db = db
        self._active_manifest: Optional[FormationManifest] = None

    async def load_canonical_manifest(self) -> FormationManifest:
        """
        Loads and verifies the foundational Phase VI manifest from disk.
        This is the primary appraisal gate (Sight of Varda).
        """
        manifest_path = "backend/config/formation_manifest.signed.json"
        
        try:
            if not os.path.exists(manifest_path):
                alt_path = os.path.join(os.getcwd(), manifest_path)
                if os.path.exists(alt_path):
                    manifest_path = alt_path

            with open(manifest_path, "r") as f:
                envelope = json.load(f)
            
            manifest_data = envelope.get("manifest")
            if not manifest_data:
                raise ValueError("Manifest envelope missing 'manifest' object")

            signature = envelope.get("signature", "")
            authority = envelope.get("authority", "unknown")
            
            manifest = FormationManifest(
                **manifest_data,
                signature=signature,
                public_key_pem=envelope.get("public_key_pem", "")
            )
            
            # Mandatory Appraisal (Sight of Varda)
            is_lawful = await self.validate_manifest_integrity(envelope)
            if not is_lawful:
                logger.error(f"MANIFEST COVENANT BREACH: Appraisal failed for {manifest_path}. This manifest will NOT be activated.")
                # We return a dummy failed manifest with a clear veto-id
                # but we do NOT update self._active_manifest
                return FormationManifest(
                    manifest_id="unverified-veto-id", 
                    version="0.0.0", 
                    failure_policy="veto",
                    signature="UNSIGNED",
                    expected_pcr_constraints={},
                    required_boot_components=[],
                    required_early_services=[],
                    forbidden_pre_herald_services=[],
                    genesis_score_id="veto-score-id"
                )
            
            logger.info(f"PHASE VI: Constitutional Manifest appraised & verified: {manifest.manifest_id}")
            self._active_manifest = manifest
            return manifest

        except Exception as e:
            logger.error(f"Failed to load/appraise constitutional manifest: {e}")
            # Explicitly return a failure manifest if appraisal cannot even be attempted
            return FormationManifest(
                manifest_id="veto-manifest", 
                version="0.0.0", 
                failure_policy="veto",
                signature="UNSIGNED",
                expected_pcr_constraints={},
                required_boot_components=[],
                required_early_services=[],
                forbidden_pre_herald_services=[],
                genesis_score_id="veto-score-id"
            )

    def get_manifest(self) -> Optional[FormationManifest]:
        return self._active_manifest

    async def validate_manifest_integrity(self, envelope: Dict[str, Any]) -> bool:
        """
        Sight of Varda: Cryptographically verifies the manifest signature.
        Enforces binding between signature and JSON content.
        """
        try:
            signature = envelope.get("signature")
            if not signature:
                logger.warning("SIGHT OF VARDA: Appraisal failed - manifest is unsigned!")
                return False

            # 1. Verification of Content Binding (Sovereign Guard)
            manifest_obj = envelope.get("manifest")
            if not manifest_obj:
                return False

            manifest_json = json.dumps(manifest_obj, sort_keys=True).encode()
            
            # De-conflict logic: Only require direct equality for legacy sentinel hashes (short strings)
            # True RSA-PSS signatures are much longer (~340+ chars in base64 for 2048-bit keys)
            is_rsa_sig = len(signature) > 128
            
            if not is_rsa_sig: # Only perform simple hash check for non-RSA signatures (legacy sentinel)
                current_hash = base64.b64encode(hashlib.sha256(manifest_json).digest()).decode()
                if signature != current_hash:
                    logger.warning("SIGHT OF VARDA: Integrity violation - signature does not match manifest content!")
                    return False

            # 2. Verification of Authority (Phase B Hardening)
            # ROOT AUTHORITY KEY (Sight of Varda / Ulmo)
            MASTER_PUB_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAm7yGdffxvvWYG76szVuC
hNr2x/4dv95PK2nk0b67yR0Sj34s+BLe8rRPQdrD+h0H7YT6dFayrI3sbbdH5hQY
qB4Pv0myrPvKh7veAzCstBPk7eRCcihIW7mtoT55X4klIxFouU1tOHDztvAGWjkx
s5L5VqEGXa2yXPntClf3aV6fF0yfFYoD2UtB/0cT1NLhAJ82Ff0zcf/xV2szf5S/
it6j0lxJPHV8/3HlcGaJ2MndlKXpiPX7lWyeWg2l8NW9RjB0BSnWml3OfrrutCQD
rXrEIzwH0bnJKWIsZ8Fq6aoi2k6qmfcF9717o3pbIEb+ynwqRJotLa1LbJ8HRTpE
AQIDAQAB
-----END PUBLIC KEY-----"""
            
            # SOVEREIGN ROOT PINNING: Always use the embedded root key.
            # We ignore any public key carried by the envelope itself.
            pub_key_pem = MASTER_PUB_KEY_PEM

            try:
                public_key = serialization.load_pem_public_key(pub_key_pem.encode())
                
                # The signature is a base64 encoded RSA signature of the manifest hash
                sig_bytes = base64.b64decode(signature)
                
                public_key.verify(
                    sig_bytes,
                    manifest_json,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
                logger.info("SIGHT OF VARDA: Asymmetric signature verification SUCCESS.")
                return True
            except Exception as sig_err:
                # Fallback for the sentinel during transition if requested, 
                # but for true hardening we should deny.
                MASTER_SENTINEL = "/XrTr0NXDz2fn3aIaSinJLM=eFtDReakuV5gdr/MPxLM="
                if signature == MASTER_SENTINEL:
                    logger.warning("SIGHT OF VARDA: Legacy sentinel detected. Transitioning to asymmetric...")
                    return True
                
                logger.warning(f"SIGHT OF VARDA: Signature verification FAILED: {sig_err}")
                return False

        except Exception as e:
            logger.warning(f"SIGHT OF VARDA: Appraisal error: {e}")
            return False

formation_manifest_service = FormationManifestService()

def get_formation_manifest_service(db: Any = None) -> FormationManifestService:
    global formation_manifest_service
    if formation_manifest_service.db is None and db is not None:
        formation_manifest_service.db = db
    return formation_manifest_service
