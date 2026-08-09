"""
EDR (Endpoint Detection & Response) Router
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from pydantic import BaseModel

from .dependencies import get_current_user, check_permission

# Import EDR service
from edr_service import edr_manager, EDRManager

router = APIRouter(prefix="/edr", tags=["EDR"])

class MemoryAnalysisRequest(BaseModel):
    dump_path: str

class FIMPathRequest(BaseModel):
    path: str

class USBDeviceRequest(BaseModel):
    vendor_id: str
    product_id: str

@router.get("/status")
async def get_edr_status(current_user: dict = Depends(get_current_user)):
    """Get EDR system status"""
    return edr_manager.get_status()

# Process Tree endpoints
@router.get("/process-tree")
async def get_process_tree(current_user: dict = Depends(get_current_user)):
    """Get current process tree"""
    tree = await edr_manager.get_process_tree()
    return {"process_tree": tree, "count": len(tree)}

# File Integrity Monitoring endpoints
@router.get("/fim/status")
async def get_fim_status(current_user: dict = Depends(get_current_user)):
    """Get FIM status"""
    return edr_manager.fim.get_status()

@router.post("/fim/baseline")
async def create_fim_baseline(current_user: dict = Depends(check_permission("write"))):
    """Create FIM baseline"""
    result = await edr_manager.create_fim_baseline()
    return result

@router.post("/fim/check")
async def check_file_integrity(current_user: dict = Depends(get_current_user)):
    """Check file integrity against baseline"""
    events = await edr_manager.check_file_integrity()
    return {
        "events": events,
        "count": len(events),
        "has_violations": len(events) > 0
    }

@router.post("/fim/monitor")
async def add_monitored_path(request: FIMPathRequest, current_user: dict = Depends(check_permission("write"))):
    """Add path to FIM monitoring"""
    edr_manager.fim.add_monitored_path(request.path)
    return {"message": f"Added {request.path} to monitoring"}

# USB Device Control endpoints
@router.get("/usb/devices")
async def get_usb_devices(current_user: dict = Depends(get_current_user)):
    """Get connected USB devices"""
    devices = await edr_manager.scan_usb_devices()
    return {"devices": devices, "count": len(devices)}

@router.get("/usb/status")
async def get_usb_status(current_user: dict = Depends(get_current_user)):
    """Get USB control status"""
    return edr_manager.usb_control.get_status()

@router.post("/usb/allow")
async def allow_usb_device(request: USBDeviceRequest, current_user: dict = Depends(check_permission("write"))):
    """Allow a USB device"""
    edr_manager.usb_control.allow_device(request.vendor_id, request.product_id)
    return {"message": f"Device {request.vendor_id}:{request.product_id} allowed"}

@router.post("/usb/block")
async def block_usb_device(request: USBDeviceRequest, current_user: dict = Depends(check_permission("write"))):
    """Block a USB device"""
    edr_manager.usb_control.block_device(request.vendor_id, request.product_id)
    return {"message": f"Device {request.vendor_id}:{request.product_id} blocked"}

# Memory Forensics endpoints
@router.get("/memory/status")
async def get_memory_forensics_status(current_user: dict = Depends(get_current_user)):
    """Get memory forensics status"""
    return edr_manager.memory_forensics.get_status()

@router.post("/memory/analyze")
async def analyze_memory_dump(request: MemoryAnalysisRequest, current_user: dict = Depends(check_permission("write"))):
    """Analyze a memory dump file"""
    result = await edr_manager.analyze_memory(request.dump_path)
    return result

@router.post("/memory/capture")
async def capture_live_memory(current_user: dict = Depends(check_permission("manage_users"))):
    """Capture live system memory"""
    result = await edr_manager.capture_memory()
    return result

# Telemetry endpoints
@router.get("/telemetry")
async def collect_telemetry(current_user: dict = Depends(get_current_user)):
    """Collect EDR telemetry"""
    telemetry = await edr_manager.collect_telemetry()
    return telemetry
