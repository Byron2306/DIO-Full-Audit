"""
Mobile Security Router - API endpoints for mobile threat defense
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from pydantic import BaseModel
from dataclasses import asdict

from .dependencies import get_current_user, check_permission
from mobile_security import mobile_security_service

router = APIRouter(prefix="/mobile-security", tags=["Mobile Security"])


# Request/Response Models
class RegisterDeviceRequest(BaseModel):
    device_name: str
    platform: str  # ios, android
    os_version: str
    model: str
    serial_number: str
    user_id: str = ""
    user_email: str = ""
    imei: str = ""


class UpdateDeviceStatusRequest(BaseModel):
    is_jailbroken: Optional[bool] = None
    is_encrypted: Optional[bool] = None
    has_passcode: Optional[bool] = None
    mdm_enrolled: Optional[bool] = None
    installed_apps: Optional[List[dict]] = None
    network_info: Optional[dict] = None


class AnalyzeAppRequest(BaseModel):
    package_name: str
    app_name: str
    version: str
    platform: str
    permissions: Optional[List[str]] = None
    is_sideloaded: bool = False
    is_debuggable: bool = False
    manifest_data: Optional[dict] = None


class ResolveThreatRequest(BaseModel):
    resolution_notes: str = ""


class UpdatePolicyRequest(BaseModel):
    policy_name: str
    settings: dict


@router.get("/stats")
async def get_mobile_security_stats(current_user: dict = Depends(get_current_user)):
    """Get mobile security statistics"""
    return mobile_security_service.get_stats()


@router.get("/devices")
async def get_all_devices(current_user: dict = Depends(get_current_user)):
    """Get all registered mobile devices"""
    devices = mobile_security_service.get_all_devices()
    return {"devices": devices, "count": len(devices)}


@router.get("/devices/{device_id}")
async def get_device(device_id: str, current_user: dict = Depends(get_current_user)):
    """Get details of a specific device"""
    device = mobile_security_service.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.post("/devices")
async def register_device(
    request: RegisterDeviceRequest,
    current_user: dict = Depends(get_current_user)
):
    """Register a new mobile device"""
    device = mobile_security_service.register_device(
        device_name=request.device_name,
        platform=request.platform,
        os_version=request.os_version,
        model=request.model,
        serial_number=request.serial_number,
        user_id=request.user_id,
        user_email=request.user_email,
        imei=request.imei
    )
    return {
        **asdict(device),
        "platform": device.platform.value,
        "status": device.status.value
    }


@router.put("/devices/{device_id}/status")
async def update_device_status(
    device_id: str,
    request: UpdateDeviceStatusRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update device security status"""
    device = mobile_security_service.update_device_status(
        device_id=device_id,
        is_jailbroken=request.is_jailbroken,
        is_encrypted=request.is_encrypted,
        has_passcode=request.has_passcode,
        mdm_enrolled=request.mdm_enrolled,
        installed_apps=request.installed_apps,
        network_info=request.network_info
    )
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    return {
        **asdict(device),
        "platform": device.platform.value,
        "status": device.status.value
    }


@router.delete("/devices/{device_id}")
async def unenroll_device(
    device_id: str,
    current_user: dict = Depends(check_permission("write"))
):
    """Unenroll a device"""
    success = mobile_security_service.unenroll_device(device_id)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"message": "Device unenrolled", "device_id": device_id}


@router.get("/devices/{device_id}/compliance")
async def check_device_compliance(
    device_id: str,
    policy_name: str = "default",
    current_user: dict = Depends(get_current_user)
):
    """Check device compliance against policy"""
    report = mobile_security_service.check_compliance(device_id, policy_name)
    if not report:
        raise HTTPException(status_code=404, detail="Device not found")
    return asdict(report)


