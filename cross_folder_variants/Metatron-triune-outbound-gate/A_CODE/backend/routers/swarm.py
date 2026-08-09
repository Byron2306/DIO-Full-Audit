"""
Swarm Management Router
=======================
Manages the agent swarm - discovery, deployment, telemetry.
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
import uuid

from .dependencies import get_current_user, check_permission, db

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/swarm", tags=["Swarm Management"])

# Default server URL embedded in the Windows batch installer.
# Kept as a constant so it only needs to be updated in one place.
_BAT_DEFAULT_SERVER_URL = "http://165.22.41.184:8001"

SWARM_CONTROL_PLANE_CONTRACT_VERSION = "2026-03-07.1"


# =============================================================================
# MODELS
# =============================================================================

class ScanNetworkRequest(BaseModel):
    network: Optional[str] = None  # e.g., "192.168.1.0/24"


class DeployAgentRequest(BaseModel):
    device_ip: str
    credentials: Optional[dict] = None


class DeploymentCredentials(BaseModel):
    method: str  # "ssh" or "winrm"
    username: str
    password: Optional[str] = None
    key_path: Optional[str] = None


class TelemetryIngestRequest(BaseModel):
    events: List[dict]


class CLIEventRequest(BaseModel):
    host_id: str
    session_id: str
    command: str
    user: Optional[str] = None
    shell_type: Optional[str] = None
    timestamp: Optional[str] = None


class ScannerReportRequest(BaseModel):
    scanner_id: str
    network: str
    scan_time: str
    devices: List[dict]
    auto_deploy_request: Optional[bool] = False  # Request auto-deployment of unified agent


class AgentRegistrationRequest(BaseModel):
    agent_id: str
    hostname: str
    os_type: str
    version: str
    ip_address: Optional[str] = None


class AgentHeartbeatRequest(BaseModel):
    status: str = "online"
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    uptime: Optional[int] = None


# =============================================================================
# AGENT REGISTRATION & HEARTBEAT
# =============================================================================

@router.post("/agents/register")
async def register_agent(request: AgentRegistrationRequest):
    """Register a new Seraph Defender agent"""
    now = datetime.now(timezone.utc).isoformat()
    
    # Fields to always update
    update_doc = {
        "agent_id": request.agent_id,
        "hostname": request.hostname,
        "os": request.os_type,
        "version": request.version,
        "ip_address": request.ip_address,
        "status": "online",
        "last_seen": now
    }
    
    await db.agents.update_one(
        {"agent_id": request.agent_id},
        {
            "$set": update_doc,
            "$setOnInsert": {"first_seen": now}
        },
        upsert=True
    )
    
    logger.info(f"Agent registered: {request.agent_id} ({request.hostname})")
    
    return {
        "status": "ok",
        "message": "Agent registered successfully",
        "agent_id": request.agent_id,
        "contract_version": SWARM_CONTROL_PLANE_CONTRACT_VERSION,
    }


@router.post("/agents/{agent_id}/heartbeat")
async def agent_heartbeat(agent_id: str, request: AgentHeartbeatRequest):
    """Receive heartbeat from agent"""
    now = datetime.now(timezone.utc).isoformat()
    
    update_doc = {
        "status": request.status,
        "last_seen": now
    }
    
    if request.cpu_percent is not None:
        update_doc["cpu_percent"] = request.cpu_percent
    if request.memory_percent is not None:
        update_doc["memory_percent"] = request.memory_percent
    if request.uptime is not None:
        update_doc["uptime"] = request.uptime
    
    result = await db.agents.update_one(
        {"agent_id": agent_id},
        {"$set": update_doc}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return {"status": "ok", "timestamp": now}


# =============================================================================
# AGENT COMMAND QUEUE (Server -> Agent)
# =============================================================================

class AgentCommandRequest(BaseModel):
    type: str  # kill_process, block_ip, scan, quarantine_file
    params: dict = {}
    priority: str = "normal"  # low, normal, high, critical


@router.post("/agents/{agent_id}/command")
async def send_command_to_agent(
    agent_id: str,
    request: AgentCommandRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Send a command to an agent for execution"""
    now = datetime.now(timezone.utc).isoformat()
    
    command_doc = {
        "command_id": f"cmd-{uuid.uuid4().hex[:8]}",
        "agent_id": agent_id,
        "type": request.type,
        "params": request.params,
        "priority": request.priority,
        "status": "pending",
        "state_version": 1,
        "state_transition_log": [
            {
                "from_status": None,
                "to_status": "pending",
                "actor": current_user.get("email", "system"),
                "reason": "command queued",
                "timestamp": now,
            }
        ],
        "created_at": now,
        "created_by": current_user.get("email", "system")
    }
    
    await db.agent_commands.insert_one(command_doc)
    
    logger.info(f"Command queued for agent {agent_id}: {request.type}")
    
    return {
        "status": "ok",
        "command_id": command_doc["command_id"],
        "message": f"Command {request.type} queued for agent {agent_id}",
        "contract_version": SWARM_CONTROL_PLANE_CONTRACT_VERSION,
    }


@router.get("/agents/{agent_id}/commands")
async def get_pending_commands(agent_id: str):
    """Get pending commands for an agent (agent polls this)"""
    cursor = db.agent_commands.find(
        {"agent_id": agent_id, "status": "pending"},
        {"_id": 0}
    ).sort("created_at", 1)
    
    commands = await cursor.to_list(100)
    
    # Mark as delivered
    for cmd in commands:
        delivery_now = datetime.now(timezone.utc).isoformat()
        await db.agent_commands.update_one(
            {
                "command_id": cmd["command_id"],
                "agent_id": agent_id,
                "status": "pending",
            },
            {
                "$set": {
                    "status": "delivered",
                    "delivered_at": delivery_now,
                    "updated_at": delivery_now,
                },
                "$inc": {"state_version": 1},
                "$push": {
                    "state_transition_log": {
                        "from_status": "pending",
                        "to_status": "delivered",
                        "actor": f"agent:{agent_id}",
                        "reason": "agent polled commands",
                        "timestamp": delivery_now,
                    }
                },
            }
        )
    
    return {"commands": commands}


