"""
Multi-Tenant Architecture Service
=================================
Enterprise multi-tenant support for Seraph AI.
Provides tenant isolation, resource management, and cross-tenant analytics.
"""

import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class TenantTier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TRIAL = "trial"
    PENDING = "pending"


@dataclass
class TenantQuota:
    """Resource quotas for a tenant"""
    max_agents: int = 5
    max_users: int = 10
    max_playbooks: int = 20
    max_honeypots: int = 5
    max_api_calls_per_day: int = 10000
    max_storage_gb: float = 10.0
    max_retention_days: int = 30
    features: List[str] = field(default_factory=list)


@dataclass
class TenantUsage:
    """Current resource usage for a tenant"""
    agents: int = 0
    users: int = 0
    playbooks: int = 0
    honeypots: int = 0
    api_calls_today: int = 0
    storage_used_gb: float = 0.0
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Tenant:
    """Tenant entity"""
    id: str
    name: str
    slug: str  # URL-friendly identifier
    tier: TenantTier
    status: TenantStatus
    quota: TenantQuota
    usage: TenantUsage
    settings: Dict[str, Any]
    contact_email: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    trial_ends_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# Tier quotas configuration
TIER_QUOTAS = {
    TenantTier.FREE: TenantQuota(
        max_agents=3,
        max_users=5,
        max_playbooks=5,
        max_honeypots=2,
        max_api_calls_per_day=1000,
        max_storage_gb=1.0,
        max_retention_days=7,
        features=["basic_dashboard", "threat_detection", "alerts"]
    ),
    TenantTier.STARTER: TenantQuota(
        max_agents=10,
        max_users=25,
        max_playbooks=20,
        max_honeypots=10,
        max_api_calls_per_day=10000,
        max_storage_gb=10.0,
        max_retention_days=30,
        features=["basic_dashboard", "threat_detection", "alerts", "soar_basic", "reporting", "api_access"]
    ),
    TenantTier.PROFESSIONAL: TenantQuota(
        max_agents=50,
        max_users=100,
        max_playbooks=100,
        max_honeypots=50,
        max_api_calls_per_day=100000,
        max_storage_gb=100.0,
        max_retention_days=90,
        features=["basic_dashboard", "threat_detection", "alerts", "soar_full", "reporting", "api_access",
                 "threat_hunting", "ai_analysis", "vns", "custom_playbooks", "integrations"]
    ),
    TenantTier.ENTERPRISE: TenantQuota(
        max_agents=-1,  # Unlimited
        max_users=-1,
        max_playbooks=-1,
        max_honeypots=-1,
        max_api_calls_per_day=-1,
        max_storage_gb=-1,
        max_retention_days=365,
        features=["all"]
    )
}


