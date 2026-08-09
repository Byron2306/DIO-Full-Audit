"""
Quarantine Router
"""
from fastapi import APIRouter, HTTPException, Depends
from dataclasses import asdict

from .dependencies import get_current_user, get_db

# Import quarantine service
from quarantine import (
    get_quarantine_summary, list_quarantined,
    get_quarantine_entry, restore_file, delete_quarantined
)
from quarantine import ingest_quarantine_metadata
from pydantic import BaseModel
from typing import Optional, Dict, Any

router = APIRouter(prefix="/quarantine", tags=["Quarantine"])

class DemoIngestRequest(BaseModel):
    filepath: str
    threat_name: str
    threat_type: str = "unknown"
    detection_source: str = "agent"
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    sha256: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@router.get("")
async def get_quarantine_list(current_user: dict = Depends(get_current_user)):
    """Get all quarantined files"""
    # list_quarantined is sync, not async
    entries = list_quarantined()
    # Convert dataclass entries to dicts
    return [asdict(e) for e in entries]

@router.get("/summary")
async def get_summary(current_user: dict = Depends(get_current_user)):
    """Get quarantine summary stats"""
    # get_quarantine_summary is sync, not async
    summary = get_quarantine_summary()
    return {
        "total_files": summary.get("total_entries", 0),
        "total_size": summary.get("storage", {}).get("total_size_bytes", 0),
        "by_status": summary.get("by_status", {}),
        "by_threat_type": summary.get("by_threat_type", {}),
        "storage": summary.get("storage", {})
    }

@router.get("/{entry_id}")
async def get_entry(entry_id: str, current_user: dict = Depends(get_current_user)):
    """Get specific quarantine entry"""
    # get_quarantine_entry is sync, not async
    entry = get_quarantine_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return asdict(entry)

@router.post("/{entry_id}/restore")
async def restore_entry(entry_id: str, current_user: dict = Depends(get_current_user)):
    """Restore a quarantined file"""
    # restore_file is sync, returns bool
    result = restore_file(entry_id)
    if not result:
        raise HTTPException(status_code=400, detail="Restore failed - entry not found or already restored")
    return {"success": True, "message": "File restored successfully"}

@router.delete("/{entry_id}")
async def delete_entry(entry_id: str, current_user: dict = Depends(get_current_user)):
    """Permanently delete a quarantined file"""
    # delete_quarantined is sync, returns bool
    result = delete_quarantined(entry_id)
    if not result:
        raise HTTPException(status_code=400, detail="Delete failed - entry not found")
    return {"success": True, "message": "File deleted successfully"}


@router.post("/demo-ingest")
async def demo_ingest(request: DemoIngestRequest, current_user: dict = Depends(get_current_user)):
    """Ingest a quarantine record by metadata only (for remote agents / demos)."""
    entry = ingest_quarantine_metadata(
        original_path=request.filepath,
        threat_name=request.threat_name,
        threat_type=request.threat_type,
        detection_source=request.detection_source,
        agent_id=request.agent_id,
        agent_name=request.agent_name,
        file_hash_sha256=request.sha256,
        metadata={
            **(request.metadata or {}),
            "ingested_by": current_user.get("email") or current_user.get("id") or "unknown",
        },
    )
    return {"success": True, "entry": asdict(entry)}