@router.post("/agents/{agent_id}/commands/{command_id}/ack")
async def acknowledge_command(agent_id: str, command_id: str, result: dict = None):
    """Agent acknowledges command execution"""
    now = datetime.now(timezone.utc).isoformat()
    
    ack_status = "completed" if result and result.get("success") else "failed"
    update_result = await db.agent_commands.update_one(
        {
            "command_id": command_id,
            "agent_id": agent_id,
            "status": {"$in": ["pending", "delivered"]},
        },
        {
            "$set": {
                "status": ack_status,
                "completed_at": now,
                "result": result,
                "updated_at": now,
            },
            "$inc": {"state_version": 1},
            "$push": {
                "state_transition_log": {
                    "from_status": ["pending", "delivered"],
                    "to_status": ack_status,
                    "actor": f"agent:{agent_id}",
                    "reason": "agent acknowledged command",
                    "timestamp": now,
                }
            },
        }
    )

    if getattr(update_result, "matched_count", 0) == 0:
        existing = await db.agent_commands.find_one(
            {"command_id": command_id, "agent_id": agent_id},
            {"_id": 0, "status": 1},
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Command not found")
        raise HTTPException(
            status_code=409,
            detail=f"Command is already terminal (status={existing.get('status')})",
        )
    
    return {"status": "ok"}


@router.get("/agents/{agent_id}/command-history")
async def get_command_history(
    agent_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get command history for an agent"""
    cursor = db.agent_commands.find(
        {"agent_id": agent_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(50)
    
    commands = await cursor.to_list(50)
    
    return {"commands": commands}


# =============================================================================
# THREAT RESPONSE (Server-initiated remediation)
# =============================================================================

@router.post("/threats/respond")
async def respond_to_threat(
    threat_id: str,
    action: str,
    target_agent: str,
    params: dict = None,
    current_user: dict = Depends(check_permission("write"))
):
    """Send a remediation command to an agent in response to a threat"""
    
    # Create command for agent
    command_doc = {
        "command_id": f"cmd-{uuid.uuid4().hex[:8]}",
        "agent_id": target_agent,
        "type": action,
        "params": params or {},
        "priority": "critical",
        "status": "pending",
        "state_version": 1,
        "state_transition_log": [
            {
                "from_status": None,
                "to_status": "pending",
                "actor": current_user.get("email", "system"),
                "reason": "threat response command queued",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user.get("email", "system"),
        "threat_id": threat_id
    }
    
    await db.agent_commands.insert_one(command_doc)
    
    # Log the response
    await db.threat_responses.insert_one({
        "threat_id": threat_id,
        "action": action,
        "target_agent": target_agent,
        "command_id": command_doc["command_id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "initiated_by": current_user.get("email", "system")
    })
    
    return {
        "status": "ok",
        "message": f"Remediation command sent to agent {target_agent}",
        "command_id": command_doc["command_id"]
    }


# =============================================================================
# NETWORK DISCOVERY
# =============================================================================

@router.post("/scanner/report")
async def receive_scanner_report(request: ScannerReportRequest):
    """
    Receive device reports from network scanners running on user's LAN.
    This is the PRIMARY way devices get into the system.
    """
    now = datetime.now(timezone.utc).isoformat()
    
    # Track the scanner
    await db.network_scanners.update_one(
        {"scanner_id": request.scanner_id},
        {
            "$set": {
                "scanner_id": request.scanner_id,
                "network": request.network,
                "last_report": now,
                "last_device_count": len(request.devices)
            },
            "$inc": {"total_reports": 1}
        },
        upsert=True
    )
    
    new_devices = 0
    updated_devices = 0
    
    for device in request.devices:
        ip = device.get('ip_address')
        if not ip:
            continue
        
        # Determine risk score
        risk_score = 30  # Base risk
        if not device.get('deployable', False):
            risk_score += 20  # Higher risk if can't deploy agent
        if device.get('os') == 'unknown':
            risk_score += 15
        if device.get('device_type') == 'iot':
            risk_score += 10
        
        device_doc = {
            "ip_address": ip,
            "mac_address": device.get('mac_address'),
            "hostname": device.get('hostname'),
            "vendor": device.get('vendor'),
            "os_type": device.get('os', 'unknown'),
            "device_type": device.get('device_type', 'unknown'),
            "open_ports": device.get('open_ports', []),
            "discovery_method": device.get('discovery_method'),
            "deployable": device.get('deployable', False),
            "mobile_manageable": device.get('mobile_manageable', False),
            "risk_score": min(risk_score, 100),
            "last_seen": now,
            "scanner_id": request.scanner_id,
            "network": request.network
        }
        
        # Upsert device
        result = await db.discovered_devices.update_one(
            {"ip_address": ip},
            {
                "$set": device_doc,
                "$setOnInsert": {
                    "first_seen": now,
                    "deployment_status": "discovered",
                    "is_managed": False
                }
            },
            upsert=True
        )
        
        if result.upserted_id:
            new_devices += 1
        else:
            updated_devices += 1
    
    logger.info(f"Scanner {request.scanner_id} reported {len(request.devices)} devices ({new_devices} new, {updated_devices} updated)")
    
    # Auto-deploy unified agents to deployable devices if requested
    auto_deploy_queued = 0
    if request.auto_deploy_request or True:  # Always attempt auto-deploy for deployable devices
        for device in request.devices:
            ip = device.get('ip_address')
            if not ip:
                continue
            
            # Only auto-deploy to deployable devices that are not already managed
            if device.get('deployable', False):
                # Check if device is already managed
                existing_agent = await db.unified_agents.find_one({"ip_address": ip})
                if existing_agent:
                    continue
                
                # Check deployment status
                existing_device = await db.discovered_devices.find_one({"ip_address": ip})
                if existing_device and existing_device.get('deployment_status') in ['deployed', 'deploying', 'queued']:
                    continue
                
                # Queue for auto-deployment
                await db.discovered_devices.update_one(
                    {"ip_address": ip},
                    {"$set": {
                        "deployment_status": "queued",
                        "deployment_queued_at": now,
                        "deployment_method": "auto"
                    }}
                )
                
                # Create deployment task
                deploy_task = {
                    "task_id": f"deploy-{uuid.uuid4().hex[:8]}",
                    "target_ip": ip,
                    "target_hostname": device.get('hostname'),
                    "target_os": device.get('os', device.get('os_type', 'unknown')),
                    "status": "pending",
                    "created_at": now,
                    "method": "auto",
                    "agent_type": "unified"
                }
                await db.deployment_tasks.insert_one(deploy_task)
                auto_deploy_queued += 1
    
    return {
        "status": "ok",
        "message": f"Received {len(request.devices)} devices",
        "new_devices": new_devices,
        "updated_devices": updated_devices,
        "auto_deploy_queued": auto_deploy_queued,
        "contract_version": SWARM_CONTROL_PLANE_CONTRACT_VERSION,
    }


@router.get("/scanners")
async def get_network_scanners(current_user: dict = Depends(get_current_user)):
    """Get list of active network scanners"""
    cursor = db.network_scanners.find({}, {"_id": 0})
    scanners = await cursor.to_list(100)
    return {"scanners": scanners}


@router.get("/devices")
async def get_discovered_devices(
    status: Optional[str] = None,
    os_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all discovered devices"""
    query = {}
    if status:
        query["deployment_status"] = status
    if os_type:
        query["os_type"] = os_type
    
    cursor = db.discovered_devices.find(query, {"_id": 0})
    devices = await cursor.to_list(500)
    
    # Calculate stats
    stats = {
        "total": len(devices),
        "managed": sum(1 for d in devices if d.get("is_managed")),
        "unmanaged": sum(1 for d in devices if not d.get("is_managed")),
        "by_os": {},
        "by_status": {},
        "high_risk": sum(1 for d in devices if d.get("risk_score", 0) >= 50)
    }
    
    for d in devices:
        os_type = d.get("os_type", "unknown")
        stats["by_os"][os_type] = stats["by_os"].get(os_type, 0) + 1
        
        status = d.get("deployment_status", "discovered")
        stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
    
    return {"devices": devices, "stats": stats}


@router.post("/scan")
async def trigger_network_scan(
    request: ScanNetworkRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(check_permission("write"))
):
    """Trigger a network scan"""
    from services.network_discovery import get_network_discovery, start_network_discovery
    
    discovery = get_network_discovery()
    if discovery is None:
        # Auto-start the discovery service on first use
        try:
            discovery = await start_network_discovery(db, scan_interval_s=300)
            logger.info("Started NetworkDiscoveryService on demand for /swarm/scan")
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Network discovery service could not be started: {exc}"
            )
    
    # Run scan in background
    async def run_scan():
        await discovery.trigger_manual_scan(request.network)
    
    background_tasks.add_task(run_scan)
    
    return {"message": "Network scan initiated", "network": request.network or "all"}


@router.get("/scan/status")
async def get_scan_status(current_user: dict = Depends(get_current_user)):
    """Get current scan status"""
    from services.network_discovery import get_network_discovery, start_network_discovery
    
    discovery = get_network_discovery()
    if discovery is None:
        return {"running": False, "message": "Discovery service not active"}
    
    return {
        "running": discovery.running,
        "devices_found": len(discovery.discovered_devices),
        "last_scan": discovery.discovered_devices and max(
            d.last_seen for d in discovery.discovered_devices.values()
        ) if discovery.discovered_devices else None
    }


# =============================================================================
# AGENT DOWNLOAD
# =============================================================================

@router.get("/agent/download/{platform}")
async def download_agent(platform: str, request: Request, server_url: Optional[str] = None):
    """
    Download the Seraph agent for the specified platform.

    All agent platforms now serve the Unified Agent package.
    Legacy platform names (linux, windows, macos, local, v7, full, scanner,
    mobile, mobile-v7, mobile-full) are silently mapped to the canonical
    unified agent endpoints so existing bookmarks and installers keep working.

    Special platforms that still serve distinct content:
      - windows-installer / batch  → install_seraph_windows.bat
      - browser-extension          → browser extension ZIP
    """
    from fastapi.responses import FileResponse, StreamingResponse, Response
    import io, os, zipfile, tarfile

    UNIFIED_AGENT_DIR = "/app/unified_agent"

    # ── Windows batch installer ──────────────────────────────────────────────
    if platform in ("windows-installer", "batch"):
        batch_path = "/app/scripts/install_seraph_windows.bat"
        if not os.path.exists(batch_path):
            raise HTTPException(status_code=404, detail="Windows installer not found")

        # Derive the backend server URL from the inbound request.
        # In production, nginx sets the Host header correctly so
        # request.base_url reflects the actual public address of the Droplet.
        if not server_url:
            base = request.base_url          # e.g. http://165.22.41.184:8001/
            server_url = str(base).rstrip("/")

        with open(batch_path, "r", encoding="utf-8") as fh:
            content = fh.read()

        # Replace the hard-coded default server URL with the live one.
        content = content.replace(
            f'set "SERAPH_SERVER={_BAT_DEFAULT_SERVER_URL}"',
            f'set "SERAPH_SERVER={server_url}"',
            1,
        )

        return Response(
            content=content.encode("utf-8"),
            media_type="application/x-bat",
            headers={"Content-Disposition": "attachment; filename=install_seraph_windows.bat"},
        )

    # ── Browser extension ZIP ────────────────────────────────────────────────
    if platform == "browser-extension":
        extension_dir = "/app/scripts/browser_extension"
        if not os.path.exists(extension_dir):
            raise HTTPException(status_code=404, detail="Browser extension not found")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(extension_dir):
                for fname in files:
                    fp = os.path.join(root, fname)
                    zf.write(fp, os.path.relpath(fp, extension_dir))
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=seraph_browser_shield.zip"},
        )

    # ── Windows ZIP (unified agent) ──────────────────────────────────────────
    if platform in ("windows",):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in ("core", "requirements.txt"):
                item_path = os.path.join(UNIFIED_AGENT_DIR, item)
                if not os.path.exists(item_path):
                    continue
                if os.path.isdir(item_path):
                    for root, _dirs, files in os.walk(item_path):
                        for fname in files:
                            fp = os.path.join(root, fname)
                            zf.write(fp, os.path.relpath(fp, UNIFIED_AGENT_DIR))
                else:
                    zf.write(item_path, item)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=seraph-agent-windows.zip"},
        )

    # ── All other platform names → unified agent tarball (Linux / macOS / etc.)
    # Accepted aliases: linux, macos, local, v7, full, scanner, mobile,
    #                   mobile-v7, mobile-full, and any future names.
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for item in ("core", "requirements.txt"):
            item_path = os.path.join(UNIFIED_AGENT_DIR, item)
            if os.path.exists(item_path):
                tar.add(item_path, arcname=item)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/gzip",
        headers={"Content-Disposition": "attachment; filename=seraph-agent.tar.gz"},
    )


