#!/usr/bin/env python3
"""
Seraph AI Unified Agent Server API
REST API for agent management, deployment, and monitoring.
Also serves as the basic end-user interface that proxies key data
from the main backend API on port 8001.
"""

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import json
import os
import logging
from datetime import datetime, timedelta
import hashlib
import secrets
import threading
import time
import httpx

# Configure logging with UTF-8 support for Windows console
import sys
_file_handler = logging.FileHandler('server_api.log', encoding='utf-8')
_stream_handler = logging.StreamHandler(stream=open(sys.stdout.fileno(), mode='w', encoding='utf-8', closefd=False))
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[_file_handler, _stream_handler]
)
logger = logging.getLogger(__name__)

# Backend URL (main backend API)
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8001")

app = FastAPI(
    title="Seraph AI Unified Agent Server",
    description="End-user security dashboard & agent management API",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Async HTTP client for proxying to the main backend
http_client: Optional[httpx.AsyncClient] = None

@app.on_event("startup")
async def init_http_client():
    """Initialize the HTTP client for backend communication"""
    global http_client
    http_client = httpx.AsyncClient(base_url=BACKEND_URL, timeout=15.0)
    logger.info(f"[Proxy] Backend proxy configured -> {BACKEND_URL}")

@app.on_event("shutdown")
async def close_http_client():
    """Close the HTTP client"""
    global http_client
    if http_client:
        await http_client.aclose()

# In-memory storage (in production, use a database)
agents_db: Dict[str, Dict] = {}
alerts_db: List[Dict] = []
deployments_db: Dict[str, Dict] = {}
sessions_db: Dict[str, Dict] = {}

# Background monitoring
monitoring_active = False
monitoring_thread = None

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, agent_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[agent_id] = websocket
        logger.info(f"Agent {agent_id} connected via WebSocket")

    def disconnect(self, agent_id: str):
        if agent_id in self.active_connections:
            del self.active_connections[agent_id]
            logger.info(f"Agent {agent_id} disconnected")

    async def send_personal_message(self, agent_id: str, message: Dict):
        if agent_id in self.active_connections:
            await self.active_connections[agent_id].send_json(message)

    async def broadcast(self, message: Dict):
        for connection in self.active_connections.values():
            await connection.send_json(message)

manager = ConnectionManager()

# Pydantic models
class AgentRegistration(BaseModel):
    agent_id: str
    platform: str
    hostname: str
    ip_address: str
    version: str
    capabilities: List[str] = []

class AgentHeartbeat(BaseModel):
    agent_id: str
    status: str
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    network_connections: Optional[int] = None
    alerts: List[Dict] = []

class AlertData(BaseModel):
    agent_id: str
    severity: str  # "low", "medium", "high", "critical"
    category: str  # "network", "process", "file", "system"
    message: str
    details: Optional[Dict] = None

class DeploymentRequest(BaseModel):
    target_platform: str
    target_ip: str
    agent_config: Optional[Dict] = None

class ServerConfig(BaseModel):
    heartbeat_interval: int = 60
    alert_thresholds: Dict[str, Any] = {}
    monitoring_enabled: bool = True

@app.on_event("startup")
async def startup_event():
    """Initialize server on startup"""
    logger.info("Starting Seraph AI Unified Agent Server")
    logger.info("+==============================================================+")
    logger.info("|                                                              |")
    logger.info("|     M M M EEEEE TTTTT  AAA  TTTTT RRRR   OOO  N   N   !     |")
    logger.info("|     MMMM  E       T   A   A   T   R   R O   O NN  N   !     |")
    logger.info("|     M M M EEEE    T   AAAAA   T   RRRR  O   O N N N   !     |")
    logger.info("|     M   M E       T   A   A   T   R  R  O   O N  NN         |")
    logger.info("|     M   M EEEEE   T   A   A   T   R   R  OOO  N   N   !     |")
    logger.info("|                                                              |")
    logger.info("|           UNIFIED AGENT SERVER v2.0 (End-User Portal)        |")
    logger.info("|                                                              |")
    logger.info("+==============================================================+")

    # Load existing data
    load_data()

    # Check backend connectivity
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BACKEND_URL}/api/")
            if resp.status_code == 200:
                logger.info(f"[Backend] Connected to main backend at {BACKEND_URL} [OK]")
            else:
                logger.warning(f"[Backend] Backend returned status {resp.status_code}")
    except Exception as e:
        logger.warning(f"[Backend] Cannot reach backend at {BACKEND_URL}: {e}")
        logger.warning("[Backend] End-user dashboard proxy features will be unavailable")

    # Start background monitoring
    global monitoring_thread
    monitoring_thread = threading.Thread(target=background_monitoring, daemon=True)
    monitoring_thread.start()

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Seraph AI Agent Server API")
    save_data()

