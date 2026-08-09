"""
Arda Fabric Router
==================
Exposes the Arda Fabric peer mesh and WireGuard transport verification layer.
Endpoints:
  GET  /api/fabric/peers              — list all known fabric peers
  POST /api/fabric/handshake/initiate — initiate TPM handshake with remote peer
  POST /api/fabric/handshake/verify   — verify handshake response
  GET  /api/fabric/peer/{node_id}     — get peer state and influence budget
  GET  /api/fabric/local-node         — get local node identity
  POST /api/fabric/summons            — broadcast sovereign summons across mesh
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Any, Dict, Optional
import socket

from .dependencies import get_current_user, check_permission, get_db

router = APIRouter(prefix="/fabric", tags=["Arda Fabric"])


class HandshakeInitRequest(BaseModel):
    remote_node_id: str


class HandshakeVerifyRequest(BaseModel):
    session_id: str
    secret_fire_packet: Dict[str, Any]


class SummonsRequest(BaseModel):
    payload: Dict[str, Any]


@router.get("/peers")
async def list_peers(current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    """List all peers known to the Arda Fabric engine, merged with VPN peers."""
    try:
        from services.arda_fabric import get_arda_fabric
        fabric = get_arda_fabric()

        # Build a pubkey index from VPN peers so we can enrich fabric peers
        vpn_pubkey_index: dict = {}
        agent_index: dict = {}
        try:
            from vpn_integration import vpn_manager
            for vp in vpn_manager.get_peers():
                pk = vp.get("public_key", "")
                pid = vp.get("peer_id") or vp.get("name") or ""
                if pid:
                    vpn_pubkey_index[str(pid)] = vp
            if db is not None and getattr(db, "unified_agents", None) is not None:
                agent_rows = await db.unified_agents.find(
                    {},
                    {"_id": 0, "agent_id": 1, "hostname": 1, "ip_address": 1, "status": 1},
                ).limit(250).to_list(250)
                agent_index = {
                    str(row.get("agent_id") or row.get("hostname") or ""): row
                    for row in agent_rows
                    if str(row.get("agent_id") or row.get("hostname") or "").strip()
                }
        except Exception:
            pass

        seen_node_ids: set = set()
        peers = []

        # Fabric-attested peers first
        for node_id, peer in fabric.known_peers.items():
            budget = peer.get("influence_budget")
            vp = vpn_pubkey_index.get(str(node_id), {})
            wg_pubkey = peer.get("wg_pubkey", "") or vp.get("public_key", "")
            is_verified = peer.get("is_peer_verified", False) or bool(wg_pubkey)
            seen_node_ids.add(str(node_id))
            peers.append({
                "node_id": node_id,
                "hostname": peer.get("hostname") or vp.get("name") or node_id,
                "ip": peer.get("ip") or str(vp.get("allowed_ips", "")).split("/")[0],
                "wg_pubkey": wg_pubkey,
                "last_handshake": peer.get("last_handshake") or vp.get("last_handshake"),
                "is_peer_verified": is_verified,
                "constitutional_state": getattr(budget, "constitutional_state", "transport_discovered") if budget else "transport_discovered",
                "network_trust": getattr(budget, "network_trust", 0.75) if budget else 0.75,
                "source": "fabric",
            })

        # Add remaining VPN peers not already represented in fabric
        for peer_id, vp in vpn_pubkey_index.items():
            if str(peer_id) in seen_node_ids:
                continue
            agent = agent_index.get(str(peer_id)) or agent_index.get(str(vp.get("name") or ""))
            peers.append({
                "node_id": peer_id or vp.get("name") or "unknown-peer",
                "hostname": vp.get("name") or (agent or {}).get("hostname") or peer_id,
                "ip": ((agent or {}).get("ip_address") or str(vp.get("allowed_ips", "")).split("/")[0]),
                "wg_pubkey": vp.get("public_key", ""),
                "last_handshake": vp.get("last_handshake"),
                "is_peer_verified": bool(vp.get("public_key")),
                "constitutional_state": "transport_discovered",
                "network_trust": 0.5 if vp.get("public_key") else 0.0,
                "source": "vpn_peers",
            })

        return {"peers": peers, "count": len(peers)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/local-node")
async def get_local_node(current_user: dict = Depends(get_current_user)):
    """Get the local node's sovereign identity."""
    try:
        from services.arda_fabric import get_arda_fabric
        from vpn_integration import vpn_manager
        fabric = get_arda_fabric()
        node_id = await fabric.get_local_node_id()
        server_pubkey = None
        try:
            server_pubkey = getattr(getattr(vpn_manager.server, "server_config", None), "public_key", None)
        except Exception:
            server_pubkey = None
        return {
            "node_id": node_id,
            "hostname": getattr(fabric, "hostname", None) or socket.gethostname(),
            "wg_pubkey": getattr(getattr(fabric, "wireguard_identity", None), "public_key", None) or server_pubkey,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/handshake/initiate")
async def initiate_handshake(
    req: HandshakeInitRequest,
    current_user: dict = Depends(check_permission("write")),
):
    """Initiate a TPM-attested handshake with a remote peer."""
    try:
        from services.arda_fabric import get_arda_fabric
        fabric = get_arda_fabric()
        session_id = await fabric.initiate_handshake(req.remote_node_id)
        return {"session_id": session_id, "remote_node_id": req.remote_node_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/handshake/verify")
async def verify_handshake(
    req: HandshakeVerifyRequest,
    current_user: dict = Depends(check_permission("write")),
):
    """Verify a peer's handshake response (TPM quote + secret fire packet)."""
    try:
        from services.arda_fabric import get_arda_fabric
        fabric = get_arda_fabric()
        verified = await fabric.verify_handshake(req.session_id, req.secret_fire_packet)
        return {"verified": verified, "session_id": req.session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/peer/{node_id}")
async def get_peer(node_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific peer's state and influence budget."""
    try:
        from services.arda_fabric import get_arda_fabric
        fabric = get_arda_fabric()
        peer = fabric.known_peers.get(node_id)
        if not peer:
            raise HTTPException(status_code=404, detail=f"Peer {node_id} not found")
        budget = peer.get("influence_budget")
        return {
            "node_id": node_id,
            "peer": {k: v for k, v in peer.items() if k != "influence_budget"},
            "constitutional_state": budget.model_dump() if hasattr(budget, "model_dump") else vars(budget) if budget else None,
            "transport_verified": peer.get("is_peer_verified", False),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transport-lock/{node_id}")
async def check_transport_lock(node_id: str, current_user: dict = Depends(get_current_user)):
    """Check whether a peer has a verified WireGuard transport lock."""
    try:
        from services.outbound_gate import OutboundGateService
        gate = OutboundGateService(db=None)
        locked = gate.verify_transport_lock(node_id)
        return {"node_id": node_id, "transport_locked": locked}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summons")
async def broadcast_summons(
    req: SummonsRequest,
    current_user: dict = Depends(check_permission("manage_users")),
):
    """Broadcast a sovereign summons across the fabric mesh."""
    try:
        from services.arda_fabric import get_arda_fabric
        fabric = get_arda_fabric()
        await fabric.broadcast_sovereign_summons(req.payload)
        return {"status": "dispatched"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