# =============================================================================
# WIREGUARD VPN AUTO-CONFIGURATION FOR AGENTS
# =============================================================================

class VPNConfigRequest(BaseModel):
    agent_id: str
    agent_public_key: Optional[str] = None


@router.get("/vpn/server-config")
async def get_vpn_server_config():
    """
    Get VPN server configuration for agents.
    Returns server public key and endpoint for split-tunnel VPN setup.
    Agents only route Seraph network traffic - does NOT block internet.
    """
    import os
    
    # Read server public key if available
    server_public_key = os.environ.get('WIREGUARD_PUBLIC_KEY', '')
    server_endpoint = os.environ.get('WIREGUARD_ENDPOINT', '')
    
    # Try to read from WireGuard config if not in env
    if not server_public_key:
        try:
            wg_pubkey_path = '/etc/wireguard/publickey'
            if os.path.exists(wg_pubkey_path):
                with open(wg_pubkey_path, 'r') as f:
                    server_public_key = f.read().strip()
        except Exception:
            pass
    
    # If still no config, provide placeholder
    if not server_public_key:
        return {
            "configured": False,
            "message": "VPN server not configured. Contact administrator.",
            "split_tunnel": True,
            "allowed_ips": "10.200.200.0/24",
            "note": "Split tunnel mode - normal internet NOT affected"
        }
    
    return {
        "configured": True,
        "server_public_key": server_public_key,
        "server_endpoint": server_endpoint or "your-server:51820",
        "allowed_ips": "10.200.200.0/24",
        "dns": None,  # No DNS change = split tunnel
        "split_tunnel": True,
        "note": "Split tunnel mode - only Seraph traffic routed through VPN"
    }


@router.post("/vpn/register-agent")
async def register_vpn_agent(request: VPNConfigRequest):
    """
    Register an agent for VPN access.
    Agent provides its public key, server assigns an IP.
    """
    now = datetime.now(timezone.utc).isoformat()
    
    # Assign IP based on agent_id hash
    import hashlib
    agent_hash = int(hashlib.md5(request.agent_id.encode()).hexdigest()[:8], 16)
    client_num = (agent_hash % 200) + 10  # Range: 10-209
    assigned_ip = f"10.200.200.{client_num}/32"
    
    # Store agent VPN registration
    vpn_doc = {
        "agent_id": request.agent_id,
        "agent_public_key": request.agent_public_key,
        "assigned_ip": assigned_ip,
        "registered_at": now,
        "last_seen": now,
        "status": "registered"
    }
    
    await db.vpn_agents.update_one(
        {"agent_id": request.agent_id},
        {"$set": vpn_doc},
        upsert=True
    )
    
    return {
        "status": "registered",
        "agent_id": request.agent_id,
        "assigned_ip": assigned_ip,
        "message": "VPN registration successful. Configure WireGuard with the provided IP."
    }


@router.get("/vpn/agents")
async def list_vpn_agents(current_user: dict = Depends(get_current_user)):
    """List all registered VPN agents"""
    cursor = db.vpn_agents.find({}, {"_id": 0})
    agents = await cursor.to_list(100)
    return {"agents": agents, "count": len(agents)}


# =============================================================================
# SIEM INTEGRATION
# =============================================================================

@router.get("/siem/status")
async def get_siem_status(current_user: dict = Depends(get_current_user)):
    """Get SIEM integration status"""
    from services.siem import siem_service
    return siem_service.get_status()


@router.post("/siem/test")
async def test_siem_connection(current_user: dict = Depends(check_permission("write"))):
    """Send test event to SIEM"""
    from services.siem import siem_service
    
    if not siem_service.enabled:
        return {
            "success": False,
            "message": "SIEM not configured. Set ELASTICSEARCH_URL, SPLUNK_HEC_URL, or SYSLOG_SERVER"
        }
    
    siem_service.log_event(
        event_type="test.connection",
        severity="info",
        data={
            "message": "Test event from Seraph AI",
            "test_timestamp": datetime.now(timezone.utc).isoformat()
        },
        immediate=True
    )
    
    return {
        "success": True,
        "message": f"Test event sent to {siem_service.siem_type}",
        "siem_type": siem_service.siem_type
    }


# =============================================================================
# AGENT DEPLOYMENT
# =============================================================================

