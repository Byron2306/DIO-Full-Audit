"""
Threat Response Router - Automated threat response actions
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel

from .dependencies import get_current_user, get_db, check_permission, logger

# Import threat response services
from threat_response import (
    response_engine, firewall, sms_service, openclaw, forensics,
    ThreatContext, ResponseStatus,
    manual_block_ip, manual_unblock_ip, config as response_config
)

router = APIRouter(prefix="/threat-response", tags=["Threat Response"])


def _configure_response_engine_db(db):
    """Ensure threat response durability writes use the active DB handle."""
    response_engine.configure_db(db)


def _result_to_dict(result) -> dict:
    """Serialize a ResponseResult dataclass to a JSON-safe dict."""
    from dataclasses import asdict
    from enum import Enum
    raw = asdict(result)
    return {k: (v.value if isinstance(v, Enum) else v) for k, v in raw.items()}

class BlockIPRequest(BaseModel):
    ip: str
    reason: str = "Manual block"
    duration_hours: int = 24

class SMSTestRequest(BaseModel):
    phone_number: str
    message: str = "Test alert from Anti-AI Defense System"

@router.get("/stats")
async def get_response_stats(current_user: dict = Depends(get_current_user)):
    """Get threat response statistics"""
    _configure_response_engine_db(get_db())
    return await response_engine.get_response_stats()

@router.get("/blocked-ips")
async def get_blocked_ips(current_user: dict = Depends(get_current_user)):
    """Get list of blocked IPs"""
    _configure_response_engine_db(get_db())
    # FirewallManager tracks state, but the public accessor is exposed on response_engine.
    # Frontend expects `{ blocked_ips: [...] }`.
    return {"blocked_ips": response_engine.get_blocked_ips(), "count": len(response_engine.get_blocked_ips())}

@router.post("/block-ip")
async def block_ip(request: BlockIPRequest, current_user: dict = Depends(check_permission("write"))):
    """Manually block an IP address"""
    try:
        _configure_response_engine_db(get_db())
        result = await manual_block_ip(
            request.ip,
            request.reason,
            request.duration_hours,
            current_user.get("name", "admin")
        )
        return _result_to_dict(result)
    except Exception as e:
        logger.error(f"Failed to block IP: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/unblock-ip/{ip}")
async def unblock_ip(ip: str, current_user: dict = Depends(check_permission("write"))):
    """Unblock an IP address"""
    try:
        _configure_response_engine_db(get_db())
        result = await manual_unblock_ip(ip, current_user.get("name", "admin"))
        return _result_to_dict(result)
    except Exception as e:
        logger.error(f"Failed to unblock IP: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_response_history(limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Get response action history"""
    db = get_db()
    _configure_response_engine_db(db)
    history = await db.response_history.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return {"history": history, "count": len(history)}

@router.post("/settings/auto-block")
async def toggle_auto_block(enabled: bool, current_user: dict = Depends(check_permission("write"))):
    """Toggle auto-block functionality"""
    db = get_db()
    
    await db.response_settings.update_one(
        {},
        {"$set": {
            "auto_block_enabled": enabled,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": current_user["id"]
        }},
        upsert=True
    )
    
    # Update in-memory config
    response_config.auto_block_enabled = enabled
    
    return {"auto_block_enabled": enabled, "message": f"Auto-block {'enabled' if enabled else 'disabled'}"}

@router.get("/settings")
async def get_response_settings(current_user: dict = Depends(get_current_user)):
    """Get threat response settings"""
    db = get_db()
    settings = await db.response_settings.find_one({}, {"_id": 0})
    if not settings:
        settings = {
            "auto_response": {
                "auto_block_enabled": response_config.auto_block_enabled,
                "block_duration_hours": response_config.block_duration_hours,
                "critical_threat_threshold": 3
            },
            "sms_alerts": {
                "enabled": response_config.twilio_enabled,
                "contacts_count": len([c for c in response_config.emergency_contacts if c])
            },
            "twilio_account_sid": "",
            "twilio_auth_token": "",
            "twilio_phone_number": "",
            "emergency_contacts": []
        }
    else:
        # Normalize settings structure for frontend
        if "auto_response" not in settings:
            settings["auto_response"] = {
                "auto_block_enabled": settings.get("auto_block_enabled", response_config.auto_block_enabled),
                "block_duration_hours": settings.get("block_duration_hours", response_config.block_duration_hours),
                "critical_threat_threshold": settings.get("critical_threat_threshold", 3)
            }
        if "sms_alerts" not in settings:
            settings["sms_alerts"] = {
                "enabled": settings.get("sms_alerts_enabled", response_config.twilio_enabled),
                "contacts_count": len(settings.get("emergency_contacts", []))
            }
    
    # Mask sensitive data
    if settings.get("twilio_auth_token"):
        settings["twilio_auth_token"] = "***" + settings["twilio_auth_token"][-4:]
    
    return settings

