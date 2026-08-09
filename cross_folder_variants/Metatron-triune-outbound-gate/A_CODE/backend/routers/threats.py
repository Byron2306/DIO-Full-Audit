"""
Threats Router
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import List, Optional
import uuid

from .dependencies import (
    ThreatCreate, ThreatResponse, get_current_user, get_optional_current_user,
    get_db, has_permission, optional_machine_token,
)

router = APIRouter(prefix="/threats", tags=["Threats"])

# Machine-to-machine auth: allows the multi-source correlator and SOAR to read
# threats without a user JWT, using x-internal-token header.
_verify_threats_machine_token = optional_machine_token(
    env_keys=["INTEGRATION_API_KEY", "SWARM_AGENT_TOKEN"],
    header_names=["x-internal-token", "x-agent-token"],
    subject="threats read",
)

@router.post("", response_model=ThreatResponse)
async def create_threat(threat_data: ThreatCreate, current_user: dict = Depends(get_current_user)):
    db = get_db()
    threat_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    threat_doc = {
        "id": threat_id,
        "name": threat_data.name,
        "type": threat_data.type,
        "severity": threat_data.severity,
        "status": "active",
        "source_ip": threat_data.source_ip,
        "target_system": threat_data.target_system,
        "description": threat_data.description,
        "indicators": threat_data.indicators or [],
        "ai_analysis": None,
        "created_at": now,
        "updated_at": now,
        "created_by": current_user["id"]
    }
    await db.threats.insert_one(threat_doc)
    return ThreatResponse(**threat_doc)

@router.get("", response_model=List[ThreatResponse])
async def get_threats(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    machine_auth: Optional[dict] = Depends(_verify_threats_machine_token),
    current_user: Optional[dict] = Depends(get_optional_current_user),
):
    if machine_auth is None and not has_permission(current_user, "read"):
        raise HTTPException(status_code=403, detail="Not authorized")
    db = get_db()
    query = {}
    if status:
        query["status"] = status
    if severity:
        query["severity"] = severity

    threats = await db.threats.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [ThreatResponse(**t) for t in threats]

@router.get("/{threat_id}", response_model=ThreatResponse)
async def get_threat(
    threat_id: str,
    machine_auth: Optional[dict] = Depends(_verify_threats_machine_token),
    current_user: Optional[dict] = Depends(get_optional_current_user),
):
    if machine_auth is None and not has_permission(current_user, "read"):
        raise HTTPException(status_code=403, detail="Not authorized")
    db = get_db()
    threat = await db.threats.find_one({"id": threat_id}, {"_id": 0})
    if not threat:
        raise HTTPException(status_code=404, detail="Threat not found")
    return ThreatResponse(**threat)

@router.patch("/{threat_id}/status")
async def update_threat_status(threat_id: str, status: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    if status not in ["active", "contained", "resolved"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    result = await db.threats.update_one(
        {"id": threat_id},
        {"$set": {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Threat not found")
    return {"message": "Status updated", "status": status}