@router.post("/deploy")
async def deploy_agent_to_device(
    request: DeployAgentRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Deploy agent to a specific device"""
    from services.agent_deployment import get_deployment_service
    
    service = get_deployment_service()
    if service is None:
        raise HTTPException(status_code=503, detail="Deployment service not running")
    
    # Get device info
    device = await db.discovered_devices.find_one({"ip_address": request.device_ip}, {"_id": 0})
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    task = await service.queue_deployment(
        device_ip=request.device_ip,
        device_hostname=device.get("hostname"),
        os_type=device.get("os_type", "unknown"),
        credentials=request.credentials
    )
    
    return {
        "message": "Deployment queued",
        "device_ip": request.device_ip,
        "status": task.status,
        "contract_version": SWARM_CONTROL_PLANE_CONTRACT_VERSION,
    }


@router.post("/deploy/batch")
async def deploy_agents_batch(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(check_permission("write"))
):
    """Deploy agents to all deployable devices"""
    from services.agent_deployment import get_deployment_service, start_deployment_service
    
    service = get_deployment_service()
    
    # If service not running, try to start it
    if service is None:
        try:
            import os
            api_url = os.environ.get('API_URL', 'http://localhost:8001')
            service = await start_deployment_service(db, api_url)
            logger.info("Deployment service started on-demand")
        except Exception as e:
            logger.error(f"Failed to start deployment service: {e}")
            raise HTTPException(status_code=503, detail=f"Deployment service could not be started: {str(e)}")
    
    # Get deployable devices - case-insensitive OS check
    cursor = db.discovered_devices.find({
        "deployment_status": {"$in": ["discovered", "failed", None]},
        "$or": [
            {"os_type": {"$regex": "^(windows|linux|macos|darwin)$", "$options": "i"}},
            {"deployable": True}
        ]
    }, {"_id": 0})
    devices = await cursor.to_list(100)
    
    if not devices:
        # Check total devices for better error message
        total_devices = await db.discovered_devices.count_documents({})
        return {
            "message": f"No deployable devices found (total devices: {total_devices}). Devices need OS type (Windows/Linux/macOS) or deployable=True flag.",
            "devices": [],
            "total_devices_in_db": total_devices,
            "contract_version": SWARM_CONTROL_PLANE_CONTRACT_VERSION,
        }
    
    queued = []
    errors = []
    for device in devices:
        try:
            task_id = await service.queue_deployment(
                device_ip=device["ip_address"],
                device_hostname=device.get("hostname"),
                os_type=device.get("os_type", "unknown")
            )
            queued.append({
                "ip": device["ip_address"],
                "hostname": device.get("hostname"),
                "os_type": device.get("os_type"),
                "task_id": task_id
            })
            
            # Update device status
            await db.discovered_devices.update_one(
                {"ip_address": device["ip_address"]},
                {"$set": {"deployment_status": "queued"}}
            )
        except Exception as e:
            error_msg = f"Failed to queue deployment for {device['ip_address']}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    logger.info(f"Batch deployment: queued {len(queued)} devices, {len(errors)} errors")
    
    return {
        "message": f"Batch deployment initiated for {len(queued)} devices",
        "devices": queued,
        "errors": errors if errors else None,
        "contract_version": SWARM_CONTROL_PLANE_CONTRACT_VERSION,
    }


@router.get("/deployment/status")
async def get_deployment_status(
    device_ip: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get deployment task status"""
    from services.agent_deployment import get_deployment_service
    
    service = get_deployment_service()
    if service is None:
        return {"tasks": [], "message": "Deployment service not running"}
    
    tasks = await service.get_deployment_status(device_ip)
    
    return {
        "tasks": tasks,
        "queue_size": service.deployment_queue.qsize() if service else 0
    }


@router.post("/deployment/retry")
async def retry_failed_deployments(
    current_user: dict = Depends(check_permission("write"))
):
    """Retry all failed deployments"""
    from services.agent_deployment import get_deployment_service
    
    service = get_deployment_service()
    if service is None:
        raise HTTPException(status_code=503, detail="Deployment service not running")
    
    count = await service.retry_failed_deployments()
    
    return {"message": f"Retrying {count} failed deployments"}


@router.post("/credentials")
async def set_deployment_credentials(
    credentials: DeploymentCredentials,
    current_user: dict = Depends(check_permission("admin"))
):
    """Set default deployment credentials"""
    from services.agent_deployment import get_deployment_service
    
    service = get_deployment_service()
    if service is None:
        raise HTTPException(status_code=503, detail="Deployment service not running")
    
    creds = {}
    if credentials.username:
        creds["username"] = credentials.username
    if credentials.password:
        creds["password"] = credentials.password
    if credentials.key_path:
        creds["key_path"] = credentials.key_path
    
    service.set_credentials(credentials.method, creds)
    
    return {"message": f"Credentials updated for {credentials.method}"}


@router.post("/deploy/single")
async def deploy_to_single_device(
    device_ip: str,
    os_type: str = "windows",
    username: str = None,
    password: str = None,
    current_user: dict = Depends(check_permission("write"))
):
    """Deploy agent to a single device with credentials"""
    from services.agent_deployment import get_deployment_service, start_deployment_service
    import os
    
    service = get_deployment_service()
    
    # If service not running, start it
    if service is None:
        try:
            api_url = os.environ.get('API_URL', 'http://localhost:8001')
            service = await start_deployment_service(db, api_url)
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Could not start deployment service: {e}")
    
    # Build credentials
    credentials = None
    if username and password:
        credentials = {
            "username": username,
            "password": password
        }
    
    try:
        task_id = await service.queue_deployment(
            device_ip=device_ip,
            device_hostname=None,
            os_type=os_type,
            credentials=credentials
        )
        
        return {
            "message": f"Deployment queued for {device_ip}",
            "task_id": task_id,
            "os_type": os_type,
            "method": "winrm" if os_type.lower() == "windows" else "ssh"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue deployment: {e}")


@router.post("/deploy/winrm")
async def deploy_via_winrm(
    device_ip: str,
    username: str,
    password: str,
    use_ssl: bool = False,
    port: Optional[int] = None,
    transport: str = "ntlm",
    server_cert_validation: str = "ignore",
    current_user: dict = Depends(check_permission("write"))
):
    """Deploy agent to Windows device via WinRM"""
    from services.agent_deployment import get_deployment_service, start_deployment_service
    import os
    
    service = get_deployment_service()
    
    if service is None:
        try:
            api_url = os.environ.get('API_URL', 'http://localhost:8001')
            service = await start_deployment_service(db, api_url)
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Could not start deployment service: {e}")
    
    # Set WinRM credentials for this deployment
    credentials = {
        "username": username,
        "password": password,
        "use_ssl": use_ssl,
        "port": port or (5986 if use_ssl else 5985),
        "transport": transport,
        "server_cert_validation": server_cert_validation,
    }
    
    try:
        task_id = await service.queue_deployment(
            device_ip=device_ip,
            device_hostname=None,
            os_type="Windows",
            credentials=credentials
        )
        
        return {
            "message": f"WinRM deployment queued for {device_ip}",
            "task_id": task_id,
            "method": "winrm",
            "endpoint": f"{'https' if use_ssl else 'http'}://{device_ip}:{credentials['port']}/wsman",
            "transport": transport,
            "note": "Agent will be deployed via WinRM using provided credentials"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"WinRM deployment failed: {e}")


# =============================================================================
# TELEMETRY INGESTION
# =============================================================================

@router.post("/telemetry/ingest")
async def ingest_telemetry(request: TelemetryIngestRequest):
    """Ingest telemetry events from agents and process through AATL"""
    from services.aatl import get_aatl_engine
    
    events = request.events
    if not events:
        return {
            "status": "ok",
            "ingested": 0,
            "contract_version": SWARM_CONTROL_PLANE_CONTRACT_VERSION,
        }
    
    # Process and store events
    now = datetime.now(timezone.utc).isoformat()
    aatl_assessments = []
    agents_updated = 0
    
    for event in events:
        event["ingested_at"] = now
        
        # Handle agent heartbeat - register/update agent
        event_type = event.get("event_type", "")
        if event_type == "agent.heartbeat":
            agent_data = event.get("data", {})
            agent_id = event.get("agent_id") or event.get("host_id")
            
            if agent_id:
                await db.agents.update_one(
                    {"agent_id": agent_id},
                    {
                        "$set": {
                            "agent_id": agent_id,
                            "host_id": event.get("host_id"),
                            "hostname": agent_data.get("hostname"),
                            "os": agent_data.get("os"),
                            "version": agent_data.get("version"),
                            "status": "online",
                            "last_seen": now,
                            "uptime": agent_data.get("uptime")
                        },
                        "$setOnInsert": {
                            "first_seen": now
                        }
                    },
                    upsert=True
                )
                agents_updated += 1
        
        # Determine severity for alerting
        severity = event.get("severity", "info")
        event_type = event.get("event_type", "")
        
        # Store in telemetry collection
        await db.agent_telemetry.insert_one(event)
        
        # Process CLI events through AATL
        if event_type == "cli.command":
            engine = get_aatl_engine()
            if engine:
                try:
                    assessment = await engine.process_cli_event(event)
                    if assessment:
                        aatl_assessments.append(assessment.to_dict())
                        
                        # Update severity based on AATL assessment
                        if assessment.threat_score >= 80:
                            severity = "critical"
                        elif assessment.threat_score >= 60:
                            severity = "high"
                        elif assessment.threat_score >= 40:
                            severity = "medium"
                except Exception as e:
                    logger.warning(f"AATL processing failed: {e}")
        
        # Create alert for high severity events
        if severity in ("critical", "high"):
            await db.alerts.insert_one({
                "type": "telemetry",
                "severity": severity,
                "source": event.get("host_id", "unknown"),
                "event_type": event_type,
                "message": event.get("data", {}).get("message", "Security event detected"),
                "data": event.get("data"),
                "timestamp": now,
                "status": "open"
            })
    
    logger.info(f"Ingested {len(events)} telemetry events, {len(aatl_assessments)} AATL assessments")
    
    return {
        "status": "ok", 
        "ingested": len(events),
        "aatl_assessments": len(aatl_assessments),
        "contract_version": SWARM_CONTROL_PLANE_CONTRACT_VERSION,
    }


@router.post("/alerts/critical")
async def receive_critical_alert(alert: Dict[str, Any]):
    """Receive critical alerts from agents (auto-kill notifications, etc.)"""
    now = datetime.now(timezone.utc).isoformat()
    
    # Store the alert
    alert_doc = {
        "type": "agent_critical",
        "alert_type": alert.get("alert_type", "UNKNOWN"),
        "severity": alert.get("severity", "critical"),
        "agent_id": alert.get("agent_id"),
        "host_id": alert.get("host_id"),
        "threat_id": alert.get("threat_id"),
        "threat_title": alert.get("threat_title"),
        "threat_type": alert.get("threat_type"),
        "message": alert.get("message"),
        "evidence": alert.get("evidence"),
        "remediation_action": alert.get("remediation_action"),
        "timestamp": alert.get("timestamp", now),
        "received_at": now,
        "status": "open",
        "acknowledged": False
    }
    
    await db.critical_alerts.insert_one(alert_doc)
    
    # Also add to regular alerts for dashboard visibility
    await db.alerts.insert_one({
        "type": "auto_remediation",
        "severity": alert.get("severity", "critical"),
        "source": alert.get("host_id", "unknown"),
        "event_type": alert.get("alert_type"),
        "message": f"{alert.get('alert_type')}: {alert.get('threat_title')} - {alert.get('message')}",
        "data": alert,
        "timestamp": now,
        "status": "open"
    })
    
    logger.warning(f"🚨 CRITICAL ALERT from {alert.get('host_id')}: {alert.get('alert_type')} - {alert.get('threat_title')}")
    
    return {"status": "received", "alert_type": alert.get("alert_type")}


# =============================================================================
# SERVER-SIDE AUTO-KILL FUNCTIONALITY
# =============================================================================

class AutoKillRequest(BaseModel):
    agent_id: str
    target_type: str  # process, ip, file, connection
    target: str  # pid, ip address, filepath, etc.
    reason: str
    priority: str = "critical"


@router.post("/auto-kill/process")
async def auto_kill_process(
    agent_id: str,
    pid: int,
    reason: str = "Server-initiated kill",
    current_user: dict = Depends(check_permission("write"))
):
    """Server-initiated process kill on agent"""
    now = datetime.now(timezone.utc).isoformat()
    
    command_id = f"kill-{uuid.uuid4().hex[:8]}"
    
    # Create kill command
    command_doc = {
        "command_id": command_id,
        "agent_id": agent_id,
        "command_type": "kill_process",
        "command_name": "Server Auto-Kill Process",
        "parameters": {"pid": pid, "reason": reason},
        "status": "approved",  # Auto-approved for kill commands
        "state_version": 1,
        "state_transition_log": [{
            "from_status": None,
            "to_status": "approved",
            "actor": current_user.get("email", "system"),
            "reason": "auto-kill command approved",
            "timestamp": now,
        }],
        "priority": "critical",
        "risk_level": "high",
        "created_by": current_user.get("email", "system"),
        "created_at": now,
        "auto_kill": True
    }
    
    await db.agent_commands.insert_one(command_doc)
    
    # Also add to command queue for immediate pickup
    await db.command_queue.insert_one({
        "command_id": command_id,
        "agent_id": agent_id,
        "command_type": "kill_process",
        "parameters": {"pid": pid, "reason": reason},
        "status": "pending",
        "created_at": now
    })
    
    logger.warning(f"🔥 AUTO-KILL: Process {pid} on agent {agent_id} - {reason}")
    
    return {
        "status": "queued",
        "command_id": command_id,
        "agent_id": agent_id,
        "target": f"PID {pid}",
        "message": f"Kill command sent to agent {agent_id}"
    }


@router.post("/auto-kill/ip")
async def auto_kill_ip(
    agent_id: str,
    ip_address: str,
    reason: str = "Server-initiated block",
    duration_hours: int = 24,
    current_user: dict = Depends(check_permission("write"))
):
    """Server-initiated IP block on agent"""
    now = datetime.now(timezone.utc).isoformat()
    
    command_id = f"block-{uuid.uuid4().hex[:8]}"
    
    command_doc = {
        "command_id": command_id,
        "agent_id": agent_id,
        "command_type": "block_ip",
        "command_name": "Server Auto-Block IP",
        "parameters": {
            "ip_address": ip_address,
            "reason": reason,
            "duration_hours": duration_hours
        },
        "status": "approved",
        "state_version": 1,
        "state_transition_log": [{
            "from_status": None,
            "to_status": "approved",
            "actor": current_user.get("email", "system"),
            "reason": "auto-kill command approved",
            "timestamp": now,
        }],
        "priority": "critical",
        "risk_level": "medium",
        "created_by": current_user.get("email", "system"),
        "created_at": now,
        "auto_kill": True
    }
    
    await db.agent_commands.insert_one(command_doc)
    await db.command_queue.insert_one({
        "command_id": command_id,
        "agent_id": agent_id,
        "command_type": "block_ip",
        "parameters": {"ip_address": ip_address, "duration_hours": duration_hours},
        "status": "pending",
        "created_at": now
    })
    
    logger.warning(f"🔥 AUTO-KILL: Blocking IP {ip_address} on agent {agent_id} - {reason}")
    
    return {
        "status": "queued",
        "command_id": command_id,
        "agent_id": agent_id,
        "target": ip_address,
        "message": f"IP block command sent to agent {agent_id}"
    }


@router.post("/auto-kill/file")
async def auto_kill_file(
    agent_id: str,
    file_path: str,
    reason: str = "Server-initiated quarantine",
    current_user: dict = Depends(check_permission("write"))
):
    """Server-initiated file quarantine on agent"""
    now = datetime.now(timezone.utc).isoformat()
    
    command_id = f"quar-{uuid.uuid4().hex[:8]}"
    
    command_doc = {
        "command_id": command_id,
        "agent_id": agent_id,
        "command_type": "quarantine_file",
        "command_name": "Server Auto-Quarantine File",
        "parameters": {"file_path": file_path, "reason": reason},
        "status": "approved",
        "state_version": 1,
        "state_transition_log": [{
            "from_status": None,
            "to_status": "approved",
            "actor": current_user.get("email", "system"),
            "reason": "auto-kill command approved",
            "timestamp": now,
        }],
        "priority": "critical",
        "risk_level": "high",
        "created_by": current_user.get("email", "system"),
        "created_at": now,
        "auto_kill": True
    }
    
    await db.agent_commands.insert_one(command_doc)
    await db.command_queue.insert_one({
        "command_id": command_id,
        "agent_id": agent_id,
        "command_type": "quarantine_file",
        "parameters": {"file_path": file_path},
        "status": "pending",
        "created_at": now
    })
    
    logger.warning(f"🔥 AUTO-KILL: Quarantining {file_path} on agent {agent_id} - {reason}")
    
    return {
        "status": "queued",
        "command_id": command_id,
        "agent_id": agent_id,
        "target": file_path,
        "message": f"Quarantine command sent to agent {agent_id}"
    }


@router.post("/auto-kill/isolate")
async def auto_kill_isolate_host(
    agent_id: str,
    reason: str = "Server-initiated isolation",
    duration_hours: int = 1,
    current_user: dict = Depends(check_permission("write"))
):
    """Server-initiated host isolation (block all network)"""
    now = datetime.now(timezone.utc).isoformat()
    
    command_id = f"iso-{uuid.uuid4().hex[:8]}"
    
    command_doc = {
        "command_id": command_id,
        "agent_id": agent_id,
        "command_type": "isolate_host",
        "command_name": "Server Auto-Isolate Host",
        "parameters": {"reason": reason, "duration_hours": duration_hours},
        "status": "approved",
        "state_version": 1,
        "state_transition_log": [{
            "from_status": None,
            "to_status": "approved",
            "actor": current_user.get("email", "system"),
            "reason": "auto-kill command approved",
            "timestamp": now,
        }],
        "priority": "critical",
        "risk_level": "critical",
        "created_by": current_user.get("email", "system"),
        "created_at": now,
        "auto_kill": True
    }
    
    await db.agent_commands.insert_one(command_doc)
    await db.command_queue.insert_one({
        "command_id": command_id,
        "agent_id": agent_id,
        "command_type": "isolate_host",
        "parameters": {"duration_hours": duration_hours},
        "status": "pending",
        "created_at": now
    })
    
    logger.warning(f"🔥 AUTO-KILL: Isolating host {agent_id} - {reason}")
    
    return {
        "status": "queued",
        "command_id": command_id,
        "agent_id": agent_id,
        "target": "full_network_isolation",
        "message": f"Host isolation command sent to agent {agent_id}"
    }


@router.post("/auto-kill/batch")
async def auto_kill_batch(
    targets: List[Dict[str, Any]],
    current_user: dict = Depends(check_permission("write"))
):
    """Send multiple kill commands at once"""
    now = datetime.now(timezone.utc).isoformat()
    results = []
    
    for target in targets:
        command_id = f"batch-{uuid.uuid4().hex[:8]}"
        agent_id = target.get("agent_id")
        command_type = target.get("type")
        params = target.get("parameters", {})
        
        command_doc = {
            "command_id": command_id,
            "agent_id": agent_id,
            "command_type": command_type,
            "command_name": f"Batch Auto-Kill: {command_type}",
            "parameters": params,
            "status": "approved",
            "state_version": 1,
            "state_transition_log": [{
                "from_status": None,
                "to_status": "approved",
                "actor": current_user.get("email", "system"),
                "reason": "batch auto-kill command approved",
                "timestamp": now,
            }],
            "priority": "critical",
            "risk_level": "high",
            "created_by": current_user.get("email", "system"),
            "created_at": now,
            "auto_kill": True,
            "batch": True
        }
        
        await db.agent_commands.insert_one(command_doc)
        await db.command_queue.insert_one({
            "command_id": command_id,
            "agent_id": agent_id,
            "command_type": command_type,
            "parameters": params,
            "status": "pending",
            "created_at": now
        })
        
        results.append({
            "command_id": command_id,
            "agent_id": agent_id,
            "type": command_type,
            "status": "queued"
        })
    
    logger.warning(f"🔥 BATCH AUTO-KILL: {len(results)} commands queued")
    
    return {
        "status": "queued",
        "count": len(results),
        "commands": results
    }


# Browser extension command endpoint
@router.post("/browser-shield/kill")
async def browser_kill_command(command: Dict[str, Any]):
    """
    Send kill command to browser extension.
    Extensions poll this endpoint to receive commands.
    """
    now = datetime.now(timezone.utc).isoformat()
    
    command_doc = {
        "command_id": f"browser-{uuid.uuid4().hex[:8]}",
        "type": "browser_kill",
        "action": command.get("action"),  # block_domain, block_url, kill_tab, clear_cache
        "target": command.get("target"),
        "reason": command.get("reason", "Server command"),
        "created_at": now,
        "status": "pending",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    }
    
    await db.browser_commands.insert_one(command_doc)
    
    return {"status": "queued", "command_id": command_doc["command_id"]}


@router.get("/browser-shield/commands")
async def get_browser_commands():
    """Browser extensions poll this to get pending commands"""
    now = datetime.now(timezone.utc)
    
    # Get pending commands that haven't expired
    cursor = db.browser_commands.find({
        "status": "pending",
        "expires_at": {"$gt": now.isoformat()}
    }, {"_id": 0})
    
    commands = await cursor.to_list(50)
    
    # Mark as delivered
    for cmd in commands:
        await db.browser_commands.update_one(
            {"command_id": cmd["command_id"]},
            {"$set": {"status": "delivered", "delivered_at": now.isoformat()}}
        )
    
    return {"commands": commands}


@router.get("/browser-shield/blocklist")
async def get_browser_blocklist():
    """Get domain blocklist for browser extension"""
    # Static blocklist + dynamic from threats
    static_domains = [
        "malware-test.com", "phishing-example.org", "evil-download.net",
        "credential-steal.xyz", "cryptominer.io", "ransomware-delivery.com"
    ]
    
    # Get domains from recent threats
    cursor = db.alerts.find({
        "severity": {"$in": ["critical", "high"]},
        "data.domain": {"$exists": True}
    }, {"data.domain": 1}).limit(100)
    
    threat_domains = []
    async for alert in cursor:
        domain = alert.get("data", {}).get("domain")
        if domain:
            threat_domains.append(domain)
    
    return {
        "domains": list(set(static_domains + threat_domains)),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/alerts/critical")
async def get_critical_alerts(
    limit: int = 50,
    acknowledged: Optional[bool] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get critical alerts from agents"""
    query = {}
    if acknowledged is not None:
        query["acknowledged"] = acknowledged
    
    cursor = db.critical_alerts.find(query, {"_id": 0}).sort("received_at", -1).limit(limit)
    alerts = await cursor.to_list(limit)
    
    return {"alerts": alerts, "count": len(alerts)}


@router.post("/alerts/critical/{alert_id}/acknowledge")
async def acknowledge_critical_alert(
    alert_id: str,
    current_user: dict = Depends(check_permission("write"))
):
    """Acknowledge a critical alert"""
    result = await db.critical_alerts.update_one(
        {"threat_id": alert_id},
        {"$set": {
            "acknowledged": True,
            "acknowledged_by": current_user.get("email"),
            "acknowledged_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    return {"status": "acknowledged"}


@router.get("/telemetry")
async def get_telemetry(
    host_id: Optional[str] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """Get telemetry events"""
    query = {}
    if host_id:
        query["host_id"] = host_id
    if event_type:
        query["event_type"] = event_type
    if severity:
        query["severity"] = severity
    
    cursor = db.agent_telemetry.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit)
    events = await cursor.to_list(limit)
    
    return {"events": events, "count": len(events)}


@router.get("/telemetry/stats")
async def get_telemetry_stats(current_user: dict = Depends(get_current_user)):
    """Get telemetry statistics"""
    
    # Get event counts by type
    pipeline = [
        {"$group": {
            "_id": "$event_type",
            "count": {"$sum": 1}
        }}
    ]
    by_type = await db.agent_telemetry.aggregate(pipeline).to_list(50)
    
    # Get counts by severity
    pipeline = [
        {"$group": {
            "_id": "$severity",
            "count": {"$sum": 1}
        }}
    ]
    by_severity = await db.agent_telemetry.aggregate(pipeline).to_list(10)
    
    # Get counts by host
    pipeline = [
        {"$group": {
            "_id": "$host_id",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 20}
    ]
    by_host = await db.agent_telemetry.aggregate(pipeline).to_list(20)
    
    total = await db.agent_telemetry.count_documents({})
    
    return {
        "total_events": total,
        "by_type": {item["_id"]: item["count"] for item in by_type if item["_id"]},
        "by_severity": {item["_id"]: item["count"] for item in by_severity if item["_id"]},
        "by_host": {item["_id"]: item["count"] for item in by_host if item["_id"]}
    }


# =============================================================================
# SWARM OVERVIEW
# =============================================================================

@router.get("/overview")
async def get_swarm_overview(current_user: dict = Depends(get_current_user)):
    """Get swarm overview statistics"""
    
    # Count devices
    total_devices = await db.discovered_devices.count_documents({})
    managed_devices = await db.discovered_devices.count_documents({"is_managed": True})
    
    # Count agents
    total_agents = await db.agents.count_documents({})
    online_agents = await db.agents.count_documents({"status": "online"})
    
    # Recent telemetry
    recent_events = await db.agent_telemetry.count_documents({})
    critical_events = await db.agent_telemetry.count_documents({"severity": "critical"})
    
    # Deployment stats
    deployments = await db.deployment_tasks.count_documents({})
    successful = await db.deployment_tasks.count_documents({"status": "deployed"})
    failed = await db.deployment_tasks.count_documents({"status": "failed"})
    
    return {
        "devices": {
            "total": total_devices,
            "managed": managed_devices,
            "unmanaged": total_devices - managed_devices
        },
        "agents": {
            "total": total_agents,
            "online": online_agents,
            "offline": total_agents - online_agents
        },
        "telemetry": {
            "total_events": recent_events,
            "critical": critical_events
        },
        "deployments": {
            "total": deployments,
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / deployments * 100) if deployments > 0 else 0
        }
    }



# =============================================================================
# CLI EVENT INGESTION (AATL Integration)
# =============================================================================

@router.post("/cli/event")
async def ingest_cli_event(request: CLIEventRequest):
    """
    Ingest a CLI event and process through AATL for AI threat detection.
    This is the primary endpoint for CLI monitoring integration.
    """
    from services.aatl import get_aatl_engine
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Store CLI command
    cli_doc = {
        "host_id": request.host_id,
        "session_id": request.session_id,
        "command": request.command,
        "user": request.user,
        "shell_type": request.shell_type,
        "timestamp": request.timestamp or now,
        "ingested_at": now
    }
    
    await db.cli_commands.insert_one(cli_doc)
    
    # Process through AATL
    assessment = None
    engine = get_aatl_engine()
    
    if engine:
        try:
            event = {
                "host_id": request.host_id,
                "event_type": "cli.command",
                "timestamp": request.timestamp or now,
                "data": {
                    "session_id": request.session_id,
                    "command": request.command,
                    "user": request.user,
                    "shell_type": request.shell_type
                }
            }
            assessment = await engine.process_cli_event(event)
        except Exception as e:
            logger.error(f"AATL processing error: {e}")
    
    result = {
        "status": "ok",
        "command_stored": True
    }
    
    if assessment:
        result["aatl_assessment"] = {
            "machine_plausibility": assessment.machine_plausibility,
            "threat_score": assessment.threat_score,
            "threat_level": assessment.threat_level,
            "actor_type": assessment.actor_type.value,
            "recommended_strategy": assessment.recommended_strategy.value
        }
    
    return result


@router.post("/cli/batch")
async def ingest_cli_batch(events: List[CLIEventRequest]):
    """Ingest multiple CLI events in batch"""
    from services.aatl import get_aatl_engine
    
    now = datetime.now(timezone.utc).isoformat()
    processed = 0
    assessments = []
    
    engine = get_aatl_engine()
    
    for request in events:
        # Store CLI command
        cli_doc = {
            "host_id": request.host_id,
            "session_id": request.session_id,
            "command": request.command,
            "user": request.user,
            "shell_type": request.shell_type,
            "timestamp": request.timestamp or now,
            "ingested_at": now
        }
        
        await db.cli_commands.insert_one(cli_doc)
        processed += 1
        
        # Process through AATL
        if engine:
            try:
                event = {
                    "host_id": request.host_id,
                    "event_type": "cli.command",
                    "timestamp": request.timestamp or now,
                    "data": {
                        "session_id": request.session_id,
                        "command": request.command,
                        "user": request.user,
                        "shell_type": request.shell_type
                    }
                }
                assessment = await engine.process_cli_event(event)
                if assessment and assessment.threat_score >= 30:
                    assessments.append(assessment.to_dict())
            except Exception as e:
                logger.warning(f"AATL batch processing error: {e}")
    
    return {
        "status": "ok",
        "processed": processed,
        "aatl_assessments": len(assessments),
        "high_threat_sessions": [a for a in assessments if a.get("threat_score", 0) >= 60]
    }


@router.get("/cli/sessions/{host_id}")
async def get_cli_sessions(
    host_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get CLI sessions for a host with AATL assessments"""
    from services.aatl import get_aatl_engine
    
    # Get unique session IDs
    pipeline = [
        {"$match": {"host_id": host_id}},
        {"$group": {
            "_id": "$session_id",
            "command_count": {"$sum": 1},
            "first_seen": {"$min": "$timestamp"},
            "last_seen": {"$max": "$timestamp"}
        }},
        {"$sort": {"last_seen": -1}},
        {"$limit": 50}
    ]
    
    sessions = await db.cli_commands.aggregate(pipeline).to_list(50)
    
    # Enrich with AATL assessments
    engine = get_aatl_engine()
    enriched = []
    
    for session in sessions:
        session_data = {
            "session_id": session["_id"],
            "command_count": session["command_count"],
            "first_seen": session["first_seen"],
            "last_seen": session["last_seen"]
        }
        
        if engine:
            assessment = await engine.get_assessment(host_id, session["_id"])
            if assessment:
                session_data["aatl"] = {
                    "machine_plausibility": assessment.get("machine_plausibility"),
                    "threat_score": assessment.get("threat_score"),
                    "threat_level": assessment.get("threat_level"),
                    "actor_type": assessment.get("actor_type"),
                    "recommended_strategy": assessment.get("recommended_strategy")
                }
        
        enriched.append(session_data)
    
    return {"sessions": enriched, "host_id": host_id}



# =============================================================================
# DEVICE GROUPING AND TAGGING
# =============================================================================

class DeviceGroupRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    color: Optional[str] = "#06b6d4"


class DeviceTagRequest(BaseModel):
    tags: List[str]


@router.post("/groups")
async def create_device_group(
    group: DeviceGroupRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Create a new device group"""
    now = datetime.now(timezone.utc).isoformat()
    
    group_doc = {
        "group_id": f"grp-{uuid.uuid4().hex[:8]}",
        "name": group.name,
        "description": group.description,
        "color": group.color,
        "device_count": 0,
        "created_by": current_user.get("email"),
        "created_at": now
    }
    
    await db.device_groups.insert_one(group_doc)
    
    return {"status": "created", "group": {k: v for k, v in group_doc.items() if k != "_id"}}


@router.get("/groups")
async def list_device_groups(current_user: dict = Depends(get_current_user)):
    """List all device groups with device counts"""
    groups = await db.device_groups.find({}, {"_id": 0}).to_list(100)
    
    # Count devices per group
    for group in groups:
        count = await db.discovered_devices.count_documents({"group_id": group.get("group_id")})
        group["device_count"] = count
    
    return {"groups": groups}


@router.put("/groups/{group_id}")
async def update_device_group(
    group_id: str,
    group: DeviceGroupRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Update a device group"""
    result = await db.device_groups.update_one(
        {"group_id": group_id},
        {"$set": {
            "name": group.name,
            "description": group.description,
            "color": group.color,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Group not found")
    
    return {"status": "updated"}


@router.delete("/groups/{group_id}")
async def delete_device_group(
    group_id: str,
    current_user: dict = Depends(check_permission("write"))
):
    """Delete a device group"""
    # Remove group from all devices first
    await db.discovered_devices.update_many(
        {"group_id": group_id},
        {"$unset": {"group_id": ""}}
    )
    
    result = await db.device_groups.delete_one({"group_id": group_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Group not found")
    
    return {"status": "deleted"}


@router.put("/devices/{device_ip}/group")
async def assign_device_to_group(
    device_ip: str,
    group_id: str,
    current_user: dict = Depends(check_permission("write"))
):
    """Assign a device to a group"""
    result = await db.discovered_devices.update_one(
        {"ip_address": device_ip},
        {"$set": {"group_id": group_id}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Device not found")
    
    return {"status": "assigned", "device_ip": device_ip, "group_id": group_id}


@router.put("/devices/{device_ip}/tags")
async def update_device_tags(
    device_ip: str,
    tags: DeviceTagRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Update tags for a device"""
    result = await db.discovered_devices.update_one(
        {"ip_address": device_ip},
        {"$set": {"tags": tags.tags}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Device not found")
    
    return {"status": "updated", "device_ip": device_ip, "tags": tags.tags}


@router.get("/tags")
async def list_all_tags(current_user: dict = Depends(get_current_user)):
    """List all unique tags across devices"""
    pipeline = [
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    
    tags = await db.discovered_devices.aggregate(pipeline).to_list(100)
    
    return {"tags": [{"name": t["_id"], "count": t["count"]} for t in tags if t["_id"]]}


# =============================================================================
# USB SCAN
# =============================================================================

class USBScanRequest(BaseModel):
    host_id: str
    device_path: str
    device_name: Optional[str] = None


@router.post("/usb/scan")
async def initiate_usb_scan(
    request: USBScanRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Initiate USB device scan on an agent"""
    now = datetime.now(timezone.utc).isoformat()
    
    # Create scan task
    scan_id = f"usb-{uuid.uuid4().hex[:8]}"
    
    scan_doc = {
        "scan_id": scan_id,
        "host_id": request.host_id,
        "device_path": request.device_path,
        "device_name": request.device_name,
        "status": "pending",
        "created_by": current_user.get("email"),
        "created_at": now,
        "results": None
    }
    
    await db.usb_scans.insert_one(scan_doc)
    
    # Queue command to agent
    command_doc = {
        "command_id": f"cmd-{uuid.uuid4().hex[:8]}",
        "agent_id": request.host_id,
        "command_type": "usb_scan",
        "parameters": {
            "scan_id": scan_id,
            "device_path": request.device_path
        },
        "status": "pending",
        "created_at": now
    }
    
    await db.command_queue.insert_one(command_doc)
    
    return {"status": "queued", "scan_id": scan_id}


@router.get("/usb/scans")
async def list_usb_scans(
    host_id: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """List USB scan results"""
    query = {}
    if host_id:
        query["host_id"] = host_id
    
    scans = await db.usb_scans.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {"scans": scans}


@router.post("/usb/scan/{scan_id}/results")
async def submit_usb_scan_results(
    scan_id: str,
    results: Dict[str, Any]
):
    """Agent submits USB scan results"""
    now = datetime.now(timezone.utc).isoformat()
    
    # Calculate threat level based on results
    files_scanned = results.get("files_scanned", 0)
    threats_found = results.get("threats_found", [])
    malware_detected = len([t for t in threats_found if t.get("type") == "malware"])
    
    threat_level = "safe"
    if malware_detected > 0:
        threat_level = "critical"
    elif len(threats_found) > 0:
        threat_level = "suspicious"
    
    await db.usb_scans.update_one(
        {"scan_id": scan_id},
        {"$set": {
            "status": "completed",
            "completed_at": now,
            "results": results,
            "files_scanned": files_scanned,
            "threats_found": len(threats_found),
            "malware_detected": malware_detected,
            "threat_level": threat_level
        }}
    )
    
    # Create alert if threats found
    if threat_level in ("critical", "suspicious"):
        await db.alerts.insert_one({
            "type": "usb_threat",
            "severity": "critical" if threat_level == "critical" else "high",
            "source": results.get("host_id", "unknown"),
            "event_type": "usb_scan_complete",
            "message": f"USB scan detected {len(threats_found)} threats ({malware_detected} malware)",
            "data": {"scan_id": scan_id, "threats": threats_found},
            "timestamp": now,
            "status": "open"
        })
    
    return {"status": "recorded", "threat_level": threat_level}


# =============================================================================
# AI THREAT PRIORITIZATION WITH MITRE ATT&CK
# =============================================================================

MITRE_ATTACK_TACTICS = {
    "TA0001": {"name": "Initial Access", "severity_weight": 0.8},
    "TA0002": {"name": "Execution", "severity_weight": 0.9},
    "TA0003": {"name": "Persistence", "severity_weight": 0.85},
    "TA0004": {"name": "Privilege Escalation", "severity_weight": 0.95},
    "TA0005": {"name": "Defense Evasion", "severity_weight": 0.7},
    "TA0006": {"name": "Credential Access", "severity_weight": 1.0},
    "TA0007": {"name": "Discovery", "severity_weight": 0.5},
    "TA0008": {"name": "Lateral Movement", "severity_weight": 0.9},
    "TA0009": {"name": "Collection", "severity_weight": 0.75},
    "TA0010": {"name": "Exfiltration", "severity_weight": 1.0},
    "TA0011": {"name": "Command and Control", "severity_weight": 0.95},
    "TA0040": {"name": "Impact", "severity_weight": 1.0},
}

THREAT_KEYWORDS_TO_TACTICS = {
    # Credential Access (TA0006) - HIGHEST PRIORITY
    "mimikatz": "TA0006", "lazagne": "TA0006", "credential": "TA0006",
    "password": "TA0006", "lsass": "TA0006", "sekurlsa": "TA0006",
    "dump": "TA0006", "ntlm": "TA0006", "kerberos": "TA0006",
    
    # Exfiltration (TA0010) - HIGHEST PRIORITY
    "exfil": "TA0010", "upload": "TA0010", "transfer": "TA0010",
    "compress": "TA0010", "archive": "TA0010",
    
    # Impact (TA0040) - HIGHEST PRIORITY
    "ransomware": "TA0040", "encrypt": "TA0040", "wiper": "TA0040",
    "delete": "TA0040", "destroy": "TA0040", "format": "TA0040",
    
    # Privilege Escalation (TA0004)
    "privilege": "TA0004", "escalat": "TA0004", "sudo": "TA0004",
    "admin": "TA0004", "root": "TA0004", "uac": "TA0004",
    
    # Execution (TA0002)
    "powershell": "TA0002", "cmd": "TA0002", "script": "TA0002",
    "execute": "TA0002", "invoke": "TA0002", "spawn": "TA0002",
    
    # C2 (TA0011)
    "beacon": "TA0011", "callback": "TA0011", "reverse": "TA0011",
    "shell": "TA0011", "c2": "TA0011", "cobalt": "TA0011",
    
    # Lateral Movement (TA0008)
    "lateral": "TA0008", "pivot": "TA0008", "psexec": "TA0008",
    "wmi": "TA0008", "remote": "TA0008",
    
    # Persistence (TA0003)
    "persist": "TA0003", "startup": "TA0003", "scheduled": "TA0003",
    "registry": "TA0003", "service": "TA0003",
}


@router.post("/threats/prioritize")
async def prioritize_threats(
    limit: int = 50,
    current_user: dict = Depends(check_permission("write"))
):
    """
    AI-powered threat prioritization using MITRE ATT&CK framework.
    Returns threats sorted by priority score.
    """
    now = datetime.now(timezone.utc).isoformat()
    
    # Fetch recent critical/high alerts
    alerts = await db.alerts.find(
        {"status": "open", "severity": {"$in": ["critical", "high", "medium"]}},
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    
    # Fetch recent critical telemetry
    telemetry = await db.agent_telemetry.find(
        {"severity": {"$in": ["critical", "high"]}},
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    
    # Combine and prioritize
    all_threats = []
    
    for alert in alerts:
        threat_text = f"{alert.get('message', '')} {alert.get('event_type', '')}".lower()
        priority_data = calculate_threat_priority(threat_text, alert.get('severity', 'medium'))
        
        all_threats.append({
            "id": alert.get("id", str(uuid.uuid4())[:8]),
            "type": "alert",
            "source": alert.get("source"),
            "message": alert.get("message"),
            "severity": alert.get("severity"),
            "timestamp": alert.get("timestamp"),
            "mitre_tactic": priority_data["tactic"],
            "mitre_tactic_name": priority_data["tactic_name"],
            "priority_score": priority_data["score"],
            "priority_level": priority_data["level"],
            "recommended_action": priority_data["action"]
        })
    
    for event in telemetry:
        threat_text = f"{event.get('event_type', '')} {event.get('data', {})}".lower()
        priority_data = calculate_threat_priority(threat_text, event.get('severity', 'medium'))
        
        all_threats.append({
            "id": event.get("id", str(uuid.uuid4())[:8]),
            "type": "telemetry",
            "source": event.get("host_id"),
            "message": event.get("event_type"),
            "severity": event.get("severity"),
            "timestamp": event.get("timestamp"),
            "mitre_tactic": priority_data["tactic"],
            "mitre_tactic_name": priority_data["tactic_name"],
            "priority_score": priority_data["score"],
            "priority_level": priority_data["level"],
            "recommended_action": priority_data["action"]
        })
    
    # Sort by priority score (highest first)
    all_threats.sort(key=lambda x: x["priority_score"], reverse=True)
    
    # Calculate summary
    summary = {
        "total_threats": len(all_threats),
        "critical_priority": len([t for t in all_threats if t["priority_level"] == "critical"]),
        "high_priority": len([t for t in all_threats if t["priority_level"] == "high"]),
        "medium_priority": len([t for t in all_threats if t["priority_level"] == "medium"]),
        "top_tactics": get_top_tactics(all_threats)
    }
    
    return {
        "prioritized_threats": all_threats[:limit],
        "summary": summary,
        "analyzed_at": now
    }


def calculate_threat_priority(threat_text: str, severity: str) -> dict:
    """Calculate threat priority using MITRE ATT&CK mapping"""
    # Base severity scores
    severity_scores = {
        "critical": 90,
        "high": 70,
        "medium": 50,
        "low": 30,
        "info": 10
    }
    
    base_score = severity_scores.get(severity, 50)
    
    # Find matching MITRE tactic
    tactic_id = None
    for keyword, tactic in THREAT_KEYWORDS_TO_TACTICS.items():
        if keyword in threat_text:
            tactic_id = tactic
            break
    
    # Calculate final score
    if tactic_id and tactic_id in MITRE_ATTACK_TACTICS:
        tactic_info = MITRE_ATTACK_TACTICS[tactic_id]
        weight = tactic_info["severity_weight"]
        final_score = min(100, base_score * (1 + weight * 0.2))
        tactic_name = tactic_info["name"]
    else:
        final_score = base_score
        tactic_id = "UNKNOWN"
        tactic_name = "Unclassified"
    
    # Determine priority level
    if final_score >= 90:
        level = "critical"
        action = "IMMEDIATE: Auto-kill or manual intervention required"
    elif final_score >= 70:
        level = "high"
        action = "URGENT: Review and remediate within 1 hour"
    elif final_score >= 50:
        level = "medium"
        action = "REVIEW: Investigate within 4 hours"
    else:
        level = "low"
        action = "MONITOR: Track for patterns"
    
    return {
        "tactic": tactic_id,
        "tactic_name": tactic_name,
        "score": round(final_score, 1),
        "level": level,
        "action": action
    }


def get_top_tactics(threats: list) -> list:
    """Get most common MITRE tactics from threats"""
    tactic_counts = {}
    for t in threats:
        tactic = t.get("mitre_tactic")
        if tactic and tactic != "UNKNOWN":
            tactic_counts[tactic] = tactic_counts.get(tactic, 0) + 1
    
    sorted_tactics = sorted(tactic_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return [
        {
            "tactic_id": tactic_id,
            "tactic_name": MITRE_ATTACK_TACTICS.get(tactic_id, {}).get("name", "Unknown"),
            "count": count
        }
        for tactic_id, count in sorted_tactics
    ]


@router.get("/threats/mitre-mapping")
async def get_mitre_mapping(current_user: dict = Depends(get_current_user)):
    """Get MITRE ATT&CK tactic mapping and threat distribution"""
    # Get recent threats and map to tactics
    alerts = await db.alerts.find(
        {"status": "open"},
        {"_id": 0, "message": 1, "event_type": 1, "severity": 1}
    ).limit(200).to_list(200)
    
    tactic_distribution = {tactic_id: {"count": 0, "name": info["name"], "severity_weight": info["severity_weight"]} 
                          for tactic_id, info in MITRE_ATTACK_TACTICS.items()}
    
    for alert in alerts:
        text = f"{alert.get('message', '')} {alert.get('event_type', '')}".lower()
        for keyword, tactic_id in THREAT_KEYWORDS_TO_TACTICS.items():
            if keyword in text:
                tactic_distribution[tactic_id]["count"] += 1
                break
    
    # Filter to only tactics with threats
    active_tactics = {k: v for k, v in tactic_distribution.items() if v["count"] > 0}
    
    return {
        "all_tactics": MITRE_ATTACK_TACTICS,
        "active_tactics": active_tactics,
        "keyword_mappings": len(THREAT_KEYWORDS_TO_TACTICS)
    }


# =============================================================================
# UNIFIED AGENT AUTO-DEPLOYMENT
# =============================================================================

@router.post("/unified/scan-and-deploy")
async def scan_and_auto_deploy(
    request: ScanNetworkRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(check_permission("write"))
):
    """
    Trigger network scan and auto-deploy unified agents to discovered devices.
    This is the main endpoint for the dashboard "Scan Network" button.
    
    Flow:
    1. Triggers network discovery scan
    2. Discovered devices get queued for auto-deployment
    3. Unified agents are deployed via SSH/WinRM
    4. Agents auto-configure VPN and start monitoring
    """
    from services.network_discovery import get_network_discovery, start_network_discovery
    from services.agent_deployment import get_deployment_service, start_deployment_service
    import os
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Step 1: Get or start network discovery
    discovery = get_network_discovery()
    if discovery is None:
        try:
            discovery = await start_network_discovery(db, scan_interval_s=300)
            logger.info("Started network discovery service for unified auto-deploy")
        except Exception as e:
            logger.warning(f"Could not start network discovery service: {e}")
    
    # Step 2: Get or start deployment service
    service = get_deployment_service()
    if service is None:
        try:
            api_url = os.environ.get('API_URL', 'http://localhost:8001')
            service = await start_deployment_service(db, api_url)
            logger.info("Started deployment service for unified agent auto-deploy")
        except Exception as e:
            logger.warning(f"Could not start deployment service: {e}")
    
    # Step 3: Trigger scan
    scan_triggered = False
    if discovery is not None:
        try:
            background_tasks.add_task(discovery.trigger_manual_scan, request.network)
            scan_triggered = True
        except Exception as e:
            logger.error(f"Network scan failed: {e}")
    
    # Step 4: Queue existing discovered devices for deployment
    cursor = db.discovered_devices.find({
        "deployment_status": {"$in": ["discovered", "failed", None]},
        "$or": [
            {"os_type": {"$regex": "^(windows|linux|macos|darwin)$", "$options": "i"}},
            {"deployable": True}
        ]
    }, {"_id": 0})
    devices = await cursor.to_list(100)
    
    queued_count = 0
    for device in devices:
        ip = device.get("ip_address")
        if not ip:
            continue
        
        # Check if already has an agent
        existing = await db.unified_agents.find_one({"ip_address": ip})
        if existing:
            continue
        
        # Queue for deployment
        await db.discovered_devices.update_one(
            {"ip_address": ip},
            {"$set": {
                "deployment_status": "queued",
                "deployment_queued_at": now,
                "agent_type": "unified"
            }}
        )
        
        # Create deployment task
        deploy_task = {
            "task_id": f"unified-{uuid.uuid4().hex[:8]}",
            "target_ip": ip,
            "target_hostname": device.get("hostname"),
            "target_os": device.get("os_type", "unknown"),
            "status": "pending",
            "created_at": now,
            "method": "auto",
            "agent_type": "unified"
        }
        await db.deployment_tasks.insert_one(deploy_task)
        queued_count += 1
    
    return {
        "status": "ok",
        "message": "Network scan and auto-deploy initiated",
        "scan_triggered": scan_triggered,
        "devices_queued": queued_count,
        "network": request.network or "all networks"
    }


@router.get("/unified/deployment-status")
async def get_unified_deployment_status(current_user: dict = Depends(get_current_user)):
    """Get status of unified agent deployments"""
    
    # Get deployment tasks
    cursor = db.deployment_tasks.find(
        {"agent_type": "unified"},
        {"_id": 0}
    ).sort("created_at", -1).limit(50)
    tasks = await cursor.to_list(50)
    
    # Get discovered devices status
    device_stats = {
        "total": await db.discovered_devices.count_documents({}),
        "queued": await db.discovered_devices.count_documents({"deployment_status": "queued"}),
        "deploying": await db.discovered_devices.count_documents({"deployment_status": "deploying"}),
        "deployed": await db.discovered_devices.count_documents({"deployment_status": "deployed"}),
        "failed": await db.discovered_devices.count_documents({"deployment_status": "failed"}),
        "discovered": await db.discovered_devices.count_documents({"deployment_status": "discovered"})
    }
    
    # Get registered unified agents
    agent_count = await db.unified_agents.count_documents({})
    online_count = await db.unified_agents.count_documents({"status": "online"})
    
    return {
        "tasks": tasks,
        "device_stats": device_stats,
        "agents": {
            "total": agent_count,
            "online": online_count
        }
    }


@router.post("/unified/deploy-to-device")
async def deploy_unified_to_device(
    device_ip: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(check_permission("write"))
):
    """Deploy unified agent to a specific discovered device"""
    from services.agent_deployment import get_deployment_service, start_deployment_service
    import os
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Check if device exists
    device = await db.discovered_devices.find_one({"ip_address": device_ip})
    if not device:
        raise HTTPException(status_code=404, detail=f"Device {device_ip} not found")
    
    # Check if already has agent
    existing = await db.unified_agents.find_one({"ip_address": device_ip})
    if existing:
        return {
            "status": "already_deployed",
            "message": f"Unified agent already deployed to {device_ip}",
            "agent_id": existing.get("agent_id")
        }
    
    # Get or start deployment service
    service = get_deployment_service()
    if service is None:
        try:
            api_url = os.environ.get('API_URL', 'http://localhost:8001')
            service = await start_deployment_service(db, api_url)
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Deployment service unavailable: {e}")
    
    # Queue deployment
    await db.discovered_devices.update_one(
        {"ip_address": device_ip},
        {"$set": {
            "deployment_status": "queued",
            "deployment_queued_at": now,
            "agent_type": "unified"
        }}
    )
    
    deploy_task = {
        "task_id": f"unified-{uuid.uuid4().hex[:8]}",
        "target_ip": device_ip,
        "target_hostname": device.get("hostname"),
        "target_os": device.get("os_type", "unknown"),
        "status": "pending",
        "created_at": now,
        "method": "manual",
        "agent_type": "unified"
    }
    await db.deployment_tasks.insert_one(deploy_task)
    
    return {
        "status": "queued",
        "message": f"Unified agent deployment queued for {device_ip}",
        "task_id": deploy_task["task_id"],
        "os_type": device.get("os_type")
    }

