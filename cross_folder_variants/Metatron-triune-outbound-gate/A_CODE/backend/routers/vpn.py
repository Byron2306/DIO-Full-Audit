"""
VPN Integration Router
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from fastapi.responses import PlainTextResponse
from typing import Optional
from pydantic import BaseModel

from .dependencies import get_current_user, check_permission, security
from .unified_agent import verify_agent_auth

# Import VPN service
from vpn_integration import vpn_manager, VPNManager

router = APIRouter(prefix="/vpn", tags=["VPN"])

class AddPeerRequest(BaseModel):
    name: str
    peer_id: Optional[str] = None
    public_key: Optional[str] = None
    hostname: Optional[str] = None
    platform: Optional[str] = None
    auto_setup: Optional[bool] = None
    allowed_ips: Optional[str] = None


class UpdateVPNConfigRequest(BaseModel):
    enabled: Optional[bool] = None
    type: Optional[str] = None
    server_address: Optional[str] = None
    port: Optional[int] = None
    dns_servers: Optional[list[str]] = None
    kill_switch_enabled: Optional[bool] = None
    split_tunnel_enabled: Optional[bool] = None
    server_endpoint: Optional[str] = None

async def get_vpn_identity(
    request: Request,
    x_agent_id: Optional[str] = Header(None),
    x_agent_token: Optional[str] = Header(None),
    x_enrollment_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    if x_agent_id or x_agent_token or x_enrollment_key:
        return await verify_agent_auth(
            request,
            x_agent_id=x_agent_id,
            x_agent_token=x_agent_token,
            x_enrollment_key=x_enrollment_key,
        )

    if authorization:
        credentials = await security(request)
        return await get_current_user(request=request, credentials=credentials)

    raise HTTPException(status_code=403, detail="Authentication required")

@router.get("/status")
async def get_vpn_status(auth: dict = Depends(get_vpn_identity)):
    """Get VPN server status"""
    status = await vpn_manager.get_status()

    if vpn_manager.server.server_config:
        status["server"]["public_key"] = vpn_manager.server.server_config.public_key

    if auth.get("type") == "authenticated":
        agent_id = auth.get("agent_id")
        status["peers"] = [
            peer for peer in status.get("peers", [])
            if peer.get("peer_id") == agent_id or peer.get("name") == agent_id
        ]
        status["clients_connected"] = len(status["peers"])
        status["agent_id"] = agent_id

    return status

@router.get("/clients")
async def get_vpn_clients(auth: dict = Depends(get_vpn_identity)):
    """Get VPN clients/peers"""
    peers = vpn_manager.get_peers()
    if auth.get("type") == "authenticated":
        agent_id = auth.get("agent_id")
        peers = [
            peer for peer in peers
            if peer.get("peer_id") == agent_id or peer.get("name") == agent_id
        ]
    return {"clients": peers, "count": len(peers)}

@router.post("/initialize")
async def initialize_vpn(current_user: dict = Depends(check_permission("write"))):
    """Initialize VPN server (generates keys and config)"""
    result = await vpn_manager.initialize()
    return result

@router.post("/start")
async def start_vpn(current_user: dict = Depends(check_permission("write"))):
    """Start VPN server"""
    result = await vpn_manager.start()
    return result

@router.post("/stop")
async def stop_vpn(current_user: dict = Depends(check_permission("write"))):
    """Stop VPN server"""
    result = await vpn_manager.stop()
    return result


@router.get("/config")
async def get_vpn_config(current_user: dict = Depends(get_current_user)):
    """Get editable VPN configuration"""
    return vpn_manager.get_config()


@router.put("/config")
async def update_vpn_config(
    request: UpdateVPNConfigRequest,
    current_user: dict = Depends(check_permission("write")),
):
    """Update editable VPN configuration"""
    return await vpn_manager.update_config(request.model_dump(exclude_none=True))

@router.get("/peers")
async def get_peers(auth: dict = Depends(get_vpn_identity)):
    """Get VPN peers"""
    peers = vpn_manager.get_peers()
    if auth.get("type") == "authenticated":
        agent_id = auth.get("agent_id")
        peers = [
            peer for peer in peers
            if peer.get("peer_id") == agent_id or peer.get("name") == agent_id
        ]
    return {"peers": peers, "count": len(peers)}

@router.post("/peers")
async def add_peer(request: AddPeerRequest, auth: dict = Depends(get_vpn_identity)):
    """Add a new VPN peer/client"""
    if auth.get("type") == "authenticated":
        if request.name != auth.get("agent_id"):
            raise HTTPException(status_code=403, detail="Agent may only register its own VPN peer")
        peer_id = request.peer_id or auth.get("agent_id")
    else:
        peer_id = request.peer_id

    peer = await vpn_manager.add_peer(request.name, peer_id=peer_id, allowed_ips=request.allowed_ips)
    return {"message": "Peer added", "peer": peer}

@router.get("/peers/{peer_id}/config")
async def get_peer_config(peer_id: str, auth: dict = Depends(get_vpn_identity)):
    """Get WireGuard configuration file for a peer"""
    if auth.get("type") == "authenticated" and auth.get("agent_id") != peer_id:
        raise HTTPException(status_code=403, detail="Agent may only request its own VPN config")

    config = vpn_manager.get_peer_config(peer_id)
    if not config:
        raise HTTPException(status_code=404, detail="Peer not found")
    return PlainTextResponse(content=config, media_type="text/plain")

@router.delete("/peers/{peer_id}")
async def remove_peer(peer_id: str, current_user: dict = Depends(check_permission("write"))):
    """Remove a VPN peer"""
    success = await vpn_manager.remove_peer(peer_id)
    if not success:
        raise HTTPException(status_code=404, detail="Peer not found")
    return {"message": "Peer removed"}

@router.get("/kill-switch")
async def get_kill_switch_status(current_user: dict = Depends(get_current_user)):
    """Get kill switch status"""
    return vpn_manager.kill_switch.get_status()

@router.post("/kill-switch/enable")
async def enable_kill_switch(current_user: dict = Depends(check_permission("manage_users"))):
    """Enable VPN kill switch"""
    result = await vpn_manager.kill_switch.enable()
    return result

@router.post("/kill-switch/disable")
async def disable_kill_switch(current_user: dict = Depends(check_permission("manage_users"))):
    """Disable VPN kill switch"""
    result = await vpn_manager.kill_switch.disable()
    return result
