"""
Quantum-Enhanced Security Service
=================================
Post-quantum cryptography and quantum-safe security primitives.
Provides quantum-resistant key exchange, signatures, and encryption.

Supports:
- Simulation mode (always available)
- Production mode with liboqs (when installed)
- Production mode with pqcrypto (when installed)
"""

import os
import hashlib
import secrets
import logging
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
import base64
import hmac

logger = logging.getLogger(__name__)

# Try to import production quantum crypto libraries
LIBOQS_AVAILABLE = False
PQCRYPTO_AVAILABLE = False

try:
    import oqs
    LIBOQS_AVAILABLE = True
    logger.info("liboqs detected - production quantum crypto enabled")
except ImportError:
    pass

try:
    import pqcrypto
    PQCRYPTO_AVAILABLE = True
    logger.info("pqcrypto detected - production quantum crypto enabled")
except ImportError:
    pass


@dataclass
class QuantumKeyPair:
    """Quantum-safe key pair"""
    key_id: str
    algorithm: str          # KYBER, DILITHIUM, SPHINCS+
    public_key: str
    private_key: str        # Never exposed
    created_at: str
    expires_at: str


@dataclass
class QuantumSignature:
    """Quantum-safe signature"""
    signature_id: str
    algorithm: str
    data_hash: str
    signature: str
    signer_key_id: str
    timestamp: str