@router.get("/devices/{device_id}/threats")
async def get_device_threats(
    device_id: str,
    include_resolved: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """Get threats for a specific device"""
    threats = mobile_security_service.get_device_threats(device_id, include_resolved)
    return {"threats": threats, "count": len(threats)}


@router.get("/threats")
async def get_all_threats(
    include_resolved: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """Get all mobile threats"""
    threats = mobile_security_service.get_all_threats(include_resolved)
    return {"threats": threats, "count": len(threats)}


@router.post("/threats/{threat_id}/resolve")
async def resolve_threat(
    threat_id: str,
    request: ResolveThreatRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Mark a threat as resolved"""
    success = mobile_security_service.resolve_threat(threat_id, request.resolution_notes)
    if not success:
        raise HTTPException(status_code=404, detail="Threat not found")
    return {"message": "Threat resolved", "threat_id": threat_id}


@router.post("/analyze-app")
async def analyze_app(
    request: AnalyzeAppRequest,
    current_user: dict = Depends(get_current_user)
):
    """Analyze a mobile app for security issues"""
    analysis = mobile_security_service.analyze_app(
        package_name=request.package_name,
        app_name=request.app_name,
        version=request.version,
        platform=request.platform,
        permissions=request.permissions,
        is_sideloaded=request.is_sideloaded,
        is_debuggable=request.is_debuggable,
        manifest_data=request.manifest_data
    )
    
    result = asdict(analysis)
    result['platform'] = analysis.platform.value
    result['risk_level'] = analysis.risk_level.value
    return result


@router.get("/app-analyses")
async def get_app_analyses(current_user: dict = Depends(get_current_user)):
    """Get all app security analyses"""
    analyses = [
        {
            **asdict(a),
            'platform': a.platform.value,
            'risk_level': a.risk_level.value
        }
        for a in mobile_security_service.app_analyses.values()
    ]
    return {"analyses": analyses, "count": len(analyses)}


@router.get("/policies")
async def get_policies(current_user: dict = Depends(get_current_user)):
    """Get all compliance policies"""
    return {"policies": mobile_security_service.policies}


@router.put("/policies/{policy_name}")
async def update_policy(
    policy_name: str,
    request: UpdatePolicyRequest,
    current_user: dict = Depends(check_permission("admin"))
):
    """Update a compliance policy"""
    mobile_security_service.policies[policy_name] = {
        "name": request.settings.get("name", policy_name),
        **request.settings
    }
    return {"message": f"Policy {policy_name} updated", "policy": mobile_security_service.policies[policy_name]}


@router.get("/threat-categories")
async def get_threat_categories(current_user: dict = Depends(get_current_user)):
    """Get available threat categories"""
    from mobile_security import ThreatCategory, ThreatSeverity
    return {
        "categories": [
            {"id": c.value, "name": c.name.replace("_", " ").title()}
            for c in ThreatCategory
        ],
        "severities": [
            {"id": s.value, "name": s.name.title()}
            for s in ThreatSeverity
        ]
    }


@router.get("/compliance-checks")
async def get_compliance_checks(current_user: dict = Depends(get_current_user)):
    """Get available compliance checks"""
    from mobile_security import ComplianceCheck
    return {
        "checks": [
            {"id": c.value, "name": c.name.replace("_", " ").title()}
            for c in ComplianceCheck
        ]
    }


@router.get("/dashboard")
async def get_mobile_dashboard(current_user: dict = Depends(get_current_user)):
    """Get mobile security dashboard data"""
    stats = mobile_security_service.get_stats()
    devices = mobile_security_service.get_all_devices()
    threats = mobile_security_service.get_all_threats(include_resolved=False)
    
    # Get top at-risk devices
    at_risk_devices = sorted(
        [d for d in devices if d['risk_score'] > 0.3],
        key=lambda x: x['risk_score'],
        reverse=True
    )[:5]
    
    # Get recent threats
    recent_threats = sorted(
        threats,
        key=lambda x: x.get('detected_at', ''),
        reverse=True
    )[:10]
    
    return {
        "stats": stats,
        "at_risk_devices": at_risk_devices,
        "recent_threats": recent_threats,
        "compliance_overview": {
            "total_devices": stats['total_devices'],
            "compliant": stats['by_status'].get('compliant', 0),
            "non_compliant": stats['by_status'].get('non_compliant', 0),
            "at_risk": stats['by_status'].get('at_risk', 0),
            "compromised": stats['by_status'].get('compromised', 0)
        }
    }
