"""
CLI Event Ingestion Router
===========================
Handles CLI command events, session summaries, and deception hits
for AI-Agentic defense playbook triggering.

Event Types:
- cli.command: Raw CLI command from agent
- cli.session_summary: Computed cognition summary over time window
- deception.hit: Honey token / decoy interaction
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import logging
import uuid

from routers.dependencies import get_current_user, get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cli", tags=["CLI Events"])
deception_router = APIRouter(prefix="/deception-hits", tags=["Deception Hit Events"])


# =============================================================================
# ENUMS
# =============================================================================

class IntentType(str, Enum):
    RECON = "recon"
    CREDENTIAL_ACCESS = "credential_access"
    LATERAL_MOVEMENT = "lateral_movement"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    PERSISTENCE = "persistence"
    DEFENSE_EVASION = "defense_evasion"
    EXFIL_PREP = "exfil_prep"
    DATA_STAGING = "data_staging"
    EXECUTION = "execution"
    DISCOVERY = "discovery"


class DeceptionSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# REQUEST MODELS
# =============================================================================

class CLICommandEvent(BaseModel):
    """Raw CLI command event from agent"""
    host_id: str = Field(..., description="Unique host identifier")
    session_id: str = Field(..., description="Session identifier")
    user: str = Field(..., description="Username executing command")
    shell_type: str = Field(..., description="Shell type (bash, powershell, cmd, zsh)")
    command: str = Field(..., description="The command string")
    parent_process: Optional[str] = Field(None, description="Parent process name or PID")
    cwd: Optional[str] = Field(None, description="Current working directory")
    exit_code: Optional[int] = Field(None, description="Command exit code")
    duration_ms: Optional[int] = Field(None, description="Command execution duration")
    timestamp: Optional[str] = Field(None, description="Event timestamp (ISO format)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "host_id": "workstation-001",
                "session_id": "sess-9f2c",
                "user": "alice",
                "shell_type": "powershell",
                "command": "whoami /all",
                "parent_process": "explorer.exe",
                "cwd": "C:\\Users\\alice"
            }
        }


class CLISessionSummary(BaseModel):
    """Computed cognition summary over a time window"""
    host_id: str
    session_id: str
    user: str
    window_start: str
    window_end: str
    machine_likelihood: float = Field(..., ge=0, le=1, description="Probability session is machine-driven")
    burstiness_score: float = Field(..., ge=0, le=1, description="Command burst pattern score")
    tool_switch_latency_ms: int = Field(..., description="Average latency between tool switches")
    goal_persistence: float = Field(..., ge=0, le=1, description="Goal persistence score")
    dominant_intents: List[str] = Field(default_factory=list, description="Detected intent categories")
    decoy_touched: bool = Field(False, description="Whether a decoy/honey token was touched")
    command_count: Optional[int] = Field(None, description="Number of commands in window")
    unique_tools: Optional[List[str]] = Field(None, description="Unique tools/commands used")
    suspect_pid: Optional[int] = Field(None, description="Suspected malicious process ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "host_id": "workstation-001",
                "session_id": "sess-9f2c",
                "user": "alice",
                "window_start": "2026-02-10T00:40:00Z",
                "window_end": "2026-02-10T00:40:30Z",
                "machine_likelihood": 0.86,
                "burstiness_score": 0.79,
                "tool_switch_latency_ms": 220,
                "goal_persistence": 0.74,
                "dominant_intents": ["recon"],
                "decoy_touched": False
            }
        }


class DeceptionHitEvent(BaseModel):
    """Honey token / decoy interaction event"""
    host_id: str
    token_id: str
    severity: DeceptionSeverity
    suspect_pid: Optional[int] = Field(None, description="Suspected process ID that touched decoy")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context (path, env var, etc)")
    timestamp: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "host_id": "workstation-001",
                "token_id": "honey-aws-creds-001",
                "severity": "critical",
                "suspect_pid": 4532,
                "context": {
                    "path": "C:\\Users\\alice\\.aws\\credentials",
                    "access_type": "read"
                }
            }
        }


# =============================================================================
# CLI EVENT ENDPOINTS
# =============================================================================

@router.post("/event")
async def ingest_cli_command(
    event: CLICommandEvent,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Ingest a raw CLI command event from an agent.
    Stores in MongoDB and triggers background cognition processing.
    """
    db = get_db()
    
    event_doc = {
        "event_id": str(uuid.uuid4()),
        "event_type": "cli.command",
        "timestamp": event.timestamp or datetime.now(timezone.utc).isoformat(),
        "host_id": event.host_id,
        "session_id": event.session_id,
        "user": event.user,
        "shell_type": event.shell_type,
        "command": event.command,
        "parent_process": event.parent_process,
        "cwd": event.cwd,
        "exit_code": event.exit_code,
        "duration_ms": event.duration_ms,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "ingested_by": current_user.get("email", "system")
    }
    
    await db.cli_commands.insert_one(event_doc)
    await db.events_raw.insert_one({**event_doc})
    
    # Trigger background cognition analysis
    background_tasks.add_task(
        analyze_session_window,
        db,
        event.host_id,
        event.session_id
    )
    
    logger.info(f"CLI command ingested: {event.host_id}/{event.session_id} - {event.command[:50]}")
    
    return {
        "status": "accepted",
        "event_id": event_doc["event_id"],
        "message": "CLI command event ingested successfully"
    }


