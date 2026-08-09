"""
Honey Tokens & Credentials - Deception Technology
Detects attackers by monitoring access to fake credentials
"""
import uuid
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class HoneyTokenType(str, Enum):
    API_KEY = "api_key"
    PASSWORD = "password"
    AWS_KEY = "aws_key"
    DATABASE_CRED = "database_cred"
    SSH_KEY = "ssh_key"
    JWT_TOKEN = "jwt_token"
    OAUTH_TOKEN = "oauth_token"
    WEBHOOK_URL = "webhook_url"

@dataclass
class HoneyToken:
    id: str
    name: str
    token_type: HoneyTokenType
    token_value: str
    token_hash: str  # SHA256 hash for secure storage
    description: str
    location: str  # Where it's planted (e.g., ".env file", "config.json")
    created_at: str
    created_by: str
    access_count: int = 0
    last_accessed: Optional[str] = None
    is_active: bool = True
    alerts_enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class HoneyTokenAccess:
    id: str
    token_id: str
    token_name: str
    accessed_at: str
    source_ip: str
    user_agent: Optional[str]
    request_path: Optional[str]
    request_method: Optional[str]
    headers: Dict[str, str]
    severity: str = "critical"
    acknowledged: bool = False

class HoneyTokenManager:
    def __init__(self):
        self.db = None
        self.tokens: Dict[str, HoneyToken] = {}
        self.accesses: List[HoneyTokenAccess] = []
        self._init_sample_tokens()
    
    def set_database(self, db):
        self.db = db
    
    def _init_sample_tokens(self):
        """Create some sample honey tokens"""
        samples = [
            {
                "name": "AWS Production Key",
                "token_type": HoneyTokenType.AWS_KEY,
                "description": "Fake AWS access key to detect credential theft",
                "location": "~/.aws/credentials"
            },
            {
                "name": "Database Admin Password",
                "token_type": HoneyTokenType.DATABASE_CRED,
                "description": "Fake database credentials in config file",
                "location": "/etc/app/database.conf"
            },
            {
                "name": "API Master Key",
                "token_type": HoneyTokenType.API_KEY,
                "description": "Fake API key that should never be used",
                "location": ".env.production"
            },
            {
                "name": "Service Account JWT",
                "token_type": HoneyTokenType.JWT_TOKEN,
                "description": "Fake service account token",
                "location": "/var/run/secrets/token"
            }
        ]
        
        for sample in samples:
            token = self._generate_token(
                sample["name"],
                HoneyTokenType(sample["token_type"]),
                sample["description"],
                sample["location"],
                "system"
            )
            self.tokens[token.id] = token
    
    def _generate_token(
        self,
        name: str,
        token_type: HoneyTokenType,
        description: str,
        location: str,
        created_by: str
    ) -> HoneyToken:
        """Generate a realistic-looking honey token"""
        token_id = f"ht_{uuid.uuid4().hex[:12]}"
        
        # Generate realistic token values based on type
        if token_type == HoneyTokenType.AWS_KEY:
            token_value = f"AKIA{secrets.token_hex(8).upper()}"
        elif token_type == HoneyTokenType.API_KEY:
            token_value = f"sk-{secrets.token_urlsafe(32)}"
        elif token_type == HoneyTokenType.PASSWORD:
            token_value = secrets.token_urlsafe(16)
        elif token_type == HoneyTokenType.DATABASE_CRED:
            token_value = f"postgres://admin:{secrets.token_urlsafe(12)}@db.internal:5432/prod"
        elif token_type == HoneyTokenType.SSH_KEY:
            token_value = f"ssh-rsa AAAA{secrets.token_urlsafe(40)} honey@token"
        elif token_type == HoneyTokenType.JWT_TOKEN:
            token_value = f"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.{secrets.token_urlsafe(32)}.{secrets.token_urlsafe(22)}"
        elif token_type == HoneyTokenType.OAUTH_TOKEN:
            token_value = f"ya29.{secrets.token_urlsafe(40)}"
        elif token_type == HoneyTokenType.WEBHOOK_URL:
            token_value = f"https://hooks.internal.io/webhook/{secrets.token_urlsafe(24)}"
        else:
            token_value = secrets.token_urlsafe(32)
        
        token_hash = hashlib.sha256(token_value.encode()).hexdigest()
        
        return HoneyToken(
            id=token_id,
            name=name,
            token_type=token_type,
            token_value=token_value,
            token_hash=token_hash,
            description=description,
            location=location,
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by=created_by
        )
    
    def create_token(
        self,
        name: str,
        token_type: str,
        description: str,
        location: str,
        created_by: str,
        custom_value: Optional[str] = None
    ) -> Dict:
        """Create a new honey token"""
        token = self._generate_token(
            name,
            HoneyTokenType(token_type),
            description,
            location,
            created_by
        )
        
        if custom_value:
            token.token_value = custom_value
            token.token_hash = hashlib.sha256(custom_value.encode()).hexdigest()
        
        self.tokens[token.id] = token
        
        # Store in database if available
        if self.db is not None:
            import asyncio
            asyncio.create_task(self._save_token_to_db(token))
        
        return asdict(token)
    
    async def _save_token_to_db(self, token: HoneyToken):
        """Save token to database"""
        if self.db is not None:
            token_dict = asdict(token)
            token_dict["token_type"] = token.token_type.value
            await self.db.honey_tokens.update_one(
                {"id": token.id},
                {"$set": token_dict},
                upsert=True
            )
    
    def get_tokens(self, include_values: bool = False) -> List[Dict]:
        """Get all honey tokens"""
        result = []
        for token in self.tokens.values():
            token_dict = asdict(token)
            token_dict["token_type"] = token.token_type.value
            if not include_values:
                # Mask the actual token value
                token_dict["token_value"] = token_dict["token_value"][:8] + "..." + token_dict["token_value"][-4:]
            result.append(token_dict)
        return result
    
    def get_token(self, token_id: str) -> Optional[Dict]:
        """Get a specific token"""
        token = self.tokens.get(token_id)
        if token:
            token_dict = asdict(token)
            token_dict["token_type"] = token.token_type.value
            return token_dict
        return None
    
    def check_token(self, value: str) -> Optional[HoneyTokenAccess]:
        """Check if a value matches any honey token (used for detection)"""
        value_hash = hashlib.sha256(value.encode()).hexdigest()
        
        for token in self.tokens.values():
            if token.token_hash == value_hash and token.is_active:
                return token
        return None
    
    def record_access(
        self,
        token_id: str,
        source_ip: str,
        user_agent: Optional[str] = None,
        request_path: Optional[str] = None,
        request_method: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> HoneyTokenAccess:
        """Record an access to a honey token (CRITICAL ALERT)"""
        token = self.tokens.get(token_id)
        if not token:
            raise ValueError(f"Token {token_id} not found")
        
        # Update token access count
        token.access_count += 1
        token.last_accessed = datetime.now(timezone.utc).isoformat()
        
        # Create access record
        access = HoneyTokenAccess(
            id=f"hta_{uuid.uuid4().hex[:12]}",
            token_id=token_id,
            token_name=token.name,
            accessed_at=datetime.now(timezone.utc).isoformat(),
            source_ip=source_ip,
            user_agent=user_agent,
            request_path=request_path,
            request_method=request_method,
            headers=headers or {},
            severity="critical"
        )
        
        self.accesses.append(access)
        
        # Keep only last 1000 accesses
        if len(self.accesses) > 1000:
            self.accesses = self.accesses[-1000:]
        
        logger.critical(f"HONEY TOKEN ACCESSED: {token.name} from {source_ip}")
        
        return access
    
    def get_accesses(self, limit: int = 50, token_id: Optional[str] = None) -> List[Dict]:
        """Get honey token access records"""
        accesses = self.accesses
        
        if token_id:
            accesses = [a for a in accesses if a.token_id == token_id]
        
        # Most recent first
        accesses = sorted(accesses, key=lambda x: x.accessed_at, reverse=True)[:limit]
        return [asdict(a) for a in accesses]
    
    def delete_token(self, token_id: str) -> bool:
        """Delete a honey token"""
        if token_id in self.tokens:
            del self.tokens[token_id]
            return True
        return False
    
    def toggle_token(self, token_id: str) -> Optional[Dict]:
        """Toggle token active status"""
        token = self.tokens.get(token_id)
        if token:
            token.is_active = not token.is_active
            return asdict(token)
        return None
    
    def get_stats(self) -> Dict:
        """Get honey token statistics"""
        total = len(self.tokens)
        active = sum(1 for t in self.tokens.values() if t.is_active)
        total_accesses = len(self.accesses)
        unacknowledged = sum(1 for a in self.accesses if not a.acknowledged)
        
        by_type = {}
        for token in self.tokens.values():
            t = token.token_type.value
            by_type[t] = by_type.get(t, 0) + 1
        
        recent_accesses = [
            asdict(a) for a in sorted(
                self.accesses, key=lambda x: x.accessed_at, reverse=True
            )[:5]
        ]
        
        return {
            "total_tokens": total,
            "active_tokens": active,
            "inactive_tokens": total - active,
            "total_accesses": total_accesses,
            "unacknowledged_alerts": unacknowledged,
            "by_type": by_type,
            "recent_accesses": recent_accesses,
            "available_types": [t.value for t in HoneyTokenType]
        }


# Global instance
honey_token_manager = HoneyTokenManager()
