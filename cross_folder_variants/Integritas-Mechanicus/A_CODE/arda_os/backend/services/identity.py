"""
Identity & Attestation Service
==============================
mTLS identity, SPIFFE-style workload identity, and remote attestation.
Every agent gets a cryptographic identity - not IP-based trust.
"""

import os
import json
import hashlib
import hmac
import base64
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class TrustState(Enum):
    """Trust states for agents/nodes"""
    TRUSTED = "trusted"           # Full trust - all actions allowed
    DEGRADED = "degraded"         # Partial trust - observe/contain only
    QUARANTINED = "quarantined"   # No trust - isolated
    UNKNOWN = "unknown"           # New/unverified - observe only


@dataclass
class WorkloadIdentity:
    """SPIFFE-style workload identity"""
    spiffe_id: str              # spiffe://seraph.local/agent/{agent_id}
    agent_id: str
    hostname: str
    os_type: str
    cert_fingerprint: str       # SHA256 of client cert
    issued_at: str
    expires_at: str
    attestation: Dict[str, Any]
    trust_state: TrustState = TrustState.UNKNOWN
    trust_score: int = 0        # 0-100


@dataclass
class AttestationData:
    """Remote attestation / posture data"""
    agent_version_hash: str     # SHA256 of agent binary
    os_build_hash: str          # OS fingerprint
    secure_boot: bool           # Secure boot enabled
    tpm_available: bool         # TPM/Secure Enclave available
    key_isolated: bool          # Private key in TPM/Keystore
    posture_score: int          # Endpoint posture score (0-100)
    timestamp: str
    nonce: str                  # Anti-replay
    signature: str              # Signed by agent