def load_data():
    """Load persisted data"""
    try:
        if os.path.exists('agents_db.json'):
            with open('agents_db.json', 'r') as f:
                global agents_db
                agents_db = json.load(f)
        if os.path.exists('alerts_db.json'):
            with open('alerts_db.json', 'r') as f:
                global alerts_db
                alerts_db = json.load(f)
        if os.path.exists('deployments_db.json'):
            with open('deployments_db.json', 'r') as f:
                global deployments_db
                deployments_db = json.load(f)
        logger.info("Data loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load data: {e}")

def save_data():
    """Save data to disk"""
    try:
        with open('agents_db.json', 'w') as f:
            json.dump(agents_db, f, indent=2, default=str)
        with open('alerts_db.json', 'w') as f:
            json.dump(alerts_db, f, indent=2, default=str)
        with open('deployments_db.json', 'w') as f:
            json.dump(deployments_db, f, indent=2, default=str)
        logger.info("Data saved successfully")
    except Exception as e:
        logger.error(f"Failed to save data: {e}")

def background_monitoring():
    """Background monitoring thread"""
    global monitoring_active
    monitoring_active = True

    while monitoring_active:
        try:
            # Check for offline agents
            current_time = datetime.now()
            offline_agents = []

            for agent_id, agent_data in agents_db.items():
                last_heartbeat = agent_data.get('last_heartbeat')
                if last_heartbeat:
                    last_seen = datetime.fromisoformat(last_heartbeat)
                    if current_time - last_seen > timedelta(minutes=5):
                        offline_agents.append(agent_id)

            # Create alerts for offline agents
            for agent_id in offline_agents:
                if agents_db[agent_id]['status'] != 'offline':
                    agents_db[agent_id]['status'] = 'offline'
                    create_alert(
                        agent_id=agent_id,
                        severity="high",
                        category="system",
                        message=f"Agent {agent_id} went offline",
                        details={"agent_id": agent_id}
                    )

            time.sleep(60)  # Check every minute

        except Exception as e:
            logger.error(f"Error in background monitoring: {e}")
            time.sleep(10)

def create_alert(agent_id: str, severity: str, category: str, message: str, details: Optional[Dict] = None):
    """Create and store an alert"""
    alert = {
        "id": secrets.token_hex(8),
        "agent_id": agent_id,
        "severity": severity,
        "category": category,
        "message": message,
        "details": details or {},
        "timestamp": datetime.now().isoformat(),
        "acknowledged": False
    }

    alerts_db.append(alert)
    logger.warning(f"ALERT [{severity.upper()}]: {message}")

    # Auto-save alerts
    save_data()

# API Routes

@app.get("/")
async def root():
    """API root endpoint — end-user portal"""
    # Check backend health
    backend_status = "unknown"
    try:
        resp = await http_client.get("/api/")
        if resp.status_code == 200:
            backend_status = "connected"
        else:
            backend_status = "degraded"
    except Exception:
        backend_status = "offline"

    return {
        "message": "Metatron Unified Agent Server",
        "version": "2.0.0",
        "role": "end-user-portal",
        "status": "running",
        "backend_status": backend_status,
        "backend_url": BACKEND_URL,
        "local_agents": len(agents_db),
        "endpoints": {
            "user_dashboard": "/user/dashboard",
            "user_alerts": "/user/alerts",
            "user_status": "/user/status",
            "agents": "/agents",
            "alerts": "/alerts",
            "deployments": "/deployments",
            "config": "/config",
            "proxy": "/proxy/api/{path}"
        }
    }

@app.post("/agents/register")
async def register_agent(agent: AgentRegistration):
    """Register a new agent"""
    if agent.agent_id in agents_db:
        raise HTTPException(status_code=409, detail="Agent already registered")

    agent_data = {
        "agent_id": agent.agent_id,
        "platform": agent.platform,
        "hostname": agent.hostname,
        "ip_address": agent.ip_address,
        "version": agent.version,
        "capabilities": agent.capabilities,
        "status": "online",
        "registered_at": datetime.now().isoformat(),
        "last_heartbeat": datetime.now().isoformat(),
        "config": {
            "heartbeat_interval": 60,
            "monitoring_enabled": True,
            "alert_thresholds": {}
        }
    }

    agents_db[agent.agent_id] = agent_data
    save_data()

    logger.info(f"Agent registered: {agent.agent_id} ({agent.platform}) from {agent.ip_address}")
    return {"status": "registered", "agent_id": agent.agent_id}

