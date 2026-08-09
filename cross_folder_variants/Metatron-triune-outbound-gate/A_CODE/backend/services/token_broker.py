"""
Token Broker / Secrets Vault
============================
Secure token issuance with scoped capability tokens.
Never exposes refresh tokens or secrets to agents/LLMs.
"""

import os
import json
import hashlib
import hmac
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import base64

logger = logging.getLogger(__name__)


@dataclass
class CapabilityToken:
    """Scoped capability token for tool access"""
    token_id: str
    token_type: str             # "capability" / "access"
    
    # Binding
    principal: str              # Who can use this token
    principal_identity: str     # SPIFFE ID or cert fingerprint
    audience: str               # Tool gateway
    
    # Scope
    action: str
    targets: List[str]
    tool_id: Optional[str]
    
    # Limits
    expires_at: str
    max_uses: int
    uses_remaining: int
    constraints: Dict[str, Any]
    
    # Signature
    signature: str
    
    # Metadata
    issued_at: str
    issuer: str
    nonce: str
    
    # Governance
    governance_decision_id: Optional[str]
    governance_queue_id: Optional[str]
    governance_action_type: Optional[str]


@dataclass
class SecretEntry:
    """Encrypted secret storage"""
    secret_id: str
    secret_type: str            # "api_key" / "oauth_refresh" / "password" / "private_key"
    owner: str                  # Service or user that owns this secret
    
    # Encrypted value (only broker can decrypt)
    encrypted_value: str
    
    # Metadata (not encrypted)
    created_at: str
    expires_at: Optional[str]
    rotation_schedule: Optional[str]
    last_accessed: Optional[str]
    access_count: int
    
    # Access control
    allowed_principals: List[str]
    allowed_scopes: List[str]


