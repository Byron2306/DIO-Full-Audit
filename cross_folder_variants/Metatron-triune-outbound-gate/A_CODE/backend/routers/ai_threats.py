"""
AATL & AATR Router
==================
API endpoints for Autonomous Agent Threat Layer and 
Autonomous AI Threat Registry.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from pydantic import BaseModel

from .dependencies import get_current_user, db

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-threats", tags=["AI Threat Intelligence"])


# =============================================================================
# MODELS
# =============================================================================

class AnalyzeCLIRequest(BaseModel):
    host_id: str
    session_id: str
    commands: List[dict]


# =============================================================================
# AATL ENDPOINTS
# =============================================================================

@router.get("/aatl/summary")
async def get_aatl_summary(current_user: dict = Depends(get_current_user)):
    """Get AATL threat summary"""
    from backend.services.aatl import get_aatl_engine
    
    engine = get_aatl_engine()
    if engine is None:
        return {
            "total_sessions": 0,
            "autonomous_agent_sessions": 0,
            "by_actor_type": {},
            "by_lifecycle_stage": {},
            "by_threat_level": {}
        }
    
    return await engine.get_threat_summary()


@router.get("/aatl/assessments")
async def get_aatl_assessments(
    min_threat: float = Query(0, ge=0, le=100),
    actor_type: Optional[str] = None,
    limit: int = Query(50, le=200),
    current_user: dict = Depends(get_current_user)
):
    """Get AATL assessments"""
    from backend.services.aatl import get_aatl_engine
    
    engine = get_aatl_engine()
    if engine is None:
        return {"assessments": []}
    
    assessments = await engine.get_all_assessments(min_threat)
    
    if actor_type:
        assessments = [a for a in assessments if a.get("actor_type") == actor_type]
    
    return {"assessments": assessments[:limit]}


@router.get("/aatl/assessment/{host_id}/{session_id}")
async def get_specific_assessment(
    host_id: str,
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get specific session assessment"""
    from backend.services.aatl import get_aatl_engine
    
    engine = get_aatl_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="AATL engine not available")
    
    assessment = await engine.get_assessment(host_id, session_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    return assessment


@router.post("/aatl/analyze")
async def analyze_cli_session(
    request: AnalyzeCLIRequest,
    current_user: dict = Depends(get_current_user)
):
    """Manually trigger AATL analysis on a CLI session"""
    from backend.services.aatl import get_aatl_engine
    
    engine = get_aatl_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="AATL engine not available")
    
    # Process each command through AATL
    assessment = None
    for cmd in request.commands:
        event = {
            "host_id": request.host_id,
            "data": {
                "session_id": request.session_id,
                "command": cmd.get("command", ""),
            },
            "timestamp": cmd.get("timestamp")
        }
        assessment = await engine.process_cli_event(event)
    
    if assessment:
        return assessment.to_dict()
    
    return {"message": "Not enough data for assessment"}


@router.get("/aatl/lifecycle-stages")
async def get_lifecycle_stages(current_user: dict = Depends(get_current_user)):
    """Get all lifecycle stages with descriptions"""
    from backend.services.aatl import AgentLifecycleStage
    
    stages = {
        "reconnaissance": "Initial information gathering and mapping",
        "initial_access": "First entry point into the system",
        "execution": "Running malicious code or commands",
        "persistence": "Establishing long-term access",
        "privilege_escalation": "Gaining higher privileges",
        "defense_evasion": "Avoiding detection",
        "credential_access": "Stealing credentials",
        "discovery": "Learning about the environment",
        "lateral_movement": "Moving to other systems",
        "collection": "Gathering target data",
        "exfiltration": "Stealing data out",
        "impact": "Causing damage or disruption"
    }
    
    return {"stages": stages}


