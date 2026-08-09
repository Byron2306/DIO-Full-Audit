"""
Enterprise Security Router
===========================
API endpoints for enterprise security features:
- Identity & Attestation
- Tamper-Evident Telemetry
- Policy & Permissions
- Token Broker
- CLI Tool Gateway
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone

from .dependencies import get_current_user, check_permission, db

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/enterprise", tags=["Enterprise Security"])

ENTERPRISE_CONTROL_PLANE_CONTRACT_VERSION = "2026-03-07.1"


def _normalize_boundary_outcome(raw_outcome: Any) -> str:
    normalized = str(raw_outcome or "").strip().lower()
    if normalized in {"deny", "denied", "blocked", "reject", "rejected"}:
        return "denied"
    if normalized in {"queue", "queued", "throttle", "throttled", "pending"}:
        return "queued"
    if normalized in {"allow", "allowed", "success", "completed"}:
        return "allowed"
    return "queued"


def _extract_endpoint_boundary_context(data: Dict[str, Any], fallback_agent_id: Optional[str] = None) -> Dict[str, Any]:
    boundary = data.get("boundary") if isinstance(data, dict) else {}
    boundary = boundary if isinstance(boundary, dict) else {}
    post_observation = data.get("post_observation") if isinstance(data, dict) else {}
    post_observation = post_observation if isinstance(post_observation, dict) else {}

    outcome = data.get("outcome") or post_observation.get("gate_outcome") or boundary.get("outcome")
    return {
        "agent_id": data.get("agent_id") or fallback_agent_id,
        "decision_context": boundary.get("decision_context") or data.get("decision_context") or {},
        "outcome": _normalize_boundary_outcome(outcome),
        "beacon": post_observation.get("beacon") or data.get("beacon") or {},
        "raw": data,
    }


def _endpoint_boundary_trigger_triune(boundary_context: Dict[str, Any]) -> bool:
    beacon = boundary_context.get("beacon") if isinstance(boundary_context, dict) else {}
    state = str((beacon or {}).get("state") or "").strip().lower()
    outcome = _normalize_boundary_outcome((boundary_context or {}).get("outcome"))
    return state in {"red", "amber"} or outcome in {"denied", "queued"}


# =============================================================================
# MODELS
# =============================================================================

class AttestationRequest(BaseModel):
    agent_id: str
    hostname: str
    os_type: str
    cert_fingerprint: str
    agent_version_hash: str
    os_build_hash: str
    secure_boot: bool
    tpm_available: bool
    key_isolated: bool
    posture_score: int
    timestamp: str
    nonce: str
    signature: str


class PolicyEvaluationRequest(BaseModel):
    principal: str
    action: str
    targets: List[str]
    trust_state: str = "unknown"
    role: str = "agent"
    tool_id: Optional[str] = None
    evidence_confidence: float = 0.5
    incident_mode: str = "normal"


class TokenRequest(BaseModel):
    principal: str
    principal_identity: str
    action: str
    targets: List[str]
    tool_id: Optional[str] = None
    ttl_seconds: int = 300
    max_uses: int = 1
    constraints: Optional[Dict] = None


class ToolExecutionRequest(BaseModel):
    tool_id: str
    parameters: Dict[str, Any]
    token_id: str
    trust_state: str = "unknown"


class TelemetryEventRequest(BaseModel):
    event_type: str
    severity: str
    data: Dict[str, Any]
    agent_id: Optional[str] = None
    hostname: Optional[str] = None
    signature: Optional[str] = None
    trace_id: Optional[str] = None


class AuditActionRequest(BaseModel):
    principal: str
    principal_trust_state: str
    action: str
    targets: List[str]
    case_id: Optional[str] = None
    evidence_refs: Optional[List[str]] = None
    policy_decision_hash: Optional[str] = None
    token_id: Optional[str] = None
    tool_id: Optional[str] = None
    constraints: Optional[Dict] = None


# =============================================================================
# IDENTITY & ATTESTATION ENDPOINTS
# =============================================================================

@router.post("/identity/attest")
async def submit_attestation(request: AttestationRequest):
    """
    Submit agent attestation for identity registration.
    Returns trust state and score.
    """
    from services.identity import identity_service, AttestationData
    
    # Create attestation data
    attestation = AttestationData(
        agent_version_hash=request.agent_version_hash,
        os_build_hash=request.os_build_hash,
        secure_boot=request.secure_boot,
        tpm_available=request.tpm_available,
        key_isolated=request.key_isolated,
        posture_score=request.posture_score,
        timestamp=request.timestamp,
        nonce=request.nonce,
        signature=request.signature
    )
    
    # Register identity
    identity = identity_service.register_identity(
        agent_id=request.agent_id,
        hostname=request.hostname,
        os_type=request.os_type,
        cert_fingerprint=request.cert_fingerprint,
        attestation=attestation
    )
    
    return {
        "spiffe_id": identity.spiffe_id,
        "trust_state": identity.trust_state.value,
        "trust_score": identity.trust_score,
        "expires_at": identity.expires_at,
        "message": "Attestation accepted",
        "contract_version": ENTERPRISE_CONTROL_PLANE_CONTRACT_VERSION,
    }


@router.get("/identity/nonce")
async def get_attestation_nonce():
    """Get a one-time nonce for attestation"""
    from services.identity import identity_service
    
    nonce = identity_service.generate_nonce()
    return {"nonce": nonce, "valid_seconds": 60}


@router.get("/identity/{agent_id}")
async def get_identity(agent_id: str, current_user: dict = Depends(get_current_user)):
    """Get identity for an agent"""
    from services.identity import identity_service
    
    identity = identity_service.get_identity(agent_id)
    if not identity:
        raise HTTPException(status_code=404, detail="Identity not found")
    
    return {
        "spiffe_id": identity.spiffe_id,
        "agent_id": identity.agent_id,
        "hostname": identity.hostname,
        "trust_state": identity.trust_state.value,
        "trust_score": identity.trust_score,
        "expires_at": identity.expires_at
    }


@router.get("/identity")
async def list_identities(current_user: dict = Depends(get_current_user)):
    """List all registered identities"""
    from services.identity import identity_service
    
    return {"identities": identity_service.get_all_identities()}


@router.post("/identity/{agent_id}/quarantine")
async def quarantine_agent(
    agent_id: str, 
    reason: str = "Manual quarantine",
    current_user: dict = Depends(check_permission("write"))
):
    """Quarantine an agent"""
    from services.identity import identity_service
    
    success = identity_service.quarantine_agent(agent_id, reason)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return {"status": "quarantined", "agent_id": agent_id, "reason": reason}


# =============================================================================
# POLICY ENGINE ENDPOINTS
# =============================================================================

@router.post("/policy/evaluate")
async def evaluate_policy(request: PolicyEvaluationRequest):
    """
    Evaluate a policy decision.
    Returns permit/deny and constraints.
    """
    from services.policy_engine import policy_engine
    
    decision = policy_engine.evaluate(
        principal=request.principal,
        action=request.action,
        targets=request.targets,
        trust_state=request.trust_state,
        role=request.role,
        tool_id=request.tool_id,
        evidence_confidence=request.evidence_confidence,
        incident_mode=request.incident_mode
    )
    
    return {
        "decision_id": decision.decision_id,
        "permitted": decision.permitted,
        "approval_tier": decision.approval_tier.value,
        "denial_reason": decision.denial_reason,
        "allowed_scopes": decision.allowed_scopes,
        "rate_limit": decision.rate_limit,
        "blast_radius_cap": decision.blast_radius_cap,
        "ttl_seconds": decision.ttl_seconds,
        "decision_hash": decision.decision_hash,
        "contract_version": ENTERPRISE_CONTROL_PLANE_CONTRACT_VERSION,
    }


@router.post("/policy/approve/{decision_id}")
async def approve_decision(
    decision_id: str,
    current_user: dict = Depends(check_permission("write"))
):
    """Approve a pending policy decision"""
    from services.policy_engine import policy_engine
    
    approver = current_user.get("email", "unknown")
    success, message = policy_engine.approve(decision_id, approver)
    
    return {"success": success, "message": message}


@router.post("/policy/deny/{decision_id}")
async def deny_decision(
    decision_id: str,
    reason: str = None,
    current_user: dict = Depends(check_permission("write"))
):
    """Deny a pending policy decision"""
    from services.policy_engine import policy_engine
    
    denier = current_user.get("email", "unknown")
    success = policy_engine.deny(decision_id, denier, reason)
    
    return {"success": success}


@router.get("/policy/pending")
async def get_pending_approvals(current_user: dict = Depends(get_current_user)):
    """Get pending policy approvals"""
    from services.policy_engine import policy_engine
    
    return {"pending": policy_engine.get_pending_approvals()}


@router.get("/policy/status")
async def get_policy_status(current_user: dict = Depends(get_current_user)):
    """Get policy engine status"""
    from services.policy_engine import policy_engine
    
    return policy_engine.get_policy_status()


# =============================================================================
# TOKEN BROKER ENDPOINTS
# =============================================================================

@router.post("/token/issue")
async def issue_token(
    request: TokenRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Issue a capability token"""
    from services.token_broker import token_broker
    
    try:
        token = token_broker.issue_token(
            principal=request.principal,
            principal_identity=request.principal_identity,
            action=request.action,
            targets=request.targets,
            tool_id=request.tool_id,
            ttl_seconds=request.ttl_seconds,
            max_uses=request.max_uses,
            constraints=request.constraints
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    
    return {
        "token_id": token.token_id,
        "expires_at": token.expires_at,
        "max_uses": token.max_uses,
        "message": "Token issued",
        "contract_version": ENTERPRISE_CONTROL_PLANE_CONTRACT_VERSION,
    }


@router.post("/token/validate")
async def validate_token(
    token_id: str,
    principal: str,
    principal_identity: str,
    action: str,
    target: str
):
    """Validate a capability token"""
    from services.token_broker import token_broker
    
    valid, message = token_broker.validate_token(
        token_id=token_id,
        principal=principal,
        principal_identity=principal_identity,
        action=action,
        target=target
    )
    
    return {"valid": valid, "message": message}


@router.post("/token/revoke/{token_id}")
async def revoke_token(
    token_id: str,
    current_user: dict = Depends(check_permission("write"))
):
    """Revoke a token"""
    from services.token_broker import token_broker
    
    success = token_broker.revoke_token(token_id)
    return {"success": success}


@router.post("/token/revoke-principal/{principal}")
async def revoke_principal_tokens(
    principal: str,
    current_user: dict = Depends(check_permission("write"))
):
    """Revoke all tokens for a principal"""
    from services.token_broker import token_broker
    
    count = token_broker.revoke_tokens_for_principal(principal)
    return {"revoked_count": count}


@router.get("/token/active")
async def get_active_tokens(
    principal: str = None,
    current_user: dict = Depends(get_current_user)
):
    """Get active tokens"""
    from services.token_broker import token_broker
    
    return {"tokens": token_broker.get_active_tokens(principal)}


@router.get("/token/status")
async def get_broker_status(current_user: dict = Depends(get_current_user)):
    """Get token broker status"""
    from services.token_broker import token_broker
    
    return token_broker.get_broker_status()


# =============================================================================
# CLI TOOL GATEWAY ENDPOINTS
# =============================================================================

@router.get("/tools")
async def list_tools(current_user: dict = Depends(get_current_user)):
    """List available tools"""
    from services.tool_gateway import tool_gateway
    
    return {"tools": tool_gateway.list_tools()}


@router.get("/tools/status")
async def get_gateway_status(current_user: dict = Depends(get_current_user)):
    """Get tool gateway status"""
    from services.tool_gateway import tool_gateway
    
    return tool_gateway.get_gateway_status()


@router.get("/tools/history")
async def get_execution_history(
    principal: str = None,
    tool_id: str = None,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """Get tool execution history"""
    from services.tool_gateway import tool_gateway
    
    return {"executions": tool_gateway.get_execution_history(principal, tool_id, limit)}


@router.get("/tools/{tool_id}")
async def get_tool(tool_id: str, current_user: dict = Depends(get_current_user)):
    """Get tool definition"""
    from services.tool_gateway import tool_gateway
    
    tool = tool_gateway.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    return {
        "tool_id": tool.tool_id,
        "name": tool.name,
        "description": tool.description,
        "args_schema": tool.args_schema,
        "allowed_flags": tool.allowed_flags,
        "requires_approval": tool.requires_approval,
        "min_trust_state": tool.min_trust_state,
        "timeout_seconds": tool.timeout_seconds
    }


@router.post("/tools/execute")
async def execute_tool(
    request: ToolExecutionRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Execute a tool through the gateway"""
    from services.tool_gateway import tool_gateway
    
    principal = f"operator:{current_user.get('email', 'unknown')}"
    
    execution = tool_gateway.execute(
        tool_id=request.tool_id,
        parameters=request.parameters,
        principal=principal,
        token_id=request.token_id,
        trust_state=request.trust_state
    )
    
    return {
        "execution_id": execution.execution_id,
        "status": execution.status,
        "exit_code": execution.exit_code,
        "stdout": execution.stdout,
        "stderr": execution.stderr,
        "duration_ms": execution.duration_ms,
        "contract_version": ENTERPRISE_CONTROL_PLANE_CONTRACT_VERSION,
    }


# =============================================================================
# TAMPER-EVIDENT TELEMETRY ENDPOINTS
# =============================================================================

@router.post("/telemetry/event")
async def ingest_event(request: TelemetryEventRequest):
    """Ingest a telemetry event into the tamper-evident chain"""
    from services.telemetry_chain import tamper_evident_telemetry
    
    event = tamper_evident_telemetry.ingest_event(
        event_type=request.event_type,
        severity=request.severity,
        data=request.data,
        agent_id=request.agent_id,
        hostname=request.hostname,
        signature=request.signature,
        trace_id=request.trace_id
    )
    
    return {
        "event_id": event.event_id,
        "event_hash": event.event_hash,
        "prev_hash": event.prev_hash,
        "trace_id": event.trace_id,
        "contract_version": ENTERPRISE_CONTROL_PLANE_CONTRACT_VERSION,
    }


@router.post("/telemetry/audit")
async def record_audit_action(
    request: AuditActionRequest,
    current_user: dict = Depends(check_permission("write"))
):
    """Record an action in the audit chain"""
    from services.telemetry_chain import tamper_evident_telemetry
    
    record = tamper_evident_telemetry.record_action(
        principal=request.principal,
        principal_trust_state=request.principal_trust_state,
        action=request.action,
        targets=request.targets,
        case_id=request.case_id,
        evidence_refs=request.evidence_refs,
        policy_decision_id=request.policy_decision_hash,
        token_id=request.token_id,
        tool_id=request.tool_id,
        constraints=request.constraints
    )
    
    return {
        "record_id": record.record_id,
        "record_hash": record.record_hash,
        "contract_version": ENTERPRISE_CONTROL_PLANE_CONTRACT_VERSION,
    }


@router.get("/telemetry/events")
async def query_events(
    event_type: str = None,
    agent_id: str = None,
    severity: str = None,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """Query telemetry events"""
    from services.telemetry_chain import tamper_evident_telemetry
    
    return {"events": tamper_evident_telemetry.get_events(event_type, agent_id, severity, limit)}


@router.get("/telemetry/audit")
async def query_audit_trail(
    principal: str = None,
    action: str = None,
    case_id: str = None,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """Query audit trail"""
    from services.telemetry_chain import tamper_evident_telemetry
    
    return {"records": tamper_evident_telemetry.get_audit_trail(principal, action, case_id, limit)}


@router.get("/telemetry/verify")
async def verify_chain_integrity(current_user: dict = Depends(get_current_user)):
    """Verify chain integrity"""
    from services.telemetry_chain import tamper_evident_telemetry
    
    valid, message = tamper_evident_telemetry.verify_chain_integrity()
    status = tamper_evident_telemetry.get_chain_status()
    
    return {
        "integrity_verified": valid,
        "message": message,
        **status
    }


# =============================================================================
# ENTERPRISE DASHBOARD
# =============================================================================

@router.get("/status")
async def get_enterprise_status(current_user: dict = Depends(get_current_user)):
    """Get overall enterprise security status"""
    from services.identity import identity_service
    from services.policy_engine import policy_engine
    from services.token_broker import token_broker
    from services.tool_gateway import tool_gateway
    from services.telemetry_chain import tamper_evident_telemetry

    trust_states: Dict[str, int] = {}
    for identity in identity_service.identities.values():
        trust_state = getattr(identity, "trust_state", "unknown")
        trust_state_key = getattr(trust_state, "value", str(trust_state))
        trust_states[trust_state_key] = trust_states.get(trust_state_key, 0) + 1

    return {
        "identity": {
            "registered_agents": len(identity_service.identities),
            "trust_states": trust_states
        },
        "policy": policy_engine.get_policy_status(),
        "tokens": token_broker.get_broker_status(),
        "tools": tool_gateway.get_gateway_status(),
        "telemetry": tamper_evident_telemetry.get_chain_status()
    }