class IdentityService:
    """
    Centralized identity and attestation service.
    Implements "friend from foe" with hard cryptographic signals.
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
        
        # Configuration
        self.ca_cert_path = os.environ.get('SERAPH_CA_CERT', '/etc/seraph/ca.pem')
        self.signing_key = os.environ.get('SERAPH_SIGNING_KEY', secrets.token_hex(32))
        self.cert_validity_hours = int(os.environ.get('CERT_VALIDITY_HOURS', '24'))
        
        # Identity store (in production, use DB)
        self.identities: Dict[str, WorkloadIdentity] = {}
        self.nonce_cache: Dict[str, datetime] = {}  # Anti-replay
        
        # Trust thresholds
        self.trust_thresholds = {
            TrustState.TRUSTED: 80,
            TrustState.DEGRADED: 50,
            TrustState.UNKNOWN: 0
        }
        
        logger.info("Identity & Attestation Service initialized")
    
    def generate_spiffe_id(self, agent_id: str, workload_type: str = "agent") -> str:
        """Generate SPIFFE-style workload ID"""
        return f"spiffe://seraph.local/{workload_type}/{agent_id}"
    
    def generate_nonce(self) -> str:
        """Generate a one-time nonce for attestation"""
        nonce = secrets.token_hex(16)
        self.nonce_cache[nonce] = datetime.now(timezone.utc)
        return nonce
    
    def verify_nonce(self, nonce: str, max_age_seconds: int = 60) -> bool:
        """Verify nonce is valid and not replayed"""
        if nonce not in self.nonce_cache:
            return False
        
        issued = self.nonce_cache[nonce]
        age = (datetime.now(timezone.utc) - issued).total_seconds()
        
        if age > max_age_seconds:
            del self.nonce_cache[nonce]
            return False
        
        # Consume nonce (one-time use)
        del self.nonce_cache[nonce]
        return True
    
    def compute_attestation_signature(self, data: Dict[str, Any], agent_key: str) -> str:
        """Compute HMAC signature for attestation data"""
        payload = json.dumps(data, sort_keys=True)
        return hmac.new(
            agent_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def verify_attestation(self, attestation: AttestationData, agent_key: str) -> Tuple[bool, str]:
        """Verify attestation data signature and validity"""
        # Check nonce
        if not self.verify_nonce(attestation.nonce):
            return False, "Invalid or expired nonce"
        
        # Verify signature
        data = {
            "agent_version_hash": attestation.agent_version_hash,
            "os_build_hash": attestation.os_build_hash,
            "secure_boot": attestation.secure_boot,
            "tpm_available": attestation.tpm_available,
            "key_isolated": attestation.key_isolated,
            "posture_score": attestation.posture_score,
            "timestamp": attestation.timestamp,
            "nonce": attestation.nonce
        }
        
        expected_sig = self.compute_attestation_signature(data, agent_key)
        if not hmac.compare_digest(expected_sig, attestation.signature):
            return False, "Invalid attestation signature"
        
        # Check timestamp freshness
        try:
            ts = datetime.fromisoformat(attestation.timestamp.replace('Z', '+00:00'))
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            if age > 300:  # 5 minutes max
                return False, "Attestation timestamp too old"
        except Exception:
            return False, "Invalid timestamp format"
        
        return True, "Attestation verified"
    
    def calculate_trust_score(self, attestation: AttestationData, 
                              historical_data: Dict[str, Any] = None) -> int:
        """
        Calculate trust score based on hard signals.
        Returns 0-100 score.
        """
        score = 0
        
        # Hard signals (high weight)
        if attestation.secure_boot:
            score += 20  # Secure boot enabled
        
        if attestation.tpm_available:
            score += 15  # TPM available
        
        if attestation.key_isolated:
            score += 20  # Key in secure storage
        
        # Posture score contribution
        score += int(attestation.posture_score * 0.25)  # Up to 25 points
        
        # Historical signals (if available)
        if historical_data:
            # Known enrollment history
            if historical_data.get('enrollment_verified'):
                score += 10
            
            # Consistent behavior
            if historical_data.get('behavior_consistent'):
                score += 5
            
            # No prior incidents
            if historical_data.get('no_incidents'):
                score += 5
        
        return min(100, score)
    
    def determine_trust_state(self, trust_score: int) -> TrustState:
        """Determine trust state from score"""
        if trust_score >= self.trust_thresholds[TrustState.TRUSTED]:
            return TrustState.TRUSTED
        elif trust_score >= self.trust_thresholds[TrustState.DEGRADED]:
            return TrustState.DEGRADED
        else:
            return TrustState.UNKNOWN
    
    def register_identity(self, agent_id: str, hostname: str, os_type: str,
                          cert_fingerprint: str, attestation: AttestationData) -> WorkloadIdentity:
        """Register or update workload identity"""
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=self.cert_validity_hours)
        
        # Calculate trust
        trust_score = self.calculate_trust_score(attestation)
        trust_state = self.determine_trust_state(trust_score)
        
        identity = WorkloadIdentity(
            spiffe_id=self.generate_spiffe_id(agent_id),
            agent_id=agent_id,
            hostname=hostname,
            os_type=os_type,
            cert_fingerprint=cert_fingerprint,
            issued_at=now.isoformat(),
            expires_at=expires.isoformat(),
            attestation=asdict(attestation),
            trust_state=trust_state,
            trust_score=trust_score
        )
        
        self.identities[agent_id] = identity
        
        logger.info(f"Identity registered: {agent_id} | Trust: {trust_state.value} ({trust_score})")
        
        return identity
    
    def get_identity(self, agent_id: str) -> Optional[WorkloadIdentity]:
        """Get workload identity"""
        return self.identities.get(agent_id)
    
    def update_trust_state(self, agent_id: str, new_state: TrustState, 
                           reason: str = None) -> bool:
        """Update trust state (e.g., on anomaly detection)"""
        identity = self.identities.get(agent_id)
        if not identity:
            return False
        
        old_state = identity.trust_state
        identity.trust_state = new_state
        
        logger.warning(f"Trust state changed: {agent_id} | {old_state.value} -> {new_state.value} | Reason: {reason}")
        
        return True
    
    def quarantine_agent(self, agent_id: str, reason: str) -> bool:
        """Quarantine an agent (no trust)"""
        return self.update_trust_state(agent_id, TrustState.QUARANTINED, reason)
    
    def get_all_identities(self) -> List[Dict[str, Any]]:
        """Get all registered identities"""
        return [
            {
                "agent_id": i.agent_id,
                "spiffe_id": i.spiffe_id,
                "hostname": i.hostname,
                "trust_state": i.trust_state.value,
                "trust_score": i.trust_score,
                "expires_at": i.expires_at
            }
            for i in self.identities.values()
        ]
    
    def is_action_allowed(self, agent_id: str, action_type: str) -> Tuple[bool, str]:
        """
        Check if an action is allowed based on trust state.
        
        Action types:
        - observe: Read-only queries
        - collect: Acquire artifacts
        - contain: Isolate, block
        - remediate: Kill, delete, patch
        - credential: Rotate/revoke tokens
        """
        identity = self.identities.get(agent_id)
        
        if not identity:
            return False, "Unknown identity"
        
        trust_state = identity.trust_state
        
        # Action permissions by trust state
        permissions = {
            TrustState.TRUSTED: ['observe', 'collect', 'contain', 'remediate', 'credential'],
            TrustState.DEGRADED: ['observe', 'collect', 'contain'],
            TrustState.UNKNOWN: ['observe'],
            TrustState.QUARANTINED: []
        }
        
        allowed = action_type in permissions.get(trust_state, [])
        
        if not allowed:
            return False, f"Action '{action_type}' not allowed for trust state '{trust_state.value}'"
        
        return True, "Allowed"


# Global singleton
identity_service = IdentityService()
