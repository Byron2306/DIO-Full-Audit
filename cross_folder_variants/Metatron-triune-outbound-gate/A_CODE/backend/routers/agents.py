"""
Agents Router - Handle local security agents
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from pathlib import Path
import uuid
import json
import io
from enum import Enum
from fastapi.responses import RedirectResponse

from .dependencies import (
    AgentEvent, AgentInfo, get_current_user, get_db, logger, check_permission
)
from .honeypots import ws_manager

router = APIRouter(prefix="/agent", tags=["Agents"])


def _deprecated_redirect(replacement: str) -> RedirectResponse:
    return RedirectResponse(
        url=replacement,
        status_code=307,
        headers={
            "X-Seraph-Deprecated": "true",
            "X-Seraph-Replacement": replacement
        }
    )


async def _track_deprecated_alias_hit(request: Request, legacy_path: str, replacement: str):
    """Track legacy alias usage for sunset planning"""
    try:
        db = get_db()
        await db.api_deprecation_hits.insert_one({
            "legacy_path": legacy_path,
            "replacement": replacement,
            "method": request.method,
            "user_agent": request.headers.get("user-agent"),
            "client_ip": request.client.host if request.client else None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except Exception as exc:
        logger.warning(f"Failed to track deprecated alias hit for {legacy_path}: {exc}")


class LegacyDownloadPlatform(str, Enum):
    linux = "linux"
    windows = "windows"
    macos = "macos"
    android = "android"
    ios = "ios"
    v7 = "v7"
    browser_extension = "browser-extension"

@router.post("/event")
async def receive_agent_event(event: AgentEvent):
    """Receive events from local security agents (no auth required for agents)"""
    db = get_db()
    logger.info(f"Agent event from {event.agent_name}: {event.event_type}")
    
    # Update or create agent record
    agent_doc = {
        "id": event.agent_id,
        "name": event.agent_name,
        "status": "online",
        "last_heartbeat": datetime.now(timezone.utc).isoformat(),
    }
    
    if event.event_type == "heartbeat":
        # Update agent system info
        agent_doc["system_info"] = event.data
        agent_doc["ip"] = event.data.get("network_interfaces", [{}])[0].get("ip") if event.data.get("network_interfaces") else None
        agent_doc["os"] = event.data.get("os")
        
        await db.agents.update_one(
            {"id": event.agent_id},
            {"$set": agent_doc, "$setOnInsert": {"created_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        
        # Broadcast to WebSocket
        await ws_manager.broadcast({
            "type": "agent_heartbeat",
            "agent_id": event.agent_id,
            "agent_name": event.agent_name,
            "timestamp": event.timestamp
        })
        
        return {"status": "ok", "message": "Heartbeat received"}
    
    elif event.event_type == "alert":
        # Create alert from agent
        alert_data = event.data
        alert_doc = {
            "id": str(uuid.uuid4()),
            "title": alert_data.get("title", "Agent Alert"),
            "type": alert_data.get("alert_type", "agent"),
            "severity": alert_data.get("severity", "medium"),
            "message": json.dumps(alert_data.get("details", {}))[:500],
            "status": "new",
            "source_agent": event.agent_name,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.alerts.insert_one(alert_doc)
        
        # Broadcast to WebSocket
        await ws_manager.broadcast({
            "type": "new_alert",
            "alert": alert_doc,
            "from_agent": event.agent_name
        })
        
        return {"status": "ok", "alert_id": alert_doc["id"]}
    
    elif event.event_type == "suricata_alert":
        # Create threat from Suricata IDS alert
        suricata_data = event.data
        severity = "critical" if suricata_data.get("severity", 3) == 1 else "high" if suricata_data.get("severity", 3) == 2 else "medium"
        
        threat_doc = {
            "id": str(uuid.uuid4()),
            "name": f"IDS Alert: {suricata_data.get('signature', 'Unknown')}",
            "type": "ids_alert",
            "severity": severity,
            "status": "active",
            "source_ip": suricata_data.get("src_ip"),
            "target_system": suricata_data.get("dest_ip"),
            "description": f"Suricata IDS detected: {suricata_data.get('signature', 'Unknown attack')}. Category: {suricata_data.get('category', 'unknown')}",
            "indicators": [
                f"Source: {suricata_data.get('src_ip')}:{suricata_data.get('src_port', 0)}",
                f"Destination: {suricata_data.get('dest_ip')}:{suricata_data.get('dest_port', 0)}",
                f"Signature ID: {suricata_data.get('signature_id', 'unknown')}"
            ],
            "ai_analysis": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "source_agent": event.agent_name
        }
        await db.threats.insert_one(threat_doc)
        
        # Broadcast
        await ws_manager.broadcast({
            "type": "new_threat",
            "threat": threat_doc,
            "from_agent": event.agent_name
        })
        
        return {"status": "ok", "threat_id": threat_doc["id"]}
    
    elif event.event_type == "falco_alert":
        # Create alert from Falco runtime security
        falco_data = event.data
        alert_doc = {
            "id": str(uuid.uuid4()),
            "title": f"Runtime: {falco_data.get('rule', 'Unknown')}",
            "type": "runtime_security",
            "severity": falco_data.get("priority", "medium").lower(),
            "message": falco_data.get("output", "Falco runtime security alert"),
            "status": "new",
            "source_agent": event.agent_name,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.alerts.insert_one(alert_doc)
        
        await ws_manager.broadcast({
            "type": "new_alert",
            "alert": alert_doc,
            "from_agent": event.agent_name
        })
        
        return {"status": "ok", "alert_id": alert_doc["id"]}
    
    elif event.event_type == "yara_match":
        # Create threat from YARA malware match
        yara_data = event.data
        threat_doc = {
            "id": str(uuid.uuid4()),
            "name": f"Malware: {yara_data.get('matches', [{}])[0].get('rule', 'Unknown')}",
            "type": "malware",
            "severity": yara_data.get('matches', [{}])[0].get('meta', {}).get('severity', 'high'),
            "status": "active",
            "source_ip": None,
            "target_system": yara_data.get("filepath", "Unknown"),
            "description": f"YARA rule matched on file: {yara_data.get('filepath', 'Unknown')}",
            "indicators": [m.get('rule', 'Unknown rule') for m in yara_data.get('matches', [])],
            "ai_analysis": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "source_agent": event.agent_name
        }
        await db.threats.insert_one(threat_doc)
        
        await ws_manager.broadcast({
            "type": "new_threat",
            "threat": threat_doc,
            "from_agent": event.agent_name
        })
        
        return {"status": "ok", "threat_id": threat_doc["id"]}
    
    elif event.event_type == "network_scan":
        # Store network scan results
        scan_doc = {
            "id": str(uuid.uuid4()),
            "agent_id": event.agent_id,
            "agent_name": event.agent_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hosts": event.data.get("hosts", [])
        }
        await db.network_scans.insert_one(scan_doc)
        
        # Update discovered hosts
        for host in event.data.get("hosts", []):
            await db.discovered_hosts.update_one(
                {"ip": host.get("ip")},
                {"$set": {**host, "last_seen": datetime.now(timezone.utc).isoformat(), "discovered_by": event.agent_name}},
                upsert=True
            )
        
        return {"status": "ok", "scan_id": scan_doc["id"]}
    
    # Default response for unknown event types
    return {"status": "ok", "message": f"Event {event.event_type} received"}

@router.get("/download/installer")
async def download_installer():
    """Download the defender installer script"""
    try:
        # Container runtime stores scripts under /app/scripts.
        script_path = Path("/app/scripts/defender_installer.py")
        if not script_path.exists():
            # Fallback for local non-container execution.
            script_path = Path(__file__).resolve().parent.parent / "scripts" / "defender_installer.py"
        with open(script_path, 'r') as f:
            content = f.read()
        
        return StreamingResponse(
            io.StringIO(content),
            media_type="text/x-python",
            headers={
                "Content-Disposition": "attachment; filename=defender_installer.py"
            }
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Installer not found")

@router.get("/download/advanced-agent")
async def download_advanced_agent(request: Request):
    """
    Legacy endpoint: the standalone advanced_agent.py has been superseded by the
    Unified Agent (unified_agent/core/agent.py).  Redirect to the canonical
    unified download so existing links and scripts keep working.
    """
    replacement = "/api/unified/agent/download"
    await _track_deprecated_alias_hit(request, "/api/agent/download/advanced-agent", replacement)
    return _deprecated_redirect(replacement)


@router.get("/download")
async def legacy_download_bundle_alias(request: Request):
    """Legacy alias: redirect to canonical unified bundle endpoint"""
    replacement = "/api/unified/agent/download"
    await _track_deprecated_alias_hit(request, "/api/agent/download", replacement)
    return _deprecated_redirect(replacement)


@router.get("/download/{platform}")
async def legacy_platform_download_alias(platform: LegacyDownloadPlatform, request: Request):
    """Legacy alias: redirect to canonical swarm platform download endpoint"""
    legacy_path = f"/api/agent/download/{platform.value}"
    replacement = f"/api/swarm/agent/download/{platform.value}"
    await _track_deprecated_alias_hit(request, legacy_path, replacement)
    return _deprecated_redirect(replacement)


@router.get("/install")
async def legacy_install_alias(request: Request):
    """Legacy alias: redirect to canonical unified linux install script endpoint"""
    replacement = "/api/unified/agent/install-script"
    await _track_deprecated_alias_hit(request, "/api/agent/install", replacement)
    return _deprecated_redirect(replacement)


@router.get("/install-script")
async def legacy_install_script_alias(request: Request):
    """Legacy alias: redirect to canonical unified linux install script endpoint"""
    replacement = "/api/unified/agent/install-script"
    await _track_deprecated_alias_hit(request, "/api/agent/install-script", replacement)
    return _deprecated_redirect(replacement)


@router.get("/install-windows")
async def legacy_install_windows_alias(request: Request):
    """Legacy alias: redirect to canonical unified windows install script endpoint"""
    replacement = "/api/unified/agent/install-windows"
    await _track_deprecated_alias_hit(request, "/api/agent/install-windows", replacement)
    return _deprecated_redirect(replacement)


@router.get("/deprecations/usage")
async def get_deprecation_usage(
    days: int = 30,
    limit: int = 20,
    current_user: dict = Depends(check_permission("admin"))
):
    """Get deprecated alias usage summary for migration tracking."""
    db = get_db()

    days = max(1, min(days, 365))
    limit = max(1, min(limit, 200))
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    pipeline = [
        {"$match": {"timestamp": {"$gte": since}}},
        {"$group": {
            "_id": {
                "legacy_path": "$legacy_path",
                "replacement": "$replacement"
            },
            "hits": {"$sum": 1},
            "last_seen": {"$max": "$timestamp"},
            "methods": {"$addToSet": "$method"},
            "user_agents": {"$addToSet": "$user_agent"}
        }},
        {"$sort": {"hits": -1, "last_seen": -1}},
        {"$limit": limit}
    ]

    rows = await db.api_deprecation_hits.aggregate(pipeline).to_list(limit)

    summary = []
    for row in rows:
        summary.append({
            "legacy_path": row.get("_id", {}).get("legacy_path"),
            "replacement": row.get("_id", {}).get("replacement"),
            "hits": row.get("hits", 0),
            "last_seen": row.get("last_seen"),
            "methods": row.get("methods", []),
            "sample_user_agents": [ua for ua in row.get("user_agents", []) if ua][:3]
        })

    total_hits = await db.api_deprecation_hits.count_documents({"timestamp": {"$gte": since}})

    return {
        "window_days": days,
        "since": since,
        "total_hits": total_hits,
        "top_paths": summary
    }

# Agents list endpoint
agents_router = APIRouter(prefix="/agents", tags=["Agents"])

@agents_router.get("", response_model=List[AgentInfo])
async def get_agents(current_user: dict = Depends(get_current_user)):
    """Get all registered agents"""
    db = get_db()
    agents = await db.agents.find({}, {"_id": 0}).sort("last_heartbeat", -1).to_list(100)
    
    # Mark agents as offline if no heartbeat in 2 minutes
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    result = []
    for agent in agents:
        if agent.get("last_heartbeat", "") < cutoff:
            agent["status"] = "offline"
        # Handle both 'id' and 'agent_id' field names
        if "agent_id" in agent and "id" not in agent:
            agent["id"] = agent["agent_id"]
        # Ensure name field exists
        if "name" not in agent:
            agent["name"] = agent.get("hostname", agent.get("id", "Unknown"))
        try:
            result.append(AgentInfo(**agent))
        except Exception as e:
            logger.warning(f"Skipping invalid agent record: {e}")
    
    return result
