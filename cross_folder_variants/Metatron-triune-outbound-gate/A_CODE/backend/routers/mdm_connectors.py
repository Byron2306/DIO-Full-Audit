"""
MDM Connectors Router - API endpoints for MDM platform management
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Optional, List
from pydantic import BaseModel
from dataclasses import asdict
import asyncio

from .dependencies import get_current_user, check_permission
from mdm_connectors import mdm_manager, MDMPlatform, DeviceManagementAction

router = APIRouter(prefix="/mdm", tags=["MDM Connectors"])


class AddConnectorRequest(BaseModel):
    name: str
    platform: str  # intune, jamf, workspace_one, google_workspace
    config: dict  # Platform-specific configuration


class ExecuteActionRequest(BaseModel):
    action: str  # sync, lock, wipe, retire, etc.
    params: Optional[dict] = None


@router.get("/status")
async def get_mdm_status(current_user: dict = Depends(get_current_user)):
    """Get status of all MDM connectors"""
    return {
        "connectors": mdm_manager.get_connector_status(),
        "total_devices": len(mdm_manager.all_devices)
    }


@router.post("/connectors")
async def add_mdm_connector(
    request: AddConnectorRequest,
    current_user: dict = Depends(check_permission("admin"))
):
    """Add a new MDM connector"""
    try:
        platform = MDMPlatform(request.platform.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid platform: {request.platform}")
    
    success = mdm_manager.add_connector(request.name, platform, request.config)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to add connector")
    
    return {"message": f"Connector {request.name} added", "platform": platform.value}


@router.delete("/connectors/{name}")
async def remove_mdm_connector(
    name: str,
    current_user: dict = Depends(check_permission("admin"))
):
    """Remove an MDM connector"""
    success = mdm_manager.remove_connector(name)
    if not success:
        raise HTTPException(status_code=404, detail="Connector not found")
    return {"message": f"Connector {name} removed"}


@router.post("/connectors/{name}/connect")
async def connect_mdm_connector(
    name: str,
    current_user: dict = Depends(check_permission("admin"))
):
    """Connect a specific MDM connector"""
    if name not in mdm_manager.connectors:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    success = await mdm_manager.connectors[name].connect()
    return {"message": f"Connector {name} {'connected' if success else 'connection failed'}", "connected": success}


@router.post("/connectors/{name}/disconnect")
async def disconnect_mdm_connector(
    name: str,
    current_user: dict = Depends(check_permission("admin"))
):
    """Disconnect a specific MDM connector"""
    if name not in mdm_manager.connectors:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    success = await mdm_manager.connectors[name].disconnect()
    return {"message": f"Connector {name} disconnected", "success": success}


@router.post("/connect-all")
async def connect_all_mdm(current_user: dict = Depends(check_permission("admin"))):
    """Connect all configured MDM connectors"""
    results = await mdm_manager.connect_all()
    return {"results": results}


@router.post("/sync")
async def sync_all_devices(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(check_permission("write"))
):
    """Sync devices from all connected MDM platforms"""
    # Run sync in background for large inventories
    async def do_sync():
        await mdm_manager.sync_all_devices()
        await mdm_manager.sync_all_policies()
    
    background_tasks.add_task(asyncio.create_task, do_sync())
    return {"message": "Sync initiated", "status": "running"}


@router.post("/sync/now")
async def sync_all_devices_now(current_user: dict = Depends(check_permission("write"))):
    """Sync devices immediately (blocking)"""
    devices = await mdm_manager.sync_all_devices()
    policies = await mdm_manager.sync_all_policies()
    return {
        "devices_synced": len(devices),
        "policies_synced": len(policies)
    }


@router.get("/devices")
async def get_all_mdm_devices(current_user: dict = Depends(get_current_user)):
    """Get all devices from all MDM platforms"""
    devices = mdm_manager.get_all_devices()
    return {"devices": devices, "count": len(devices)}


@router.get("/devices/{device_id}")
async def get_mdm_device(
    device_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get specific device details"""
    device = mdm_manager.all_devices.get(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return asdict(device)


@router.post("/devices/{device_id}/action")
async def execute_device_action(
    device_id: str,
    request: ExecuteActionRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Execute management action on device"""
    try:
        action = DeviceManagementAction(request.action.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid action: {request.action}")
    
    result = await mdm_manager.execute_action(device_id, action, request.params)
    return asdict(result)


@router.post("/devices/{device_id}/lock")
async def lock_device(
    device_id: str,
    current_user: dict = Depends(check_permission("write"))
):
    """Lock a device"""
    result = await mdm_manager.execute_action(device_id, DeviceManagementAction.LOCK)
    return asdict(result)


@router.post("/devices/{device_id}/wipe")
async def wipe_device(
    device_id: str,
    current_user: dict = Depends(check_permission("admin"))
):
    """Wipe a device (requires admin)"""
    result = await mdm_manager.execute_action(device_id, DeviceManagementAction.WIPE)
    return asdict(result)


@router.post("/devices/{device_id}/retire")
async def retire_device(
    device_id: str,
    current_user: dict = Depends(check_permission("admin"))
):
    """Retire a device (requires admin)"""
    result = await mdm_manager.execute_action(device_id, DeviceManagementAction.RETIRE)
    return asdict(result)


@router.post("/devices/{device_id}/sync")
async def sync_single_device(
    device_id: str,
    current_user: dict = Depends(check_permission("write"))
):
    """Sync a single device"""
    result = await mdm_manager.execute_action(device_id, DeviceManagementAction.SYNC)
    return asdict(result)


@router.get("/devices/{device_id}/compliance")
async def get_device_compliance(
    device_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get device compliance details"""
    device = mdm_manager.all_devices.get(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # Find the right connector
    for connector in mdm_manager.connectors.values():
        if device_id in connector.devices:
            return await connector.get_device_compliance(device_id)
    
    raise HTTPException(status_code=404, detail="Connector not found for device")


@router.get("/policies")
async def get_all_mdm_policies(current_user: dict = Depends(get_current_user)):
    """Get all compliance policies from all platforms"""
    all_policies = []
    for connector in mdm_manager.connectors.values():
        all_policies.extend([asdict(p) for p in connector.policies.values()])
    return {"policies": all_policies, "count": len(all_policies)}


@router.get("/platforms")
async def get_supported_platforms(current_user: dict = Depends(get_current_user)):
    """Get list of supported MDM platforms"""
    return {
        "platforms": [
            {
                "id": "intune",
                "name": "Microsoft Intune",
                "description": "Azure AD integrated MDM for Windows, iOS, Android, macOS",
                "config_required": ["tenant_id", "client_id", "client_secret"]
            },
            {
                "id": "jamf",
                "name": "JAMF Pro",
                "description": "Apple device management for iOS, iPadOS, macOS",
                "config_required": ["server_url", "client_id", "client_secret"]
            },
            {
                "id": "workspace_one",
                "name": "VMware Workspace ONE",
                "description": "Cross-platform UEM solution",
                "config_required": ["server_url", "api_key", "tenant_code"]
            },
            {
                "id": "google_workspace",
                "name": "Google Workspace",
                "description": "Android Enterprise and Chrome OS management",
                "config_required": ["service_account_json", "customer_id"]
            }
        ]
    }