@router.get("/aatl/response-strategies")
async def get_response_strategies(current_user: dict = Depends(get_current_user)):
    """Get AI-specific response strategies"""
    strategies = {
        "observe": {
            "name": "Observe",
            "description": "Monitor and collect intelligence without intervention",
            "actions": ["Increase logging", "Capture all telemetry", "Track behavior patterns"]
        },
        "slow": {
            "name": "Slow",
            "description": "Inject latency and throttle to degrade agent performance",
            "actions": ["Command throttling", "Latency injection", "Rate limiting"]
        },
        "poison": {
            "name": "Poison",
            "description": "Feed false data to mislead the agent",
            "actions": ["Decoy data deployment", "False credential injection", "Misleading responses"]
        },
        "deceive": {
            "name": "Deceive",
            "description": "Full honeypot engagement with fake success",
            "actions": ["Honeypot redirection", "Fake success responses", "Simulated environment"]
        },
        "contain": {
            "name": "Contain",
            "description": "Isolate without full eradication to preserve evidence",
            "actions": ["Network isolation", "Process containment", "Evidence preservation"]
        },
        "eradicate": {
            "name": "Eradicate",
            "description": "Full removal and system recovery",
            "actions": ["Kill process tree", "Remove persistence", "System restoration"]
        }
    }
    
    return {"strategies": strategies}


# =============================================================================
# AATR ENDPOINTS
# =============================================================================

@router.get("/aatr/summary")
async def get_aatr_summary(current_user: dict = Depends(get_current_user)):
    """Get AATR registry summary"""
    from backend.services.aatr import get_aatr
    
    aatr = get_aatr()
    if aatr is None:
        return {"error": "AATR not initialized"}
    
    return aatr.get_summary()


