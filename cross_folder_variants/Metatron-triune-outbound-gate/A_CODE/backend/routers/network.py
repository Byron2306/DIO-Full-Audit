"""
Network Topology Router
"""
from fastapi import APIRouter, Depends
from typing import List

from .dependencies import (
    NetworkNode, NetworkLink, NetworkTopology, get_current_user, get_db
)

router = APIRouter(prefix="/network", tags=["Network"])

@router.get("/topology", response_model=NetworkTopology)
async def get_network_topology(current_user: dict = Depends(get_current_user)):
    """Generate network topology based on threats and system data"""
    db = get_db()
    
    # Get all threats with IPs
    threats = await db.threats.find({"status": {"$ne": "resolved"}}, {"_id": 0}).to_list(100)
    
    # Build nodes - core infrastructure
    nodes = [
        NetworkNode(id="firewall-1", label="Edge Firewall", type="firewall", ip="10.0.0.1", status="protected"),
        NetworkNode(id="router-1", label="Core Router", type="router", ip="10.0.0.2", status="normal"),
        NetworkNode(id="server-web", label="Web Server", type="server", ip="10.0.1.10", status="normal"),
        NetworkNode(id="server-api", label="API Server", type="server", ip="10.0.1.11", status="normal"),
        NetworkNode(id="server-db", label="Database", type="server", ip="10.0.1.20", status="protected"),
        NetworkNode(id="server-ml", label="ML Pipeline", type="server", ip="10.0.1.30", status="normal"),
        NetworkNode(id="server-file", label="File Server", type="server", ip="10.0.1.40", status="normal"),
        NetworkNode(id="cloud-1", label="Cloud Services", type="cloud", ip="cloud.defense.io", status="normal"),
        NetworkNode(id="ws-1", label="Analyst WS-01", type="workstation", ip="10.0.2.10", status="normal"),
        NetworkNode(id="ws-2", label="Analyst WS-02", type="workstation", ip="10.0.2.11", status="normal"),
    ]
    
    # Add attacker nodes based on threats
    attacker_ips = set()
    for threat in threats:
        if threat.get("source_ip") and threat["source_ip"] not in attacker_ips:
            attacker_ips.add(threat["source_ip"])
            severity = threat.get("severity", "medium")
            nodes.append(NetworkNode(
                id=f"attacker-{threat['source_ip'].replace('.', '-')}",
                label=f"Threat: {threat['name'][:20]}",
                type="attacker",
                ip=threat["source_ip"],
                status="compromised" if severity in ["critical", "high"] else "suspicious",
                threat_count=1
            ))
    
    # Update node statuses based on threats targeting them
    target_threats = {}
    for threat in threats:
        target = threat.get("target_system", "")
        if target:
            target_lower = target.lower()
            if "api" in target_lower:
                target_threats["server-api"] = target_threats.get("server-api", 0) + 1
            elif "web" in target_lower:
                target_threats["server-web"] = target_threats.get("server-web", 0) + 1
            elif "ml" in target_lower or "pipeline" in target_lower:
                target_threats["server-ml"] = target_threats.get("server-ml", 0) + 1
            elif "file" in target_lower:
                target_threats["server-file"] = target_threats.get("server-file", 0) + 1
            elif "database" in target_lower or "db" in target_lower:
                target_threats["server-db"] = target_threats.get("server-db", 0) + 1
    
    for node in nodes:
        if node.id in target_threats:
            node.threat_count = target_threats[node.id]
            node.status = "suspicious" if target_threats[node.id] >= 1 else node.status
            if target_threats[node.id] >= 2:
                node.status = "compromised"
    
    # Build links - infrastructure connections
    links = [
        NetworkLink(source="firewall-1", target="router-1", type="connection"),
        NetworkLink(source="router-1", target="server-web", type="connection"),
        NetworkLink(source="router-1", target="server-api", type="connection"),
        NetworkLink(source="router-1", target="server-db", type="connection"),
        NetworkLink(source="router-1", target="server-ml", type="connection"),
        NetworkLink(source="router-1", target="server-file", type="connection"),
        NetworkLink(source="server-api", target="server-db", type="data_flow"),
        NetworkLink(source="server-api", target="server-ml", type="data_flow"),
        NetworkLink(source="server-web", target="server-api", type="data_flow"),
        NetworkLink(source="cloud-1", target="firewall-1", type="connection"),
        NetworkLink(source="router-1", target="ws-1", type="connection"),
        NetworkLink(source="router-1", target="ws-2", type="connection"),
    ]
    
    # Add attack links from threats
    for threat in threats:
        if threat.get("source_ip"):
            attacker_id = f"attacker-{threat['source_ip'].replace('.', '-')}"
            
            links.append(NetworkLink(
                source=attacker_id,
                target="firewall-1",
                type="attack",
                strength=2.0 if threat.get("severity") == "critical" else 1.5
            ))
    
    return NetworkTopology(nodes=nodes, links=links)

@router.get("/discovered-hosts")
async def get_discovered_hosts(current_user: dict = Depends(get_current_user)):
    db = get_db()
    # Primary source is discovered_devices from services.network_discovery.
    hosts = await db.discovered_devices.find({}, {"_id": 0}).sort("last_seen", -1).to_list(100)
    # Backward compatibility for older agent ingest paths.
    if not hosts:
        hosts = await db.discovered_hosts.find({}, {"_id": 0}).sort("last_seen", -1).to_list(100)
    return {"hosts": hosts, "count": len(hosts)}

@router.get("/hosts")
async def get_network_hosts(limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Get network hosts - alias for discovered-hosts"""
    db = get_db()
    hosts = await db.discovered_devices.find({}, {"_id": 0}).sort("last_seen", -1).to_list(limit)
    if not hosts:
        hosts = await db.discovered_hosts.find({}, {"_id": 0}).sort("last_seen", -1).to_list(limit)
    return {"hosts": hosts, "count": len(hosts)}

@router.get("/scans")
async def get_network_scans(current_user: dict = Depends(get_current_user)):
    db = get_db()
    scans = await db.network_scans.find({}, {"_id": 0}).sort("timestamp", -1).to_list(50)
    return scans