@app.post("/agents/{agent_id}/heartbeat")
async def agent_heartbeat(agent_id: str, heartbeat: AgentHeartbeat):
    """Receive heartbeat from agent"""
    if agent_id not in agents_db:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Update agent data
    agents_db[agent_id].update({
        "status": heartbeat.status,
        "last_heartbeat": datetime.now().isoformat(),
        "cpu_usage": heartbeat.cpu_usage,
        "memory_usage": heartbeat.memory_usage,
        "network_connections": heartbeat.network_connections
    })

    # Process alerts
    for alert_data in heartbeat.alerts:
        create_alert(
            agent_id=agent_id,
            severity=alert_data.get("severity", "low"),
            category=alert_data.get("category", "unknown"),
            message=alert_data.get("message", "Unknown alert"),
            details=alert_data.get("details", {})
        )

    # Return commands for agent
    commands = []
    # Add any pending commands here

    return {
        "status": "ok",
        "commands": commands,
        "config": agents_db[agent_id].get("config", {})
    }

@app.get("/agents")
async def list_agents():
    """List all registered agents"""
    return {
        "agents": list(agents_db.values()),
        "total": len(agents_db)
    }

@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent details"""
    if agent_id not in agents_db:
        raise HTTPException(status_code=404, detail="Agent not found")

    return agents_db[agent_id]

@app.delete("/agents/{agent_id}")
async def unregister_agent(agent_id: str):
    """Unregister an agent"""
    if agent_id not in agents_db:
        raise HTTPException(status_code=404, detail="Agent not found")

    del agents_db[agent_id]
    save_data()

    logger.info(f"Agent unregistered: {agent_id}")
    return {"status": "unregistered"}

@app.post("/agents/{agent_id}/command")
async def send_command(agent_id: str, command: Dict[str, Any]):
    """Send command to agent"""
    if agent_id not in agents_db:
        raise HTTPException(status_code=404, detail="Agent not found")

    # In a real implementation, this would queue the command for the agent
    # For now, just log it
    logger.info(f"Command sent to {agent_id}: {command}")

    return {"status": "command_queued"}

@app.get("/alerts")
async def list_alerts(severity: Optional[str] = None, acknowledged: Optional[bool] = None):
    """List alerts with optional filtering"""
    filtered_alerts = alerts_db

    if severity:
        filtered_alerts = [a for a in filtered_alerts if a["severity"] == severity]

    if acknowledged is not None:
        filtered_alerts = [a for a in filtered_alerts if a["acknowledged"] == acknowledged]

    return {
        "alerts": filtered_alerts[-100:],  # Last 100 alerts
        "total": len(filtered_alerts)
    }

@app.put("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Acknowledge an alert"""
    for alert in alerts_db:
        if alert["id"] == alert_id:
            alert["acknowledged"] = True
            alert["acknowledged_at"] = datetime.now().isoformat()
            save_data()
            return {"status": "acknowledged"}

    raise HTTPException(status_code=404, detail="Alert not found")

