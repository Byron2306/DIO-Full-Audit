"""
Advanced Security Router
========================
API endpoints for advanced security features:
- MCP Server
- Vector Memory
- VNS (Virtual Network Sensor)
- Quantum Security
- AI Reasoning
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone

from .dependencies import get_current_user, check_permission, get_db

import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/advanced", tags=["Advanced Security"])


# =============================================================================
# MODELS
# =============================================================================

class MCPToolRequest(BaseModel):
    tool_id: str
    params: Dict[str, Any]
    trace_id: Optional[str] = None


class MemoryStoreRequest(BaseModel):
    content: str
    namespace: str = "observations"
    structured_data: Optional[Dict[str, Any]] = None
    source: str = "api"
    trust_level: str = "low"
    confidence: float = 0.5
    ttl_days: Optional[int] = None


class MemorySearchRequest(BaseModel):
    query: str
    namespace: Optional[str] = None
    top_k: int = 10
    min_confidence: float = 0.0


class IncidentCaseRequest(BaseModel):
    title: str
    symptoms: List[Dict[str, Any]]
    indicators: List[str]
    affected_hosts: List[str]
    confidence: float = 0.5


class FlowRecordRequest(BaseModel):
    src_ip: str
    src_port: int
    dst_ip: str
    dst_port: int
    protocol: str = "TCP"
    bytes_sent: int = 0
    bytes_recv: int = 0
    ja3_hash: Optional[str] = None
    sni: Optional[str] = None


class DNSQueryRequest(BaseModel):
    src_ip: str
    query_name: str
    query_type: str = "A"
    response_code: str = "NOERROR"
    response_ips: List[str] = []


class ThreatAnalysisRequest(BaseModel):
    title: str
    description: str
    source: Optional[str] = None
    indicators: List[str] = []
    process_name: Optional[str] = None
    command_line: Optional[str] = None


class AIQueryRequest(BaseModel):
    question: str
    context: Optional[Dict[str, Any]] = None


# =============================================================================
# DASHBOARD (AGGREGATED STATUS)
# =============================================================================

@router.get("/dashboard")
async def get_advanced_dashboard(current_user: dict = Depends(get_current_user)):
    """Get unified advanced security dashboard data.

    This endpoint powers `frontend/src/pages/AdvancedServicesPage.jsx`. Keep it:
    - Shape-compatible with the UI (no extra nesting)
    - Fail-open (partial results when optional subsystems are unavailable)
    - Useful after restarts (seed vector memory from DB when empty)
    """
    _ = current_user

    payload: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mcp": {},
        "memory": {},
        "vns": {},
        "deception": {},
        "world": {},
        "governance": {},
        "quantum": {},
        "ai": {},
        "errors": {},
    }

    # MCP server
    try:
        from services.mcp_server import mcp_server
        payload["mcp"] = mcp_server.get_server_status()
    except Exception as e:
        payload["mcp"] = {"tools_registered": 0, "pending_requests": 0, "total_executions": 0}
        payload["errors"]["mcp"] = str(e)

    # Vector memory (seed from DB if empty)
    try:
        from services.vector_memory import vector_memory
        stats = vector_memory.get_memory_stats()
        if int(stats.get("total_entries") or 0) <= 0:
            try:
                db = get_db()
                from services.vector_memory import MemoryNamespace, TrustLevel

                threats = await db.threats.find({}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
                alerts = await db.alerts.find({}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)

                for t in threats:
                    tid = t.get("id") or t.get("threat_id")
                    name = t.get("name") or "Threat"
                    severity = t.get("severity") or "unknown"
                    ttype = t.get("type") or "unknown"
                    created_at = t.get("created_at") or ""
                    vector_memory.store(
                        content=f"[Threat] {name} ({ttype}/{severity}) {created_at} id={tid}",
                        namespace=MemoryNamespace.OBSERVATIONS,
                        structured_data={"origin": "db.threats", "threat_id": tid, "severity": severity, "type": ttype},
                        source="db.threats",
                        source_type="pipeline",
                        created_by="system:seed",
                        trust_level=TrustLevel.MEDIUM,
                        confidence=0.7,
                        ttl_days=30,
                    )

                for a in alerts:
                    aid = a.get("id") or a.get("alert_id")
                    title = a.get("title") or "Alert"
                    severity = a.get("severity") or "unknown"
                    atype = a.get("type") or "unknown"
                    created_at = a.get("created_at") or ""
                    vector_memory.store(
                        content=f"[Alert] {title} ({atype}/{severity}) {created_at} id={aid}",
                        namespace=MemoryNamespace.OBSERVATIONS,
                        structured_data={"origin": "db.alerts", "alert_id": aid, "severity": severity, "type": atype},
                        source="db.alerts",
                        source_type="pipeline",
                        created_by="system:seed",
                        trust_level=TrustLevel.LOW,
                        confidence=0.6,
                        ttl_days=14,
                    )

                stats = vector_memory.get_memory_stats()
                stats["seeded_from_db"] = True
                stats["seeded_threats"] = len(threats)
                stats["seeded_alerts"] = len(alerts)
            except Exception as se:
                stats["seed_error"] = str(se)

        payload["memory"] = stats
    except Exception as e:
        payload["memory"] = {
            "total_entries": 0,
            "total_cases": 0,
            "total_intel": 0,
            "embedding_dimension": 0,
        }
        payload["errors"]["memory"] = str(e)

    # VNS
    try:
        from services.vns import vns
        payload["vns"] = vns.get_vns_stats()
    except Exception as e:
        payload["vns"] = {
            "total_flows": 0,
            "suspicious_flows": 0,
            "total_dns_queries": 0,
            "suspicious_dns": 0,
            "tls_fingerprints": 0,
            "beacon_detections": 0,
        }
        payload["errors"]["vns"] = str(e)

    # Deception state
    try:
        from deception_engine import deception_engine

        deception_status = deception_engine.get_status()
        db = get_db()
        recent_events = []
        active_campaigns = 0
        route_mix: Dict[str, int] = {}
        disinformation_sessions = 0

        try:
            recent_events = await db.deception_events.find({}, {"_id": 0}).sort("timestamp", -1).limit(100).to_list(100)
        except Exception:
            recent_events = []

        try:
            active_campaigns = await db.deception_campaigns.count_documents({})
        except Exception:
            active_campaigns = 0

        for event in recent_events:
            route = str(event.get("route") or "unknown")
            route_mix[route] = route_mix.get(route, 0) + 1
            if route == "disinformation":
                disinformation_sessions += 1

        payload["deception"] = {
            "engine": "Seraph Deception Engine",
            "status": "active",
            "active_campaigns": active_campaigns,
            "recent_events": len(recent_events),
            "route_mix": route_mix,
            "trap_hits": route_mix.get("trap_sink", 0),
            "disinformation_sessions": disinformation_sessions,
            "config": deception_status.get("config", {}) if isinstance(deception_status, dict) else {},
        }
    except Exception as e:
        payload["deception"] = {
            "engine": "Seraph Deception Engine",
            "status": "degraded",
            "active_campaigns": 0,
            "recent_events": 0,
            "route_mix": {},
            "trap_hits": 0,
            "disinformation_sessions": 0,
            "config": {},
        }
        payload["errors"]["deception"] = str(e)

    # World / triune state
    try:
        db = get_db()
        world_summary: Dict[str, Any] = {
            "risk_level": "unknown",
            "ml_confidence": 0.0,
            "active_campaigns": 0,
            "trust": {},
            "hotspots": 0,
            "actions": 0,
            "hypotheses": 0,
            "triune_analyses": 0,
        }

        try:
            from backend.services.world_manifold import world_manifold

            manifold = world_manifold.get_current_manifold() or {}
            snapshot = manifold.get("snapshot") if isinstance(manifold, dict) else {}
            trust = snapshot.get("trust") if isinstance(snapshot, dict) else {}
            if isinstance(trust, dict):
                world_summary["trust"] = trust
            if isinstance(manifold, dict):
                world_summary["world_state_hash"] = manifold.get("world_state_hash")
                world_summary["snapshot_version"] = manifold.get("version")
        except Exception:
            pass

        try:
            triune_count = await db.triune_analysis.count_documents({})
        except Exception:
            triune_count = 0

        try:
            threats = await db.threats.find({}, {"_id": 0, "severity": 1, "status": 1}).sort("created_at", -1).limit(25).to_list(25)
        except Exception:
            threats = []

        severity_weights = {"critical": 95, "high": 78, "medium": 52, "low": 28}
        active_threat_scores = [
            severity_weights.get(str(t.get("severity") or "medium").lower(), 45)
            for t in threats
            if str(t.get("status") or "active").lower() in {"active", "open", "new"}
        ]
        max_risk = max(active_threat_scores) if active_threat_scores else 18
        if max_risk >= 90:
            risk_level = "critical"
        elif max_risk >= 70:
            risk_level = "elevated"
        elif max_risk >= 45:
            risk_level = "guarded"
        else:
            risk_level = "stable"

        try:
            campaigns_count = await db.threat_campaigns.count_documents({})
        except Exception:
            campaigns_count = 0

        world_summary.update(
            {
                "risk_level": risk_level,
                "ml_confidence": round(min(0.98, max_risk / 100), 2),
                "active_campaigns": campaigns_count,
                "hotspots": min(len(active_threat_scores), 8),
                "actions": min(len(active_threat_scores), 8),
                "hypotheses": min(max(1, len(threats)), 8) if threats else 0,
                "triune_analyses": triune_count,
            }
        )
        payload["world"] = world_summary
    except Exception as e:
        payload["world"] = {
            "risk_level": "unknown",
            "ml_confidence": 0.0,
            "active_campaigns": 0,
            "trust": {},
            "hotspots": 0,
            "actions": 0,
            "hypotheses": 0,
            "triune_analyses": 0,
        }
        payload["errors"]["world"] = str(e)

    # Governance / harmonic / outbound state
    try:
        db = get_db()
        pending_decisions = []
        executor_ready = 0
        harmonic_review_required = 0
        world_state_mismatches = 0
        notation_narrowed = 0
        pulse_alerts = 0

        try:
            pending_decisions = await db.triune_decisions.find(
                {"status": "pending"},
                {"_id": 0, "decision_id": 1, "decision_type": 1, "created_at": 1},
            ).sort("created_at", 1).limit(50).to_list(50)
        except Exception:
            pending_decisions = []

        try:
            queue_docs = await db.outbound_gate_queue.find(
                {},
                {
                    "_id": 0,
                    "status": 1,
                    "harmonic_review_required": 1,
                    "world_state_hash_match": 1,
                    "harmonic_notation_controls": 1,
                    "vns_events": 1,
                },
            ).sort("created_at", -1).limit(100).to_list(100)
        except Exception:
            queue_docs = []

        for doc in queue_docs:
            if str(doc.get("status") or "").lower() in {"approved", "approved_pending_harmonic_controls", "pending_executor"}:
                executor_ready += 1
            if bool(doc.get("harmonic_review_required")):
                harmonic_review_required += 1
            if doc.get("world_state_hash_match") is False:
                world_state_mismatches += 1
            notation_controls = doc.get("harmonic_notation_controls") or {}
            if isinstance(notation_controls, dict) and notation_controls.get("notation_narrowing_required"):
                notation_narrowed += 1
            pulse_alerts += len(doc.get("vns_events") or [])

        payload["governance"] = {
            "pending_decisions": len(pending_decisions),
            "executor_ready": executor_ready,
            "harmonic_review_required": harmonic_review_required,
            "world_state_mismatches": world_state_mismatches,
            "notation_narrowed": notation_narrowed,
            "pulse_events": pulse_alerts,
            "recent_pending": pending_decisions[:5],
        }
    except Exception as e:
        payload["governance"] = {
            "pending_decisions": 0,
            "executor_ready": 0,
            "harmonic_review_required": 0,
            "world_state_mismatches": 0,
            "notation_narrowed": 0,
            "pulse_events": 0,
            "recent_pending": [],
        }
        payload["errors"]["governance"] = str(e)

    # Quantum security
    try:
        from services.quantum_security import quantum_security
        payload["quantum"] = quantum_security.get_quantum_status()
    except Exception as e:
        payload["quantum"] = {"mode": "simulation", "keypairs": {"total": 0}}
        payload["errors"]["quantum"] = str(e)

    # AI reasoning
    try:
        from services.ai_reasoning import ai_reasoning
        payload["ai"] = ai_reasoning.get_reasoning_stats()
    except Exception as e:
        payload["ai"] = {"analyses_performed": 0, "ollama": {"status": "disconnected"}}
        payload["errors"]["ai"] = str(e)

    if not payload["errors"]:
        payload.pop("errors", None)

    return payload


# =============================================================================
# MCP SERVER ENDPOINTS
# =============================================================================

@router.get("/mcp/tools")
async def list_mcp_tools(current_user: dict = Depends(get_current_user)):
    """List available MCP tools"""
    from services.mcp_server import mcp_server
    return {"tools": mcp_server.get_tool_catalog()}


@router.get("/mcp/tools/{tool_id}")
async def get_mcp_tool(tool_id: str, current_user: dict = Depends(get_current_user)):
    """Get MCP tool details"""
    from services.mcp_server import mcp_server
    
    if tool_id not in mcp_server.tools:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    tool = mcp_server.tools[tool_id]
    return {
        "tool_id": tool.tool_id,
        "name": tool.name,
        "description": tool.description,
        "category": tool.category.value,
        "version": tool.version,
        "input_schema": tool.input_schema,
        "output_schema": tool.output_schema,
        "required_trust_state": tool.required_trust_state,
        "rate_limit": tool.rate_limit
    }


@router.post("/mcp/execute")
async def execute_mcp_tool(
    request: MCPToolRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Execute an MCP tool"""
    from services.mcp_server import mcp_server, MCPMessageType
    import asyncio
    
    # Create MCP message
    message = mcp_server.create_message(
        message_type=MCPMessageType.TOOL_REQUEST,
        source=f"operator:{current_user.get('email', 'unknown')}",
        destination=request.tool_id,
        payload={"params": request.params},
        trace_id=request.trace_id
    )
    
    # Execute
    response = await mcp_server.handle_message(message)
    
    return {
        "message_id": response.message_id,
        "status": response.payload.get("status"),
        "output": response.payload.get("output"),
        "error": response.payload.get("error"),
        "execution_id": response.payload.get("execution_id")
    }