@router.post("/settings")
async def update_response_settings(settings: dict, current_user: dict = Depends(check_permission("write"))):
    """Update threat response settings"""
    db = get_db()
    
    current = await db.response_settings.find_one({}, {"_id": 0}) or {}
    
    update_doc = {
        "auto_block_enabled": settings.get("auto_block_enabled", current.get("auto_block_enabled", True)),
        "block_duration_hours": settings.get("block_duration_hours", current.get("block_duration_hours", 24)),
        "sms_alerts_enabled": settings.get("sms_alerts_enabled", current.get("sms_alerts_enabled", False)),
        "twilio_account_sid": settings.get("twilio_account_sid") if settings.get("twilio_account_sid") else current.get("twilio_account_sid", ""),
        "twilio_phone_number": settings.get("twilio_phone_number") if settings.get("twilio_phone_number") else current.get("twilio_phone_number", ""),
        "emergency_contacts": settings.get("emergency_contacts", current.get("emergency_contacts", [])),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": current_user["id"]
    }
    
    # Only update auth token if new value provided
    if settings.get("twilio_auth_token") and not settings.get("twilio_auth_token", "").startswith("***"):
        update_doc["twilio_auth_token"] = settings["twilio_auth_token"]
    else:
        update_doc["twilio_auth_token"] = current.get("twilio_auth_token", "")
    
    await db.response_settings.update_one(
        {},
        {"$set": update_doc},
        upsert=True
    )
    
    # Update in-memory config
    response_config.auto_block_enabled = update_doc["auto_block_enabled"]
    response_config.block_duration_hours = update_doc["block_duration_hours"]
    response_config.sms_alerts_enabled = update_doc["sms_alerts_enabled"]
    sms_service.account_sid = update_doc["twilio_account_sid"]
    sms_service.auth_token = update_doc["twilio_auth_token"]
    sms_service.from_number = update_doc["twilio_phone_number"]
    
    return {"message": "Settings updated", "updated_at": update_doc["updated_at"]}

@router.post("/test-sms")
async def test_sms(request: SMSTestRequest, current_user: dict = Depends(check_permission("write"))):
    """Test SMS alerting"""
    try:
        result = await sms_service.send_emergency_sms(message=request.message, recipients=[request.phone_number] if request.phone_number else None)
        if result:
            return {"success": True, "message": "SMS sent"}
        else:
            raise HTTPException(status_code=500, detail="SMS sending failed")
    except Exception as e:
        logger.error(f"SMS test failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/openclaw/status")
async def get_openclaw_status(current_user: dict = Depends(get_current_user)):
    """Get OpenClaw AI integration status"""
    try:
        status = await openclaw.get_status()
        return status
    except Exception as e:
        return {"connected": False, "error": str(e)}

@router.post("/openclaw/analyze")
async def analyze_with_openclaw(threat_data: dict, current_user: dict = Depends(get_current_user)):
    """Analyze threat with OpenClaw AI"""
    try:
        context = ThreatContext(
            threat_id=threat_data.get("id", "unknown"),
            threat_type=threat_data.get("type", "unknown"),
            severity=threat_data.get("severity", "medium"),
            source_ip=threat_data.get("source_ip"),
            target_ip=threat_data.get("target_ip") or threat_data.get("target_system"),
            indicators=threat_data.get("indicators", []),
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        result = await openclaw.analyze_threat(context)
        return result
    except Exception as e:
        logger.error(f"OpenClaw analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/forensics/{incident_id}")
async def get_forensics(incident_id: str, current_user: dict = Depends(get_current_user)):
    """Get forensic evidence for an incident"""
    try:
        evidence = await forensics.get_evidence_by_id(incident_id)
        return evidence
    except Exception as e:
        logger.error(f"Forensics retrieval failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