@app.post("/deployments")
async def create_deployment(deployment: DeploymentRequest, background_tasks: BackgroundTasks):
    """Create a new deployment"""
    deployment_id = secrets.token_hex(8)

    deployment_data = {
        "id": deployment_id,
        "target_platform": deployment.target_platform,
        "target_ip": deployment.target_ip,
        "agent_config": deployment.agent_config or {},
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

    deployments_db[deployment_id] = deployment_data
    save_data()

    # Start deployment in background
    background_tasks.add_task(process_deployment, deployment_id)

    logger.info(f"Deployment created: {deployment_id} for {deployment.target_platform} at {deployment.target_ip}")
    return {"deployment_id": deployment_id, "status": "pending"}

@app.get("/deployments")
async def list_deployments():
    """List all deployments"""
    return {
        "deployments": list(deployments_db.values()),
        "total": len(deployments_db)
    }

@app.get("/deployments/{deployment_id}")
async def get_deployment(deployment_id: str):
    """Get deployment details"""
    if deployment_id not in deployments_db:
        raise HTTPException(status_code=404, detail="Deployment not found")

    return deployments_db[deployment_id]

@app.get("/config")
async def get_server_config():
    """Get server configuration"""
    return {
        "heartbeat_interval": 60,
        "alert_thresholds": {
            "cpu_usage": 90,
            "memory_usage": 90,
            "network_connections": 100
        },
        "monitoring_enabled": True,
        "supported_platforms": ["windows", "linux", "macos", "android", "ios"]
    }

@app.put("/config")
async def update_server_config(config: ServerConfig):
    """Update server configuration"""
    # In a real implementation, this would update global config
    logger.info(f"Server config updated: {config}")
    return {"status": "updated"}

@app.get("/stats")
async def get_stats():
    """Get server statistics"""
    total_agents = len(agents_db)
    online_agents = len([a for a in agents_db.values() if a.get("status") == "online"])
    total_alerts = len(alerts_db)
    unacknowledged_alerts = len([a for a in alerts_db if not a.get("acknowledged", False)])

    platform_stats = {}
    for agent in agents_db.values():
        platform = agent.get("platform", "unknown")
        platform_stats[platform] = platform_stats.get(platform, 0) + 1

    return {
        "total_agents": total_agents,
        "online_agents": online_agents,
        "offline_agents": total_agents - online_agents,
        "total_alerts": total_alerts,
        "unacknowledged_alerts": unacknowledged_alerts,
        "platform_distribution": platform_stats,
        "uptime": "running"  # In a real implementation, track actual uptime
    }

def process_deployment(deployment_id: str):
    """Process a deployment in the background"""
    try:
        deployment = deployments_db[deployment_id]
        deployment["status"] = "processing"
        deployment["updated_at"] = datetime.now().isoformat()
        save_data()

        time.sleep(1)

        deployment["status"] = "manual_required"
        deployment["manual_action"] = {
            "message": "This API server does not execute remote installs. Use backend /api/unified deployment endpoints with AgentDeploymentService for actual deployment.",
            "target_platform": deployment.get("target_platform"),
            "target_ip": deployment.get("target_ip")
        }
        deployment["updated_at"] = datetime.now().isoformat()
        save_data()

        logger.info(f"Deployment {deployment_id} marked manual_required (no simulated completion)")

    except Exception as e:
        logger.error(f"Deployment {deployment_id} failed: {e}")
        deployment = deployments_db.get(deployment_id, {})
        deployment["status"] = "failed"
        deployment["error"] = str(e)
        deployment["updated_at"] = datetime.now().isoformat()
        save_data()

# WebSocket endpoint for real-time agent communication
@app.websocket("/ws/agent/{agent_id}")
async def websocket_endpoint(websocket: WebSocket, agent_id: str):
    await manager.connect(agent_id, websocket)
    try:
        while True:
            # Receive messages from agent
            data = await websocket.receive_json()
            logger.info(f"Received message from agent {agent_id}: {data}")

            # Handle different message types
            msg_type = data.get("type")

            if msg_type == "heartbeat":
                # Update agent status
                if agent_id in agents_db:
                    agents_db[agent_id]["last_seen"] = datetime.now().isoformat()
                    agents_db[agent_id]["status"] = "online"
                    save_data()

                # Send pong response
                await manager.send_personal_message(agent_id, {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })

            elif msg_type == "alert":
                # Store alert
                alert_data = data.get("data", {})
                alert_entry = {
                    "id": secrets.token_hex(8),
                    "agent_id": agent_id,
                    "timestamp": datetime.now().isoformat(),
                    **alert_data
                }
                alerts_db.append(alert_entry)
                save_data()

                logger.info(f"Alert received from agent {agent_id}: {alert_data.get('title', 'Unknown')}")

            elif msg_type == "command_result":
                # Log command result
                logger.info(f"Command result from agent {agent_id}: {data}")

    except WebSocketDisconnect:
        manager.disconnect(agent_id)
        # Mark agent as offline
        if agent_id in agents_db:
            agents_db[agent_id]["status"] = "offline"
            save_data()

# REST endpoint to send commands to agents
@app.post("/agents/{agent_id}/send_command")
async def send_command_to_agent(agent_id: str, command: Dict[str, Any]):
    """Send a command to a specific agent via WebSocket"""
    if agent_id not in manager.active_connections:
        raise HTTPException(status_code=404, detail="Agent not connected")

    # Generate command ID
    command_id = secrets.token_hex(8)
    command_message = {
        "type": "command",
        "command_id": command_id,
        "command_type": command.get("type"),
        "parameters": command.get("parameters", {}),
        "timestamp": datetime.now().isoformat()
    }

    await manager.send_personal_message(agent_id, command_message)

    logger.info(f"Command sent to agent {agent_id}: {command}")
    return {"status": "command_sent", "command_id": command_id}

# =============================================================================
# VPN MANAGEMENT ENDPOINTS
# =============================================================================

class VPNConfigModel(BaseModel):
    enabled: bool = True
    server_address: str = "10.200.200.1/24"
    port: int = 51820
    dns_servers: List[str] = ["1.1.1.1", "8.8.8.8"]
    kill_switch: bool = True
    max_clients: int = 10

class VPNClientModel(BaseModel):
    client_id: str
    name: str
    public_key: str
    private_key: str
    ip_address: str
    status: str = "active"

# In-memory VPN storage
vpn_config: Dict = {
    "enabled": True,
    "server_address": "10.200.200.1/24",
    "port": 51820,
    "dns_servers": ["1.1.1.1", "8.8.8.8"],
    "kill_switch": True,
    "max_clients": 10
}
vpn_clients: Dict[str, Dict] = {}

@app.get("/api/vpn/status")
async def get_vpn_status():
    """Get VPN server status"""
    try:
        # Check if WireGuard is running
        import subprocess
        result = subprocess.run(["wg", "show"], capture_output=True, text=True)
        is_running = result.returncode == 0

        return {
            "status": "running" if is_running else "stopped",
            "config": vpn_config,
            "clients_connected": len(vpn_clients),
            "server_address": vpn_config["server_address"],
            "port": vpn_config["port"]
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/api/vpn/clients")
async def get_vpn_clients():
    """Get all VPN clients"""
    return {"clients": list(vpn_clients.values())}

@app.post("/api/vpn/clients")
async def create_vpn_client(client: VPNClientModel):
    """Create a new VPN client"""
    if len(vpn_clients) >= vpn_config["max_clients"]:
        raise HTTPException(status_code=400, detail="Maximum clients reached")

    if client.client_id in vpn_clients:
        raise HTTPException(status_code=409, detail="Client already exists")

    vpn_clients[client.client_id] = client.dict()
    save_data()

    logger.info(f"VPN client created: {client.client_id}")
    return {"status": "created", "client": client.dict()}

@app.delete("/api/vpn/clients/{client_id}")
async def delete_vpn_client(client_id: str):
    """Delete a VPN client"""
    if client_id not in vpn_clients:
        raise HTTPException(status_code=404, detail="Client not found")

    del vpn_clients[client_id]
    save_data()

    logger.info(f"VPN client deleted: {client_id}")
    return {"status": "deleted"}

@app.put("/api/vpn/config")
async def update_vpn_config(config: VPNConfigModel):
    """Update VPN configuration"""
    global vpn_config
    vpn_config.update(config.dict())
    save_data()

    logger.info("VPN configuration updated")
    return {"status": "updated", "config": vpn_config}

@app.post("/api/vpn/generate-keys")
async def generate_wireguard_keys():
    """Generate new WireGuard key pair"""
    try:
        import subprocess

        # Generate private key
        private_proc = subprocess.run(["wg", "genkey"], capture_output=True, text=True, check=True)
        private_key = private_proc.stdout.strip()

        # Generate public key
        public_proc = subprocess.run(["wg", "pubkey"], input=private_key, capture_output=True, text=True, check=True)
        public_key = public_proc.stdout.strip()

        return {
            "private_key": private_key,
            "public_key": public_key
        }
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Key generation failed: {e}")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="WireGuard tools not found")

@app.get("/api/vpn/client-config/{client_id}")
async def get_client_config(client_id: str):
    """Generate client configuration file"""
    if client_id not in vpn_clients:
        raise HTTPException(status_code=404, detail="Client not found")

    client = vpn_clients[client_id]

    config = f"""[Interface]
PrivateKey = {client['private_key']}
Address = {client['ip_address']}/24
DNS = {', '.join(vpn_config['dns_servers'])}

[Peer]
PublicKey = {vpn_config.get('server_public_key', 'SERVER_PUBLIC_KEY_PLACEHOLDER')}
Endpoint = {vpn_config.get('server_endpoint', 'localhost')}:{vpn_config['port']}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
"""

    return {"config": config}


# =============================================================================
# END-USER DASHBOARD ENDPOINTS
# These provide a simplified view for normal end users, proxying data from
# the main backend (server_old.py on port 8001) and combining it with
# local agent data.
# =============================================================================

@app.get("/user/dashboard")
async def user_dashboard():
    """
    Simplified end-user dashboard.
    Combines backend system status with local agent metrics.
    """
    # Gather local agent stats
    total_agents = len(agents_db)
    online_agents = len([a for a in agents_db.values() if a.get("status") == "online"])
    recent_alerts = [a for a in alerts_db if not a.get("acknowledged", False)][-10:]

    # Try to get backend dashboard stats
    backend_stats = None
    try:
        resp = await http_client.get("/api/")
        if resp.status_code == 200:
            backend_info = resp.json()
            backend_stats = {
                "status": backend_info.get("status", "unknown"),
                "version": backend_info.get("version", "unknown"),
                "message": backend_info.get("message", ""),
            }
    except Exception as e:
        logger.warning(f"[Dashboard] Could not fetch backend stats: {e}")

    return {
        "system_status": "operational" if backend_stats else "degraded",
        "backend": backend_stats or {"status": "offline"},
        "agents": {
            "total": total_agents,
            "online": online_agents,
            "offline": total_agents - online_agents,
            "list": [
                {
                    "id": a.get("agent_id"),
                    "hostname": a.get("hostname"),
                    "platform": a.get("platform"),
                    "status": a.get("status"),
                    "ip": a.get("ip_address"),
                    "last_seen": a.get("last_heartbeat"),
                }
                for a in agents_db.values()
            ],
        },
        "alerts": {
            "total_unacknowledged": len(recent_alerts),
            "recent": recent_alerts,
        },
        "deployments": {
            "total": len(deployments_db),
            "active": len([d for d in deployments_db.values() if d.get("status") in ("pending", "processing")]),
        },
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/user/alerts")
async def user_alerts(limit: int = 50):
    """
    Get alerts for end users - combines local agent alerts with
    backend threat alerts (proxied).
    """
    # Local alerts
    local_alerts = sorted(
        alerts_db,
        key=lambda a: a.get("timestamp", ""),
        reverse=True
    )[:limit]

    # Try to get backend alerts
    backend_alerts = []
    try:
        resp = await http_client.get("/api/alerts", params={"limit": limit})
        if resp.status_code == 200:
            data = resp.json()
            backend_alerts = data if isinstance(data, list) else data.get("alerts", [])
    except Exception as e:
        logger.debug(f"[Alerts] Could not fetch backend alerts: {e}")

    return {
        "local_alerts": local_alerts,
        "backend_alerts": backend_alerts,
        "total": len(local_alerts) + len(backend_alerts),
    }


@app.get("/user/status")
async def user_system_status():
    """
    Quick system health check for end users.
    Shows whether the defense system is active and responsive.
    """
    checks = {
        "unified_agent": {"status": "online", "port": 8002},
        "backend_api": {"status": "unknown", "port": 8001},
        "database": {"status": "unknown"},
        "agents_active": len([a for a in agents_db.values() if a.get("status") == "online"]),
    }

    # Check backend health
    try:
        resp = await http_client.get("/api/", timeout=5.0)
        if resp.status_code == 200:
            checks["backend_api"]["status"] = "online"
            # If backend is online and connected to DB, it would return status: operational
            body = resp.json()
            if body.get("status") == "operational":
                checks["database"]["status"] = "connected"
            else:
                checks["database"]["status"] = "unknown"
        else:
            checks["backend_api"]["status"] = "degraded"
    except Exception:
        checks["backend_api"]["status"] = "offline"
        checks["database"]["status"] = "unreachable"

    all_online = all(
        v.get("status") in ("online", "connected")
        for k, v in checks.items()
        if isinstance(v, dict) and "status" in v
    )

    return {
        "overall": "healthy" if all_online else "degraded",
        "checks": checks,
        "timestamp": datetime.now().isoformat(),
    }


# =============================================================================
# BACKEND PROXY - Forward requests to the main backend for end users
# This allows the unified agent to act as a gateway to the full backend API
# =============================================================================

@app.api_route("/proxy/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_to_backend(path: str, request: Request):
    """
    Proxy any request to the main backend API.
    Forwards auth headers, query params, and body.
    Usage: GET /proxy/api/dashboard/stats → GET http://localhost:8001/api/dashboard/stats
    """
    try:
        # Forward headers (especially Authorization)
        headers = {}
        if "authorization" in request.headers:
            headers["Authorization"] = request.headers["authorization"]
        if "content-type" in request.headers:
            headers["Content-Type"] = request.headers["content-type"]

        # Build the target URL
        target_url = f"/api/{path}"

        # Forward query params
        params = dict(request.query_params)

        # Forward body for POST/PUT/PATCH
        body = None
        if request.method in ("POST", "PUT", "PATCH"):
            body = await request.body()

        resp = await http_client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=params,
            content=body,
        )

        # Return the backend's response
        return JSONResponse(
            status_code=resp.status_code,
            content=resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"raw": resp.text},
        )

    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Backend server is not reachable")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Backend server timed out")
    except Exception as e:
        logger.error(f"[Proxy] Error forwarding to backend: {e}")
        raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")


# =============================================================================
# END-USER HTML DASHBOARD (lightweight built-in UI)
# =============================================================================

@app.get("/portal", response_class=HTMLResponse)
async def user_portal():
    """
    Built-in lightweight HTML dashboard for end users.
    No React/npm required — works directly in the browser.
    """
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Metatron - Security Portal</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: #0a0e1a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }
        .header { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); border-bottom: 1px solid #1e40af33; padding: 20px 40px; display: flex; align-items: center; justify-content: space-between; }
        .header h1 { font-size: 1.5rem; color: #60a5fa; font-weight: 700; letter-spacing: 2px; }
        .header .status { display: flex; align-items: center; gap: 8px; }
        .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
        .dot.green { background: #22c55e; box-shadow: 0 0 8px #22c55e88; }
        .dot.red { background: #ef4444; box-shadow: 0 0 8px #ef444488; }
        .dot.yellow { background: #eab308; box-shadow: 0 0 8px #eab30888; }
        .container { max-width: 1400px; margin: 0 auto; padding: 30px 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .card { background: #0f172a; border: 1px solid #1e293b; border-radius: 12px; padding: 24px; transition: border-color 0.3s; }
        .card:hover { border-color: #3b82f655; }
        .card h3 { color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; }
        .card .value { font-size: 2.5rem; font-weight: 700; font-family: 'Consolas', monospace; }
        .card .sub { color: #64748b; font-size: 0.8rem; margin-top: 6px; }
        .blue { color: #3b82f6; }
        .green { color: #22c55e; }
        .red { color: #ef4444; }
        .amber { color: #f59e0b; }
        .section { background: #0f172a; border: 1px solid #1e293b; border-radius: 12px; padding: 24px; margin-bottom: 20px; }
        .section h2 { color: #60a5fa; font-size: 1.1rem; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; color: #64748b; font-size: 0.8rem; text-transform: uppercase; padding: 8px 12px; border-bottom: 1px solid #1e293b; }
        td { padding: 10px 12px; border-bottom: 1px solid #1e293b22; font-size: 0.9rem; }
        .badge { padding: 2px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
        .badge.online { background: #22c55e22; color: #22c55e; }
        .badge.offline { background: #ef444422; color: #ef4444; }
        .badge.critical { background: #ef444422; color: #ef4444; }
        .badge.high { background: #f59e0b22; color: #f59e0b; }
        .badge.medium { background: #eab30822; color: #eab308; }
        .badge.low { background: #3b82f622; color: #3b82f6; }
        .refresh-btn { background: #1e293b; border: 1px solid #334155; color: #94a3b8; padding: 8px 16px; border-radius: 8px; cursor: pointer; font-size: 0.85rem; }
        .refresh-btn:hover { background: #334155; color: #e2e8f0; }
        .footer { text-align: center; color: #475569; font-size: 0.8rem; padding: 20px; margin-top: 40px; border-top: 1px solid #1e293b; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .loading { animation: pulse 1.5s infinite; }
    </style>
</head>
<body>
    <div class="header">
        <h1>&#x1f6e1; METATRON SECURITY PORTAL</h1>
        <div class="status">
            <span id="statusDot" class="dot yellow"></span>
            <span id="statusText" style="font-size:0.9rem;">Connecting...</span>
            <button class="refresh-btn" onclick="loadDashboard()">&#x21bb; Refresh</button>
        </div>
    </div>
    <div class="container">
        <div class="grid" id="statsGrid">
            <div class="card loading"><h3>System Status</h3><div class="value blue">--</div></div>
            <div class="card loading"><h3>Active Agents</h3><div class="value green">--</div></div>
            <div class="card loading"><h3>Open Alerts</h3><div class="value amber">--</div></div>
            <div class="card loading"><h3>Deployments</h3><div class="value blue">--</div></div>
        </div>
        <div class="section">
            <h2>&#x1f4e1; Connected Agents</h2>
            <table>
                <thead><tr><th>Agent ID</th><th>Hostname</th><th>Platform</th><th>IP Address</th><th>Status</th><th>Last Seen</th></tr></thead>
                <tbody id="agentsTable"><tr><td colspan="6" style="color:#64748b;text-align:center;">Loading...</td></tr></tbody>
            </table>
        </div>
        <div class="section">
            <h2>&#x26a0; Recent Alerts</h2>
            <table>
                <thead><tr><th>Time</th><th>Agent</th><th>Severity</th><th>Category</th><th>Message</th></tr></thead>
                <tbody id="alertsTable"><tr><td colspan="5" style="color:#64748b;text-align:center;">Loading...</td></tr></tbody>
            </table>
        </div>
        <div class="section">
            <h2>&#x2705; System Health</h2>
            <div id="healthChecks" style="color:#64748b;">Loading...</div>
        </div>
    </div>
    <div class="footer">
        Metatron Anti-AI Defense System &bull; Unified Agent Portal v2.0 &bull; <span id="timestamp"></span>
    </div>
    <script>
        async function loadDashboard() {
            try {
                // Load dashboard data
                const [dashRes, statusRes] = await Promise.all([
                    fetch('/user/dashboard'),
                    fetch('/user/status')
                ]);
                const dash = await dashRes.json();
                const status = await statusRes.json();

                // Update status indicator
                const dot = document.getElementById('statusDot');
                const txt = document.getElementById('statusText');
                if (status.overall === 'healthy') {
                    dot.className = 'dot green'; txt.textContent = 'All Systems Operational';
                } else {
                    dot.className = 'dot yellow'; txt.textContent = 'Degraded';
                }

                // Update stat cards
                document.getElementById('statsGrid').innerHTML = `
                    <div class="card"><h3>System Status</h3><div class="value ${dash.system_status === 'operational' ? 'green' : 'amber'}">${dash.system_status.toUpperCase()}</div><div class="sub">Backend: ${dash.backend?.status || 'unknown'}</div></div>
                    <div class="card"><h3>Active Agents</h3><div class="value green">${dash.agents.online}</div><div class="sub">${dash.agents.total} total &bull; ${dash.agents.offline} offline</div></div>
                    <div class="card"><h3>Open Alerts</h3><div class="value amber">${dash.alerts.total_unacknowledged}</div><div class="sub">Unacknowledged</div></div>
                    <div class="card"><h3>Deployments</h3><div class="value blue">${dash.deployments.active}</div><div class="sub">${dash.deployments.total} total</div></div>
                `;

                // Update agents table
                const agents = dash.agents.list;
                document.getElementById('agentsTable').innerHTML = agents.length ? agents.map(a => `
                    <tr>
                        <td style="font-family:monospace;">${a.id || '-'}</td>
                        <td>${a.hostname || '-'}</td>
                        <td>${a.platform || '-'}</td>
                        <td style="font-family:monospace;">${a.ip || '-'}</td>
                        <td><span class="badge ${a.status}">${a.status}</span></td>
                        <td style="color:#64748b;">${a.last_seen ? new Date(a.last_seen).toLocaleString() : '-'}</td>
                    </tr>
                `).join('') : '<tr><td colspan="6" style="color:#64748b;text-align:center;">No agents registered</td></tr>';

                // Update alerts table
                const alerts = dash.alerts.recent;
                document.getElementById('alertsTable').innerHTML = alerts.length ? alerts.map(a => `
                    <tr>
                        <td style="color:#64748b;">${new Date(a.timestamp).toLocaleString()}</td>
                        <td style="font-family:monospace;">${a.agent_id || '-'}</td>
                        <td><span class="badge ${a.severity}">${a.severity}</span></td>
                        <td>${a.category || '-'}</td>
                        <td>${a.message || '-'}</td>
                    </tr>
                `).join('') : '<tr><td colspan="5" style="color:#64748b;text-align:center;">No alerts</td></tr>';

                // Update health checks
                const checks = status.checks;
                document.getElementById('healthChecks').innerHTML = Object.entries(checks).map(([k, v]) => {
                    if (typeof v === 'object') {
                        const color = v.status === 'online' || v.status === 'connected' ? '#22c55e' : v.status === 'offline' ? '#ef4444' : '#eab308';
                        return `<div style="display:flex;align-items:center;gap:8px;padding:6px 0;"><span class="dot" style="background:${color};box-shadow:0 0 6px ${color}88;"></span><span>${k}</span><span style="color:${color};margin-left:auto;">${v.status}${v.port ? ' :' + v.port : ''}</span></div>`;
                    }
                    return `<div style="padding:6px 0;"><span>${k}: </span><span class="blue">${v}</span></div>`;
                }).join('');

                document.getElementById('timestamp').textContent = new Date().toLocaleString();
            } catch (e) {
                document.getElementById('statusDot').className = 'dot red';
                document.getElementById('statusText').textContent = 'Connection Error';
                console.error('Dashboard load error:', e);
            }
        }

        // Initial load and auto-refresh every 15 seconds
        loadDashboard();
        setInterval(loadDashboard, 15000);
    </script>
</body>
</html>"""
    return HTMLResponse(content=html)


if __name__ == "__main__":
    uvicorn.run(
        "server_api:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info"
    )
