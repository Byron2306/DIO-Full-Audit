"""
WebSocket Router - Real-time communication management
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any

from .dependencies import get_current_user

# Import websocket services
from websocket_service import realtime_ws, WSMessageType, WSMessage

router = APIRouter(prefix="/websocket", tags=["WebSocket"])

@router.get("/stats")
async def get_websocket_stats(current_user: dict = Depends(get_current_user)):
    """Get WebSocket connection statistics"""
    return realtime_ws.get_stats()

@router.get("/agents")
async def get_connected_agents(current_user: dict = Depends(get_current_user)):
    """Get list of connected agents"""
    return realtime_ws.get_connected_agents()

@router.post("/command/{agent_id}")
async def send_command_to_agent(agent_id: str, command: Dict[str, Any], current_user: dict = Depends(get_current_user)):
    """Send a command to a specific agent"""
    message = WSMessage(
        type=WSMessageType.COMMAND,
        payload={
            "command": command.get("command"),
            "params": command.get("params", {}),
            "issued_by": current_user.get("name", "admin")
        }
    )
    
    result = await realtime_ws.send_to_agent(agent_id, message)
    if not result:
        raise HTTPException(status_code=404, detail="Agent not connected")
    
    return {"message": "Command sent", "agent_id": agent_id, "command": command.get("command")}

@router.post("/scan/{agent_id}")
async def request_agent_scan(agent_id: str, scan_type: str = "full", current_user: dict = Depends(get_current_user)):
    """Request an agent to perform a scan"""
    message = WSMessage(
        type=WSMessageType.SCAN_REQUEST,
        payload={
            "scan_type": scan_type,
            "requested_by": current_user.get("name", "admin")
        }
    )
    
    result = await realtime_ws.send_to_agent(agent_id, message)
    if not result:
        raise HTTPException(status_code=404, detail="Agent not connected")
    
    return {"message": "Scan requested", "agent_id": agent_id, "scan_type": scan_type}
