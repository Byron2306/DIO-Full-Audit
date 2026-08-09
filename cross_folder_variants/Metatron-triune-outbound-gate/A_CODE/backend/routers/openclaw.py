"""
OpenClaw Router - AI Gateway Configuration
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel
import os

from .dependencies import get_current_user, get_db, check_permission, logger

router = APIRouter(prefix="/openclaw", tags=["OpenClaw"])

class OpenClawConfig(BaseModel):
    enabled: bool = False
    gateway_url: Optional[str] = None
    api_key: Optional[str] = None
    auto_analyze: bool = True
    auto_respond: bool = False
    response_threshold: str = "high"  # critical, high, medium, low

@router.get("/config")
async def get_openclaw_config(current_user: dict = Depends(get_current_user)):
    """Get OpenClaw configuration"""
    db = get_db()
    config = await db.openclaw_config.find_one({}, {"_id": 0})
    
    if not config:
        config = {
            "enabled": os.environ.get("OPENCLAW_ENABLED", "false").lower() == "true",
            "gateway_url": os.environ.get("OPENCLAW_GATEWAY_URL", ""),
            "api_key": "",
            "auto_analyze": True,
            "auto_respond": False,
            "response_threshold": "high"
        }
    
    # Mask API key
    if config.get("api_key"):
        config["api_key"] = "***" + config["api_key"][-4:]
    
    return config

@router.post("/config")
async def update_openclaw_config(config: OpenClawConfig, current_user: dict = Depends(check_permission("write"))):
    """Update OpenClaw configuration"""
    db = get_db()
    
    current = await db.openclaw_config.find_one({}, {"_id": 0}) or {}
    
    update_doc = {
        "enabled": config.enabled,
        "gateway_url": config.gateway_url if config.gateway_url else current.get("gateway_url", ""),
        "auto_analyze": config.auto_analyze,
        "auto_respond": config.auto_respond,
        "response_threshold": config.response_threshold,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": current_user["id"]
    }
    
    # Only update API key if new value provided
    if config.api_key and not config.api_key.startswith("***"):
        update_doc["api_key"] = config.api_key
    else:
        update_doc["api_key"] = current.get("api_key", "")
    
    await db.openclaw_config.update_one(
        {},
        {"$set": update_doc},
        upsert=True
    )
    
    return {"message": "OpenClaw configuration updated", "updated_at": update_doc["updated_at"]}

@router.post("/test")
async def test_openclaw_connection(current_user: dict = Depends(get_current_user)):
    """Test OpenClaw gateway connection"""
    db = get_db()
    config = await db.openclaw_config.find_one({}, {"_id": 0})
    
    if not config or not config.get("gateway_url"):
        raise HTTPException(status_code=400, detail="OpenClaw not configured")
    
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            headers = {}
            if config.get("api_key"):
                headers["Authorization"] = f"Bearer {config['api_key']}"
            
            response = await client.get(
                f"{config['gateway_url']}/health",
                headers=headers,
                timeout=10.0
            )
            
            if response.status_code == 200:
                return {"connected": True, "message": "OpenClaw gateway is reachable"}
            else:
                return {"connected": False, "message": f"Gateway returned status {response.status_code}"}
    except Exception as e:
        logger.error(f"OpenClaw test failed: {str(e)}")
        return {"connected": False, "error": str(e)}
