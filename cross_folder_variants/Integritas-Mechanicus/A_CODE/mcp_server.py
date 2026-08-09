"""
Model Context Protocol (MCP) Server
===================================
Standardized agent ↔ tools ↔ permissions ↔ audit protocol.
The "governed tool bus" for the swarm and SOAR.
"""

import os
import json
import hashlib
import logging
import asyncio
import socket
import ipaddress
import time
import signal
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
import uuid
from collections import deque

try:
    from services.polyphonic_governance import get_polyphonic_governance_service
except Exception:
    try:
        from backend.services.polyphonic_governance import get_polyphonic_governance_service
    except Exception:
        get_polyphonic_governance_service = None

try:
    from services.governance_epoch import get_governance_epoch_service
except Exception:
    try:
        from backend.services.governance_epoch import get_governance_epoch_service
    except Exception:
        get_governance_epoch_service = None

try:
    from services.notation_token import get_notation_token_service
except Exception:
    try:
        from backend.services.notation_token import get_notation_token_service
    except Exception:
        get_notation_token_service = None

try:
    from services.world_events import emit_world_event
except Exception:
    try:
        from backend.services.world_events import emit_world_event
    except Exception:
        emit_world_event = None

try:
    from services.telemetry_chain import tamper_evident_telemetry
except Exception:
    try:
        from backend.services.telemetry_chain import tamper_evident_telemetry
    except Exception:
        tamper_evident_telemetry = None

try:
    from services.boundary_control import (
        boundary_control,
        build_boundary_contract,
        contract_to_dict,
    )
except Exception:
    try:
        from backend.services.boundary_control import (
            boundary_control,
            build_boundary_contract,
            contract_to_dict,
        )
    except Exception:
        boundary_control = None
        build_boundary_contract = None
        contract_to_dict = None

logger = logging.getLogger(__name__)


def _is_production_security_mode() -> bool:
    environment = os.environ.get("ENVIRONMENT", "").strip().lower()
    strict_flag = os.environ.get("SERAPH_STRICT_SECURITY", "false").strip().lower()
    mcp_strict_flag = os.environ.get("MCP_STRICT_SECURITY", "false").strip().lower()
    return (
        environment in {"prod", "production"}
        or strict_flag in {"1", "true", "yes", "on"}
        or mcp_strict_flag in {"1", "true", "yes", "on"}
    )


def _resolve_mcp_signing_key() -> str:
    configured_key = os.environ.get("MCP_SIGNING_KEY")
    weak_defaults = {
        "mcp-default-key",
        "secret",
        "changeme",
        "password",
        "default",
    }

    if not configured_key:
        generated_key = f"ephemeral-mcp-{uuid.uuid4().hex}{uuid.uuid4().hex}"
        logger.warning(
            "MCP_SIGNING_KEY is not set. Using an ephemeral in-memory signing key for this process. "
            "Set a strong MCP_SIGNING_KEY (>=32 chars) for stable message signatures."
        )
        return generated_key

    if configured_key in weak_defaults or len(configured_key) < 32:
        message = (
            "Weak MCP_SIGNING_KEY detected. Use a strong random signing key with length >= 32 "
            "for secure MCP message signatures."
        )
        if _is_production_security_mode():
            raise RuntimeError(f"{message} Refusing to start in production/strict mode.")
        logger.warning(message)

    return configured_key


class MCPMessageType(Enum):
    """MCP message types"""
    TOOL_REQUEST = "tool_request"
    TOOL_RESPONSE = "tool_response"
    POLICY_CHECK = "policy_check"
    POLICY_RESULT = "policy_result"
    AUDIT_EVENT = "audit_event"
    TELEMETRY = "telemetry"
    COMMAND = "command"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


class MCPToolCategory(Enum):
    """Tool categories for MCP"""
    SCANNER = "scanner"
    EDR = "edr"
    FIREWALL = "firewall"
    SOAR = "soar"
    FORENSICS = "forensics"
    DECEPTION = "deception"
    IDENTITY = "identity"
    NETWORK = "network"
    AI_DEFENSE = "ai_defense"      # AI threat defense tools (tarpit, decoy, escalation)
    QUARANTINE = "quarantine"       # Quarantine pipeline tools


@dataclass
class MCPToolSchema:
    """Tool schema definition for MCP registry"""
    tool_id: str
    name: str
    description: str
    category: MCPToolCategory
    version: str
    
    # Input/output schemas
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    
    # Security
    required_trust_state: str
    required_scopes: List[str]
    rate_limit: int  # per hour
    
    # Execution
    timeout_seconds: int
    async_capable: bool
    idempotent: bool
    
    # Audit
    audit_level: str  # none, basic, full
    redact_fields: List[str]
    # Phase 1 HGL metadata (classification only, no enforcement).
    voice_type: Optional[str] = None
    capability_class: Optional[str] = None
    timbre_profile: Optional[str] = None
    allowed_register: Optional[str] = None


@dataclass
class MCPMessage:
    """MCP protocol message"""
    message_id: str
    message_type: MCPMessageType
    timestamp: str
    
    # Routing
    source: str          # agent_id / service_name
    destination: str     # tool_id / service_name / broadcast
    
    # Payload
    payload: Dict[str, Any]
    
    # Security
    signature: str
    trace_id: str
    
    # Metadata
    priority: int = 5    # 1-10, 10 = highest
    ttl_seconds: int = 60
    requires_ack: bool = True


@dataclass
class MCPToolExecution:
    """Tool execution record"""
    execution_id: str
    tool_id: str
    request_message_id: str
    
    # Request
    principal: str
    input_params: Dict[str, Any]
    
    # Execution
    started_at: str
    completed_at: Optional[str]
    status: str  # pending, running, success, failed, timeout
    
    # Result
    output: Optional[Dict[str, Any]]
    error: Optional[str]
    
    # Audit
    policy_decision_id: Optional[str]
    token_id: Optional[str]
    audit_hash: str