@router.get("/aatr/entries")
async def get_aatr_entries(
    classification: Optional[str] = None,
    risk_profile: Optional[str] = None,
    active_only: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """Get AATR registry entries"""
    from backend.services.aatr import get_aatr
    
    aatr = get_aatr()
    if aatr is None:
        return {"entries": []}
    
    if active_only:
        entries = aatr.get_active_threats()
    elif classification:
        entries = aatr.get_by_classification(classification)
    elif risk_profile:
        entries = aatr.get_by_risk_profile(risk_profile)
    else:
        entries = aatr.get_all_entries()
    
    return {"entries": entries, "count": len(entries)}


@router.get("/aatr/entry/{entry_id}")
async def get_aatr_entry(
    entry_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get specific AATR entry"""
    from backend.services.aatr import get_aatr
    
    aatr = get_aatr()
    if aatr is None:
        raise HTTPException(status_code=503, detail="AATR not initialized")
    
    entry = aatr.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    return entry


@router.get("/aatr/indicators")
async def get_defensive_indicators(
    category: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get all defensive indicators"""
    from backend.services.aatr import get_aatr
    
    aatr = get_aatr()
    if aatr is None:
        return {"indicators": []}
    
    indicators = aatr.get_defensive_indicators(category)
    
    return {"indicators": indicators, "count": len(indicators)}


@router.post("/aatr/match")
async def match_behavior_to_registry(
    behavior: dict,
    current_user: dict = Depends(get_current_user)
):
    """Match observed behavior against AATR registry"""
    from backend.services.aatr import get_aatr
    
    aatr = get_aatr()
    if aatr is None:
        raise HTTPException(status_code=503, detail="AATR not initialized")
    
    matches = aatr.match_behavior(behavior)
    
    return {"matches": matches}


@router.get("/aatr/classifications")
async def get_classifications(current_user: dict = Depends(get_current_user)):
    """Get all agent classifications"""
    classifications = {
        "task_automation": "Basic task automation agents",
        "reasoning_agent": "Agents with chain-of-thought reasoning",
        "planning_agent": "Agents with multi-step planning capabilities",
        "tool_using_agent": "Agents that can use external tools",
        "multi_agent_system": "Coordinated systems of multiple agents",
        "code_generation": "Agents focused on generating and executing code",
        "autonomous_hacking": "Agents designed for autonomous offensive operations"
    }
    
    return {"classifications": classifications}


# =============================================================================
# COMBINED INTELLIGENCE
# =============================================================================

@router.get("/intelligence/dashboard")
async def get_intelligence_dashboard(current_user: dict = Depends(get_current_user)):
    """Get combined AI threat intelligence dashboard data"""
    from backend.services.aatl import get_aatl_engine
    from backend.services.aatr import get_aatr
    
    result = {
        "aatl": {},
        "aatr": {},
        "combined_threat_score": 0
    }
    
    # AATL data
    engine = get_aatl_engine()
    if engine:
        result["aatl"] = await engine.get_threat_summary()
    
    # AATR data
    aatr = get_aatr()
    if aatr:
        result["aatr"] = aatr.get_summary()
        result["active_threat_types"] = len(aatr.get_active_threats())
    
    # Combined threat calculation
    aatl_sessions = result["aatl"].get("autonomous_agent_sessions", 0)
    total_sessions = result["aatl"].get("total_sessions", 1) or 1
    
    result["combined_threat_score"] = min(100, (aatl_sessions / total_sessions) * 100)
    
    return result


# =============================================================================
# AI DEFENSE ENGINE INTEGRATION
# =============================================================================

class AIDefenseRequest(BaseModel):
    session_id: str
    host_id: str
    behavior_data: dict = {}


@router.post("/defense/assess")
async def assess_ai_threat_combined(
    request: AIDefenseRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Combined AI threat assessment using AIDefenseEngine + AATL.
    Returns unified threat assessment with correlated analysis.
    """
    from threat_response import AIDefenseEngine
    
    result = await AIDefenseEngine.integrate_with_aatl(
        session_id=request.session_id,
        host_id=request.host_id,
        behavior_data=request.behavior_data
    )
    
    return result


@router.post("/defense/engage-tarpit")
async def engage_tarpit(
    session_id: str,
    host_id: str,
    mode: str = "standard",
    current_user: dict = Depends(get_current_user)
):
    """Engage tarpit on a session to slow down AI attacker"""
    from threat_response import AIDefenseEngine
    from dataclasses import asdict
    
    result = await AIDefenseEngine.engage_tarpit(
        session_id=session_id,
        host_id=host_id,
        mode=mode
    )
    
    return asdict(result)


@router.post("/defense/deploy-decoy")
async def deploy_decoy(
    host_id: str,
    decoy_type: str,
    decoys: List[str],
    placement: str = "standard",
    current_user: dict = Depends(get_current_user)
):
    """Deploy decoys targeting AI attackers"""
    from threat_response import AIDefenseEngine
    from dataclasses import asdict
    
    result = await AIDefenseEngine.deploy_decoy(
        host_id=host_id,
        decoy_type=decoy_type,
        decoys=decoys,
        placement=placement
    )
    
    return asdict(result)


@router.post("/defense/escalate")
async def escalate_defense(
    session_id: str,
    escalation_level: str,
    threat_type: str = "ai_autonomous",
    severity: str = "high",
    current_user: dict = Depends(get_current_user)
):
    """Execute graduated defense escalation"""
    from threat_response import AIDefenseEngine, ThreatContext, DefenseEscalationLevel
    from dataclasses import asdict
    
    # Create context
    context = ThreatContext(
        threat_id=f"ai_{session_id}",
        threat_type=threat_type,
        session_id=session_id,
        severity=severity
    )
    
    # Map level
    level_map = {
        "observe": DefenseEscalationLevel.OBSERVE,
        "degrade": DefenseEscalationLevel.DEGRADE,
        "deceive": DefenseEscalationLevel.DECEIVE,
        "contain": DefenseEscalationLevel.CONTAIN,
        "isolate": DefenseEscalationLevel.ISOLATE,
        "eradicate": DefenseEscalationLevel.ERADICATE
    }
    level = level_map.get(escalation_level.lower(), DefenseEscalationLevel.OBSERVE)
    
    results = await AIDefenseEngine.execute_escalated_response(context, level)
    
    return {
        "escalation_level": escalation_level,
        "actions_taken": len(results),
        "results": [asdict(r) for r in results]
    }


@router.get("/defense/status")
async def get_defense_status(current_user: dict = Depends(get_current_user)):
    """Get current AI defense status"""
    from threat_response import AIDefenseEngine
    
    return AIDefenseEngine.get_defense_status()


@router.get("/defense/metrics/{session_id}")
async def get_session_metrics(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get formal Agenticity and CBR/TBCR/CDI metrics for a session."""
    from threat_response import AIDefenseEngine

    metrics = AIDefenseEngine.get_session_metrics(session_id)
    if not metrics.get("agenticity") and not metrics.get("exhaustion"):
        raise HTTPException(status_code=404, detail="No metrics found for session")
    return metrics


@router.post("/defense/sync-aatr")
async def sync_with_aatr(
    session_id: str,
    indicators: List[str],
    current_user: dict = Depends(get_current_user)
):
    """Sync detected patterns with AATR for framework identification"""
    from threat_response import AIDefenseEngine
    
    result = await AIDefenseEngine.sync_with_aatr(
        threat_indicators=indicators,
        session_id=session_id
    )
    
    return result
