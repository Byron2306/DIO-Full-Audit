"""
Alerts Router
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import List, Optional
import uuid

from .dependencies import (
    AlertCreate, AlertResponse, get_current_user, get_db
)

# Optional analysis services
try:
    from services.diagnostic_classifier import DiagnosticClassifier
except ImportError:
    DiagnosticClassifier = None

try:
    from services.assessment_ecology import AssessmentEcologyService
except ImportError:
    AssessmentEcologyService = None

router = APIRouter(prefix="/alerts", tags=["Alerts"])

@router.post("", response_model=AlertResponse)
async def create_alert(alert_data: AlertCreate, current_user: dict = Depends(get_current_user)):
    db = get_db()
    alert_id = str(uuid.uuid4())
    alert_doc = {
        "id": alert_id,
        "title": alert_data.title,
        "type": alert_data.type,
        "severity": alert_data.severity,
        "threat_id": alert_data.threat_id,
        "message": alert_data.message,
        "status": "new",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.alerts.insert_one(alert_doc)
    return AlertResponse(**alert_doc)

@router.get("")
async def get_alerts(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    db = get_db()
    query = {}
    if status:
        query["status"] = status
    alerts = await db.alerts.find(query, {"_id": 0}).sort([("created_at", -1), ("timestamp", -1)]).to_list(100)
    
    # Normalize alerts to ensure required fields exist
    normalized_alerts = []
    for a in alerts:
        normalized = {
            "id": a.get("id") or str(uuid.uuid4()),
            "title": a.get("title") or a.get("event_type") or a.get("message", "Alert")[:50],
            "type": a.get("type", "unknown"),
            "severity": a.get("severity", "medium"),
            "threat_id": a.get("threat_id"),
            "message": a.get("message", ""),
            "status": a.get("status", "new"),
            "created_at": a.get("created_at") or a.get("timestamp") or datetime.now(timezone.utc).isoformat()
        }
        normalized_alerts.append(normalized)
    
    return {"alerts": normalized_alerts, "count": len(normalized_alerts)}

@router.patch("/{alert_id}/status")
async def update_alert_status(alert_id: str, status: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    if status not in ["new", "acknowledged", "resolved"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    result = await db.alerts.update_one({"id": alert_id}, {"$set": {"status": status}})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Alert status updated", "status": status}


@router.post("/classify")
async def classify_alert(
    alert_data: dict,
    current_user: dict = Depends(get_current_user),
):
    """Classify an alert using diagnostic classification."""
    if not DiagnosticClassifier:
        raise HTTPException(status_code=501, detail="Diagnostic classifier not available")
    
    try:
        classifier = DiagnosticClassifier()
        classification = await classifier.classify(alert_data)
        return {
            "success": True,
            "classification": classification,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")


@router.get("/assessment")
async def get_assessment_ecology(
    alert_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Get assessment ecology for alerts or a specific alert."""
    if not AssessmentEcologyService:
        raise HTTPException(status_code=501, detail="Assessment ecology service not available")
    
    try:
        service = AssessmentEcologyService()
        if alert_id:
            assessment = await service.assess_alert(alert_id)
        else:
            assessment = await service.get_ecology()
        return {
            "success": True,
            "assessment": assessment,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assessment failed: {str(e)}")
