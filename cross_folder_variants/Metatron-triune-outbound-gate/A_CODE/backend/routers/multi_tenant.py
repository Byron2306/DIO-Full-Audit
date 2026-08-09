"""
Multi-Tenant API Router
=======================
API endpoints for multi-tenant management.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from dataclasses import asdict

from backend.services.multi_tenant import (
    multi_tenant_service, 
    Tenant, 
    TenantTier, 
    TenantStatus,
    TIER_QUOTAS
)
from .dependencies import get_current_user, check_permission

router = APIRouter(prefix="/tenants", tags=["Multi-Tenant"])


class CreateTenantRequest(BaseModel):
    name: str
    contact_email: EmailStr
    tier: str = "starter"
    trial_days: int = 14


class UpdateTenantRequest(BaseModel):
    name: Optional[str] = None
    tier: Optional[str] = None
    status: Optional[str] = None
    contact_email: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    tier: str
    status: str
    contact_email: str
    created_at: str
    quota: Dict[str, Any]
    usage: Dict[str, Any]


@router.get("/")
async def list_tenants(
    status: Optional[str] = None,
    tier: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """List all tenants"""
    status_enum = TenantStatus(status) if status else None
    tier_enum = TenantTier(tier) if tier else None
    
    tenants = multi_tenant_service.list_tenants(status=status_enum, tier=tier_enum)
    
    return {
        "tenants": [
            {
                "id": t.id,
                "name": t.name,
                "slug": t.slug,
                "tier": t.tier.value,
                "status": t.status.value,
                "contact_email": t.contact_email,
                "created_at": t.created_at,
                "users": t.usage.users,
                "agents": t.usage.agents
            }
            for t in tenants
        ],
        "total": len(tenants)
    }


@router.post("/")
async def create_tenant(
    request: CreateTenantRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new tenant"""
    try:
        tier_enum = TenantTier(request.tier)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {request.tier}")
    
    tenant = multi_tenant_service.create_tenant(
        name=request.name,
        contact_email=request.contact_email,
        tier=tier_enum,
        trial_days=request.trial_days
    )
    
    return {
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "tier": tenant.tier.value,
        "status": tenant.status.value,
        "message": "Tenant created successfully"
    }


@router.get("/stats")
async def get_tenant_stats(
    current_user: dict = Depends(get_current_user)
):
    """Get multi-tenant statistics"""
    return multi_tenant_service.get_tenant_stats()


@router.get("/tiers")
async def get_available_tiers():
    """Get available tenant tiers and their quotas"""
    return {
        tier.value: {
            "name": tier.value.title(),
            "quota": {
                "max_agents": quota.max_agents,
                "max_users": quota.max_users,
                "max_playbooks": quota.max_playbooks,
                "max_honeypots": quota.max_honeypots,
                "max_api_calls_per_day": quota.max_api_calls_per_day,
                "max_storage_gb": quota.max_storage_gb,
                "max_retention_days": quota.max_retention_days,
                "features": quota.features
            }
        }
        for tier, quota in TIER_QUOTAS.items()
    }


@router.get("/{tenant_id}")
async def get_tenant(
    tenant_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get tenant details"""
    tenant = multi_tenant_service.get_tenant(tenant_id)
    
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return {
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "tier": tenant.tier.value,
        "status": tenant.status.value,
        "contact_email": tenant.contact_email,
        "created_at": tenant.created_at,
        "updated_at": tenant.updated_at,
        "trial_ends_at": tenant.trial_ends_at,
        "quota": asdict(tenant.quota),
        "usage": asdict(tenant.usage),
        "settings": tenant.settings
    }


@router.put("/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    request: UpdateTenantRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update a tenant"""
    updates = request.dict(exclude_unset=True)
    
    tenant = multi_tenant_service.update_tenant(tenant_id, updates)
    
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return {
        "id": tenant.id,
        "name": tenant.name,
        "tier": tenant.tier.value,
        "status": tenant.status.value,
        "message": "Tenant updated successfully"
    }


@router.delete("/{tenant_id}")
async def delete_tenant(
    tenant_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete (suspend) a tenant"""
    success = multi_tenant_service.delete_tenant(tenant_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Tenant not found or cannot be deleted")
    
    return {"message": "Tenant suspended successfully"}


@router.get("/{tenant_id}/context")
async def get_tenant_context(
    tenant_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get full tenant context for request handling"""
    context = multi_tenant_service.get_tenant_context(tenant_id)
    
    if not context:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return context


@router.post("/{tenant_id}/api-key")
async def generate_api_key(
    tenant_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Generate an API key for a tenant"""
    api_key = multi_tenant_service.generate_api_key(tenant_id)
    
    if not api_key:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return {
        "api_key": api_key,
        "message": "Store this key securely. It won't be shown again."
    }


@router.post("/{tenant_id}/check-quota")
async def check_tenant_quota(
    tenant_id: str,
    resource: str,
    amount: int = 1,
    current_user: dict = Depends(get_current_user)
):
    """Check if tenant has quota for a resource"""
    has_quota = multi_tenant_service.check_quota(tenant_id, resource, amount)
    
    tenant = multi_tenant_service.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return {
        "resource": resource,
        "requested": amount,
        "has_quota": has_quota,
        "current_usage": getattr(tenant.usage, resource, 0) if hasattr(tenant.usage, resource) else 0,
        "max_quota": getattr(tenant.quota, f"max_{resource}", -1) if hasattr(tenant.quota, f"max_{resource}") else -1
    }


@router.post("/{tenant_id}/has-feature")
async def check_tenant_feature(
    tenant_id: str,
    feature: str,
    current_user: dict = Depends(get_current_user)
):
    """Check if tenant has access to a feature"""
    has_feature = multi_tenant_service.has_feature(tenant_id, feature)
    
    return {
        "feature": feature,
        "has_access": has_feature
    }


@router.post("/{tenant_id}/assign-user")
async def assign_user_to_tenant(
    tenant_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Assign a user to a tenant"""
    success = multi_tenant_service.assign_user_to_tenant(user_id, tenant_id)
    
    if not success:
        raise HTTPException(
            status_code=400, 
            detail="Failed to assign user. Tenant not found or user quota exceeded."
        )
    
    return {"message": f"User {user_id} assigned to tenant {tenant_id}"}