class TokenBroker:
    """
    Secure token broker / secrets vault.
    
    Features:
    - Never exposes raw secrets to agents/LLMs
    - Issues short-lived, scoped capability tokens
    - Automatic revocation on trust degradation
    - Audit logging of all secret access
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
        
        # Master encryption key (in production, use HSM/KMS)
        self.master_key = os.environ.get('BROKER_MASTER_KEY', secrets.token_hex(32))
        self.signing_key = os.environ.get('BROKER_SIGNING_KEY', secrets.token_hex(32))
        
        # Token storage
        self.active_tokens: Dict[str, CapabilityToken] = {}
        self.revoked_tokens: set = set()
        
        # Secret storage (in production, use proper vault)
        self.secrets: Dict[str, SecretEntry] = {}
        
        # Token usage tracking
        self.token_uses: Dict[str, int] = defaultdict(int)
        
        # Access audit log
        self.access_log: List[Dict] = []
        
        logger.info("Token Broker / Secrets Vault initialized")
        # Administrative audit log for token issuance/revocation actions
        self.token_admin_audit_log: List[Dict] = []

    
    def _encrypt(self, plaintext: str) -> str:
        """Simple encryption (in production, use proper crypto)"""
        # XOR with key-derived pad (demo only - use AES-GCM in production)
        key_bytes = hashlib.sha256(self.master_key.encode()).digest()
        plaintext_bytes = plaintext.encode()
        encrypted = bytes(p ^ k for p, k in zip(plaintext_bytes, key_bytes * (len(plaintext_bytes) // len(key_bytes) + 1)))
        return base64.b64encode(encrypted).decode()
    
    def _decrypt(self, ciphertext: str) -> str:
        """Simple decryption"""
        key_bytes = hashlib.sha256(self.master_key.encode()).digest()
        encrypted = base64.b64decode(ciphertext)
        decrypted = bytes(e ^ k for e, k in zip(encrypted, key_bytes * (len(encrypted) // len(key_bytes) + 1)))
        return decrypted.decode()
    
    def _sign_token(self, token_data: Dict) -> str:
        """Sign token data"""
        payload = json.dumps(token_data, sort_keys=True)
        return hmac.new(self.signing_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    
    def _verify_token_signature(self, token: CapabilityToken) -> bool:
        """Verify token signature"""
        token_data = {
            "token_id": token.token_id,
            "principal": token.principal,
            "action": token.action,
            "targets": token.targets,
            "expires_at": token.expires_at,
            "nonce": token.nonce
        }
        expected = self._sign_token(token_data)
        return hmac.compare_digest(expected, token.signature)
    
    # =========================================================================
    # SECRET MANAGEMENT
    # =========================================================================
    
    def store_secret(self, secret_id: str, secret_type: str, value: str,
                     owner: str, allowed_principals: List[str] = None,
                     allowed_scopes: List[str] = None,
                     expires_at: str = None) -> bool:
        """Store a secret securely"""
        
        entry = SecretEntry(
            secret_id=secret_id,
            secret_type=secret_type,
            owner=owner,
            encrypted_value=self._encrypt(value),
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=expires_at,
            rotation_schedule=None,
            last_accessed=None,
            access_count=0,
            allowed_principals=allowed_principals or [owner],
            allowed_scopes=allowed_scopes or ["*"]
        )
        
        self.secrets[secret_id] = entry
        
        logger.info(f"SECRET: Stored {secret_type} '{secret_id}' for {owner}")
        
        return True
    
    def get_secret(self, secret_id: str, principal: str, 
                   scope: str = "*") -> Tuple[Optional[str], str]:
        """
        Get a secret (internal use only).
        Returns (value, message) tuple.
        """
        if secret_id not in self.secrets:
            return None, "Secret not found"
        
        entry = self.secrets[secret_id]
        
        # Check principal permission
        if principal not in entry.allowed_principals and "*" not in entry.allowed_principals:
            self._log_access(secret_id, principal, "denied", "Principal not allowed")
            return None, "Access denied"
        
        # Check scope
        if scope not in entry.allowed_scopes and "*" not in entry.allowed_scopes:
            self._log_access(secret_id, principal, "denied", "Scope not allowed")
            return None, "Scope not allowed"
        
        # Check expiry
        if entry.expires_at:
            exp = datetime.fromisoformat(entry.expires_at.replace('Z', '+00:00'))
            if datetime.now(timezone.utc) > exp:
                self._log_access(secret_id, principal, "denied", "Secret expired")
                return None, "Secret expired"
        
        # Update access tracking
        entry.last_accessed = datetime.now(timezone.utc).isoformat()
        entry.access_count += 1
        
        self._log_access(secret_id, principal, "granted", "Success")
        
        return self._decrypt(entry.encrypted_value), "Success"
    
    def _log_access(self, secret_id: str, principal: str, 
                    result: str, message: str):
        """Log secret access"""
        self.access_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "secret_id": secret_id,
            "principal": principal,
            "result": result,
            "message": message
        })
    
    def rotate_secret(self, secret_id: str, new_value: str) -> bool:
        """Rotate a secret"""
        if secret_id not in self.secrets:
            return False
        
        self.secrets[secret_id].encrypted_value = self._encrypt(new_value)
        self.secrets[secret_id].created_at = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"SECRET: Rotated '{secret_id}'")
        
        return True
    
    def revoke_secret(self, secret_id: str) -> bool:
        """Revoke a secret"""
        if secret_id in self.secrets:
            del self.secrets[secret_id]
            logger.info(f"SECRET: Revoked '{secret_id}'")
            return True
        return False
    
    # =========================================================================
    # CAPABILITY TOKEN MANAGEMENT
    # =========================================================================
    
    def issue_token(self, principal: str, principal_identity: str,
                    action: str, targets: List[str],
                    tool_id: str = None, ttl_seconds: int = 300,
                    max_uses: int = 1, constraints: Dict = None,
                    governance_context: Dict = None,
                    polyphonic_token_context: Dict = None,
                    future_notation_token_ref: str = None,
                    issued_by: str = "token_broker") -> CapabilityToken:
        """
        Issue a scoped capability token.
        
        Args:
            principal: Who is requesting
            principal_identity: SPIFFE ID or cert fingerprint (for binding)
            action: What action is allowed
            targets: What targets are allowed
            tool_id: Optional specific tool
            ttl_seconds: Token lifetime
            max_uses: Maximum uses
            constraints: Additional constraints
            governance_context: Required governance approval context
            polyphonic_token_context: Polyphonic token context for advanced scenarios
            future_notation_token_ref: Reference to future notation token
            issued_by: Who issued this token
        
        Returns:
            CapabilityToken
        """
        # Require governance approval for all token issuance
        if not governance_context or not governance_context.get("approved", False):
            raise PermissionError("Token issuance requires approved governance context")
        
        import uuid
        
        token_id = f"tok-{uuid.uuid4().hex[:16]}"
        nonce = secrets.token_hex(8)
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=ttl_seconds)
        
        # Build token data for signing
        token_data = {
            "token_id": token_id,
            "principal": principal,
            "action": action,
            "targets": targets,
            "expires_at": expires.isoformat(),
            "nonce": nonce
        }
        
        signature = self._sign_token(token_data)
        
        token = CapabilityToken(
            token_id=token_id,
            token_type="capability",
            principal=principal,
            principal_identity=principal_identity,
            audience="tool_gateway",
            action=action,
            targets=targets,
            tool_id=tool_id,
            expires_at=expires.isoformat(),
            max_uses=max_uses,
            uses_remaining=max_uses,
            constraints=constraints or {},
            signature=signature,
            issued_at=now.isoformat(),
            issuer=issued_by,
            nonce=nonce,
            governance_decision_id=governance_context.get("decision_id"),
            governance_queue_id=governance_context.get("queue_id"),
            governance_action_type=governance_context.get("action_type")
        )
        
        self.active_tokens[token_id] = token
        
        # Audit log
        self.token_admin_audit_log.append({
            "action": "issue",
            "token_id": token_id,
            "principal": principal,
            "action": action,
            "targets": targets,
            "governance_context": governance_context,
            "issued_by": issued_by,
            "timestamp": now.isoformat()
        })
        
        logger.info(f"TOKEN: Issued {token_id} for {principal} | Action: {action} | TTL: {ttl_seconds}s")
        
        return token
    
    def validate_token(self, token_id: str, principal: str,
                       principal_identity: str, action: str,
                       target: str) -> Tuple[bool, str]:
        """
        Validate a capability token.
        
        Returns (valid, message) tuple.
        """
        # Check if revoked
        if token_id in self.revoked_tokens:
            return False, "Token revoked"
        
        # Check if exists
        if token_id not in self.active_tokens:
            return False, "Token not found"
        
        token = self.active_tokens[token_id]
        
        # Verify signature
        if not self._verify_token_signature(token):
            return False, "Invalid token signature"
        
        # Check principal binding
        if token.principal != principal:
            return False, "Token not bound to this principal"
        
        if token.principal_identity != principal_identity:
            return False, "Token identity mismatch"
        
        # Check expiry
        exp = datetime.fromisoformat(token.expires_at.replace('Z', '+00:00'))
        if datetime.now(timezone.utc) > exp:
            del self.active_tokens[token_id]
            return False, "Token expired"
        
        # Check action
        if token.action != action:
            return False, f"Token not valid for action '{action}'"
        
        # Check target
        if target not in token.targets and "*" not in token.targets:
            return False, f"Token not valid for target '{target}'"
        
        # Check uses
        if token.uses_remaining <= 0:
            del self.active_tokens[token_id]
            return False, "Token usage exhausted"
        
        # Decrement uses
        token.uses_remaining -= 1
        
        if token.uses_remaining <= 0:
            del self.active_tokens[token_id]
        
        logger.debug(f"TOKEN: Validated {token_id} | Remaining uses: {token.uses_remaining}")
        
        return True, "Token valid"
    
    def revoke_token(
        self,
        token_id: str,
        governance_context: Dict = None,
        revoked_by: str = "token_broker",
    ) -> bool:
        """Revoke a token"""
        now = datetime.now(timezone.utc)

        if token_id in self.active_tokens:
            del self.active_tokens[token_id]
        
        self.revoked_tokens.add(token_id)

        self.token_admin_audit_log.append({
            "action": "revoke",
            "token_id": token_id,
            "governance_context": governance_context,
            "revoked_by": revoked_by,
            "timestamp": now.isoformat(),
        })
        
        logger.info(f"TOKEN: Revoked {token_id}")
        
        return True
    
    def revoke_tokens_for_principal(
        self,
        principal: str,
        governance_context: Dict = None,
        revoked_by: str = "token_broker",
    ) -> int:
        """Revoke all tokens for a principal (e.g., on trust degradation)"""
        count = 0
        
        tokens_to_revoke = [
            tid for tid, tok in self.active_tokens.items()
            if tok.principal == principal
        ]
        
        for token_id in tokens_to_revoke:
            self.revoke_token(
                token_id,
                governance_context=governance_context,
                revoked_by=revoked_by,
            )
            count += 1
        
        logger.warning(f"TOKEN: Revoked {count} tokens for principal {principal}")
        
        return count

    def apply_ai_trust_degradation(
        self,
        session_id: str,
        agenticity_score: float = 0.0,
        agenticity_classification: str = "LOW",
        cbr: float = 0.0,
        tbcr: float = 0.0,
        logic_budget_force_trap: bool = False,
    ) -> Dict:
        """
        Degrade trust and revoke tokens for an AI session based on formal metrics.
        Called when agenticity classification is HIGH/VERY_HIGH or logic-budget
        exhaustion forces a TRAP_SINK.  CBR and TBCR are used to constrain future
        token TTLs (the higher the compute burn, the shorter the allowed lifetime).
        Returns a summary of actions taken.
        """
        principal = f"ai_session:{session_id}"
        actions_taken = []

        # Always revoke on forced trap — the session is adversarial.
        if logic_budget_force_trap or agenticity_classification in ("HIGH", "VERY_HIGH"):
            revoked = self.revoke_tokens_for_principal(
                principal=principal,
                governance_context={
                    "approved": True,
                    "decision_id": f"ai-trust-degrade-{session_id}",
                    "action_type": "ai_adversary_token_revocation",
                    "agenticity_score": agenticity_score,
                    "agenticity_classification": agenticity_classification,
                    "logic_budget_force_trap": logic_budget_force_trap,
                },
                revoked_by="ai_defense_engine",
            )
            if revoked > 0:
                actions_taken.append(f"revoked:{revoked}_tokens")
            logger.warning(
                f"TOKEN: AI trust degradation for session {session_id} "
                f"| classification={agenticity_classification} "
                f"| force_trap={logic_budget_force_trap} "
                f"| revoked={revoked} tokens"
            )

        # Compute an advisory TTL cap for future tokens (seconds).
        # At CBR=1.0 (budget exhausted) → 30 s max; at CBR=0 → 300 s default.
        max_cbr = max(cbr, tbcr, 0.01)
        advisory_ttl_cap = max(30, int(300 * (1.0 - min(1.0, max_cbr))))
        actions_taken.append(f"advisory_ttl_cap:{advisory_ttl_cap}s")

        return {
            "session_id": session_id,
            "principal": principal,
            "agenticity_classification": agenticity_classification,
            "logic_budget_force_trap": logic_budget_force_trap,
            "advisory_ttl_cap_seconds": advisory_ttl_cap,
            "actions_taken": actions_taken,
        }
    
    def get_active_tokens(self, principal: str = None) -> List[Dict]:
        """Get active tokens (optionally filtered by principal)"""
        tokens = []
        
        for token in self.active_tokens.values():
            if principal and token.principal != principal:
                continue
            
            # Don't expose signature
            token_dict = asdict(token)
            token_dict['signature'] = '[REDACTED]'
            tokens.append(token_dict)
        
        return tokens
    
    def get_broker_status(self) -> Dict:
        """Get broker status"""
        return {
            "active_tokens": len(self.active_tokens),
            "revoked_tokens": len(self.revoked_tokens),
            "stored_secrets": len(self.secrets),
            "access_log_size": len(self.access_log)
        }


# Global singleton
token_broker = TokenBroker()