@router.post("/session-summary")
async def ingest_session_summary(
    summary: CLISessionSummary,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Ingest a CLI session summary (from CCE worker or external source).
    Triggers SOAR playbook evaluation.
    """
    db = get_db()
    
    summary_doc = {
        "event_id": str(uuid.uuid4()),
        "event_type": "cli.session_summary",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **summary.model_dump(),
        "ingested_by": current_user.get("email", "system")
    }
    
    await db.cli_session_summaries.insert_one(summary_doc)
    await db.events_raw.insert_one({**summary_doc})
    
    # Trigger SOAR playbook evaluation
    background_tasks.add_task(
        evaluate_playbooks_for_event,
        db,
        summary_doc
    )
    
    logger.info(f"Session summary ingested: {summary.host_id}/{summary.session_id} - ML:{summary.machine_likelihood}")
    
    return {
        "status": "accepted",
        "event_id": summary_doc["event_id"],
        "playbook_evaluation": "triggered",
        "message": "Session summary ingested successfully"
    }


@router.get("/commands/{host_id}")
async def get_cli_commands(
    host_id: str,
    session_id: Optional[str] = None,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """Get CLI commands for a host, optionally filtered by session"""
    db = get_db()
    
    query = {"host_id": host_id, "event_type": "cli.command"}
    if session_id:
        query["session_id"] = session_id
    
    commands = await db.cli_commands.find(
        query, 
        {"_id": 0}
    ).sort("timestamp", -1).to_list(limit)
    
    return {"commands": commands, "count": len(commands)}


@router.get("/sessions/all")
async def get_all_session_summaries(
    limit: int = 50,
    min_ml: float = 0.0,
    current_user: dict = Depends(get_current_user)
):
    """Get all session summaries across all hosts"""
    db = get_db()
    
    query = {}
    if min_ml > 0:
        query["machine_likelihood"] = {"$gte": min_ml}
    
    summaries = await db.cli_session_summaries.find(
        query,
        {"_id": 0}
    ).sort("window_end", -1).to_list(limit)
    
    return {"summaries": summaries, "count": len(summaries)}


@router.get("/sessions/{host_id}")
async def get_session_summaries(
    host_id: str,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    """Get session summaries for a host"""
    db = get_db()
    
    summaries = await db.cli_session_summaries.find(
        {"host_id": host_id},
        {"_id": 0}
    ).sort("window_end", -1).to_list(limit)
    
    return {"summaries": summaries, "count": len(summaries)}
    
    return {"summaries": summaries, "count": len(summaries)}


# =============================================================================
# DECEPTION EVENT ENDPOINTS
# =============================================================================

@deception_router.post("/event")
async def ingest_deception_hit(
    event: DeceptionHitEvent,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Ingest a deception/honey token hit event.
    Immediately triggers SOAR containment playbooks.
    """
    db = get_db()
    
    event_doc = {
        "event_id": str(uuid.uuid4()),
        "event_type": "deception.hit",
        "timestamp": event.timestamp or datetime.now(timezone.utc).isoformat(),
        "host_id": event.host_id,
        "token_id": event.token_id,
        "severity": event.severity.value,
        "suspect_pid": event.suspect_pid,
        "context": event.context or {},
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "ingested_by": current_user.get("email", "system")
    }
    
    await db.deception_hits.insert_one(event_doc)
    await db.events_raw.insert_one({**event_doc})
    
    # Immediately trigger SOAR for deception hits
    background_tasks.add_task(
        evaluate_playbooks_for_event,
        db,
        event_doc
    )
    
    logger.warning(f"DECEPTION HIT: {event.host_id} touched token {event.token_id} (severity: {event.severity})")
    
    return {
        "status": "accepted",
        "event_id": event_doc["event_id"],
        "severity": event.severity.value,
        "playbook_evaluation": "triggered_immediate",
        "message": "Deception hit event ingested - containment playbooks triggered"
    }


@deception_router.get("/hits")
async def get_deception_hits(
    host_id: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """Get deception hit events"""
    db = get_db()
    
    query = {"event_type": "deception.hit"}
    if host_id:
        query["host_id"] = host_id
    if severity:
        query["severity"] = severity
    
    hits = await db.deception_hits.find(
        query,
        {"_id": 0}
    ).sort("timestamp", -1).to_list(limit)
    
    return {"hits": hits, "count": len(hits)}


# =============================================================================
# BACKGROUND TASKS
# =============================================================================

async def analyze_session_window(db, host_id: str, session_id: str):
    """
    Analyze recent CLI commands for a session and generate a summary.
    This is the Cognition/Correlation Engine (CCE) logic.
    """
    from services.cognition_engine import CognitionEngine
    
    try:
        engine = CognitionEngine(db)
        summary = await engine.analyze_session(host_id, session_id)
        
        if summary:
            # Store the summary
            await db.cli_session_summaries.insert_one(summary)
            
            # Evaluate playbooks
            await evaluate_playbooks_for_event(db, summary)
            
            logger.info(f"CCE analysis complete for {host_id}/{session_id}")
    except Exception as e:
        logger.error(f"CCE analysis failed: {e}")


async def evaluate_playbooks_for_event(db, event: dict):
    """Evaluate SOAR playbooks against an event"""
    from soar_engine import soar_engine
    
    try:
        await soar_engine.evaluate_event(event, db)
    except Exception as e:
        logger.error(f"SOAR evaluation failed: {e}")