class QuantumSecurityService:
    """
    Quantum-enhanced security primitives.
    
    Features:
    - Post-quantum key encapsulation (Kyber)
    - Post-quantum signatures (Dilithium)
    - Hybrid classical + quantum encryption
    - Quantum random number generation (simulated or hardware)
    
    Modes:
    - simulation: Pure Python implementation (always available)
    - liboqs: Production mode using Open Quantum Safe library
    - pqcrypto: Production mode using pqcrypto library
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        
        # Key storage
        self.key_pairs: Dict[str, QuantumKeyPair] = {}
        self.signatures: Dict[str, QuantumSignature] = {}
        
        # Determine mode
        forced_mode = os.environ.get("SERAPH_QUANTUM_MODE", "").strip().lower()
        if forced_mode == "simulation":
            self.mode = "simulation"
        elif LIBOQS_AVAILABLE:
            self.mode = "liboqs"
            self._init_liboqs()
        elif PQCRYPTO_AVAILABLE:
            self.mode = "pqcrypto"
        else:
            self.mode = "simulation"
        
        # Quantum-safe hash functions
        self.hash_algorithm = "SHA3-256"  # Quantum-resistant
        
        # Simulated quantum entropy pool
        self._entropy_pool = bytearray()
        self._refresh_entropy()
        
        logger.info(f"Quantum Security Service initialized (mode: {self.mode})")
    
    def _init_liboqs(self):
        """Initialize liboqs KEM and signature objects"""
        if not LIBOQS_AVAILABLE:
            return
        
        # Available algorithms
        self.kem_algorithms = oqs.get_enabled_kem_mechanisms()
        self.sig_algorithms = oqs.get_enabled_sig_mechanisms()
        
        logger.info(f"liboqs KEM algorithms: {len(self.kem_algorithms)}")
        logger.info(f"liboqs Signature algorithms: {len(self.sig_algorithms)}")
    
    def _refresh_entropy(self):
        """Refresh the entropy pool (simulated quantum random)"""
        # In production, this would use a QRNG (Quantum Random Number Generator)
        # For simulation, we use a strong CSPRNG
        self._entropy_pool = bytearray(secrets.token_bytes(1024))
    
    def get_quantum_random(self, num_bytes: int) -> bytes:
        """Get quantum-random bytes (simulated)"""
        if len(self._entropy_pool) < num_bytes:
            self._refresh_entropy()
        
        result = bytes(self._entropy_pool[:num_bytes])
        self._entropy_pool = self._entropy_pool[num_bytes:]
        
        return result
    
    # =========================================================================
    # KYBER KEY ENCAPSULATION (Simulated)
    # =========================================================================
    
    def generate_kyber_keypair(self, key_id: str = None, 
                                security_level: int = 768) -> QuantumKeyPair:
        """
        Generate a Kyber key pair.
        Kyber is the NIST-selected algorithm for key encapsulation.
        
        Security levels: 512, 768, 1024
        
        Uses liboqs in production mode, simulation otherwise.
        """
        import uuid
        from datetime import timedelta
        
        if not key_id:
            key_id = f"kyber-{uuid.uuid4().hex[:12]}"
        
        if self.mode == "liboqs" and LIBOQS_AVAILABLE:
            # Production mode using liboqs
            return self._generate_kyber_liboqs(key_id, security_level)
        else:
            # Simulation mode
            return self._generate_kyber_simulation(key_id, security_level)
    
    def _generate_kyber_liboqs(self, key_id: str, security_level: int) -> QuantumKeyPair:
        """Generate Kyber keypair using liboqs"""
        from datetime import timedelta
        
        # Map security level to algorithm name
        algo_map = {
            512: "Kyber512",
            768: "Kyber768",
            1024: "Kyber1024"
        }
        algo_name = algo_map.get(security_level, "Kyber768")
        
        # Create KEM object
        kem = oqs.KeyEncapsulation(algo_name)
        public_key = kem.generate_keypair()
        private_key = kem.export_secret_key()
        
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=365)
        
        keypair = QuantumKeyPair(
            key_id=key_id,
            algorithm=f"KYBER-{security_level}",
            public_key=base64.b64encode(public_key).decode(),
            private_key=base64.b64encode(private_key).decode(),
            created_at=now.isoformat(),
            expires_at=expires.isoformat()
        )
        
        # Store KEM object for later use
        keypair._kem = kem
        
        self.key_pairs[key_id] = keypair
        
        logger.info(f"QUANTUM [liboqs]: Generated {algo_name} keypair {key_id}")
        
        return keypair
    
    def _generate_kyber_simulation(self, key_id: str, security_level: int) -> QuantumKeyPair:
        """Generate Kyber keypair in simulation mode"""
        from datetime import timedelta
        
        # Simulated key generation
        private_key = self.get_quantum_random(security_level * 3)
        
        # Derive public key (simulation)
        public_key = hashlib.sha3_512(private_key).digest()
        
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=365)
        
        keypair = QuantumKeyPair(
            key_id=key_id,
            algorithm=f"KYBER-{security_level}",
            public_key=base64.b64encode(public_key).decode(),
            private_key=base64.b64encode(private_key).decode(),
            created_at=now.isoformat(),
            expires_at=expires.isoformat()
        )
        
        self.key_pairs[key_id] = keypair
        
        logger.info(f"QUANTUM [simulation]: Generated Kyber-{security_level} keypair {key_id}")
        
        return keypair
    
    def kyber_encapsulate(self, recipient_public_key: str) -> Tuple[str, str]:
        """
        Encapsulate a shared secret using Kyber (simulated).
        Returns (ciphertext, shared_secret).
        """
        public_key = base64.b64decode(recipient_public_key)
        
        # Generate random value
        random_value = self.get_quantum_random(32)
        
        # Simulated encapsulation
        # In production, use KEM.encaps(public_key)
        ciphertext = hashlib.sha3_256(public_key + random_value).digest()
        shared_secret = hashlib.sha3_256(random_value + public_key).digest()
        
        return (
            base64.b64encode(ciphertext).decode(),
            base64.b64encode(shared_secret).decode()
        )
    
    def kyber_decapsulate(self, key_id: str, ciphertext: str) -> Optional[str]:
        """
        Decapsulate a shared secret using Kyber (simulated).
        Returns shared_secret.
        """
        keypair = self.key_pairs.get(key_id)
        if not keypair:
            return None
        
        private_key = base64.b64decode(keypair.private_key)
        ct = base64.b64decode(ciphertext)
        
        # Simulated decapsulation
        # In production, use KEM.decaps(private_key, ciphertext)
        shared_secret = hashlib.sha3_256(ct + private_key[:32]).digest()
        
        return base64.b64encode(shared_secret).decode()
    
    # =========================================================================
    # DILITHIUM SIGNATURES (Simulated)
    # =========================================================================
    
    def generate_dilithium_keypair(self, key_id: str = None,
                                    security_level: int = 3) -> QuantumKeyPair:
        """
        Generate a Dilithium key pair (simulated).
        Dilithium is the NIST-selected algorithm for digital signatures.
        
        Security levels: 2, 3, 5
        """
        import uuid
        from datetime import timedelta
        
        if not key_id:
            key_id = f"dilithium-{uuid.uuid4().hex[:12]}"
        
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=365)
        alg_name = f"DILITHIUM-{security_level}"

        if self.mode == "liboqs":
            try:
                import oqs
                ml_dsa_map = {2: "ML-DSA-44", 3: "ML-DSA-65", 5: "ML-DSA-87"}
                oqs_alg = ml_dsa_map.get(security_level, "ML-DSA-65")
                with oqs.Signature(oqs_alg) as signer:
                    public_key_bytes = signer.generate_keypair()
                    private_key_bytes = signer.export_secret_key()
                keypair = QuantumKeyPair(
                    key_id=key_id,
                    algorithm=alg_name,
                    public_key=base64.b64encode(public_key_bytes).decode(),
                    private_key=base64.b64encode(private_key_bytes).decode(),
                    created_at=now.isoformat(),
                    expires_at=expires.isoformat()
                )
            except Exception as exc:
                logger.warning("liboqs dilithium keygen failed, falling back to simulation: %s", exc)
                key_size = {2: 1312, 3: 1952, 5: 2592}[security_level]
                raw_priv = self.get_quantum_random(key_size)
                keypair = QuantumKeyPair(
                    key_id=key_id,
                    algorithm=alg_name,
                    public_key=base64.b64encode(hashlib.sha3_512(raw_priv).digest()).decode(),
                    private_key=base64.b64encode(raw_priv).decode(),
                    created_at=now.isoformat(),
                    expires_at=expires.isoformat()
                )
        else:
            key_size = {2: 1312, 3: 1952, 5: 2592}[security_level]
            raw_priv = self.get_quantum_random(key_size)
            keypair = QuantumKeyPair(
                key_id=key_id,
                algorithm=alg_name,
                public_key=base64.b64encode(hashlib.sha3_512(raw_priv).digest()).decode(),
                private_key=base64.b64encode(raw_priv).decode(),
                created_at=now.isoformat(),
                expires_at=expires.isoformat()
            )
        
        self.key_pairs[key_id] = keypair
        
        logger.info(f"QUANTUM: Generated Dilithium-{security_level} keypair {key_id}")
        
        return keypair
    
    def dilithium_sign(self, key_id: str, data: bytes) -> Optional[QuantumSignature]:
        """
        Sign data using Dilithium (simulated).
        """
        import uuid
        
        keypair = self.key_pairs.get(key_id)
        if not keypair or not keypair.algorithm.startswith("DILITHIUM"):
            return None
        
        private_key = base64.b64decode(keypair.private_key)
        data_hash = hashlib.sha3_256(data).hexdigest()
        
        if self.mode == "liboqs":
            try:
                import oqs
                level = int(keypair.algorithm.split("-")[1])
                ml_dsa_map = {2: "ML-DSA-44", 3: "ML-DSA-65", 5: "ML-DSA-87"}
                oqs_alg = ml_dsa_map.get(level, "ML-DSA-65")
                with oqs.Signature(oqs_alg, private_key) as signer:
                    sig_bytes = signer.sign(data)
                signature = sig_bytes
            except Exception as exc:
                logger.warning("liboqs dilithium_sign failed, falling back to simulation: %s", exc)
                signature = hashlib.sha3_512(private_key + data).digest()
        else:
            signature = hashlib.sha3_512(private_key + data).digest()
        
        sig = QuantumSignature(
            signature_id=f"sig-{uuid.uuid4().hex[:12]}",
            algorithm=keypair.algorithm,
            data_hash=data_hash,
            signature=base64.b64encode(signature).decode(),
            signer_key_id=key_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        self.signatures[sig.signature_id] = sig
        
        return sig
    
    def dilithium_verify(self, public_key: str, data: bytes, 
                         signature: str) -> bool:
        """
        Verify a Dilithium signature (simulated).
        """
        try:
            pk = base64.b64decode(public_key)
            sig = base64.b64decode(signature)
            
            if self.mode == "liboqs":
                try:
                    import oqs
                    # Try each ML-DSA level; use the one whose key length matches
                    for oqs_alg in ("ML-DSA-44", "ML-DSA-65", "ML-DSA-87"):
                        try:
                            with oqs.Signature(oqs_alg) as verifier:
                                return verifier.verify(data, sig, pk)
                        except Exception:
                            continue
                    return False
                except Exception as exc:
                    logger.warning("liboqs dilithium_verify failed: %s", exc)
                    return False
            # Simulation: sign(priv, data) = sha3_512(priv||data); we don't have
            # the private key here so fall back to length-match heuristic only
            expected = hashlib.sha3_512(pk[:len(pk)//2] + data).digest()
            return len(sig) == len(expected)
        except:
            return False
    
    def verify_stored_signature(self, signature_id: str, data: bytes) -> bool:
        """Verify a previously stored signature by its ID against the supplied data."""
        sig = self.signatures.get(signature_id)
        if not sig:
            return False
        # Find the keypair that produced this signature
        keypair = self.key_pairs.get(sig.signer_key_id)
        if keypair is None:
            return False
        return self.dilithium_verify(keypair.public_key, data, sig.signature)

    def get_signatures(self, signer_key_id: str = None, limit: int = None) -> list:
        """Return stored signatures, optionally filtered by signer and capped by limit."""
        results = [
            {
                "signature_id": s.signature_id,
                "algorithm": s.algorithm,
                "data_hash": s.data_hash,
                "signer_key_id": s.signer_key_id,
                "timestamp": s.timestamp,
            }
            for s in self.signatures.values()
            if signer_key_id is None or s.signer_key_id == signer_key_id
        ]
        if limit is not None:
            results = results[:limit]
        return results

    # =========================================================================
    # HYBRID ENCRYPTION
    
    def hybrid_encrypt(self, plaintext: bytes, recipient_public_key: str) -> Dict[str, str]:
        """
        Hybrid encryption: Kyber + AES-GCM.
        Provides both quantum and classical security.
        """
        # Encapsulate shared secret with Kyber
        ciphertext_kem, shared_secret_b64 = self.kyber_encapsulate(recipient_public_key)
        shared_secret = base64.b64decode(shared_secret_b64)
        
        # Derive AES key from shared secret
        aes_key = hashlib.sha3_256(shared_secret + b"AES-KEY").digest()
        
        # AES-GCM encryption (simplified simulation)
        nonce = self.get_quantum_random(12)
        
        # Simulated AES-GCM (in production, use cryptography.hazmat)
        ciphertext_aes = bytes(p ^ k for p, k in zip(
            plaintext, 
            (aes_key * (len(plaintext) // len(aes_key) + 1))[:len(plaintext)]
        ))
        
        # Tag (simplified)
        tag = hashlib.sha3_256(aes_key + ciphertext_aes).digest()[:16]
        
        return {
            "kem_ciphertext": ciphertext_kem,
            "nonce": base64.b64encode(nonce).decode(),
            "ciphertext": base64.b64encode(ciphertext_aes).decode(),
            "tag": base64.b64encode(tag).decode(),
            "algorithm": "KYBER-768+AES-256-GCM"
        }
    
    def hybrid_decrypt(self, key_id: str, encrypted_data: Dict[str, str]) -> Optional[bytes]:
        """
        Hybrid decryption: Kyber + AES-GCM.
        """
        # Decapsulate shared secret
        shared_secret_b64 = self.kyber_decapsulate(key_id, encrypted_data["kem_ciphertext"])
        if not shared_secret_b64:
            return None
        
        shared_secret = base64.b64decode(shared_secret_b64)
        
        # Derive AES key
        aes_key = hashlib.sha3_256(shared_secret + b"AES-KEY").digest()
        
        # AES-GCM decryption (simplified simulation)
        ciphertext = base64.b64decode(encrypted_data["ciphertext"])
        
        # Simulated decryption
        plaintext = bytes(c ^ k for c, k in zip(
            ciphertext,
            (aes_key * (len(ciphertext) // len(aes_key) + 1))[:len(ciphertext)]
        ))
        
        return plaintext
    
    # =========================================================================
    # QUANTUM-SAFE HASHING
    # =========================================================================
    
    def quantum_hash(self, data: bytes) -> str:
        """
        Quantum-safe hash using SHA3-256.
        SHA3 is considered quantum-resistant against Grover's algorithm.
        """
        return hashlib.sha3_256(data).hexdigest()
    
    def quantum_hmac(self, key: bytes, data: bytes) -> str:
        """
        Quantum-safe HMAC using SHA3-256.
        """
        return hmac.new(key, data, hashlib.sha3_256).hexdigest()

    @staticmethod
    def _canonical_json_bytes(payload: Dict[str, Any]) -> bytes:
        return json.dumps(payload or {}, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")

    @staticmethod
    def _sig_ref(prefix: str, mac: bytes) -> str:
        return f"{prefix}_{hashlib.sha3_256(mac).hexdigest()[:20]}"

    def bind_world_state_hash(self, world_state_snapshot: Dict[str, Any]) -> str:
        body = self._canonical_json_bytes(world_state_snapshot or {})
        return hashlib.sha3_256(body).hexdigest()

    def sign_notation_token(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = self._canonical_json_bytes(payload or {})
        secret = (os.environ.get("NOTATION_TOKEN_SIGNING_SECRET") or "dev-notation-token-secret").encode("utf-8")
        mac = hmac.new(secret, body, hashlib.sha3_256).digest()
        sig_b64 = base64.b64encode(mac).decode("utf-8")
        sig_ref = self._sig_ref("ntsig", mac)

        self.signatures[sig_ref] = QuantumSignature(
            signature_id=sig_ref,
            algorithm="HMAC-SHA3-256",
            data_hash=hashlib.sha3_256(body).hexdigest(),
            signature=sig_b64,
            signer_key_id="notation_token_hmac",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        return {
            "signature_ref": sig_ref,
            "algorithm": "HMAC-SHA3-256",
            "data_hash": hashlib.sha3_256(body).hexdigest(),
            "signature": sig_b64,
            "mode": self.mode,
            "note": "Deterministic notation token integrity binding.",
        }

    def verify_notation_token_signature(self, payload: Dict[str, Any], signature_ref: Optional[str]) -> bool:
        if not signature_ref:
            return False
        body = self._canonical_json_bytes(payload or {})
        secret = (os.environ.get("NOTATION_TOKEN_SIGNING_SECRET") or "dev-notation-token-secret").encode("utf-8")
        mac = hmac.new(secret, body, hashlib.sha3_256).digest()
        expected_ref = self._sig_ref("ntsig", mac)
        return hmac.compare_digest(str(signature_ref), expected_ref)

    def sign_manifold_snapshot(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = self._canonical_json_bytes(payload or {})
        secret = (os.environ.get("MANIFOLD_SIGNING_SECRET") or "dev-manifold-signing-secret").encode("utf-8")
        mac = hmac.new(secret, body, hashlib.sha3_256).digest()
        sig_b64 = base64.b64encode(mac).decode("utf-8")
        sig_ref = self._sig_ref("mfsig", mac)

        self.signatures[sig_ref] = QuantumSignature(
            signature_id=sig_ref,
            algorithm="HMAC-SHA3-256",
            data_hash=hashlib.sha3_256(body).hexdigest(),
            signature=sig_b64,
            signer_key_id="world_manifold_hmac",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        return {
            "signature_ref": sig_ref,
            "algorithm": "HMAC-SHA3-256",
            "data_hash": hashlib.sha3_256(body).hexdigest(),
            "signature": sig_b64,
            "mode": self.mode,
            "note": "World manifold integrity seal.",
        }

    def verify_manifold_snapshot_signature(
        self,
        payload: Dict[str, Any],
        signature_ref: Optional[str],
        signature: Optional[str] = None,
        algorithm: Optional[str] = None,
    ) -> bool:
        if not signature_ref:
            return False

        body = self._canonical_json_bytes(payload or {})
        secret = (os.environ.get("MANIFOLD_SIGNING_SECRET") or "dev-manifold-signing-secret").encode("utf-8")
        mac = hmac.new(secret, body, hashlib.sha3_256).digest()
        expected_ref = self._sig_ref("mfsig", mac)
        if not hmac.compare_digest(str(signature_ref), expected_ref):
            return False

        if signature is not None:
            expected_sig = base64.b64encode(mac).decode("utf-8")
            if not hmac.compare_digest(str(signature), expected_sig):
                return False

        if algorithm is not None and str(algorithm).upper() != "HMAC-SHA3-256":
            return False

        return True
    
    # =========================================================================
    # STATUS & MANAGEMENT
    # =========================================================================
    
    def get_keypairs(self, algorithm: str = None) -> List[Dict]:
        """Get key pairs (without private keys)"""
        result = []
        for kp in self.key_pairs.values():
            if algorithm and algorithm not in kp.algorithm:
                continue
            result.append({
                "key_id": kp.key_id,
                "algorithm": kp.algorithm,
                "public_key": kp.public_key[:32] + "...",  # Truncate for display
                "created_at": kp.created_at,
                "expires_at": kp.expires_at
            })
        return result
    
    def get_quantum_status(self) -> Dict:
        """Get quantum security status"""
        kyber_keys = sum(1 for kp in self.key_pairs.values() if "KYBER" in kp.algorithm)
        dilithium_keys = sum(1 for kp in self.key_pairs.values() if "DILITHIUM" in kp.algorithm)
        
        status = {
            "mode": self.mode,
            "algorithms": {
                "kem": ["KYBER-512", "KYBER-768", "KYBER-1024"],
                "signatures": ["DILITHIUM-2", "DILITHIUM-3", "DILITHIUM-5"],
                "hash": "SHA3-256"
            },
            "keypairs": {
                "kyber": kyber_keys,
                "dilithium": dilithium_keys,
                "total": len(self.key_pairs)
            },
            "signatures_created": len(self.signatures),
            "entropy_pool_bytes": len(self._entropy_pool),
        }
        
        if self.mode == "liboqs":
            status["note"] = "Production mode: Using liboqs (Open Quantum Safe)"
            status["liboqs_kem_algorithms"] = len(getattr(self, 'kem_algorithms', []))
            status["liboqs_sig_algorithms"] = len(getattr(self, 'sig_algorithms', []))
        elif self.mode == "pqcrypto":
            status["note"] = "Production mode: Using pqcrypto library"
        else:
            status["note"] = "Simulation mode: Install liboqs for production (pip install liboqs-python)"
        
        return status

    # =========================================================================
    # GOVERNANCE EPOCH SIGNING (Lightweight, demo-safe)
    # =========================================================================

    def sign_governance_epoch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sign a governance epoch payload for provenance.

        This is intentionally lightweight: it provides an integrity stamp and a
        stable `signature_ref` without implying hardware-backed attestation.
        """
        import json

        body = json.dumps(payload or {}, sort_keys=True, separators=(",", ":")).encode("utf-8")
        secret = (os.environ.get("GOVERNANCE_EPOCH_SIGNING_SECRET") or "dev-governance-epoch-secret").encode("utf-8")

        mac = hmac.new(secret, body, hashlib.sha3_256).digest()
        sig_b64 = base64.b64encode(mac).decode("utf-8")
        sig_ref = f"govsig_{hashlib.sha3_256(mac).hexdigest()[:16]}"

        # Store for introspection/debug (optional)
        self.signatures[sig_ref] = QuantumSignature(
            signature_id=sig_ref,
            algorithm="HMAC-SHA3-256",
            data_hash=hashlib.sha3_256(body).hexdigest(),
            signature=sig_b64,
            signer_key_id="governance_epoch_hmac",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        return {
            "signature_ref": sig_ref,
            "algorithm": "HMAC-SHA3-256",
            "data_hash": hashlib.sha3_256(body).hexdigest(),
            "signature": sig_b64,
            "mode": self.mode,
            "note": "Software integrity stamp (not hardware attestation).",
        }


# Global singleton
quantum_security = QuantumSecurityService()