class MultiTenantService:
    """
    Multi-tenant management service.
    
    Features:
    - Tenant CRUD operations
    - Resource quota management
    - Usage tracking
    - Cross-tenant isolation
    - Tenant-specific configuration
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
        
        # In-memory tenant storage (in production, use database)
        self.tenants: Dict[str, Tenant] = {}
        
        # User to tenant mapping
        self.user_tenants: Dict[str, str] = {}
        
        # API key to tenant mapping
        self.api_keys: Dict[str, str] = {}
        
        # Initialize default tenant
        self._init_default_tenant()
        
        logger.info("Multi-Tenant Service initialized")
    
    def _init_default_tenant(self):
        """Initialize the default tenant"""
        default_tenant = Tenant(
            id="tenant_default",
            name="Default Organization",
            slug="default",
            tier=TenantTier.ENTERPRISE,
            status=TenantStatus.ACTIVE,
            quota=TIER_QUOTAS[TenantTier.ENTERPRISE],
            usage=TenantUsage(),
            settings={
                "branding": {
                    "logo_url": None,
                    "primary_color": "#3B82F6",
                    "dark_mode": True
                },
                "security": {
                    "mfa_required": False,
                    "session_timeout_minutes": 480,
                    "ip_whitelist": []
                },
                "notifications": {
                    "email_enabled": True,
                    "slack_enabled": True,
                    "webhook_url": None
                }
            },
            contact_email="admin@seraph.local"
        )
        
        self.tenants[default_tenant.id] = default_tenant
    
    def create_tenant(self, name: str, contact_email: str, tier: TenantTier = TenantTier.STARTER,
                      trial_days: int = 14) -> Tenant:
        """Create a new tenant"""
        tenant_id = f"tenant_{uuid.uuid4().hex[:12]}"
        slug = name.lower().replace(" ", "-").replace("_", "-")[:32]
        
        # Ensure unique slug
        existing_slugs = {t.slug for t in self.tenants.values()}
        if slug in existing_slugs:
            slug = f"{slug}-{uuid.uuid4().hex[:4]}"
        
        trial_ends = None
        status = TenantStatus.ACTIVE
        if tier in [TenantTier.FREE, TenantTier.STARTER]:
            trial_ends = (datetime.now(timezone.utc) + timedelta(days=trial_days)).isoformat()
            status = TenantStatus.TRIAL
        
        tenant = Tenant(
            id=tenant_id,
            name=name,
            slug=slug,
            tier=tier,
            status=status,
            quota=TIER_QUOTAS[tier],
            usage=TenantUsage(),
            settings={
                "branding": {
                    "logo_url": None,
                    "primary_color": "#3B82F6",
                    "dark_mode": True
                },
                "security": {
                    "mfa_required": tier in [TenantTier.PROFESSIONAL, TenantTier.ENTERPRISE],
                    "session_timeout_minutes": 480,
                    "ip_whitelist": []
                },
                "notifications": {
                    "email_enabled": True,
                    "slack_enabled": tier != TenantTier.FREE,
                    "webhook_url": None
                }
            },
            contact_email=contact_email,
            trial_ends_at=trial_ends
        )
        
        self.tenants[tenant_id] = tenant
        
        logger.info(f"Created tenant: {tenant.name} ({tenant.id}) - Tier: {tier.value}")
        
        return tenant
    
    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get a tenant by ID"""
        return self.tenants.get(tenant_id)
    
    def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        """Get a tenant by slug"""
        for tenant in self.tenants.values():
            if tenant.slug == slug:
                return tenant
        return None
    
    def list_tenants(self, status: Optional[TenantStatus] = None, 
                     tier: Optional[TenantTier] = None) -> List[Tenant]:
        """List all tenants with optional filters"""
        tenants = list(self.tenants.values())
        
        if status:
            tenants = [t for t in tenants if t.status == status]
        
        if tier:
            tenants = [t for t in tenants if t.tier == tier]
        
        return tenants
    
    def update_tenant(self, tenant_id: str, updates: Dict[str, Any]) -> Optional[Tenant]:
        """Update a tenant"""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            return None
        
        if "name" in updates:
            tenant.name = updates["name"]
        if "tier" in updates:
            tenant.tier = TenantTier(updates["tier"])
            tenant.quota = TIER_QUOTAS[tenant.tier]
        if "status" in updates:
            tenant.status = TenantStatus(updates["status"])
        if "settings" in updates:
            tenant.settings.update(updates["settings"])
        if "contact_email" in updates:
            tenant.contact_email = updates["contact_email"]
        
        tenant.updated_at = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"Updated tenant: {tenant.name} ({tenant.id})")
        
        return tenant
    
    def delete_tenant(self, tenant_id: str) -> bool:
        """Delete a tenant (soft delete - set status to suspended)"""
        tenant = self.tenants.get(tenant_id)
        if not tenant or tenant.id == "tenant_default":
            return False
        
        tenant.status = TenantStatus.SUSPENDED
        tenant.updated_at = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"Suspended tenant: {tenant.name} ({tenant.id})")
        
        return True
    
    def assign_user_to_tenant(self, user_id: str, tenant_id: str) -> bool:
        """Assign a user to a tenant"""
        if tenant_id not in self.tenants:
            return False
        
        tenant = self.tenants[tenant_id]
        
        # Check quota
        if tenant.quota.max_users != -1 and tenant.usage.users >= tenant.quota.max_users:
            logger.warning(f"User quota exceeded for tenant {tenant_id}")
            return False
        
        self.user_tenants[user_id] = tenant_id
        tenant.usage.users += 1
        tenant.usage.last_updated = datetime.now(timezone.utc).isoformat()
        
        return True
    
    def get_user_tenant(self, user_id: str) -> Optional[str]:
        """Get the tenant ID for a user"""
        return self.user_tenants.get(user_id, "tenant_default")
    
    def check_quota(self, tenant_id: str, resource: str, amount: int = 1) -> bool:
        """Check if a tenant has quota for a resource"""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            return False
        
        if tenant.status != TenantStatus.ACTIVE and tenant.status != TenantStatus.TRIAL:
            return False
        
        quota_map = {
            "agents": (tenant.quota.max_agents, tenant.usage.agents),
            "users": (tenant.quota.max_users, tenant.usage.users),
            "playbooks": (tenant.quota.max_playbooks, tenant.usage.playbooks),
            "honeypots": (tenant.quota.max_honeypots, tenant.usage.honeypots),
            "api_calls": (tenant.quota.max_api_calls_per_day, tenant.usage.api_calls_today)
        }
        
        if resource not in quota_map:
            return True
        
        max_quota, current_usage = quota_map[resource]
        
        if max_quota == -1:  # Unlimited
            return True
        
        return current_usage + amount <= max_quota
    
    def increment_usage(self, tenant_id: str, resource: str, amount: int = 1) -> bool:
        """Increment resource usage for a tenant"""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            return False
        
        if not self.check_quota(tenant_id, resource, amount):
            return False
        
        if resource == "agents":
            tenant.usage.agents += amount
        elif resource == "users":
            tenant.usage.users += amount
        elif resource == "playbooks":
            tenant.usage.playbooks += amount
        elif resource == "honeypots":
            tenant.usage.honeypots += amount
        elif resource == "api_calls":
            tenant.usage.api_calls_today += amount
        
        tenant.usage.last_updated = datetime.now(timezone.utc).isoformat()
        
        return True
    
    def reset_daily_usage(self):
        """Reset daily usage counters (call at midnight)"""
        for tenant in self.tenants.values():
            tenant.usage.api_calls_today = 0
            tenant.usage.last_updated = datetime.now(timezone.utc).isoformat()
        
        logger.info("Reset daily usage counters for all tenants")
    
    def has_feature(self, tenant_id: str, feature: str) -> bool:
        """Check if a tenant has access to a feature"""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            return False
        
        if tenant.status == TenantStatus.SUSPENDED:
            return False
        
        if "all" in tenant.quota.features:
            return True
        
        return feature in tenant.quota.features
    
    def generate_api_key(self, tenant_id: str) -> Optional[str]:
        """Generate an API key for a tenant"""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            return None
        
        api_key = f"sk_{tenant.slug}_{uuid.uuid4().hex}"
        self.api_keys[api_key] = tenant_id
        
        return api_key
    
    def validate_api_key(self, api_key: str) -> Optional[str]:
        """Validate an API key and return the tenant ID"""
        return self.api_keys.get(api_key)
    
    def get_tenant_stats(self) -> Dict[str, Any]:
        """Get multi-tenant statistics"""
        tenants = list(self.tenants.values())
        
        return {
            "total_tenants": len(tenants),
            "active_tenants": len([t for t in tenants if t.status == TenantStatus.ACTIVE]),
            "trial_tenants": len([t for t in tenants if t.status == TenantStatus.TRIAL]),
            "suspended_tenants": len([t for t in tenants if t.status == TenantStatus.SUSPENDED]),
            "by_tier": {
                tier.value: len([t for t in tenants if t.tier == tier])
                for tier in TenantTier
            },
            "total_users": sum(t.usage.users for t in tenants),
            "total_agents": sum(t.usage.agents for t in tenants),
            "total_api_calls_today": sum(t.usage.api_calls_today for t in tenants)
        }
    
    def get_tenant_context(self, tenant_id: str) -> Dict[str, Any]:
        """Get full context for a tenant (for request handling)"""
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            return None
        
        return {
            "tenant_id": tenant.id,
            "tenant_name": tenant.name,
            "tenant_slug": tenant.slug,
            "tier": tenant.tier.value,
            "status": tenant.status.value,
            "quota": asdict(tenant.quota),
            "usage": asdict(tenant.usage),
            "settings": tenant.settings,
            "features": tenant.quota.features
        }


# Global singleton
multi_tenant_service = MultiTenantService()