@router.get("/mcp/history")
async def get_mcp_history(
    tool_id: str = None,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """Get MCP execution history"""
    from services.mcp_server import mcp_server
    return {"executions": mcp_server.get_execution_history(tool_id=tool_id, limit=limit)}


@router.get("/mcp/status")
async def get_mcp_status(current_user: dict = Depends(get_current_user)):
    """Get MCP server status"""
    from services.mcp_server import mcp_server
    return mcp_server.get_server_status()


# =============================================================================
# VECTOR MEMORY ENDPOINTS
# =============================================================================

@router.post("/memory/store")
async def store_memory(
    request: MemoryStoreRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Store a memory entry"""
    from services.vector_memory import vector_memory, MemoryNamespace, TrustLevel
    
    namespace = MemoryNamespace(request.namespace)
    trust_level = TrustLevel(request.trust_level)
    
    entry = vector_memory.store(
        content=request.content,
        namespace=namespace,
        structured_data=request.structured_data,
        source=request.source,
        source_type="api",
        created_by=current_user.get("email", "unknown"),
        trust_level=trust_level,
        confidence=request.confidence,
        ttl_days=request.ttl_days
    )
    
    return {
        "entry_id": entry.entry_id,
        "namespace": entry.namespace.value,
        "trust_level": entry.trust_level.value
    }


@router.post("/memory/search")
async def search_memory(
    request: MemorySearchRequest,
    current_user: dict = Depends(get_current_user)
):
    """Search memory by semantic similarity"""
    from services.vector_memory import vector_memory, MemoryNamespace
    
    namespace = MemoryNamespace(request.namespace) if request.namespace else None
    
    results = vector_memory.retrieve(
        query=request.query,
        namespace=namespace,
        top_k=request.top_k,
        min_confidence=request.min_confidence
    )
    
    return {
        "results": [
            {
                "entry_id": entry.entry_id,
                "content": entry.content[:500],
                "namespace": entry.namespace.value,
                "trust_level": entry.trust_level.value,
                "confidence": entry.confidence,
                "similarity": score,
                "source": entry.source
            }
            for entry, score in results
        ],
        "count": len(results)
    }


@router.post("/memory/case")
async def create_incident_case(
    request: IncidentCaseRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Create an incident case"""
    from services.vector_memory import vector_memory
    
    case = vector_memory.create_case(
        title=request.title,
        symptoms=request.symptoms,
        indicators=request.indicators,
        affected_hosts=request.affected_hosts,
        created_by=current_user.get("email", "unknown"),
        confidence=request.confidence
    )
    
    return {
        "case_id": case.case_id,
        "title": case.title,
        "status": case.status
    }


@router.post("/memory/case/{case_id}/similar")
async def find_similar_cases(
    case_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Find similar historical cases"""
    from services.vector_memory import vector_memory
    
    case = vector_memory.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    similar = vector_memory.find_similar_cases(
        symptoms=case.symptoms,
        indicators=case.indicators
    )
    
    return {
        "similar_cases": [
            {
                "case_id": c.case_id,
                "title": c.title,
                "status": c.status,
                "root_cause": c.root_cause,
                "similarity": score
            }
            for c, score in similar
        ]
    }


@router.get("/memory/stats")
async def get_memory_stats(current_user: dict = Depends(get_current_user)):
    """Get memory database statistics"""
    from services.vector_memory import vector_memory
    stats = vector_memory.get_memory_stats()

    # Make the advanced dashboard useful after restart by seeding memory from
    # real DB telemetry (threats/alerts) when the in-memory store is empty.
    if int(stats.get("total_entries") or 0) <= 0:
        try:
            db = get_db()
            from services.vector_memory import MemoryNamespace, TrustLevel

            threats = await db.threats.find({}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
            alerts = await db.alerts.find({}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)

            for t in threats:
                tid = t.get("id") or t.get("threat_id")
                name = t.get("name") or "Threat"
                severity = t.get("severity") or "unknown"
                ttype = t.get("type") or "unknown"
                created_at = t.get("created_at") or ""
                vector_memory.store(
                    content=f"[Threat] {name} ({ttype}/{severity}) {created_at} id={tid}",
                    namespace=MemoryNamespace.OBSERVATIONS,
                    structured_data={"origin": "db.threats", "threat_id": tid, "severity": severity, "type": ttype},
                    source="db.threats",
                    source_type="pipeline",
                    created_by="system:seed",
                    trust_level=TrustLevel.MEDIUM,
                    confidence=0.7,
                    ttl_days=30,
                )

            for a in alerts:
                aid = a.get("id") or a.get("alert_id")
                title = a.get("title") or "Alert"
                severity = a.get("severity") or "unknown"
                atype = a.get("type") or "unknown"
                created_at = a.get("created_at") or ""
                vector_memory.store(
                    content=f"[Alert] {title} ({atype}/{severity}) {created_at} id={aid}",
                    namespace=MemoryNamespace.OBSERVATIONS,
                    structured_data={"origin": "db.alerts", "alert_id": aid, "severity": severity, "type": atype},
                    source="db.alerts",
                    source_type="pipeline",
                    created_by="system:seed",
                    trust_level=TrustLevel.LOW,
                    confidence=0.6,
                    ttl_days=14,
                )

            stats = vector_memory.get_memory_stats()
            stats["seeded_from_db"] = True
            stats["seeded_threats"] = len(threats)
            stats["seeded_alerts"] = len(alerts)
        except Exception as e:
            stats["seed_error"] = str(e)

    return stats


# =============================================================================
# VNS (VIRTUAL NETWORK SENSOR) ENDPOINTS
# =============================================================================

@router.post("/vns/flow")
async def record_network_flow(
    request: FlowRecordRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Record a network flow"""
    from services.vns import vns
    
    flow = vns.record_flow(
        src_ip=request.src_ip,
        src_port=request.src_port,
        dst_ip=request.dst_ip,
        dst_port=request.dst_port,
        protocol=request.protocol,
        bytes_sent=request.bytes_sent,
        bytes_recv=request.bytes_recv,
        ja3_hash=request.ja3_hash,
        sni=request.sni
    )
    
    return {
        "flow_id": flow.flow_id,
        "direction": flow.direction.value,
        "status": flow.status.value,
        "threat_score": flow.threat_score,
        "threat_indicators": flow.threat_indicators
    }


@router.post("/vns/dns")
async def record_dns_query(
    request: DNSQueryRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Record a DNS query"""
    from services.vns import vns
    
    query = vns.record_dns_query(
        src_ip=request.src_ip,
        query_name=request.query_name,
        query_type=request.query_type,
        response_code=request.response_code,
        response_ips=request.response_ips
    )
    
    return {
        "query_id": query.query_id,
        "is_suspicious": query.is_suspicious,
        "threat_indicators": query.threat_indicators
    }


@router.get("/vns/flows")
async def get_network_flows(
    src_ip: str = None,
    dst_ip: str = None,
    suspicious_only: bool = False,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """Query network flows"""
    from services.vns import vns

    if not vns.flows:
        # Best-effort: ingest Zeek telemetry when available so VNS dashboards aren't empty.
        try:
            vns.ingest_zeek_recent()
        except Exception:
            pass
    
    flows = vns.get_flows(
        src_ip=src_ip,
        dst_ip=dst_ip,
        suspicious_only=suspicious_only,
        limit=limit
    )
    
    return {"flows": flows, "count": len(flows)}


@router.get("/vns/dns")
async def get_dns_queries(
    src_ip: str = None,
    domain: str = None,
    suspicious_only: bool = False,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """Query DNS queries"""
    from services.vns import vns

    if not vns.dns_queries:
        try:
            vns.ingest_zeek_recent()
        except Exception:
            pass
    
    queries = vns.get_dns_queries(
        src_ip=src_ip,
        domain=domain,
        suspicious_only=suspicious_only,
        limit=limit
    )
    
    return {"queries": queries, "count": len(queries)}


@router.get("/vns/beacons")
async def get_beacon_detections(
    confirmed_only: bool = False,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Get C2 beacon detections"""
    from services.vns import vns

    if not vns.flows and not vns.beacon_detections:
        try:
            vns.ingest_zeek_recent()
        except Exception:
            pass
    
    beacons = vns.get_beacon_detections(confirmed_only=confirmed_only, limit=limit)
    return {"beacons": beacons, "count": len(beacons)}


@router.post("/vns/canary/ip")
async def add_canary_ip(
    ip: str,
    current_user: dict = Depends(check_permission("write"))
):
    """Add a canary IP"""
    from services.vns import vns
    vns.add_canary_ip(ip)
    return {"status": "added", "canary_ip": ip}


@router.post("/vns/canary/domain")
async def add_canary_domain(
    domain: str,
    current_user: dict = Depends(check_permission("write"))
):
    """Add a canary domain"""
    from services.vns import vns
    vns.add_canary_domain(domain)
    return {"status": "added", "canary_domain": domain}


@router.post("/vns/validate")
async def validate_endpoint_telemetry(
    endpoint_ip: str,
    endpoint_flows: List[Dict[str, Any]],
    current_user: dict = Depends(get_current_user)
):
    """Validate endpoint telemetry against VNS"""
    from services.vns import vns
    
    result = vns.validate_endpoint_telemetry(endpoint_ip, endpoint_flows)
    return result


@router.get("/vns/stats")
async def get_vns_stats(current_user: dict = Depends(get_current_user)):
    """Get VNS statistics"""
    from services.vns import vns
    return vns.get_vns_stats()


# =============================================================================
# QUANTUM SECURITY ENDPOINTS
# =============================================================================

@router.post("/quantum/keypair/kyber")
async def generate_kyber_keypair(
    key_id: str = None,
    security_level: int = 768,
    current_user: dict = Depends(check_permission("write"))
):
    """Generate a Kyber key pair (post-quantum KEM)"""
    from services.quantum_security import quantum_security
    
    keypair = quantum_security.generate_kyber_keypair(key_id, security_level)
    
    return {
        "key_id": keypair.key_id,
        "algorithm": keypair.algorithm,
        "public_key": keypair.public_key,
        "expires_at": keypair.expires_at
    }


@router.post("/quantum/keypair/dilithium")
async def generate_dilithium_keypair(
    key_id: str = None,
    security_level: int = 3,
    current_user: dict = Depends(check_permission("write"))
):
    """Generate a Dilithium key pair (post-quantum signatures)"""
    from services.quantum_security import quantum_security
    
    keypair = quantum_security.generate_dilithium_keypair(key_id, security_level)
    
    return {
        "key_id": keypair.key_id,
        "algorithm": keypair.algorithm,
        "public_key": keypair.public_key,
        "expires_at": keypair.expires_at
    }


@router.post("/quantum/encrypt")
async def quantum_hybrid_encrypt(
    plaintext: str,
    recipient_public_key: str,
    current_user: dict = Depends(check_permission("write"))
):
    """Hybrid encrypt (Kyber + AES-GCM)"""
    from services.quantum_security import quantum_security
    
    encrypted = quantum_security.hybrid_encrypt(
        plaintext.encode(),
        recipient_public_key
    )
    
    return encrypted


@router.post("/quantum/decrypt")
async def quantum_hybrid_decrypt(
    key_id: str,
    encrypted_data: Dict[str, str],
    current_user: dict = Depends(check_permission("write"))
):
    """Hybrid decrypt (Kyber + AES-GCM)"""
    from services.quantum_security import quantum_security
    
    plaintext = quantum_security.hybrid_decrypt(key_id, encrypted_data)
    
    if plaintext is None:
        raise HTTPException(status_code=400, detail="Decryption failed")
    
    return {"plaintext": plaintext.decode()}


@router.get("/quantum/keypairs")
async def list_quantum_keypairs(
    algorithm: str = None,
    current_user: dict = Depends(get_current_user)
):
    """List quantum key pairs"""
    from services.quantum_security import quantum_security
    return {"keypairs": quantum_security.get_keypairs(algorithm)}


@router.get("/quantum/status")
async def get_quantum_status(current_user: dict = Depends(get_current_user)):
    """Get quantum security status"""
    from services.quantum_security import quantum_security
    return quantum_security.get_quantum_status()


# =============================================================================
# AI REASONING ENDPOINTS
# =============================================================================

@router.post("/ai/analyze")
async def analyze_threat_with_ai(
    request: ThreatAnalysisRequest,
    current_user: dict = Depends(get_current_user)
):
    """Analyze a threat with AI reasoning"""
    from services.ai_reasoning import ai_reasoning
    from dataclasses import asdict
    
    analysis = ai_reasoning.analyze_threat({
        "title": request.title,
        "description": request.description,
        "source": request.source,
        "indicators": request.indicators,
        "process_name": request.process_name,
        "command_line": request.command_line
    })
    
    return asdict(analysis)


@router.post("/ai/triage")
async def triage_incidents(
    incidents: List[Dict[str, Any]],
    current_user: dict = Depends(get_current_user)
):
    """Triage and prioritize incidents"""
    from services.ai_reasoning import ai_reasoning
    
    prioritized = ai_reasoning.triage_incident(incidents)
    return {"prioritized_incidents": prioritized}


@router.post("/ai/query")
async def query_ai(
    request: AIQueryRequest,
    current_user: dict = Depends(get_current_user)
):
    """Query the AI reasoning engine"""
    from services.ai_reasoning import ai_reasoning
    from dataclasses import asdict
    
    result = ai_reasoning.query(request.question, request.context)
    return asdict(result)


@router.get("/ai/stats")
async def get_ai_stats(current_user: dict = Depends(get_current_user)):
    """Get AI reasoning statistics"""
    from services.ai_reasoning import ai_reasoning
    return ai_reasoning.get_reasoning_stats()


# =============================================================================
# OLLAMA INTEGRATION ENDPOINTS
# =============================================================================

class OllamaConfigRequest(BaseModel):
    base_url: str = "http://localhost:11434"
    model: str = "mistral"


class OllamaGenerateRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    system_prompt: Optional[str] = None


@router.post("/ai/ollama/configure")
async def configure_ollama(
    request: OllamaConfigRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Configure Ollama for local AI reasoning"""
    from services.ai_reasoning import ai_reasoning
    
    result = ai_reasoning.configure_ollama(request.base_url, request.model)
    return result


@router.get("/ai/ollama/status")
async def get_ollama_status(current_user: dict = Depends(get_current_user)):
    """Get Ollama connection status"""
    from services.ai_reasoning import ai_reasoning
    
    return ai_reasoning.get_ollama_status()


@router.post("/ai/ollama/generate")
async def ollama_generate(
    request: OllamaGenerateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate response using Ollama"""
    from services.ai_reasoning import ai_reasoning
    
    result = await ai_reasoning.ollama_generate(
        request.prompt, 
        request.model,
        request.system_prompt
    )
    return result


@router.post("/ai/ollama/analyze")
async def ollama_analyze_threat(
    request: ThreatAnalysisRequest,
    current_user: dict = Depends(get_current_user)
):
    """Analyze threat using Ollama LLM"""
    from services.ai_reasoning import ai_reasoning
    
    result = await ai_reasoning.ollama_analyze_threat({
        "title": request.title,
        "description": request.description,
        "source": request.source,
        "indicators": request.indicators,
        "process_name": request.process_name,
        "command_line": request.command_line
    })
    return result


# =============================================================================
# VNS ALERTS ENDPOINTS
# =============================================================================

class AlertConfigRequest(BaseModel):
    slack_webhook_url: Optional[str] = None
    email_config: Optional[Dict[str, Any]] = None


class TestAlertRequest(BaseModel):
    channel: str = "all"  # all, slack, email


@router.get("/alerts/status")
async def get_alert_status(current_user: dict = Depends(get_current_user)):
    """Get VNS alert service status"""
    from services.vns_alerts import vns_alert_service
    
    return vns_alert_service.get_status()


@router.post("/alerts/configure")
async def configure_alerts(
    request: AlertConfigRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Configure VNS alert channels"""
    from services.vns_alerts import vns_alert_service
    
    result = vns_alert_service.configure(
        slack_webhook=request.slack_webhook_url,
        email_config=request.email_config
    )
    
    return {"status": "configured", **result}


@router.post("/alerts/test")
async def test_alert(
    request: TestAlertRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Send a test alert"""
    from services.vns_alerts import vns_alert_service
    
    results = vns_alert_service.test_alert(request.channel)
    return {"status": "sent", "results": results}


# =============================================================================
# CUCKOO SANDBOX ENDPOINTS
# =============================================================================

class SandboxSubmitRequest(BaseModel):
    file_path: Optional[str] = None
    file_base64: Optional[str] = None
    file_name: Optional[str] = None
    url: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


@router.get("/sandbox/status")
async def get_sandbox_status(current_user: dict = Depends(get_current_user)):
    """Get Cuckoo sandbox status"""
    from services.cuckoo_sandbox import cuckoo_sandbox
    
    return cuckoo_sandbox.get_status()


@router.post("/sandbox/submit/file")
async def submit_file_to_sandbox(
    request: SandboxSubmitRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Submit a file for sandbox analysis"""
    from services.cuckoo_sandbox import cuckoo_sandbox
    import tempfile
    import base64
    
    if request.file_base64:
        # Decode base64 file
        file_data = base64.b64decode(request.file_base64)
        file_name = request.file_name or "sample.bin"
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file_name}") as f:
            f.write(file_data)
            temp_path = f.name
        
        result = cuckoo_sandbox.submit_file(temp_path, request.options)
        
        # Clean up
        try:
            os.unlink(temp_path)
        except:
            pass
        
        return result
    elif request.file_path:
        return cuckoo_sandbox.submit_file(request.file_path, request.options)
    else:
        raise HTTPException(status_code=400, detail="file_path or file_base64 required")


@router.post("/sandbox/submit/url")
async def submit_url_to_sandbox(
    request: SandboxSubmitRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Submit a URL for sandbox analysis"""
    from services.cuckoo_sandbox import cuckoo_sandbox
    
    if not request.url:
        raise HTTPException(status_code=400, detail="url required")
    
    return cuckoo_sandbox.submit_url(request.url, request.options)


@router.get("/sandbox/task/{task_id}")
async def get_sandbox_task_status(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get sandbox task status"""
    from services.cuckoo_sandbox import cuckoo_sandbox
    
    return cuckoo_sandbox.get_task_status(task_id)


@router.get("/sandbox/report/{task_id}")
async def get_sandbox_report(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get full sandbox analysis report"""
    from services.cuckoo_sandbox import cuckoo_sandbox
    
    return cuckoo_sandbox.get_report(task_id)