class MCPServer:
    """
    Model Context Protocol Server.
    
    Features:
    - Tool registry with schemas
    - Signed requests
    - Policy enforcement hooks
    - Structured logging and replay
    - Versioning
    - Connector sandboxing
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        
        # Signing key
        self.signing_key = _resolve_mcp_signing_key()
        self.polyphonic_governance = (
            get_polyphonic_governance_service() if get_polyphonic_governance_service is not None else None
        )
        
        # Tool registry
        self.tools: Dict[str, MCPToolSchema] = {}
        self.tool_handlers: Dict[str, Callable] = {}
        
        # Message queues
        self.pending_requests: Dict[str, MCPMessage] = {}
        self.message_history: deque = deque(maxlen=10000)
        
        # Execution history
        self.executions: Dict[str, MCPToolExecution] = {}
        
        # Subscriptions (for pub/sub)
        self.subscriptions: Dict[str, List[str]] = {}  # topic -> [subscriber_ids]
        
        # Register built-in tools
        self._register_builtin_tools()
        self._register_builtin_handlers()
        
        logger.info("MCP Server initialized")

    def set_db(self, db):
        """Attach optional DB context for canonical event emission."""
        self.db = db

    async def _emit_mcp_event(self, event_type: str, entity_refs: List[str], payload: Dict[str, Any], trigger_triune: bool = False):
        if emit_world_event is None or getattr(self, "db", None) is None:
            return
        try:
            await emit_world_event(
                self.db,
                event_type=event_type,
                entity_refs=entity_refs,
                payload=payload,
                trigger_triune=trigger_triune,
            )
        except Exception:
            pass

    async def _resolve_approved_governance_context(
        self,
        *,
        decision_id: Optional[str],
        queue_id: Optional[str],
        required_action_types: Optional[set] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Validate that provided governance context is approved server-side."""
        if getattr(self, "db", None) is None:
            return False, "MCP DB context unavailable for governance validation", {}

        if not decision_id and not queue_id:
            return False, "Missing approved governance context", {}

        decision_doc = None
        queue_doc = None
        if decision_id:
            decision_doc = await self.db.triune_decisions.find_one({"decision_id": decision_id}, {"_id": 0})
            if not decision_doc:
                return False, f"Unknown governance decision_id: {decision_id}", {}

        if queue_id:
            queue_doc = await self.db.triune_outbound_queue.find_one({"queue_id": queue_id}, {"_id": 0})
            if not queue_doc:
                return False, f"Unknown governance queue_id: {queue_id}", {}

        if decision_doc and queue_doc:
            if decision_doc.get("related_queue_id") and decision_doc.get("related_queue_id") != queue_doc.get("queue_id"):
                return False, "Governance decision/queue mismatch", {}

        if decision_doc and str(decision_doc.get("status") or "").lower() != "approved":
            return False, f"Governance decision is not approved (status={decision_doc.get('status')})", {}
        if queue_doc and str(queue_doc.get("status") or "").lower() not in {"approved", "released_to_execution"}:
            return False, f"Governance queue is not approved (status={queue_doc.get('status')})", {}

        action_type = None
        if decision_doc:
            action_type = str(decision_doc.get("action_type") or "").lower()
        elif queue_doc:
            action_type = str(queue_doc.get("action_type") or "").lower()
        if required_action_types and action_type and action_type not in required_action_types:
            return False, f"Governance action_type '{action_type}' not allowed for this tool execution", {}

        resolved_context = {
            "approved": True,
            "decision_id": (decision_doc or {}).get("decision_id") or decision_id,
            "queue_id": (queue_doc or {}).get("queue_id") or (decision_doc or {}).get("related_queue_id") or queue_id,
            "action_type": action_type,
        }
        return True, "ok", resolved_context

    def _validate_capability_token(
        self,
        *,
        token_id: Optional[str],
        principal: str,
        principal_identity: Optional[str],
        action: str,
        target: str,
    ) -> Tuple[bool, str]:
        if not token_id:
            return False, "Missing capability token for execution"
        if not principal_identity:
            return False, "Missing principal_identity for token-bound execution"
        try:
            from services.token_broker import token_broker
        except Exception:
            from backend.services.token_broker import token_broker
        return token_broker.validate_token(
            token_id=str(token_id),
            principal=principal,
            principal_identity=principal_identity,
            action=action,
            target=target,
        )

    def _record_mcp_execution_audit(
        self,
        *,
        execution: "MCPToolExecution",
        trace_id: Optional[str],
        governance_context: Optional[Dict[str, Any]],
        result: str,
        result_details: Optional[str] = None,
        targets: Optional[List[str]] = None,
    ) -> None:
        if tamper_evident_telemetry is None:
            return
        try:
            tamper_evident_telemetry.set_db(getattr(self, "db", None))
            ctx = governance_context or {}
            tamper_evident_telemetry.record_action(
                principal=f"service:{execution.principal}",
                principal_trust_state="trusted",
                action="mcp_tool_execution",
                targets=targets or [execution.tool_id],
                policy_decision_id=execution.policy_decision_id,
                governance_decision_id=ctx.get("decision_id"),
                governance_queue_id=ctx.get("queue_id"),
                token_id=execution.token_id,
                execution_id=execution.execution_id,
                trace_id=trace_id or "",
                constraints={"tool_id": execution.tool_id},
                result=result,
                result_details=result_details,
                tool_id=execution.tool_id,
            )
        except Exception:
            logger.exception("Failed to record MCP execution audit for %s", execution.execution_id)
    
    def _sign_message(self, message: MCPMessage) -> str:
        """Sign a message"""
        import hmac
        data = {
            "message_id": message.message_id,
            "source": message.source,
            "destination": message.destination,
            "payload": message.payload,
            "timestamp": message.timestamp
        }
        payload = json.dumps(data, sort_keys=True)
        return hmac.new(
            self.signing_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def _verify_signature(self, message: MCPMessage) -> bool:
        """Verify message signature"""
        expected = self._sign_message(message)
        import hmac as hmac_module
        return hmac_module.compare_digest(expected, message.signature)
    
    def _register_builtin_tools(self):
        """Register built-in MCP tools"""
        
        # Network scanner
        self.register_tool(MCPToolSchema(
            tool_id="mcp.scanner.network",
            name="Network Scanner",
            description="Scan network for hosts and services",
            category=MCPToolCategory.SCANNER,
            version="1.0.0",
            input_schema={
                "target": {"type": "string", "description": "IP or CIDR"},
                "ports": {"type": "array", "items": "integer", "optional": True},
                "scan_type": {"type": "string", "enum": ["quick", "full", "stealth"]}
            },
            output_schema={
                "hosts": {"type": "array"},
                "open_ports": {"type": "object"},
                "scan_time": {"type": "number"}
            },
            required_trust_state="degraded",
            required_scopes=["observe", "collect"],
            rate_limit=100,
            timeout_seconds=300,
            async_capable=True,
            idempotent=True,
            audit_level="basic",
            redact_fields=[]
        ))
        
        # Process killer
        self.register_tool(MCPToolSchema(
            tool_id="mcp.edr.process_kill",
            name="Process Killer",
            description="Terminate malicious processes",
            category=MCPToolCategory.EDR,
            version="1.0.0",
            input_schema={
                "pid": {"type": "integer", "description": "Process ID"},
                "force": {"type": "boolean", "default": False},
                "reason": {"type": "string"}
            },
            output_schema={
                "success": {"type": "boolean"},
                "process_name": {"type": "string"},
                "terminated_at": {"type": "string"}
            },
            required_trust_state="trusted",
            required_scopes=["remediate"],
            rate_limit=50,
            timeout_seconds=30,
            async_capable=False,
            idempotent=False,
            audit_level="full",
            redact_fields=[]
        ))
        
        # Firewall rule
        self.register_tool(MCPToolSchema(
            tool_id="mcp.firewall.block_ip",
            name="Firewall Block IP",
            description="Block IP address at firewall",
            category=MCPToolCategory.FIREWALL,
            version="1.0.0",
            input_schema={
                "ip": {"type": "string", "format": "ipv4"},
                "direction": {"type": "string", "enum": ["inbound", "outbound", "both"]},
                "duration_hours": {"type": "integer", "default": 24}
            },
            output_schema={
                "rule_id": {"type": "string"},
                "blocked_at": {"type": "string"},
                "expires_at": {"type": "string"}
            },
            required_trust_state="trusted",
            required_scopes=["contain"],
            rate_limit=100,
            timeout_seconds=10,
            async_capable=False,
            idempotent=True,
            audit_level="full",
            redact_fields=[]
        ))
        
        # SOAR playbook
        self.register_tool(MCPToolSchema(
            tool_id="mcp.soar.run_playbook",
            name="Run SOAR Playbook",
            description="Execute automated response playbook",
            category=MCPToolCategory.SOAR,
            version="1.0.0",
            input_schema={
                "playbook_id": {"type": "string"},
                "incident_id": {"type": "string"},
                "parameters": {"type": "object", "optional": True}
            },
            output_schema={
                "execution_id": {"type": "string"},
                "status": {"type": "string"},
                "steps_completed": {"type": "integer"},
                "results": {"type": "array"}
            },
            required_trust_state="trusted",
            required_scopes=["remediate", "contain"],
            rate_limit=20,
            timeout_seconds=600,
            async_capable=True,
            idempotent=False,
            audit_level="full",
            redact_fields=["parameters.credentials"]
        ))
        
        # Memory forensics
        self.register_tool(MCPToolSchema(
            tool_id="mcp.forensics.memory_dump",
            name="Memory Dump",
            description="Capture process memory for analysis",
            category=MCPToolCategory.FORENSICS,
            version="1.0.0",
            input_schema={
                "pid": {"type": "integer"},
                "output_path": {"type": "string"},
                "compress": {"type": "boolean", "default": True}
            },
            output_schema={
                "dump_path": {"type": "string"},
                "size_bytes": {"type": "integer"},
                "hash": {"type": "string"}
            },
            required_trust_state="trusted",
            required_scopes=["collect"],
            rate_limit=10,
            timeout_seconds=300,
            async_capable=True,
            idempotent=True,
            audit_level="full",
            redact_fields=[]
        ))
        
        # Honeypot deployment
        self.register_tool(MCPToolSchema(
            tool_id="mcp.deception.deploy_honeypot",
            name="Deploy Honeypot",
            description="Deploy deception honeypot/canary",
            category=MCPToolCategory.DECEPTION,
            version="1.0.0",
            input_schema={
                "honeypot_type": {"type": "string", "enum": ["file", "service", "credential", "network"]},
                "target_zone": {"type": "string"},
                "config": {"type": "object"}
            },
            output_schema={
                "honeypot_id": {"type": "string"},
                "deployed_at": {"type": "string"},
                "trigger_endpoint": {"type": "string"}
            },
            required_trust_state="trusted",
            required_scopes=["deception"],
            rate_limit=50,
            timeout_seconds=60,
            async_capable=False,
            idempotent=False,
            audit_level="basic",
            redact_fields=["config.credentials"]
        ))

        # AI Defense: Tarpit Engagement
        self.tools["mcp.defense.engage_tarpit"] = MCPToolSchema(
            tool_id="mcp.defense.engage_tarpit",
            name="AI Tarpit Engagement",
            description="Engage adaptive tarpit to slow down AI threats with progressive delays",
            category=MCPToolCategory.AI_DEFENSE,
            version="1.0.0",
            input_schema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "Session ID to tarpit"},
                    "threat_level": {"type": "string", "enum": ["standard", "adaptive", "aggressive"]},
                    "initial_delay_ms": {"type": "integer", "default": 500},
                    "escalation_factor": {"type": "number", "default": 2.0},
                    "max_delay_ms": {"type": "integer", "default": 30000}
                },
                "required": ["session_id"]
            },
            output_schema={"type": "object"},
            required_trust_state="trusted",
            required_scopes=["ai_defense"],
            rate_limit=100,
            timeout_seconds=5,
            async_capable=True,
            idempotent=False,
            audit_level="basic",
            redact_fields=[]
        )

        # AI Defense: Decoy Deployment
        self.tools["mcp.defense.deploy_decoy"] = MCPToolSchema(
            tool_id="mcp.defense.deploy_decoy",
            name="AI Decoy Deployment",
            description="Deploy dynamic decoys targeting AI attackers (credentials, files, endpoints)",
            category=MCPToolCategory.AI_DEFENSE,
            version="1.0.0",
            input_schema={
                "type": "object",
                "properties": {
                    "decoy_type": {"type": "string", "enum": ["credentials", "files", "endpoints", "data"]},
                    "threat_context": {"type": "object", "description": "AI threat context for targeted decoys"},
                    "quantity": {"type": "integer", "default": 5},
                    "complexity": {"type": "string", "enum": ["low", "medium", "high"], "default": "medium"}
                },
                "required": ["decoy_type"]
            },
            output_schema={"type": "object"},
            required_trust_state="trusted",
            required_scopes=["ai_defense", "deception"],
            rate_limit=50,
            timeout_seconds=30,
            async_capable=True,
            idempotent=False,
            audit_level="basic",
            redact_fields=["threat_context.credentials"]
        )

        # AI Defense: Threat Assessment
        self.tools["mcp.defense.assess_ai_threat"] = MCPToolSchema(
            tool_id="mcp.defense.assess_ai_threat",
            name="AI Threat Assessment",
            description="Assess if activity is from AI/automated agent and determine threat level",
            category=MCPToolCategory.AI_DEFENSE,
            version="1.0.0",
            input_schema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "activity_data": {"type": "object", "description": "Activity patterns to analyze"},
                    "request_timing": {"type": "array", "items": {"type": "number"}},
                    "behavioral_indicators": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["session_id", "activity_data"]
            },
            output_schema={"type": "object"},
            required_trust_state="elevated",
            required_scopes=["ai_defense"],
            rate_limit=200,
            timeout_seconds=10,
            async_capable=True,
            idempotent=True,
            audit_level="basic",
            redact_fields=[]
        )

        # AI Defense: Escalation Handler
        self.tools["mcp.defense.escalate_response"] = MCPToolSchema(
            tool_id="mcp.defense.escalate_response",
            name="Defense Escalation Handler",
            description="Execute graduated defense escalation (OBSERVE→DEGRADE→DECEIVE→CONTAIN→ISOLATE→ERADICATE)",
            category=MCPToolCategory.AI_DEFENSE,
            version="1.0.0",
            input_schema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "current_level": {"type": "string", "enum": ["observe", "degrade", "deceive", "contain", "isolate", "eradicate"]},
                    "target_level": {"type": "string", "enum": ["observe", "degrade", "deceive", "contain", "isolate", "eradicate"]},
                    "ai_confidence": {"type": "number", "description": "AI threat confidence 0.0-1.0"},
                    "threat_assessment": {"type": "object"}
                },
                "required": ["session_id", "target_level"]
            },
            output_schema={"type": "object"},
            required_trust_state="admin",
            required_scopes=["ai_defense", "escalation"],
            rate_limit=20,
            timeout_seconds=60,
            async_capable=True,
            idempotent=False,
            audit_level="full",
            redact_fields=[]
        )

        # AI Defense: Feed Disinformation
        self.tools["mcp.defense.feed_disinformation"] = MCPToolSchema(
            tool_id="mcp.defense.feed_disinformation",
            name="AI Disinformation Feed",
            description="Feed targeted disinformation to mislead AI attackers",
            category=MCPToolCategory.AI_DEFENSE,
            version="1.0.0",
            input_schema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "disinformation_type": {"type": "string", "enum": ["fake_data", "goal_misdirection", "capability_overstate", "deadline_manipulation"]},
                    "target_goals": {"type": "array", "items": {"type": "string"}},
                    "plausibility_level": {"type": "string", "enum": ["low", "medium", "high"], "default": "medium"}
                },
                "required": ["session_id", "disinformation_type"]
            },
            output_schema={"type": "object"},
            required_trust_state="trusted",
            required_scopes=["ai_defense", "deception"],
            rate_limit=50,
            timeout_seconds=15,
            async_capable=True,
            idempotent=False,
            audit_level="basic",
            redact_fields=[]
        )

        # Quarantine: Advance Pipeline
        self.tools["mcp.quarantine.advance_pipeline"] = MCPToolSchema(
            tool_id="mcp.quarantine.advance_pipeline",
            name="Quarantine Pipeline Advancement",
            description="Advance quarantined item through pipeline stages (quarantined→scanning→sandboxed→analyzed→stored)",
            category=MCPToolCategory.QUARANTINE,
            version="1.0.0",
            input_schema={
                "type": "object",
                "properties": {
                    "entry_id": {"type": "string", "description": "Quarantine entry ID"},
                    "target_stage": {"type": "string", "enum": ["quarantined", "scanning", "sandboxed", "analyzed", "stored"]},
                    "force_advance": {"type": "boolean", "default": False}
                },
                "required": ["entry_id"]
            },
            output_schema={"type": "object"},
            required_trust_state="trusted",
            required_scopes=["quarantine"],
            rate_limit=100,
            timeout_seconds=30,
            async_capable=True,
            idempotent=False,
            audit_level="basic",
            redact_fields=[]
        )

        # Quarantine: Add Scan Result
        self.tools["mcp.quarantine.add_scan_result"] = MCPToolSchema(
            tool_id="mcp.quarantine.add_scan_result",
            name="Quarantine Scan Result",
            description="Add scan result to quarantine entry from EDR/AV engines",
            category=MCPToolCategory.QUARANTINE,
            version="1.0.0",
            input_schema={
                "type": "object",
                "properties": {
                    "entry_id": {"type": "string"},
                    "engine": {"type": "string"},
                    "detected": {"type": "boolean"},
                    "threat_name": {"type": "string"},
                    "confidence": {"type": "number"}
                },
                "required": ["entry_id", "engine", "detected"]
            },
            output_schema={"type": "object"},
            required_trust_state="trusted",
            required_scopes=["quarantine"],
            rate_limit=200,
            timeout_seconds=10,
            async_capable=True,
            idempotent=False,
            audit_level="basic",
            redact_fields=[]
        )

        # Quarantine: Get Pipeline Status
        self.tools["mcp.quarantine.get_pipeline_status"] = MCPToolSchema(
            tool_id="mcp.quarantine.get_pipeline_status",
            name="Quarantine Pipeline Status",
            description="Get full status of quarantine pipeline for an entry",
            category=MCPToolCategory.QUARANTINE,
            version="1.0.0",
            input_schema={
                "type": "object",
                "properties": {
                    "entry_id": {"type": "string"}
                },
                "required": ["entry_id"]
            },
            output_schema={"type": "object"},
            required_trust_state="elevated",
            required_scopes=["quarantine"],
            rate_limit=200,
            timeout_seconds=5,
            async_capable=False,
            idempotent=True,
            audit_level="basic",
            redact_fields=[]
        )

        # ============ DECEPTION ENGINE TOOLS ============
        # Pebbles: Campaign-based attack correlation
        self.tools["mcp.deception.track_campaign"] = MCPToolSchema(
            tool_id="mcp.deception.track_campaign",
            name="Pebbles Campaign Tracking",
            description="Correlate attacks via behavioral fingerprints across sessions, IPs, and time windows",
            category=MCPToolCategory.DECEPTION,
            version="1.0.0",
            input_schema={
                "type": "object",
                "properties": {
                    "ip": {"type": "string", "description": "Source IP address"},
                    "headers": {"type": "object", "description": "Request headers for fingerprinting"},
                    "timing_data": {"type": "object", "description": "Command timing intervals"},
                    "session_id": {"type": "string"}
                },
                "required": ["ip"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "fingerprint_id": {"type": "string"},
                    "total_events": {"type": "integer"},
                    "risk_level": {"type": "string"}
                }
            },
            required_trust_state="elevated",
            required_scopes=["deception"],
            rate_limit=500,
            timeout_seconds=5,
            async_capable=True,
            idempotent=True,
            audit_level="basic",
            redact_fields=[]
        )

        # Mystique: Adaptive deception tuning
        self.tools["mcp.deception.mystique_adapt"] = MCPToolSchema(
            tool_id="mcp.deception.mystique_adapt",
            name="Mystique Adaptive Tuning",
            description="Self-adjust deception parameters (friction, tarpit, thresholds) based on attacker behavior",
            category=MCPToolCategory.DECEPTION,
            version="1.0.0",
            input_schema={
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string", "description": "Campaign to adapt"},
                    "force_adapt": {"type": "boolean", "default": False}
                },
                "required": ["campaign_id"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "adapted": {"type": "boolean"},
                    "friction_multiplier": {"type": "number"},
                    "tarpit_multiplier": {"type": "number"},
                    "sink_score_override": {"type": "integer"}
                }
            },
            required_trust_state="trusted",
            required_scopes=["deception", "ai_defense"],
            rate_limit=100,
            timeout_seconds=10,
            async_capable=True,
            idempotent=False,
            audit_level="basic",
            redact_fields=[]
        )

        # Stonewall: Progressive escalation
        self.tools["mcp.deception.stonewall_escalate"] = MCPToolSchema(
            tool_id="mcp.deception.stonewall_escalate",
            name="Stonewall Progressive Escalation",
            description="Apply progressive blocking escalation (warn→throttle→soft_ban→hard_ban→blocklist)",
            category=MCPToolCategory.DECEPTION,
            version="1.0.0",
            input_schema={
                "type": "object",
                "properties": {
                    "ip": {"type": "string"},
                    "campaign_id": {"type": "string"},
                    "target_level": {"type": "string", "enum": ["warned", "throttled", "soft_banned", "hard_banned", "blocklisted"]}
                },
                "required": ["ip"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "escalation_level": {"type": "string"},
                    "ban_until": {"type": "string"},
                    "blocklisted": {"type": "boolean"}
                }
            },
            required_trust_state="admin",
            required_scopes=["deception", "firewall"],
            rate_limit=50,
            timeout_seconds=5,
            async_capable=True,
            idempotent=False,
            audit_level="full",
            redact_fields=[]
        )

        # Risk Scoring: Comprehensive assessment
        self.tools["mcp.deception.assess_risk"] = MCPToolSchema(
            tool_id="mcp.deception.assess_risk",
            name="Deception Risk Assessment",
            description="Comprehensive risk scoring with routing decision (pass/friction/trap_sink/honeypot)",
            category=MCPToolCategory.DECEPTION,
            version="1.0.0",
            input_schema={
                "type": "object",
                "properties": {
                    "ip": {"type": "string"},
                    "path": {"type": "string"},
                    "headers": {"type": "object"},
                    "behavior_flags": {"type": "object", "description": "Flags: decoy_touched, ai_behavior, repeated_failures"}
                },
                "required": ["ip"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "score": {"type": "integer"},
                    "reasons": {"type": "array"},
                    "route": {"type": "string"},
                    "delay_ms": {"type": "integer"}
                }
            },
            required_trust_state="elevated",
            required_scopes=["deception"],
            rate_limit=500,
            timeout_seconds=5,
            async_capable=True,
            idempotent=True,
            audit_level="basic",
            redact_fields=[]
        )

        # Decoy Interaction Recording
        self.tools["mcp.deception.record_decoy_touch"] = MCPToolSchema(
            tool_id="mcp.deception.record_decoy_touch",
            name="Record Decoy Interaction",
            description="Record attacker interaction with decoy/honey token for campaign correlation",
            category=MCPToolCategory.DECEPTION,
            version="1.0.0",
            input_schema={
                "type": "object",
                "properties": {
                    "ip": {"type": "string"},
                    "decoy_type": {"type": "string", "enum": ["honey_token", "canary_file", "fake_endpoint", "credential_trap"]},
                    "decoy_id": {"type": "string"},
                    "session_id": {"type": "string"}
                },
                "required": ["ip", "decoy_type", "decoy_id"]
            },
            output_schema={"type": "object"},
            required_trust_state="trusted",
            required_scopes=["deception"],
            rate_limit=200,
            timeout_seconds=5,
            async_capable=True,
            idempotent=False,
            audit_level="full",
            redact_fields=[]
        )

    def _register_builtin_handlers(self):
        """Register default handlers for built-in MCP tools."""
        self.register_tool_handler("mcp.scanner.network", self._handler_network_scan)
        self.register_tool_handler("mcp.edr.process_kill", self._handler_process_kill)
        self.register_tool_handler("mcp.firewall.block_ip", self._handler_firewall_block_ip)
        self.register_tool_handler("mcp.soar.run_playbook", self._handler_soar_run_playbook)
        self.register_tool_handler("mcp.forensics.memory_dump", self._handler_forensics_memory_dump)
        self.register_tool_handler("mcp.deception.deploy_honeypot", self._handler_deploy_honeypot)
        # AI Defense handlers
        self.register_tool_handler("mcp.defense.engage_tarpit", self._handler_engage_tarpit)
        self.register_tool_handler("mcp.defense.deploy_decoy", self._handler_deploy_decoy)
        self.register_tool_handler("mcp.defense.assess_ai_threat", self._handler_assess_ai_threat)
        self.register_tool_handler("mcp.defense.escalate_response", self._handler_escalate_response)
        self.register_tool_handler("mcp.defense.feed_disinformation", self._handler_feed_disinformation)
        # Quarantine handlers
        self.register_tool_handler("mcp.quarantine.advance_pipeline", self._handler_advance_pipeline)
        self.register_tool_handler("mcp.quarantine.add_scan_result", self._handler_add_scan_result)
        self.register_tool_handler("mcp.quarantine.get_pipeline_status", self._handler_get_pipeline_status)
        # Deception Engine handlers (Pebbles, Mystique, Stonewall)
        self.register_tool_handler("mcp.deception.track_campaign", self._handler_track_campaign)
        self.register_tool_handler("mcp.deception.mystique_adapt", self._handler_mystique_adapt)
        self.register_tool_handler("mcp.deception.stonewall_escalate", self._handler_stonewall_escalate)
        self.register_tool_handler("mcp.deception.assess_risk", self._handler_assess_deception_risk)
        self.register_tool_handler("mcp.deception.record_decoy_touch", self._handler_record_decoy_touch)

    def register_tool_handler(self, tool_id: str, handler: Callable):
        """Register or replace a handler for an existing MCP tool."""
        if tool_id not in self.tools:
            raise ValueError(f"Cannot register handler for unknown tool: {tool_id}")
        self.tool_handlers[tool_id] = handler
        logger.info(f"MCP: Registered handler for {tool_id}")

    async def _handler_network_scan(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Basic network scan handler using socket reachability checks."""
        target = str(params.get("target", "127.0.0.1")).strip()
        scan_type = str(params.get("scan_type", "quick")).lower()

        raw_ports = params.get("ports")
        if isinstance(raw_ports, list) and raw_ports:
            ports = [int(p) for p in raw_ports if str(p).isdigit() and 1 <= int(p) <= 65535][:64]
        elif scan_type == "full":
            ports = [21, 22, 23, 53, 80, 110, 139, 143, 443, 445, 3389, 5900, 8080]
        else:
            ports = [22, 80, 443]

        hosts_to_scan: List[str] = []
        try:
            if "/" in target:
                network = ipaddress.ip_network(target, strict=False)
                hosts_to_scan = [str(host) for host in network.hosts()][:32]
            else:
                hosts_to_scan = [str(ipaddress.ip_address(target))]
        except ValueError:
            try:
                hosts_to_scan = [socket.gethostbyname(target)]
            except socket.gaierror as exc:
                raise RuntimeError(f"Invalid scan target '{target}': {exc}") from exc

        started = time.time()
        hosts = []
        open_ports: Dict[str, List[int]] = {}

        for host in hosts_to_scan:
            host_open = []
            for port in ports:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.35)
                try:
                    if sock.connect_ex((host, port)) == 0:
                        host_open.append(port)
                except OSError:
                    pass
                finally:
                    sock.close()

            open_ports[host] = host_open
            hosts.append({
                "ip": host,
                "status": "reachable" if host_open else "scanned",
                "open_ports": host_open,
            })

        return {
            "target": target,
            "scan_type": scan_type,
            "hosts": hosts,
            "open_ports": open_ports,
            "scan_time": round(time.time() - started, 3),
        }

    def _handler_process_kill(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process termination handler with safe dry-run default."""
        pid = int(params.get("pid"))
        execute = bool(params.get("execute", False))
        force = bool(params.get("force", False))

        if pid <= 1 or pid in {os.getpid(), os.getppid()}:
            raise RuntimeError(f"Refusing to terminate protected PID: {pid}")

        process_name = None
        proc_name_path = f"/proc/{pid}/comm"
        if os.path.exists(proc_name_path):
            try:
                with open(proc_name_path, "r", encoding="utf-8") as handle:
                    process_name = handle.read().strip()
            except OSError:
                process_name = None

        if not execute:
            return {
                "success": False,
                "dry_run": True,
                "pid": pid,
                "process_name": process_name,
                "message": "Set execute=true to perform process termination.",
            }

        kill_signal = signal.SIGKILL if force else signal.SIGTERM
        os.kill(pid, kill_signal)

        return {
            "success": True,
            "pid": pid,
            "process_name": process_name,
            "signal": int(kill_signal),
            "terminated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _handler_firewall_block_ip(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Firewall block handler with dry-run safety by default."""
        ip = str(params.get("ip", "")).strip()
        if not ip:
            raise RuntimeError("Missing required parameter: ip")
        ipaddress.ip_address(ip)

        execute = bool(params.get("execute", False))
        duration_hours = int(params.get("duration_hours", 24))
        direction = str(params.get("direction", "inbound"))
        reason = str(params.get("reason", f"MCP firewall block ({direction})"))

        if not execute:
            return {
                "success": False,
                "dry_run": True,
                "ip": ip,
                "direction": direction,
                "duration_hours": duration_hours,
                "message": "Set execute=true to apply firewall rule.",
            }

        from threat_response import firewall, ResponseStatus

        result = await firewall.block_ip(ip=ip, reason=reason, duration_hours=duration_hours)
        if result.status != ResponseStatus.SUCCESS:
            raise RuntimeError(result.message)

        return {
            "success": True,
            "ip": ip,
            "direction": direction,
            "blocked_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": firewall.blocked_ips.get(ip).isoformat() if firewall.blocked_ips.get(ip) else None,
            "details": result.details,
        }

    async def _handler_soar_run_playbook(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """SOAR playbook execution handler."""
        playbook_id = str(params.get("playbook_id", "")).strip()
        if not playbook_id:
            raise RuntimeError("Missing required parameter: playbook_id")

        incident_id = str(params.get("incident_id", "manual-incident"))
        event_params = params.get("parameters", {}) or {}
        event = {
            "incident_id": incident_id,
            "trigger_type": "manual",
            **event_params,
        }

        from soar_engine import soar_engine

        execution = await soar_engine.execute_playbook(playbook_id, event)
        step_results = execution.step_results or []
        completed_steps = len([s for s in step_results if s.get("status") == "completed"])

        return {
            "execution_id": execution.id,
            "status": execution.status.value,
            "steps_completed": completed_steps,
            "results": step_results,
            "playbook_id": playbook_id,
            "incident_id": incident_id,
        }

    def _handler_forensics_memory_dump(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Memory dump handler backed by governed tool gateway with dry-run default."""
        pid = int(params.get("pid"))
        execute = bool(params.get("execute", False))

        if not execute:
            return {
                "dry_run": True,
                "pid": pid,
                "message": "Set execute=true to run memory dump collection.",
            }

        from runtime_paths import ensure_data_dir
        from services.tool_gateway import tool_gateway

        output_dir = str(params.get("output_path") or ensure_data_dir("forensics", "memory_dumps"))
        token_id = str(params.get("_token_id") or params.get("token_id") or "")
        governance_context = params.get("_governance_context") or {}
        principal = str(params.get("_principal") or "mcp_server")
        principal_identity = params.get("_principal_identity")
        action = str(params.get("_action") or "mcp_tool_execution")
        target = str(params.get("_target") or "memory_dump")
        execution = tool_gateway.execute(
            tool_id="memory_dump",
            parameters={"pid": pid, "output_dir": output_dir},
            principal=principal,
            token_id=token_id,
            trust_state="trusted",
            principal_identity=principal_identity,
            action=action,
            target=target,
            governance_context=governance_context,
        )

        if execution.status != "success":
            raise RuntimeError(execution.stderr or f"Memory dump failed with status={execution.status}")

        return {
            "dump_path": output_dir,
            "size_bytes": None,
            "hash": None,
            "execution_id": execution.execution_id,
            "stdout": execution.stdout,
        }

    def _handler_deploy_honeypot(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Deception deployment handler (network canary or honey token)."""
        honeypot_type = str(params.get("honeypot_type", "file")).strip().lower()
        target_zone = str(params.get("target_zone", "default")).strip() or "default"
        config = params.get("config", {}) or {}
        honeypot_id = f"hp_{uuid.uuid4().hex[:12]}"

        if honeypot_type == "network":
            from services.vns import vns

            ip = config.get("ip")
            domain = config.get("domain")
            port = config.get("port")

            if ip:
                vns.add_canary_ip(str(ip))
            if domain:
                vns.add_canary_domain(str(domain))
            if port is not None:
                vns.add_canary_port(int(port))

            if not any([ip, domain, port is not None]):
                raise RuntimeError("Network deception requires at least one of: config.ip, config.domain, config.port")

            trigger_endpoint = f"vns://canary/{target_zone}/{honeypot_id}"
        else:
            from honey_tokens import honey_token_manager

            token_type_map = {
                "credential": "password",
                "service": "api_key",
                "file": "api_key",
            }
            token_type = token_type_map.get(honeypot_type, "api_key")

            created = honey_token_manager.create_token(
                name=f"MCP Honeypot {honeypot_id}",
                token_type=token_type,
                description=f"MCP deception token for zone {target_zone}",
                location=config.get("location", f"deception/{target_zone}"),
                created_by="mcp_server",
            )

            trigger_endpoint = f"honeytoken://{created['id']}"

        return {
            "honeypot_id": honeypot_id,
            "deployed_at": datetime.now(timezone.utc).isoformat(),
            "trigger_endpoint": trigger_endpoint,
            "honeypot_type": honeypot_type,
            "target_zone": target_zone,
        }

    # ==========================================================================
    # AI Defense Handlers
    # ==========================================================================

    async def _handler_engage_tarpit(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Engage adaptive tarpit to slow down AI threats."""
        session_id = str(params.get("session_id", "")).strip()
        if not session_id:
            raise RuntimeError("Missing required parameter: session_id")

        threat_level = str(params.get("threat_level", "standard")).lower()
        host_id = str(params.get("host_id", "unknown")).strip()

        from threat_response import AIDefenseEngine

        result = await AIDefenseEngine.engage_tarpit(
            session_id=session_id,
            host_id=host_id,
            mode=threat_level
        )

        return {
            "session_id": session_id,
            "tarpit_engaged": True,
            "threat_level": threat_level,
            "current_delay_ms": result.details.get("base_delay_ms", 500),
            "engaged_at": datetime.now(timezone.utc).isoformat(),
            "details": result.details
        }

    async def _handler_deploy_decoy(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Deploy dynamic decoys targeting AI attackers."""
        decoy_type = str(params.get("decoy_type", "")).strip().lower()
        if not decoy_type:
            raise RuntimeError("Missing required parameter: decoy_type")

        host_id = str(params.get("host_id", "unknown")).strip()
        decoys = params.get("decoys", ["trap_credential_1", "trap_file_2", "honeypot_endpoint_3"])
        if not isinstance(decoys, list):
            decoys = [str(decoys)]
        placement = str(params.get("placement", "standard")).lower()

        from threat_response import AIDefenseEngine

        result = await AIDefenseEngine.deploy_decoy(
            host_id=host_id,
            decoy_type=decoy_type,
            decoys=decoys,
            placement=placement
        )

        return {
            "decoy_type": decoy_type,
            "decoys_deployed": result.details.get("count", 0),
            "decoy_id": result.details.get("decoy_id"),
            "placement": placement,
            "deployed_at": datetime.now(timezone.utc).isoformat()
        }

    async def _handler_assess_ai_threat(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Assess if activity is from AI/automated agent."""
        session_id = str(params.get("session_id", "")).strip()
        activity_data = params.get("activity_data", {})

        if not session_id:
            raise RuntimeError("Missing required parameter: session_id")

        request_timing = params.get("request_timing", [])
        host_id = str(params.get("host_id", activity_data.get("host_id", "unknown"))).strip()

        from threat_response import AIDefenseEngine

        # Adapt params to class method signature
        behavior_data = {
            **activity_data,
            "command_timestamps": request_timing
        }
        
        assessment = await AIDefenseEngine.assess_ai_threat(
            session_id=session_id,
            host_id=host_id,
            behavior_data=behavior_data
        )

        return {
            "session_id": session_id,
            "is_ai_threat": assessment.machine_likelihood >= 0.5,
            "ai_confidence": assessment.machine_likelihood,
            "confidence_level": assessment.confidence_level,
            "threat_indicators": assessment.dominant_intents,
            "recommended_action": assessment.recommended_escalation.value,
            "assessed_at": datetime.now(timezone.utc).isoformat()
        }

    async def _handler_escalate_response(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute graduated defense escalation."""
        session_id = str(params.get("session_id", "")).strip()
        target_level = str(params.get("target_level", "")).strip().lower()

        if not session_id:
            raise RuntimeError("Missing required parameter: session_id")
        if not target_level:
            raise RuntimeError("Missing required parameter: target_level")

        valid_levels = ["observe", "degrade", "deceive", "contain", "isolate", "eradicate"]
        if target_level not in valid_levels:
            raise RuntimeError(f"Invalid escalation level: {target_level}")

        current_level = str(params.get("current_level", "observe")).lower()
        threat_assessment = params.get("threat_assessment", {})

        from threat_response import AIDefenseEngine, ThreatContext, DefenseEscalationLevel

        # Build ThreatContext from params
        context = ThreatContext(
            threat_id=f"mcp-escalation-{uuid.uuid4().hex[:8]}",
            threat_type=threat_assessment.get("threat_type", "ai_threat"),
            severity=threat_assessment.get("severity", 8),
            agent_id=threat_assessment.get("agent_id"),
            source_ip=threat_assessment.get("source_ip"),
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_id=session_id,
            process_id=threat_assessment.get("process_id")
        )

        # Map target_level string to enum
        level_map = {
            "observe": DefenseEscalationLevel.OBSERVE,
            "degrade": DefenseEscalationLevel.DEGRADE,
            "deceive": DefenseEscalationLevel.DECEIVE,
            "contain": DefenseEscalationLevel.CONTAIN,
            "isolate": DefenseEscalationLevel.ISOLATE,
            "eradicate": DefenseEscalationLevel.ERADICATE
        }

        results = await AIDefenseEngine.execute_escalated_response(
            context=context,
            escalation_level=level_map.get(target_level, DefenseEscalationLevel.OBSERVE)
        )

        actions_taken = [r.action.value for r in results] if results else []

        return {
            "session_id": session_id,
            "previous_level": current_level,
            "current_level": target_level,
            "actions_taken": actions_taken,
            "escalation_successful": len(actions_taken) > 0,
            "escalated_at": datetime.now(timezone.utc).isoformat()
        }

    async def _handler_feed_disinformation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Feed targeted disinformation to mislead AI attackers."""
        session_id = str(params.get("session_id", "")).strip()
        disinformation_type = str(params.get("disinformation_type", "")).strip()

        if not session_id:
            raise RuntimeError("Missing required parameter: session_id")
        if not disinformation_type:
            raise RuntimeError("Missing required parameter: disinformation_type")

        goal_misdirection = bool(params.get("goal_misdirection", False))

        from threat_response import AIDefenseEngine

        result = await AIDefenseEngine.feed_disinformation(
            session_id=session_id,
            disinfo_type=disinformation_type,
            goal_misdirection=goal_misdirection
        )

        return {
            "session_id": session_id,
            "disinformation_type": disinformation_type,
            "disinformation_active": result.status.value == "success",
            "details": result.details,
            "fed_at": datetime.now(timezone.utc).isoformat()
        }

    # ==========================================================================
    # Quarantine Pipeline Handlers
    # ==========================================================================

    async def _handler_advance_pipeline(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Advance quarantine entry through pipeline stages."""
        entry_id = str(params.get("entry_id", "")).strip()
        if not entry_id:
            raise RuntimeError("Missing required parameter: entry_id")

        target_stage = params.get("target_stage", "scanning")
        reason = str(params.get("reason", "MCP advancement")).strip()

        from quarantine import get_quarantine_entry, advance_pipeline_stage

        entry = get_quarantine_entry(entry_id)
        if not entry:
            raise RuntimeError(f"Quarantine entry not found: {entry_id}")

        previous_stage = entry.pipeline_stage
        
        result = advance_pipeline_stage(
            entry_id=entry_id,
            new_stage=target_stage,
            reason=reason
        )

        return {
            "entry_id": entry_id,
            "previous_stage": previous_stage,
            "current_stage": result.pipeline_stage if result else target_stage,
            "advanced_at": datetime.now(timezone.utc).isoformat(),
            "success": result is not None
        }

    async def _handler_add_scan_result(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add scan result to quarantine entry."""
        entry_id = str(params.get("entry_id", "")).strip()
        engine = str(params.get("engine", "")).strip()
        detected = bool(params.get("detected", False))

        if not entry_id:
            raise RuntimeError("Missing required parameter: entry_id")
        if not engine:
            raise RuntimeError("Missing required parameter: engine")

        threat_name = params.get("threat_name")
        threat_category = params.get("threat_category")
        confidence = float(params.get("confidence", 0.0))

        from quarantine import add_scan_result as quarantine_add_scan_result

        result = quarantine_add_scan_result(
            entry_id=entry_id,
            scanner=engine,
            detection=detected,
            threat_name=threat_name,
            threat_category=threat_category,
            confidence=confidence
        )

        return {
            "entry_id": entry_id,
            "engine": engine,
            "detected": detected,
            "threat_name": threat_name,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "success": result is not None
        }

    def _handler_get_pipeline_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get full status of quarantine pipeline for an entry."""
        entry_id = str(params.get("entry_id", "")).strip()
        if not entry_id:
            raise RuntimeError("Missing required parameter: entry_id")

        from quarantine import get_quarantine_entry, get_pipeline_status

        entry = get_quarantine_entry(entry_id)
        if not entry:
            raise RuntimeError(f"Quarantine entry not found: {entry_id}")

        # Use dedicated pipeline status function if available
        pipeline_status = get_pipeline_status(entry_id)
        if pipeline_status:
            return pipeline_status

        return {
            "entry_id": entry_id,
            "current_stage": entry.pipeline_stage,
            "original_path": entry.original_path,
            "threat_type": entry.threat_type,
            "quarantined_at": entry.quarantined_at,
            "scan_results": entry.scan_results,
            "sandbox_result": entry.sandbox_result,
            "threat_intel_hits": entry.threat_intel_hits,
            "final_verdict": entry.final_verdict,
            "pipeline_complete": entry.pipeline_stage == "stored"
        }

    # ============ DECEPTION ENGINE HANDLERS ============

    async def _handler_track_campaign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Pebbles: Track attack campaign via behavioral fingerprint."""
        from deception_engine import deception_engine

        ip = str(params.get("ip", "")).strip()
        if not ip:
            raise RuntimeError("Missing required parameter: ip")

        headers = params.get("headers", {})
        timing_data = params.get("timing_data")
        session_id = params.get("session_id")
        path = params.get("path", "/")

        # Compute fingerprint and campaign
        fingerprint = deception_engine.compute_fingerprint(headers, timing_data)
        campaign_id = deception_engine.compute_campaign_id(ip, fingerprint.fingerprint_id, path)
        campaign = deception_engine.get_or_create_campaign(campaign_id, ip, fingerprint.fingerprint_id, session_id)

        # Determine risk level
        risk_level = "low"
        if campaign.trap_events > 10:
            risk_level = "critical"
        elif campaign.total_events > 30:
            risk_level = "high"
        elif campaign.total_events > 10:
            risk_level = "medium"

        return {
            "campaign_id": campaign_id,
            "fingerprint_id": fingerprint.fingerprint_id,
            "total_events": campaign.total_events,
            "trap_events": campaign.trap_events,
            "decoy_interactions": campaign.decoy_interactions,
            "source_ips": list(campaign.source_ips),
            "risk_level": risk_level,
            "escalation_level": campaign.escalation_level.value,
            "first_seen": campaign.first_seen,
            "last_seen": campaign.last_seen
        }

    async def _handler_mystique_adapt(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Mystique: Adapt deception parameters for a campaign."""
        from deception_engine import deception_engine

        campaign_id = str(params.get("campaign_id", "")).strip()
        if not campaign_id:
            raise RuntimeError("Missing required parameter: campaign_id")

        force_adapt = params.get("force_adapt", False)

        if campaign_id not in deception_engine.campaigns:
            raise RuntimeError(f"Campaign not found: {campaign_id}")

        campaign = deception_engine.campaigns[campaign_id]

        # Force adaptation if requested
        if force_adapt:
            campaign.total_events = max(
                campaign.total_events,
                deception_engine.config.campaign_promote_threshold + 1
            )
            # Align to adapt interval
            n = deception_engine.config.adapt_every_n_events
            campaign.total_events = ((campaign.total_events // n) + 1) * n

        adapted = deception_engine.mystique_adapt(campaign_id)

        return {
            "campaign_id": campaign_id,
            "adapted": adapted,
            "friction_multiplier": campaign.friction_multiplier,
            "tarpit_multiplier": campaign.tarpit_multiplier,
            "sink_score_override": campaign.sink_score_override,
            "escalation_level": campaign.escalation_level.value
        }

    async def _handler_stonewall_escalate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Stonewall: Apply progressive blocking escalation."""
        from deception_engine import deception_engine, EscalationLevel, RouteDecision
        import time as _time

        ip = str(params.get("ip", "")).strip()
        if not ip:
            raise RuntimeError("Missing required parameter: ip")

        campaign_id = params.get("campaign_id")
        target_level = params.get("target_level")

        # If target level specified, directly apply
        if target_level:
            level_map = {
                "warned": EscalationLevel.WARNED,
                "throttled": EscalationLevel.THROTTLED,
                "soft_banned": EscalationLevel.SOFT_BANNED,
                "hard_banned": EscalationLevel.HARD_BANNED,
                "blocklisted": EscalationLevel.BLOCKLISTED
            }
            
            if target_level not in level_map:
                raise RuntimeError(f"Invalid target_level: {target_level}")

            target = level_map[target_level]
            blocklisted = False
            ban_until = None

            if target == EscalationLevel.SOFT_BANNED:
                deception_engine.soft_bans[ip] = _time.time() + deception_engine.config.ban_seconds_first
                ban_until = datetime.fromtimestamp(deception_engine.soft_bans[ip], tz=timezone.utc).isoformat()
            elif target == EscalationLevel.HARD_BANNED:
                deception_engine.soft_bans[ip] = _time.time() + deception_engine.config.ban_seconds_repeat
                ban_until = datetime.fromtimestamp(deception_engine.soft_bans[ip], tz=timezone.utc).isoformat()
            elif target == EscalationLevel.BLOCKLISTED:
                deception_engine.blocklist.add(ip)
                blocklisted = True

            # Update campaign if exists
            if campaign_id and campaign_id in deception_engine.campaigns:
                deception_engine.campaigns[campaign_id].escalation_level = target

            return {
                "ip": ip,
                "escalation_level": target.value,
                "ban_until": ban_until,
                "blocklisted": blocklisted
            }

        # Otherwise use automatic escalation
        if not campaign_id:
            raise RuntimeError("campaign_id required when target_level not specified")

        new_level = deception_engine.stonewall_check(campaign_id, ip, RouteDecision.TRAP_SINK)
        ban_until = None
        if ip in deception_engine.soft_bans:
            ban_until = datetime.fromtimestamp(deception_engine.soft_bans[ip], tz=timezone.utc).isoformat()

        return {
            "ip": ip,
            "campaign_id": campaign_id,
            "escalation_level": new_level.value,
            "ban_until": ban_until,
            "blocklisted": ip in deception_engine.blocklist
        }

    async def _handler_assess_deception_risk(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive deception risk assessment."""
        from deception_engine import deception_engine

        ip = str(params.get("ip", "")).strip()
        if not ip:
            raise RuntimeError("Missing required parameter: ip")

        path = params.get("path", "/")
        headers = params.get("headers", {})
        session_id = params.get("session_id")
        behavior_flags = params.get("behavior_flags", {})

        assessment = await deception_engine.process_request(
            ip=ip,
            path=path,
            headers=headers,
            session_id=session_id,
            behavior_flags=behavior_flags
        )

        return {
            "score": assessment.score,
            "reasons": assessment.reasons,
            "route": assessment.route.value,
            "delay_ms": assessment.delay_ms,
            "campaign_id": assessment.campaign_id,
            "fingerprint_id": assessment.fingerprint_id,
            "escalation_level": assessment.escalation_level.value
        }

    async def _handler_record_decoy_touch(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Record attacker interaction with decoy/honey token."""
        from deception_engine import deception_engine

        ip = str(params.get("ip", "")).strip()
        decoy_type = str(params.get("decoy_type", "")).strip()
        decoy_id = str(params.get("decoy_id", "")).strip()

        if not ip or not decoy_type or not decoy_id:
            raise RuntimeError("Missing required parameters: ip, decoy_type, decoy_id")

        session_id = params.get("session_id")
        headers = params.get("headers", {})

        assessment = await deception_engine.record_decoy_interaction(
            ip=ip,
            decoy_type=decoy_type,
            decoy_id=decoy_id,
            session_id=session_id,
            headers=headers
        )

        return {
            "recorded": True,
            "ip": ip,
            "decoy_type": decoy_type,
            "decoy_id": decoy_id,
            "risk_score": assessment.score,
            "route": assessment.route.value,
            "campaign_id": assessment.campaign_id,
            "escalation_level": assessment.escalation_level.value,
            "alert_triggered": True
        }
    
    def register_tool(self, schema: MCPToolSchema, handler: Callable = None):
        """Register a tool with the MCP server"""
        if self.polyphonic_governance is not None:
            voice_profile = self.polyphonic_governance.voice_registry.resolve_voice_for_action(
                tool_name=schema.tool_id,
                component_id="mcp_server",
                route="mcp:tool_request",
                component_type="ingress",
            )
            if voice_profile is not None:
                schema.voice_type = schema.voice_type or voice_profile.voice_type
                schema.capability_class = schema.capability_class or voice_profile.capability_class
                schema.timbre_profile = schema.timbre_profile or voice_profile.timbre_profile
                schema.allowed_register = schema.allowed_register or voice_profile.allowed_register
                self.polyphonic_governance.voice_registry.register_tool_voice(schema.tool_id, voice_profile)
        self.tools[schema.tool_id] = schema
        if handler:
            self.tool_handlers[schema.tool_id] = handler
        logger.info(f"MCP: Registered tool {schema.tool_id} v{schema.version}")
    
    def create_message(self, message_type: MCPMessageType, source: str,
                       destination: str, payload: Dict[str, Any],
                       trace_id: str = None, priority: int = 5) -> MCPMessage:
        """Create a signed MCP message"""
        message = MCPMessage(
            message_id=f"mcp-{uuid.uuid4().hex[:12]}",
            message_type=message_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            source=source,
            destination=destination,
            payload=payload,
            signature="",  # Will be set below
            trace_id=trace_id or uuid.uuid4().hex,
            priority=priority
        )
        
        message.signature = self._sign_message(message)
        return message
    
    async def handle_message(self, message: MCPMessage) -> MCPMessage:
        """Handle an incoming MCP message"""
        # Verify signature
        if not self._verify_signature(message):
            return self._error_response(message, "Invalid message signature")
        
        # Store in history
        self.message_history.append(message)
        
        # Route by type
        if message.message_type == MCPMessageType.TOOL_REQUEST:
            return await self._handle_tool_request(message)
        elif message.message_type == MCPMessageType.POLICY_CHECK:
            return await self._handle_policy_check(message)
        elif message.message_type == MCPMessageType.TELEMETRY:
            return await self._handle_telemetry(message)
        elif message.message_type == MCPMessageType.HEARTBEAT:
            return self._handle_heartbeat(message)
        else:
            return self._error_response(message, f"Unknown message type: {message.message_type}")
    
    async def _handle_tool_request(self, message: MCPMessage) -> MCPMessage:
        """Handle a tool execution request"""
        tool_id = message.destination
        
        # Check if tool exists
        if tool_id not in self.tools:
            return self._error_response(message, f"Unknown tool: {tool_id}")
        
        tool = self.tools[tool_id]
        payload = dict(message.payload or {})
        polyphonic_context: Dict[str, Any] = {}
        if self.polyphonic_governance is not None:
            policy_refs: List[str] = []
            if payload.get("policy_decision_id"):
                policy_refs.append(str(payload.get("policy_decision_id")))
            if payload.get("decision_id"):
                policy_refs.append(str(payload.get("decision_id")))
            envelope = self.polyphonic_governance.build_action_request_envelope(
                actor_id=str(message.source or "unknown"),
                actor_type="mcp_principal",
                operation="mcp_tool_execution",
                parameters=payload.get("params") if isinstance(payload.get("params"), dict) else {},
                tool_name=tool_id,
                resource_uris=[str(payload.get("target"))] if payload.get("target") else [],
                context_refs={
                    "request_id": message.message_id,
                    "trace_id": message.trace_id,
                    "decision_id": str(payload.get("decision_id") or payload.get("policy_decision_id") or ""),
                },
                policy_refs=policy_refs,
                evidence_hashes=[],
                target_domain=payload.get("sector_to"),
            )
            envelope = self.polyphonic_governance.attach_voice_profile(
                envelope,
                component_id="mcp_server",
                route="mcp:tool_request",
                tool_name=tool_id,
                component_type="ingress",
            )
            polyphonic_context = self.polyphonic_governance.serialize_polyphonic_context(envelope)
            if polyphonic_context:
                payload["polyphonic_context"] = polyphonic_context
        if (
            polyphonic_context
            and isinstance(polyphonic_context, dict)
            and get_governance_epoch_service is not None
            and get_notation_token_service is not None
        ):
            try:
                epoch_service = get_governance_epoch_service(getattr(self, "db", None))
                notation_service = get_notation_token_service(getattr(self, "db", None))
                scope = str(payload.get("sector_to") or payload.get("target_domain") or "global")
                active_epoch = await epoch_service.get_active_epoch(scope=scope)
                if active_epoch is not None:
                    voice_profile = polyphonic_context.get("voice_profile") or {}
                    notation = await notation_service.mint_notation_token(
                        epoch_id=active_epoch.epoch_id,
                        score_id=active_epoch.score_id,
                        genre_mode=active_epoch.genre_mode,
                        voice_role=str(voice_profile.get("voice_type") or "gateway_tenor"),
                        capability_class=str(voice_profile.get("capability_class") or "ingress"),
                        world_state_hash=active_epoch.world_state_hash,
                        issued_to=str(message.source or "unknown"),
                        entry_window_ms=payload.get("entry_window_ms") or [0, 300000],
                        sequence_slot=payload.get("sequence_slot"),
                        required_companions=payload.get("required_companions") or [],
                        response_class="mcp_tool_execution",
                        ttl_seconds=int(payload.get("notation_ttl_seconds") or 600),
                    )
                    notation_doc = (
                        notation.model_dump() if hasattr(notation, "model_dump") else notation.dict()
                    )
                    polyphonic_context["governance_epoch"] = active_epoch.epoch_id
                    polyphonic_context["score_id"] = active_epoch.score_id
                    polyphonic_context["genre_mode"] = active_epoch.genre_mode
                    polyphonic_context["strictness_level"] = active_epoch.strictness_level
                    polyphonic_context["world_state_hash"] = active_epoch.world_state_hash
                    polyphonic_context["notation_token_id"] = notation.token_id
                    polyphonic_context["notation_token"] = notation_doc
                    payload["polyphonic_context"] = polyphonic_context
                    payload["governance_epoch"] = active_epoch.epoch_id
                    payload["score_id"] = active_epoch.score_id
                    payload["genre_mode"] = active_epoch.genre_mode
                    payload["world_state_hash"] = active_epoch.world_state_hash
                    payload["notation_token_id"] = notation.token_id
            except Exception:
                logger.debug("Failed to mint notation token for MCP request", exc_info=True)
        high_impact_categories = {
            MCPToolCategory.EDR,
            MCPToolCategory.FIREWALL,
            MCPToolCategory.SOAR,
            MCPToolCategory.FORENSICS,
            MCPToolCategory.DECEPTION,
            MCPToolCategory.IDENTITY,
            MCPToolCategory.NETWORK,
            MCPToolCategory.AI_DEFENSE,
            MCPToolCategory.QUARANTINE,
        }
        decision_id = payload.get("decision_id") or payload.get("policy_decision_id")
        queue_id = payload.get("queue_id")
        governance_approved = bool(payload.get("governance_approved"))
        boundary_pre_observation: Dict[str, Any] = {}
        boundary_post_observation: Dict[str, Any] = {}
        boundary_contract = None
        if build_boundary_contract is not None:
            decision_context = {
                "decision_id": decision_id,
                "queue_id": queue_id,
                "policy_decision_id": payload.get("policy_decision_id"),
                "governance_approved": governance_approved,
            }
            boundary_contract = build_boundary_contract(
                principal=message.source,
                sector_from=payload.get("sector_from") or "governance",
                sector_to=payload.get("sector_to") or "tool_execution",
                capability=tool_id,
                target=payload.get("target") or tool_id,
                decision_context=decision_context,
                token=payload.get("token_id"),
                risk_hint=payload.get("risk_hint") if isinstance(payload.get("risk_hint"), dict) else {},
                trace_id=message.trace_id,
            )
            if boundary_control is not None:
                try:
                    boundary_pre_observation = boundary_control.pre_observe(boundary_contract)
                except Exception:
                    boundary_pre_observation = {}
        
        # Create execution record
        execution = MCPToolExecution(
            execution_id=f"exec-{uuid.uuid4().hex[:12]}",
            tool_id=tool_id,
            request_message_id=message.message_id,
            principal=message.source,
            input_params=payload.get("params", {}),
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=None,
            status="running",
            output=None,
            error=None,
            policy_decision_id=payload.get("policy_decision_id"),
            token_id=payload.get("token_id"),
            audit_hash=""
        )
        
        self.executions[execution.execution_id] = execution

        required_action_types = {"mcp_tool_execution", "tool_execution"}
        validated_governance_context: Dict[str, Any] = {}
        governance_valid = False
        governance_error = "missing"
        if decision_id or queue_id:
            governance_valid, governance_error, validated_governance_context = await self._resolve_approved_governance_context(
                decision_id=str(decision_id) if decision_id else None,
                queue_id=str(queue_id) if queue_id else None,
                required_action_types=required_action_types,
            )
            if governance_valid:
                execution.policy_decision_id = validated_governance_context.get("decision_id") or execution.policy_decision_id
        resolved_decision_id = (
            validated_governance_context.get("decision_id")
            or execution.policy_decision_id
            or (str(decision_id) if decision_id else "")
        )
        resolved_queue_id = validated_governance_context.get("queue_id") or (str(queue_id) if queue_id else "")

        async def _emit_boundary_crossing_event(mcp_outcome: str, mcp_reason: str = "") -> None:
            nonlocal boundary_post_observation
            if boundary_control is None or boundary_contract is None:
                return
            try:
                boundary_post_observation = boundary_control.post_observe(
                    boundary_contract,
                    pre_observation=boundary_pre_observation,
                    mcp_outcome=mcp_outcome,
                    mcp_reason=mcp_reason,
                    execution_status=execution.status,
                )
                await self._emit_mcp_event(
                    event_type="boundary_crossing",
                    entity_refs=[
                        execution.execution_id,
                        execution.tool_id,
                        execution.principal,
                    ],
                    payload={
                        "crossing_outcome": boundary_post_observation.get("world_event_outcome", "allowed"),
                        "mcp_outcome": str(mcp_outcome or "allowed"),
                        "mcp_reason": str(mcp_reason or ""),
                        "execution_status": execution.status,
                        "policy_decision_id": execution.policy_decision_id,
                        "governance_decision_id": resolved_decision_id,
                        "governance_queue_id": resolved_queue_id,
                        "token_id": execution.token_id,
                        "trace_id": message.trace_id,
                        "voice_type": ((polyphonic_context.get("voice_profile") or {}).get("voice_type") if polyphonic_context else None),
                        "capability_class": ((polyphonic_context.get("voice_profile") or {}).get("capability_class") if polyphonic_context else None),
                        "polyphonic_context": polyphonic_context,
                        "pre_observation": boundary_pre_observation,
                        "post_observation": boundary_post_observation,
                        "boundary_contract": contract_to_dict(boundary_contract) if contract_to_dict else {},
                    },
                    trigger_triune=True,
                )
            except Exception:
                logger.exception("Failed to emit boundary crossing event for %s", execution.execution_id)

        throttle_threshold = int(str(os.environ.get("MCP_BOUNDARY_THROTTLE_PER_MINUTE", "18")) or "18")
        crossings_per_minute = int(boundary_pre_observation.get("crossings_per_minute") or 0)
        if throttle_threshold > 0 and crossings_per_minute >= throttle_threshold:
            execution.status = "throttled"
            execution.error = (
                f"Boundary throttle: {crossings_per_minute} crossings/min "
                f"(threshold={throttle_threshold})"
            )
            execution.output = {
                "retry_after_seconds": 30,
                "crossings_per_minute": crossings_per_minute,
                "threshold": throttle_threshold,
            }
            execution.completed_at = datetime.now(timezone.utc).isoformat()
            execution.audit_hash = hashlib.sha256(
                json.dumps(asdict(execution), sort_keys=True).encode()
            ).hexdigest()[:32]
            await self._emit_mcp_event(
                event_type="mcp_tool_request_throttled",
                entity_refs=[execution.execution_id, execution.tool_id, execution.principal],
                payload={
                    "status": execution.status,
                    "execution_id": execution.execution_id,
                    "trace_id": message.trace_id,
                    "crossings_per_minute": crossings_per_minute,
                    "threshold": throttle_threshold,
                    "voice_type": ((polyphonic_context.get("voice_profile") or {}).get("voice_type") if polyphonic_context else None),
                    "capability_class": ((polyphonic_context.get("voice_profile") or {}).get("capability_class") if polyphonic_context else None),
                    "polyphonic_context": polyphonic_context,
                },
                trigger_triune=True,
            )
            await _emit_boundary_crossing_event(
                mcp_outcome="queued",
                mcp_reason=execution.error,
            )
            return self.create_message(
                message_type=MCPMessageType.TOOL_RESPONSE,
                source="mcp_server",
                destination=message.source,
                payload={
                    "execution_id": execution.execution_id,
                    "status": execution.status,
                    "output": execution.output,
                    "error": execution.error,
                    "audit_hash": execution.audit_hash,
                    "polyphonic_context": polyphonic_context,
                    "boundary": {
                        "pre": boundary_pre_observation,
                        "post": boundary_post_observation,
                    },
                },
                trace_id=message.trace_id,
            )

        # Mandatory governance boundary: high-impact MCP tools must either have
        # server-validated approved governance context or be newly queued.
        if tool.category in high_impact_categories and not governance_valid:
            if getattr(self, "db", None) is None:
                execution.status = "failed"
                execution.error = "MCP DB context unavailable for outbound governance"
            else:
                try:
                    try:
                        from services.outbound_gate import OutboundGateService
                    except Exception:
                        from backend.services.outbound_gate import OutboundGateService

                    gate = OutboundGateService(self.db)
                    gated = await gate.gate_action(
                        action_type="mcp_tool_execution",
                        actor=message.source,
                        payload={
                            "tool_id": tool_id,
                            "params": payload.get("params", {}),
                            "trace_id": message.trace_id,
                            "request_message_id": message.message_id,
                            "polyphonic_context": polyphonic_context,
                        },
                        impact_level="critical",
                        subject_id=tool_id,
                        entity_refs=[tool_id, message.source, message.message_id],
                        requires_triune=True,
                        polyphonic_context=polyphonic_context,
                    )
                    execution.status = "queued_for_triune_approval"
                    execution.output = {
                        "queue_id": gated.get("queue_id"),
                        "decision_id": gated.get("decision_id"),
                        "action_id": gated.get("action_id"),
                        "governance_context_error": governance_error,
                        "caller_governance_approved": governance_approved,
                    }
                    resolved_decision_id = str(gated.get("decision_id") or resolved_decision_id or "")
                    resolved_queue_id = str(gated.get("queue_id") or resolved_queue_id or "")
                except Exception as exc:
                    execution.status = "failed"
                    execution.error = f"Failed to outbound-gate MCP tool request: {exc}"

            execution.completed_at = datetime.now(timezone.utc).isoformat()
            execution.audit_hash = hashlib.sha256(
                json.dumps(asdict(execution), sort_keys=True).encode()
            ).hexdigest()[:32]
            await self._emit_mcp_event(
                event_type="mcp_tool_request_gated",
                entity_refs=[execution.execution_id, execution.tool_id, execution.principal],
                payload={
                    "status": execution.status,
                    "policy_decision_id": execution.policy_decision_id,
                    "governance_decision_id": resolved_decision_id,
                    "governance_queue_id": resolved_queue_id,
                    "token_id": execution.token_id,
                    "execution_id": execution.execution_id,
                    "trace_id": message.trace_id,
                    "requires_governance": True,
                    "governance_error": governance_error,
                    "voice_type": ((polyphonic_context.get("voice_profile") or {}).get("voice_type") if polyphonic_context else None),
                    "capability_class": ((polyphonic_context.get("voice_profile") or {}).get("capability_class") if polyphonic_context else None),
                    "polyphonic_context": polyphonic_context,
                },
                trigger_triune=True,
            )
            await _emit_boundary_crossing_event(
                mcp_outcome="queued" if execution.status == "queued_for_triune_approval" else "denied",
                mcp_reason=execution.error or governance_error,
            )
            return self.create_message(
                message_type=MCPMessageType.TOOL_RESPONSE,
                source="mcp_server",
                destination=message.source,
                payload={
                    "execution_id": execution.execution_id,
                    "status": execution.status,
                    "output": execution.output,
                    "error": execution.error,
                    "audit_hash": execution.audit_hash,
                    "polyphonic_context": polyphonic_context,
                    "boundary": {
                        "pre": boundary_pre_observation,
                        "post": boundary_post_observation,
                    },
                },
                trace_id=message.trace_id,
            )

        enforce_token = (
            tool.category in high_impact_categories
            or str(os.environ.get("MCP_ENFORCE_TOKEN_ALL_TOOLS", "false")).lower() in {"1", "true", "yes", "on"}
        )
        if enforce_token:
            action = str(payload.get("action") or "mcp_tool_execution")
            target = str(payload.get("target") or tool_id)
            principal_identity = payload.get("principal_identity")
            valid_token, token_message = self._validate_capability_token(
                token_id=execution.token_id,
                principal=message.source,
                principal_identity=principal_identity,
                action=action,
                target=target,
            )
            if not valid_token:
                execution.status = "failed"
                execution.error = f"Token validation failed: {token_message}"
                execution.completed_at = datetime.now(timezone.utc).isoformat()
                execution.audit_hash = hashlib.sha256(
                    json.dumps(asdict(execution), sort_keys=True).encode()
                ).hexdigest()[:32]
                self._record_mcp_execution_audit(
                    execution=execution,
                    trace_id=message.trace_id,
                    governance_context={
                        "decision_id": resolved_decision_id,
                        "queue_id": resolved_queue_id,
                    },
                    result="failed",
                    result_details=execution.error,
                    targets=[tool_id, target],
                )
                await self._emit_mcp_event(
                    event_type="mcp_tool_request_executed",
                    entity_refs=[execution.execution_id, execution.tool_id, execution.principal],
                    payload={
                        "status": execution.status,
                        "policy_decision_id": execution.policy_decision_id,
                        "governance_decision_id": resolved_decision_id,
                        "governance_queue_id": resolved_queue_id,
                        "token_id": execution.token_id,
                        "execution_id": execution.execution_id,
                        "trace_id": message.trace_id,
                        "has_error": True,
                        "token_validation_failed": True,
                        "voice_type": ((polyphonic_context.get("voice_profile") or {}).get("voice_type") if polyphonic_context else None),
                        "capability_class": ((polyphonic_context.get("voice_profile") or {}).get("capability_class") if polyphonic_context else None),
                        "polyphonic_context": polyphonic_context,
                    },
                    trigger_triune=True,
                )
                await _emit_boundary_crossing_event(
                    mcp_outcome="token-invalid",
                    mcp_reason=execution.error or token_message,
                )
                return self.create_message(
                    message_type=MCPMessageType.TOOL_RESPONSE,
                    source="mcp_server",
                    destination=message.source,
                    payload={
                        "execution_id": execution.execution_id,
                        "status": execution.status,
                        "output": execution.output,
                        "error": execution.error,
                        "audit_hash": execution.audit_hash,
                        "polyphonic_context": polyphonic_context,
                        "boundary": {
                            "pre": boundary_pre_observation,
                            "post": boundary_post_observation,
                        },
                    },
                    trace_id=message.trace_id,
                )
        
        # Execute if handler registered
        if tool_id in self.tool_handlers:
            try:
                handler = self.tool_handlers[tool_id]
                execution_params = dict(payload.get("params", {}))
                execution_params["_governance_context"] = validated_governance_context
                execution_params["_token_id"] = execution.token_id
                execution_params["_principal"] = message.source
                execution_params["_principal_identity"] = payload.get("principal_identity")
                execution_params["_action"] = payload.get("action") or "mcp_tool_execution"
                execution_params["_target"] = payload.get("target") or tool_id
                execution_params["_polyphonic_context"] = polyphonic_context
                execution_params["_notation_token_id"] = (
                    payload.get("notation_token_id")
                    or ((polyphonic_context.get("notation_token") or {}).get("token_id") if isinstance(polyphonic_context, dict) else None)
                    or (polyphonic_context.get("notation_token_id") if isinstance(polyphonic_context, dict) else None)
                )
                if asyncio.iscoroutinefunction(handler):
                    result = await asyncio.wait_for(
                        handler(execution_params),
                        timeout=tool.timeout_seconds
                    )
                else:
                    result = handler(execution_params)
                
                execution.status = "success"
                execution.output = result
                
            except asyncio.TimeoutError:
                execution.status = "timeout"
                execution.error = "Execution timed out"
            except Exception as e:
                execution.status = "failed"
                execution.error = str(e)
        else:
            allow_simulation = str(os.environ.get("MCP_ALLOW_SIMULATED_EXECUTION", "false")).lower() in {"1", "true", "yes", "on"}
            if allow_simulation:
                execution.status = "success"
                execution.output = {"simulated": True, "tool_id": tool_id}
            else:
                execution.status = "failed"
                execution.error = (
                    f"No handler registered for tool '{tool_id}'. "
                    "Set MCP_ALLOW_SIMULATED_EXECUTION=true only for demo/testing mode."
                )
        
        execution.completed_at = datetime.now(timezone.utc).isoformat()
        
        # Compute audit hash
        execution.audit_hash = hashlib.sha256(
            json.dumps(asdict(execution), sort_keys=True).encode()
        ).hexdigest()[:32]
        self._record_mcp_execution_audit(
            execution=execution,
            trace_id=message.trace_id,
            governance_context={
                "decision_id": resolved_decision_id,
                "queue_id": resolved_queue_id,
            },
            result="success" if execution.status == "success" else "failed",
            result_details=execution.error,
            targets=[tool_id, str(payload.get("target") or tool_id)],
        )

        await self._emit_mcp_event(
            event_type="mcp_tool_request_executed",
            entity_refs=[execution.execution_id, execution.tool_id, execution.principal],
            payload={
                "status": execution.status,
                "policy_decision_id": execution.policy_decision_id,
                "governance_decision_id": resolved_decision_id,
                "governance_queue_id": resolved_queue_id,
                "token_id": execution.token_id,
                "execution_id": execution.execution_id,
                "trace_id": message.trace_id,
                "has_error": execution.error is not None,
                "voice_type": ((polyphonic_context.get("voice_profile") or {}).get("voice_type") if polyphonic_context else None),
                "capability_class": ((polyphonic_context.get("voice_profile") or {}).get("capability_class") if polyphonic_context else None),
                "polyphonic_context": polyphonic_context,
            },
            trigger_triune=execution.status in {"failed", "timeout"},
        )
        await _emit_boundary_crossing_event(
            mcp_outcome="allowed" if execution.status != "denied" else "denied",
            mcp_reason=execution.error or "",
        )
        
        # Create response
        return self.create_message(
            message_type=MCPMessageType.TOOL_RESPONSE,
            source="mcp_server",
            destination=message.source,
            payload={
                "execution_id": execution.execution_id,
                "status": execution.status,
                "output": execution.output,
                "error": execution.error,
                "audit_hash": execution.audit_hash,
                "polyphonic_context": polyphonic_context,
                "boundary": {
                    "pre": boundary_pre_observation,
                    "post": boundary_post_observation,
                },
            },
            trace_id=message.trace_id
        )
    
    async def _handle_policy_check(self, message: MCPMessage) -> MCPMessage:
        """Handle a policy check request"""
        # Delegate to policy engine
        from services.policy_engine import policy_engine
        if getattr(self, "db", None) is not None and hasattr(policy_engine, "set_db"):
            policy_engine.set_db(self.db)
        
        payload = message.payload
        decision = policy_engine.evaluate(
            principal=payload.get("principal", message.source),
            action=payload.get("action", ""),
            targets=payload.get("targets", []),
            trust_state=payload.get("trust_state", "unknown"),
            role=payload.get("role", "agent")
        )

        await self._emit_mcp_event(
            event_type="mcp_policy_checked",
            entity_refs=[decision.decision_id, payload.get("principal", message.source)],
            payload={
                "action": payload.get("action", ""),
                "permitted": decision.permitted,
                "approval_tier": decision.approval_tier.value,
            },
            trigger_triune=not decision.permitted,
        )
        
        return self.create_message(
            message_type=MCPMessageType.POLICY_RESULT,
            source="mcp_server",
            destination=message.source,
            payload={
                "decision_id": decision.decision_id,
                "permitted": decision.permitted,
                "approval_tier": decision.approval_tier.value,
                "denial_reason": decision.denial_reason,
                "constraints": {
                    "rate_limit": decision.rate_limit,
                    "blast_radius_cap": decision.blast_radius_cap,
                    "ttl_seconds": decision.ttl_seconds
                }
            },
            trace_id=message.trace_id
        )
    
    async def _handle_telemetry(self, message: MCPMessage) -> MCPMessage:
        """Handle telemetry ingestion"""
        from services.telemetry_chain import tamper_evident_telemetry
        if getattr(self, "db", None) is not None and hasattr(tamper_evident_telemetry, "set_db"):
            tamper_evident_telemetry.set_db(self.db)
        
        payload = message.payload
        event = tamper_evident_telemetry.ingest_event(
            event_type=payload.get("event_type", "mcp.telemetry"),
            severity=payload.get("severity", "info"),
            data=payload.get("data", {}),
            agent_id=message.source,
            trace_id=message.trace_id
        )
        
        return self.create_message(
            message_type=MCPMessageType.TOOL_RESPONSE,
            source="mcp_server",
            destination=message.source,
            payload={
                "event_id": event.event_id,
                "event_hash": event.event_hash,
                "acknowledged": True
            },
            trace_id=message.trace_id
        )
    
    def _handle_heartbeat(self, message: MCPMessage) -> MCPMessage:
        """Handle heartbeat"""
        return self.create_message(
            message_type=MCPMessageType.HEARTBEAT,
            source="mcp_server",
            destination=message.source,
            payload={
                "status": "alive",
                "server_time": datetime.now(timezone.utc).isoformat(),
                "tools_available": len(self.tools)
            },
            trace_id=message.trace_id
        )
    
    def _error_response(self, original: MCPMessage, error: str) -> MCPMessage:
        """Create an error response"""
        return self.create_message(
            message_type=MCPMessageType.ERROR,
            source="mcp_server",
            destination=original.source,
            payload={"error": error, "original_message_id": original.message_id},
            trace_id=original.trace_id
        )
    
    def get_tool_catalog(self) -> List[Dict]:
        """Get tool catalog"""
        return [
            {
                "tool_id": t.tool_id,
                "name": t.name,
                "description": t.description,
                "category": t.category.value,
                "version": t.version,
                "required_trust_state": t.required_trust_state,
                "rate_limit": t.rate_limit,
                "voice_type": t.voice_type,
                "capability_class": t.capability_class,
                "timbre_profile": t.timbre_profile,
                "allowed_register": t.allowed_register,
            }
            for t in self.tools.values()
        ]
    
    def get_execution_history(self, tool_id: str = None, 
                              principal: str = None,
                              limit: int = 100) -> List[Dict]:
        """Get execution history"""
        results = []
        for exec in sorted(self.executions.values(), 
                          key=lambda x: x.started_at, reverse=True):
            if tool_id and exec.tool_id != tool_id:
                continue
            if principal and exec.principal != principal:
                continue
            results.append(asdict(exec))
            if len(results) >= limit:
                break
        return results
    
    def get_server_status(self) -> Dict:
        """Get MCP server status"""
        boundary_status = {}
        if boundary_control is not None:
            try:
                boundary_status = boundary_control.get_boundary_status()
            except Exception:
                boundary_status = {}
        return {
            "tools_registered": len(self.tools),
            "handlers_registered": len(self.tool_handlers),
            "pending_requests": len(self.pending_requests),
            "message_history_size": len(self.message_history),
            "total_executions": len(self.executions),
            "boundary_status": boundary_status,
        }


# Global singleton
mcp_server = MCPServer()
