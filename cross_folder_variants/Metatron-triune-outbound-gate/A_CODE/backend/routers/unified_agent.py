from __future__ import annotations
"""
Unified Agent Router - Metatron Integration
============================================
API endpoints for the Metatron/Seraph unified agent management system.
Provides cross-platform agent registration, heartbeat, deployment, and monitoring.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, WebSocket, WebSocketDisconnect, Request, Header
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
import secrets
import logging
import asyncio
import hmac
import hashlib
import json
import os
import socket
import ipaddress
from pathlib import Path


class EDMHitTelemetryModel(BaseModel):
    """EDM match telemetry emitted by endpoint agents."""
    dataset_id: str
    record_id: Optional[str] = None
    fingerprint: str
    host: Optional[str] = None
    process: Optional[str] = None
    file_path_masked: Optional[str] = None
    source: Optional[str] = None
    timestamp: Optional[str] = None
    # Additional field for telemetry
    additional_info: Optional[str] = None

from .dependencies import get_current_user, check_permission, get_db


class _DBProxy:
    """Late-binding DB accessor.

    `routers.dependencies.set_database()` runs during backend startup. This router
    must not import a snapshot of `dependencies.db` at import time, otherwise it
    stays `None` forever and all endpoints 500.
    """

    def _resolve(self):
        resolved = get_db()
        if resolved is None:
            raise HTTPException(status_code=503, detail="database_unavailable")
        return resolved

    def __getattr__(self, name: str):
        return getattr(self._resolve(), name)

    def __getitem__(self, key: str):
        return self._resolve()[key]


db = _DBProxy()

logger = logging.getLogger('seraph.unified_agent')

router = APIRouter(prefix="/unified", tags=["Unified Agent"])
ALERT_STATUSES = {"unacknowledged", "acknowledged"}


def _serialize_agent_command_for_delivery(command_doc: Dict[str, Any]) -> Dict[str, Any]:
    decision_context = {
        "decision_id": command_doc.get("decision_id"),
        "queue_id": command_doc.get("queue_id"),
    }
    decision_context = {key: value for key, value in decision_context.items() if value}
    return {
        "command_id": command_doc["command_id"],
        "command_type": command_doc["command_type"],
        "parameters": command_doc.get("parameters", {}),
        "priority": command_doc.get("priority", "normal"),
        "timestamp": command_doc.get("timestamp") or command_doc.get("created_at"),
        "decision_context": decision_context,
        "authority_context": {
            "principal": command_doc.get("issued_by") or command_doc.get("created_by") or "system",
            "capability": command_doc.get("command_type"),
            "requires_decision_context": bool(decision_context),
        },
    }


def _normalize_boundary_crossing_outcome(raw_outcome: Any) -> str:
    normalized = str(raw_outcome or "").strip().lower()
    if normalized in {"deny", "denied", "blocked", "reject", "rejected"}:
        return "denied"
    if normalized in {"queue", "queued", "throttle", "throttled", "pending"}:
        return "queued"
    if normalized in {"allow", "allowed", "success", "completed"}:
        return "allowed"
    return "queued"


def _extract_boundary_crossing_from_command_result(
    *,
    agent_id: str,
    command_id: str,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    fortress = result.get("fortress") if isinstance(result, dict) else {}
    fortress = fortress if isinstance(fortress, dict) else {}
    boundary = fortress.get("boundary") if isinstance(fortress.get("boundary"), dict) else {}
    gate = fortress.get("gate") if isinstance(fortress.get("gate"), dict) else {}
    post = fortress.get("post") if isinstance(fortress.get("post"), dict) else {}
    beacon = post.get("beacon") or result.get("beacon") or {}
    outcome = _normalize_boundary_crossing_outcome(
        post.get("gate_outcome") or gate.get("decision") or result.get("outcome")
    )
    beacon_state = str((beacon or {}).get("state") or "").strip().lower()
    return {
        "event_type": "boundary_crossing",
        "trigger_triune": outcome in {"denied", "queued"} or beacon_state in {"red", "amber"},
        "payload": {
            "agent_id": agent_id,
            "command_id": command_id,
            "crossing_outcome": outcome,
            "decision_context": boundary.get("decision_context") or result.get("decision_context") or {},
            "beacon": beacon,
        },
    }


def _alert_transition_entry(
    from_status: Optional[str],
    to_status: str,
    actor: str,
    reason: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    entry = {
        "from_status": from_status,
        "to_status": to_status,
        "actor": actor,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if metadata:
        entry["metadata"] = metadata
    return entry


def _build_unified_alert_doc(
    *,
    alert_id: str,
    agent_id: str,
    severity: str,
    category: str,
    message: str,
    details: Optional[Dict[str, Any]],
    mitre_technique: Optional[str],
    actor: str,
    reason: str,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    return {
        "alert_id": alert_id,
        "agent_id": agent_id,
        "severity": severity,
        "category": category,
        "message": message,
        "details": details or {},
        "mitre_technique": mitre_technique,
        "timestamp": ts,
        "acknowledged": False,
        "status": "unacknowledged",
        "updated_at": ts,
        "state_version": 1,
        "state_transition_log": [
            _alert_transition_entry(
                from_status=None,
                to_status="unacknowledged",
                actor=actor,
                reason=reason,
            )
        ],
    }


async def _ensure_unified_alert_state_fields(
    alert_id: str,
    *,
    actor: str,
    reason: str,
) -> Dict[str, Any]:
    alert = await db.unified_alerts.find_one({"alert_id": alert_id}, {"_id": 0})
    if not alert:
        return {}

    if alert.get("state_version") is not None and alert.get("state_transition_log") is not None:
        return alert

    current_status = str(alert.get("status") or ("acknowledged" if alert.get("acknowledged") else "unacknowledged"))
    if current_status not in ALERT_STATUSES:
        current_status = "acknowledged" if alert.get("acknowledged") else "unacknowledged"

    bootstrap = {
        "status": current_status,
        "state_version": int(alert.get("state_version") or 1),
        "state_transition_log": alert.get("state_transition_log")
        or [
            _alert_transition_entry(
                from_status=None,
                to_status=current_status,
                actor=actor,
                reason=reason,
            )
        ],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.unified_alerts.update_one({"alert_id": alert_id}, {"$set": bootstrap})
    return await db.unified_alerts.find_one({"alert_id": alert_id}, {"_id": 0}) or {}


# ============================================================
# AGENT SECURITY CONFIGURATION
# ============================================================

def _get_agent_secret() -> str:
    """Get or generate the agent enrollment secret"""
    secret = os.environ.get('SERAPH_AGENT_SECRET')
    if not secret:
        # Generate a secret for development - in production, set SERAPH_AGENT_SECRET
        secret = 'dev-agent-secret-change-in-production'
        logger.warning("SERAPH_AGENT_SECRET not set. Using default development secret.")
    return secret

AGENT_SECRET = _get_agent_secret()
EDM_DATASET_COLLECTION = "edm_dataset_versions"
EDM_HITS_COLLECTION = "agent_edm_telemetry"
EDM_ROLLOUT_COLLECTION = "edm_rollouts"
_edm_indexes_ready = False
EDM_CONTROL_PLANE_CONTRACT_VERSION = "2026-03-07.1"
UNIFIED_DEPLOYMENT_TERMINAL_STATUSES = {"completed", "failed"}
ENROLLMENT_COLLECTION = "unified_agent_enrollments"
ENROLLMENT_EVENT_COLLECTION = "unified_agent_enrollment_events"

# EDM publish-time quality gates
EDM_MAX_RECORDS_PER_PUBLISH = max(1000, int(os.environ.get("EDM_MAX_RECORDS_PER_PUBLISH", "20000")))
EDM_MIN_CANONICAL_COVERAGE = min(max(float(os.environ.get("EDM_MIN_CANONICAL_COVERAGE", "0.95")), 0.0), 1.0)
EDM_MIN_ALLOWED_MIN_CONFIDENCE = min(max(float(os.environ.get("EDM_MIN_ALLOWED_MIN_CONFIDENCE", "0.85")), 0.0), 1.0)
EDM_ALLOWED_CANDIDATE_TYPES = {
    "line",
    "delimited_bundle",
    "delimited_window_4",
    "delimited_window_3",
    "delimited_window_2",
}

# Trusted networks that agents can connect from (CIDR notation)
TRUSTED_NETWORKS = [
    "127.0.0.0/8",      # Localhost
    "10.0.0.0/8",       # Private Class A
    "172.16.0.0/12",    # Private Class B
    "192.168.0.0/16",   # Private Class C
    "::1/128",          # IPv6 localhost
    "fe80::/10",        # IPv6 link-local
]

# Server's own IPs - populated at startup
SERVER_IPS: set = set()

def _populate_server_ips():
    """Populate server's own IP addresses to prevent self-targeting"""
    global SERVER_IPS
    try:
        hostname = socket.gethostname()
        # Get all IPs for this host
        SERVER_IPS.add(socket.gethostbyname(hostname))
        for info in socket.getaddrinfo(hostname, None):
            SERVER_IPS.add(info[4][0])
        # Add common local addresses
        SERVER_IPS.update(['127.0.0.1', 'localhost', '::1', '0.0.0.0'])
        logger.info(f"Server IPs populated: {SERVER_IPS}")
    except Exception as e:
        logger.warning(f"Failed to populate server IPs: {e}")
        SERVER_IPS = {'127.0.0.1', 'localhost', '::1'}

_populate_server_ips()


def _is_ip_trusted(ip_address: str) -> bool:
    """Check if an IP is from a trusted network"""
    try:
        ip = ipaddress.ip_address(ip_address)
        for network in TRUSTED_NETWORKS:
            if ip in ipaddress.ip_network(network, strict=False):
                return True
        return False
    except ValueError:
        return False


def _generate_agent_token(agent_id: str) -> str:
    """Generate an HMAC-based token for agent authentication"""
    timestamp = str(int(datetime.now(timezone.utc).timestamp()))
    message = f"{agent_id}:{timestamp}"
    signature = hmac.new(
        AGENT_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"{timestamp}:{signature}"


def _infer_public_base_url(request: Request, server_url: Optional[str] = None) -> str:
    """Resolve a browser/device reachable base URL for installers."""
    explicit = (server_url or os.environ.get("SERAPH_PUBLIC_URL") or os.environ.get("PUBLIC_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "localhost:8000"
    forwarded_proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
    # Public tunnel hosts are HTTPS even when proxy headers are incomplete.
    if forwarded_host and ("ngrok-free.dev" in forwarded_host or "ngrok.io" in forwarded_host or "seraphai.com" in forwarded_host):
        forwarded_proto = "https"
    return f"{forwarded_proto}://{forwarded_host}".rstrip("/")


def _agent_source_dir() -> Path:
    """Find the checked-out unified_agent directory in container and local dev layouts."""
    candidates = [
        Path(os.environ.get("UNIFIED_AGENT_DIR", "")),
        Path("/app/unified_agent"),
        Path(__file__).resolve().parents[2] / "unified_agent",
        Path.cwd() / "unified_agent",
    ]
    for candidate in candidates:
        if candidate and (candidate / "core").exists():
            return candidate
    raise HTTPException(status_code=503, detail="Unified agent source directory not found")


def _artifact_paths(*relative_parts: str) -> List[Path]:
    root = Path(__file__).resolve().parents[2]
    source = _agent_source_dir()
    return [
        source.joinpath(*relative_parts),
        root.joinpath("unified_agent", *relative_parts),
        Path("/app/unified_agent").joinpath(*relative_parts),
    ]


async def _record_enrollment_event(event: Dict[str, Any]) -> None:
    payload = {
        "event_id": event.get("event_id") or f"enroll-{secrets.token_hex(8)}",
        "timestamp": event.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        **event,
    }
    try:
        await db[ENROLLMENT_EVENT_COLLECTION].insert_one(payload)
    except Exception as exc:
        logger.warning("Failed to persist enrollment event: %s", exc)


def _sync_enrollment_to_email_and_mobile(name: str, email: str, platform: str, device_label: str, device_id: str) -> Dict[str, bool]:
    """Best-effort propagate pre-enrollment into email protection, mobile security, and MDM surfaces."""
    results = {"email": False, "mobile": False, "mdm": False}

    # --- Email Protection: add user as protected executive for ALL platforms ---
    try:
        from email_protection import email_protection_service
        email_key = email.strip().lower()
        if email_key:
            existing_exec = email_protection_service.protected_executives.get(email_key)
            if not existing_exec:
                email_protection_service.add_protected_executive(email_key, name, device_label or platform)
            results["email"] = True
    except Exception as exc:
        logger.debug("Email protection sync skipped: %s", exc)

    # --- Mobile Security: register Android / iOS devices in mobile surface ---
    try:
        if platform in {"android", "ios"}:
            from mobile_security import mobile_security_service, DevicePlatform
            try:
                mobile_platform = DevicePlatform(platform)
            except Exception:
                mobile_platform = None
            if mobile_platform is not None:
                user_device = mobile_security_service.register_device(
                    device_name=device_label or f"{platform}-{device_id}",
                    platform=mobile_platform.value if hasattr(mobile_platform, "value") else str(mobile_platform),
                    os_version="unknown",
                    model=device_label or platform,
                    serial_number=device_id,
                    user_id=email.strip().lower(),
                    user_email=email.strip().lower(),
                    imei="",
                )
                mobile_security_service.update_device_status(
                    device_id=user_device.device_id,
                    mdm_enrolled=True,
                    has_passcode=True,
                    is_encrypted=(platform == "ios"),
                    network_info={"source": "unified_enrollment"},
                )
                results["mobile"] = True
    except Exception as exc:
        logger.debug("Mobile security sync skipped: %s", exc)

    # --- MDM: register desktop / server platforms directly into MDM device inventory ---
    try:
        if platform in {"windows", "linux", "macos", "docker", "unknown"}:
            from mdm_connectors import mdm_manager, MDMDevice, MDMPlatform, ComplianceState
            now_iso = datetime.now(timezone.utc).isoformat()
            mdm_dev = MDMDevice(
                device_id=device_id,
                mdm_device_id=device_id,
                platform=platform,
                device_name=device_label or f"{platform}-{device_id}",
                model=platform,
                os_version="unknown",
                serial_number=device_id,
                imei="",
                user_principal_name=email.strip().lower(),
                user_display_name=name,
                enrollment_date=now_iso,
                last_sync=now_iso,
                compliance_state=ComplianceState.UNKNOWN,
                is_managed=True,
                is_supervised=False,
                is_encrypted=(platform != "docker"),
                is_jailbroken=False,
                management_agent_version="seraph-enrollment/1.0",
                mdm_platform=MDMPlatform.INTUNE,
            )
            mdm_manager.all_devices[device_id] = mdm_dev
            results["mdm"] = True
    except Exception as exc:
        logger.debug("MDM desktop sync skipped: %s", exc)

    return results


def _verify_agent_token(agent_id: str, token: str) -> bool:
    """Verify an agent's authentication token"""
    try:
        parts = token.split(':')
        if len(parts) != 2:
            return False
        
        timestamp, provided_signature = parts
        # Token expiration: 24 hours
        token_time = int(timestamp)
        current_time = int(datetime.now(timezone.utc).timestamp())
        
        if current_time - token_time > 86400:  # 24 hours
            logger.warning(f"Expired token for agent {agent_id}")
            return False
        
        # Verify signature
        message = f"{agent_id}:{timestamp}"
        expected_signature = hmac.new(
            AGENT_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(provided_signature, expected_signature)
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        return False


async def verify_agent_auth(
    request: Request,
    x_agent_id: Optional[str] = Header(None),
    x_agent_token: Optional[str] = Header(None),
    x_enrollment_key: Optional[str] = Header(None)
) -> Dict:
    """Dependency to verify agent authentication"""
    client_ip = request.client.host if request.client else "unknown"
    
    # Check if IP is trusted (allows initial enrollment from private networks)
    is_trusted_network = _is_ip_trusted(client_ip)
    
    # For registration with enrollment key (first-time setup)
    if x_enrollment_key:
        if hmac.compare_digest(x_enrollment_key, AGENT_SECRET):
            return {"type": "enrollment", "ip": client_ip, "trusted": is_trusted_network}
        raise HTTPException(status_code=403, detail="Invalid enrollment key")
    
    # For ongoing agent authentication
    if x_agent_id and x_agent_token:
        if _verify_agent_token(x_agent_id, x_agent_token):
            # Also verify agent is registered
            agent = await db.unified_agents.find_one({"agent_id": x_agent_id})
            if agent:
                return {
                    "type": "authenticated",
                    "agent_id": x_agent_id,
                    "ip": client_ip,
                    "trusted": is_trusted_network
                }
            raise HTTPException(status_code=404, detail="Agent not registered")
        raise HTTPException(status_code=401, detail="Invalid agent token")
    
    # Allow from trusted networks for backwards compatibility (with warning)
    if is_trusted_network:
        logger.warning(f"Agent request from {client_ip} without auth - allowed from trusted network")
        return {"type": "trusted_network", "ip": client_ip, "trusted": True}
    
    raise HTTPException(status_code=401, detail="Agent authentication required")


# ============================================================
# PYDANTIC MODELS
# ============================================================

class AgentRegistrationModel(BaseModel):
    agent_id: str
    platform: str  # windows, linux, macos, android, ios
    hostname: str
    ip_address: str
    version: str
    capabilities: List[str] = []
    config: Optional[Dict[str, Any]] = None
    local_ui_url: Optional[str] = None  # URL of the agent's built-in local web UI
    # Optional workload identity anchors (for constitutional→kernel friend/foe)
    node_id: Optional[str] = None
    executable_path: Optional[str] = None
    workload_hash: Optional[str] = None


class EnrollmentRegistrationModel(BaseModel):
    name: str
    email: str
    device_label: Optional[str] = ""
    platform: Optional[str] = "unknown"


# Monitor-specific telemetry models
class MonitorTelemetry(BaseModel):
    """Base telemetry from a monitor"""
    last_run: Optional[str] = None
    threats_found: int = 0
    scan_duration_ms: Optional[int] = None


class RegistryMonitorTelemetry(MonitorTelemetry):
    """Registry/Startup persistence monitoring"""
    persistence_locations: int = 0
    changes_detected: int = 0
    recent_changes: List[Dict] = []


class ProcessTreeMonitorTelemetry(MonitorTelemetry):
    """Parent-child process chain anomalies"""
    processes_analyzed: int = 0
    suspicious_chains: int = 0
    chain_details: List[Dict] = []


class LOLBinMonitorTelemetry(MonitorTelemetry):
    """Living-off-the-land binary abuse"""
    lolbins_checked: int = 0
    detections: int = 0
    detection_details: List[Dict] = []


class CodeSigningMonitorTelemetry(MonitorTelemetry):
    """Executable signature verification"""
    executables_checked: int = 0
    unsigned_count: int = 0
    unsigned_executables: List[Dict] = []


class DNSMonitorTelemetry(MonitorTelemetry):
    """DNS anomaly detection"""
    queries_analyzed: int = 0
    suspicious_count: int = 0
    suspicious_queries: List[Dict] = []


class MemoryScannerTelemetry(MonitorTelemetry):
    """Process injection/memory scanning"""
    processes_scanned: int = 0
    suspicious_found: int = 0
    injection_details: List[Dict] = []


class ApplicationWhitelistTelemetry(MonitorTelemetry):
    """Application whitelist violations"""
    processes_checked: int = 0
    violations: int = 0
    whitelist_size: int = 0
    violation_details: List[Dict] = []


class DLPMonitorTelemetry(MonitorTelemetry):
    """Data loss prevention"""
    clipboard_alerts: int = 0
    file_alerts: int = 0
    network_alerts: int = 0
    alert_details: List[Dict] = []


class VulnerabilityScannerTelemetry(MonitorTelemetry):
    """Software vulnerability scanning"""
    software_checked: int = 0
    vulnerabilities_found: int = 0
    vulnerable_software: List[Dict] = []


class AMSIMonitorTelemetry(MonitorTelemetry):
    """Windows AMSI integration"""
    amsi_available: bool = False
    scripts_scanned: int = 0
    detections: int = 0
    detection_details: List[Dict] = []


class MonitorsTelemetry(BaseModel):
    """Aggregated telemetry from all monitors"""
    registry: Optional[RegistryMonitorTelemetry] = None
    process_tree: Optional[ProcessTreeMonitorTelemetry] = None
    lolbin: Optional[LOLBinMonitorTelemetry] = None
    code_signing: Optional[CodeSigningMonitorTelemetry] = None
    dns: Optional[DNSMonitorTelemetry] = None
    memory: Optional[MemoryScannerTelemetry] = None
    whitelist: Optional[ApplicationWhitelistTelemetry] = None
    dlp: Optional[DLPMonitorTelemetry] = None
    vulnerability: Optional[VulnerabilityScannerTelemetry] = None
    amsi: Optional[AMSIMonitorTelemetry] = None


class AgentHeartbeatModel(BaseModel):
    agent_id: str
    status: str  # online, offline, degraded
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    disk_usage: Optional[float] = None
    threat_count: Optional[int] = None
    network_connections: Optional[int] = None
    alerts: List[Dict] = []
    telemetry: Optional[Dict] = None
    edm_hits: List[EDMHitTelemetryModel] = []
    # Structured monitor telemetry
    monitors: Optional[MonitorsTelemetry] = None
    local_ui_url: Optional[str] = None  # URL of the agent's built-in local web UI
    # Optional workload identity anchors (for constitutional→kernel friend/foe)
    node_id: Optional[str] = None
    executable_path: Optional[str] = None
    workload_hash: Optional[str] = None


class DeploymentRequestModel(BaseModel):
    target_platform: str
    target_ip: str
    agent_config: Optional[Dict] = None
    credentials: Optional[Dict] = None


class AgentCommandModel(BaseModel):
    # Standard: scan, remediate, update, restart, shutdown
    # AI Defense: throttle_cli, inject_latency, deploy_decoy, engage_tarpit, 
    #            capture_triage, capture_memory, kill_tree, tag_session, rotate_creds
    command_type: Optional[str] = None
    parameters: Dict[str, Any] = {}
    priority: str = "normal"  # low, normal, high, critical
    command: Optional[str] = None
    params: Optional[Dict[str, Any]] = None


class EDMDatasetCommandModel(BaseModel):
    """Payload for updating EDM datasets on agent(s)."""
    dataset: Dict[str, Any]
    priority: str = "high"


class EDMBulkTargetModel(BaseModel):
    """Targeting options for fleet EDM fanout commands."""
    online_only: bool = True
    platforms: Optional[List[str]] = None
    groups: Optional[List[str]] = None
    agent_ids: Optional[List[str]] = None
    limit: int = 500


class EDMBulkDatasetCommandModel(BaseModel):
    """Bulk dataset update payload for multi-agent EDM orchestration."""
    dataset: Dict[str, Any]
    priority: str = "high"
    targets: EDMBulkTargetModel = EDMBulkTargetModel()


class EDMDatasetVersionCreateModel(BaseModel):
    """Create a new EDM dataset version in source-of-truth registry."""
    dataset: Dict[str, Any]
    note: Optional[str] = None


class EDMDatasetPublishModel(BaseModel):
    """Publish a stored EDM dataset version to matching agents."""
    targets: EDMBulkTargetModel = EDMBulkTargetModel()
    priority: str = "high"


class EDMDatasetRollbackModel(BaseModel):
    """Rollback dataset by cloning a previous version into new head."""
    target_version: int
    note: Optional[str] = None
    publish: bool = True
    targets: EDMBulkTargetModel = EDMBulkTargetModel()
    priority: str = "high"


class EDMHitTelemetryModel(BaseModel):
    """EDM match telemetry emitted by endpoint agents."""
    dataset_id: str
    record_id: Optional[str] = None
    fingerprint: str
    host: Optional[str] = None
    process: Optional[str] = None
    file_path_masked: Optional[str] = None
    source: Optional[str] = None
    timestamp: Optional[str] = None
class AgentHeartbeatModel(BaseModel):
    agent_id: str
    status: str  # online, offline, degraded
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    disk_usage: Optional[float] = None
    threat_count: Optional[int] = None
    network_connections: Optional[int] = None
    alerts: List[Dict] = []
    telemetry: Optional[Dict] = None
    edm_hits: List[EDMHitTelemetryModel] = []
    # Structured monitor telemetry
    monitors: Optional[MonitorsTelemetry] = None
    local_ui_url: Optional[str] = None  # URL of the agent's built-in local web UI
    # Optional workload identity anchors (for constitutional→kernel friend/foe)
    node_id: Optional[str] = None
    executable_path: Optional[str] = None
    workload_hash: Optional[str] = None


AgentHeartbeatModel.model_rebuild()


class EDMRolloutPolicyModel(BaseModel):
    """Progressive rollout controls and anomaly guardrails."""
    stages: List[int] = [5, 25, 100]
    anomaly_spike_multiplier: float = 3.0
    anomaly_min_hits: int = 20
    evaluation_window_minutes: int = 15
    auto_rollback: bool = True


class EDMRolloutStartModel(BaseModel):
    """Start canary rollout for a specific EDM dataset version."""
    dataset_id: str
    target_version: int
    targets: EDMBulkTargetModel = EDMBulkTargetModel()
    priority: str = "high"
    policy: EDMRolloutPolicyModel = EDMRolloutPolicyModel()


class EDMRolloutRollbackModel(BaseModel):
    """Manual rollback controls for an active rollout."""
    rollback_version: Optional[int] = None
    reason: Optional[str] = None


class AlertModel(BaseModel):
    agent_id: str
    severity: str  # critical, high, medium, low
    category: str  # network, process, file, system
    message: str
    details: Optional[Dict] = None
    mitre_technique: Optional[str] = None


# ============================================================
# WEBSOCKET MANAGER
# ============================================================

class AgentConnectionManager:
    """Manage WebSocket connections for real-time agent communication"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.command_queues: Dict[str, List[Dict]] = {}
    
    async def connect(self, agent_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[agent_id] = websocket
        self.command_queues[agent_id] = []
        logger.info(f"Agent {agent_id} connected via WebSocket")
    
    def disconnect(self, agent_id: str):
        if agent_id in self.active_connections:
            del self.active_connections[agent_id]
        if agent_id in self.command_queues:
            del self.command_queues[agent_id]
        logger.info(f"Agent {agent_id} disconnected")
    
    async def send_command(self, agent_id: str, command: Dict):
        if agent_id in self.active_connections:
            await self.active_connections[agent_id].send_json(command)
            return True
        # Queue command for when agent reconnects
        if agent_id not in self.command_queues:
            self.command_queues[agent_id] = []
        self.command_queues[agent_id].append(command)
        return False
    
    async def broadcast(self, message: Dict):
        for connection in self.active_connections.values():
            try:
                await connection.send_json(message)
            except Exception:
                pass
    
    def get_queued_commands(self, agent_id: str) -> List[Dict]:
        commands = self.command_queues.get(agent_id, [])
        self.command_queues[agent_id] = []
        return commands
    
    def is_connected(self, agent_id: str) -> bool:
        return agent_id in self.active_connections


agent_ws_manager = AgentConnectionManager()


# ============================================================
# ENROLLMENT ENDPOINTS (CANONICAL :3000/:8000 SURFACE)
# ============================================================

@router.post("/enrollment/register")
async def register_enrollment_device(
    enrollment: EnrollmentRegistrationModel,
    request: Request,
    server_url: Optional[str] = None,
):
    """Public pre-enrollment used by the React enrollment page before agent install."""
    import re
    import urllib.parse

    name = enrollment.name.strip()[:80]
    email = enrollment.email.strip()[:120]
    platform = (enrollment.platform or "unknown").strip().lower()[:32]
    device_label = (enrollment.device_label or platform or "unknown").strip()[:80]

    if not name or not email:
        raise HTTPException(status_code=400, detail="Name and email are required")
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        raise HTTPException(status_code=400, detail="Invalid email address")

    base_url = _infer_public_base_url(request, server_url)
    backend_url = os.environ.get("SERAPH_BACKEND_URL", "").strip().rstrip("/") or base_url
    enrollment_key = os.environ.get("SERAPH_ENROLLMENT_KEY") or os.environ.get("ENROLLMENT_KEY") or AGENT_SECRET
    encoded_key = urllib.parse.quote(enrollment_key, safe="")
    device_id = f"enroll-{secrets.token_hex(4)}"
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "device_id": device_id,
        "name": name,
        "email": email,
        "device_label": device_label,
        "platform": platform,
        "ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", ""),
        "status": "installer_issued",
        "enrolled_at": now,
        "updated_at": now,
    }
    await db[ENROLLMENT_COLLECTION].insert_one(doc)
    sync_results = _sync_enrollment_to_email_and_mobile(name, email, platform, device_label, device_id)
    await _record_enrollment_event({
        "event_type": "device_pre_enrolled",
        "severity": "info",
        "device_id": device_id,
        "platform": platform,
        "message": f"Enrollment registered for {device_label} ({platform})",
        "details": {
            "email": email,
            "name": name,
            "source": "react_enrollment",
            "synced_email_protection": sync_results.get("email", False),
            "synced_mobile_security": sync_results.get("mobile", False),
            "synced_mdm": sync_results.get("mdm", False),
        },
    })

    install = {
        "linux": {
            "cmd": f"curl -fsSL {backend_url}/api/unified/agent/install-script?server_url={urllib.parse.quote(backend_url, safe='')}&enrollment_key={encoded_key} | sudo bash",
            "download_url": f"{backend_url}/api/unified/agent/download",
            "requirements": ["Linux with systemd", "sudo/root", "python3", "curl", "wireguard-tools for VPN"],
        },
        "macos": {
            "cmd": f"curl -fsSL {backend_url}/api/unified/agent/install-macos?server_url={urllib.parse.quote(backend_url, safe='')}&enrollment_key={encoded_key} | bash",
            "download_url": f"{backend_url}/api/unified/agent/download",
            "requirements": ["macOS", "python3 or Homebrew", "curl", "WireGuard app/tools for VPN"],
        },
        "windows": {
            "cmd": f"powershell -ExecutionPolicy Bypass -Command \"Invoke-RestMethod -Uri '{backend_url}/api/unified/agent/install-windows?server_url={urllib.parse.quote(backend_url, safe='')}&enrollment_key={encoded_key}' -Headers @{{'ngrok-skip-browser-warning'='1'}} | Invoke-Expression\"",
            "download_url": f"{backend_url}/api/unified/agent/download/windows",
            "requirements": ["Windows 10/11 or Server", "Administrator PowerShell", "Python 3", "WireGuard for Windows for VPN"],
        },
        "android": {
            "apk_url": f"{backend_url}/api/unified/agent/download/android",
            "termux_cmd": f"curl -fsSL {backend_url}/api/unified/agent/install-android?server_url={urllib.parse.quote(backend_url, safe='')}&enrollment_key={encoded_key} | bash",
            "requirements": ["Termux from F-Droid for the canonical port-5000 dashboard", "Termux:Boot for autostart", "WireGuard app for VPN", "APK is a native preview shell and does not match the canonical dashboard"],
        },
        "ios": {
            "download_url": f"{backend_url}/api/unified/agent/install-ios?format=py&server_url={urllib.parse.quote(backend_url, safe='')}&enrollment_key={encoded_key}",
            "message": "Open the downloaded .py file in Pythonista 3 and tap Run. No extra installs needed.",
            "requirements": [
                "Pythonista 3 (App Store) - bundles requests + keychain modules",
                "Or TestFlight build of the native SwiftUI app",
                "Apple VPN profile for MDM-enforced VPN",
            ],
        },
        "docker": {
            "cmd": (
                "docker run -d --name seraph-agent --restart unless-stopped "
                f"-e BACKEND_URL={base_url} -e SERAPH_ENROLLMENT_KEY={enrollment_key} "
                f"-e AGENT_HOSTNAME={device_label!r} -p 5000:5000 "
                f"{os.environ.get('SERAPH_DOCKER_IMAGE', 'metatron-triune-outbound-gate-unified-agent:latest')}"
            ),
            "requirements": ["Docker engine 20.10+", "Outbound HTTPS to the Seraph backend"],
        },
    }
    return {
        "success": True,
        "device_id": device_id,
        "platform": platform,
        "install": install,
        "dashboard_url": f"{base_url}/unified-agent",
        "email": email,
        "name": name,
        "device_label": device_label,
        "synced": sync_results,
    }


@router.get("/enrollment/events")
async def get_enrollment_events(limit: int = 50, current_user: dict = Depends(get_current_user)):
    safe_limit = max(1, min(limit, 200))
    events = await db[ENROLLMENT_EVENT_COLLECTION].find({}, {"_id": 0}).sort("timestamp", -1).to_list(safe_limit)
    return {"events": events, "count": len(events)}


@router.get("/enrollment/devices")
async def get_enrollment_devices(limit: int = 100, current_user: dict = Depends(get_current_user)):
    safe_limit = max(1, min(limit, 500))
    devices = await db[ENROLLMENT_COLLECTION].find({}, {"_id": 0}).sort("enrolled_at", -1).to_list(safe_limit)
    return {"devices": devices, "count": len(devices)}


# ============================================================
# AGENT MANAGEMENT ENDPOINTS
# ============================================================

@router.post("/agents/register")
async def register_agent(
    agent: AgentRegistrationModel,
    request: Request,
    auth: Dict = Depends(verify_agent_auth)
):
    """Register a new unified agent (requires enrollment key or trusted network)"""
    
    # Log authentication method
    logger.info(f"Agent registration attempt: {agent.agent_id} via {auth['type']} from {auth['ip']}")
    
    # Check if already exists
    existing = await db.unified_agents.find_one({"agent_id": agent.agent_id})
    
    # Generate auth token for the agent
    agent_token = _generate_agent_token(agent.agent_id)
    
    if existing:
        # Update existing agent
        await db.unified_agents.update_one(
            {"agent_id": agent.agent_id},
            {"$set": {
                "platform": agent.platform,
                "hostname": agent.hostname,
                "ip_address": agent.ip_address,
                "version": agent.version,
                "capabilities": agent.capabilities,
                "config": agent.config,
                "status": "online",
                "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                **({"local_ui_url": agent.local_ui_url} if agent.local_ui_url else {}),
                **({"node_id": agent.node_id} if agent.node_id else {}),
                **({"executable_path": agent.executable_path} if agent.executable_path else {}),
                **({"workload_hash": agent.workload_hash} if agent.workload_hash else {}),
            }}
        )
        logger.info(f"Agent re-registered: {agent.agent_id} ({agent.platform})")
        await _record_enrollment_event({
            "event_type": "agent_reregistered",
            "severity": "info",
            "agent_id": agent.agent_id,
            "platform": agent.platform,
            "message": f"Agent re-registered: {agent.hostname} ({agent.platform})",
            "details": {"ip_address": agent.ip_address, "auth_type": auth["type"]},
        })

        # Best-effort coronation into the Arda Fabric registry.
        try:
            from services.arda_fabric import get_arda_fabric
            fabric = get_arda_fabric()
            fabric.ensure_subject(
                agent.node_id or agent.agent_id,
                workload_hash=agent.workload_hash,
                executable_path=agent.executable_path,
            )
        except Exception as e:
            logger.debug(f"Fabric coronation skipped on re-register: {e}")

        return {
            "status": "updated",
            "agent_id": agent.agent_id,
            "auth_token": agent_token,
            "server_ips": list(SERVER_IPS),
            "message": "Store auth_token for future requests via X-Agent-Token header"
        }
    
    # Create new agent
    agent_doc = {
        "agent_id": agent.agent_id,
        "platform": agent.platform,
        "hostname": agent.hostname,
        "ip_address": agent.ip_address,
        "version": agent.version,
        "capabilities": agent.capabilities,
        "config": agent.config or {},
        "status": "online",
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        "threat_count": 0,
        "alerts_count": 0,
        "enrolled_from_ip": auth['ip'],
        "enrollment_type": auth['type'],
        "local_ui_url": agent.local_ui_url or "",
        "node_id": agent.node_id or agent.agent_id,
        "executable_path": agent.executable_path,
        "workload_hash": agent.workload_hash,
    }
    
    await db.unified_agents.insert_one(agent_doc)
    logger.info(f"New agent registered: {agent.agent_id} ({agent.platform}) from {agent.ip_address}")
    await _record_enrollment_event({
        "event_type": "agent_registered",
        "severity": "success",
        "agent_id": agent.agent_id,
        "platform": agent.platform,
        "message": f"New agent registered: {agent.hostname} ({agent.platform})",
        "details": {"ip_address": agent.ip_address, "auth_type": auth["type"]},
    })

    # Best-effort coronation into the Arda Fabric registry.
    try:
        from services.arda_fabric import get_arda_fabric
        fabric = get_arda_fabric()
        fabric.ensure_subject(
            agent_doc["node_id"],
            workload_hash=agent.workload_hash,
            executable_path=agent.executable_path,
        )
    except Exception as e:
        logger.debug(f"Fabric coronation skipped on register: {e}")
    
    return {
        "status": "registered",
        "agent_id": agent.agent_id,
        "auth_token": agent_token,
        "server_ips": list(SERVER_IPS),
        "message": "Store auth_token for future requests via X-Agent-Token header"
    }


@router.post("/agents/{agent_id}/heartbeat")
async def agent_heartbeat(
    agent_id: str,
    heartbeat: AgentHeartbeatModel,
    request: Request,
    auth: Dict = Depends(verify_agent_auth)
):
    """Receive heartbeat from an agent (authenticated)"""
    
    # Verify agent_id matches if authenticated
    if auth.get('agent_id') and auth['agent_id'] != agent_id:
        raise HTTPException(status_code=403, detail="Agent ID mismatch")
    
    agent = await db.unified_agents.find_one({"agent_id": agent_id})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found. Please register first.")
    
    # Update agent status
    update_data = {
        "status": heartbeat.status,
        "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        "cpu_usage": heartbeat.cpu_usage,
        "memory_usage": heartbeat.memory_usage,
        "disk_usage": heartbeat.disk_usage,
        "threat_count": heartbeat.threat_count or 0,
        "network_connections": heartbeat.network_connections,
        "last_ip": auth['ip'],
        **({"node_id": heartbeat.node_id} if heartbeat.node_id else {}),
        **({"executable_path": heartbeat.executable_path} if heartbeat.executable_path else {}),
        **({"workload_hash": heartbeat.workload_hash} if heartbeat.workload_hash else {}),
    }

    # Persist local UI URL when provided
    if heartbeat.local_ui_url:
        update_data["local_ui_url"] = heartbeat.local_ui_url
    
    # Store monitor summary in agent document for quick access
    if heartbeat.monitors:
        monitors_summary = {}
        for monitor_name in ['registry', 'process_tree', 'lolbin', 'code_signing', 
                            'dns', 'memory', 'whitelist', 'dlp', 'vulnerability', 'amsi']:
            monitor_data = getattr(heartbeat.monitors, monitor_name, None)
            if monitor_data:
                monitors_summary[monitor_name] = {
                    "last_run": monitor_data.last_run,
                    "threats_found": monitor_data.threats_found,
                    "status": "active"
                }
        update_data["monitors_summary"] = monitors_summary
    
    await db.unified_agents.update_one(
        {"agent_id": agent_id},
        {"$set": update_data}
    )

    # Coronate/refresh the peer in the Arda Fabric registry on every heartbeat
    # (this keeps executable_path/workload_hash fresh for constitutional→kernel bridging).
    try:
        from services.arda_fabric import get_arda_fabric
        fabric = get_arda_fabric()
        node_id = heartbeat.node_id or agent.get("node_id") or agent_id
        fabric.ensure_subject(
            node_id,
            workload_hash=heartbeat.workload_hash or agent.get("workload_hash"),
            executable_path=heartbeat.executable_path or agent.get("executable_path"),
        )
    except Exception as e:
        logger.debug(f"Fabric coronation skipped on heartbeat: {e}")
    
    # Process any alerts
    for alert_data in heartbeat.alerts:
        await _process_agent_alert(agent_id, alert_data)

    # Ingest EDM hit telemetry loop-back from endpoint.
    if heartbeat.edm_hits:
        await _ensure_edm_indexes()
        for hit in heartbeat.edm_hits:
            await _process_agent_edm_hit(agent_id, hit.model_dump(), agent)
        await _evaluate_active_edm_rollouts(agent_id)
    
    # Store telemetry if provided
    if heartbeat.telemetry:
        await db.agent_telemetry.insert_one({
            "agent_id": agent_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "telemetry": heartbeat.telemetry
        })
        
        # Run threat hunting on telemetry
        await _hunt_telemetry(heartbeat.telemetry)
    
    # Store structured monitor telemetry separately
    if heartbeat.monitors:
        monitor_doc = {
            "agent_id": agent_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for monitor_name in ['registry', 'process_tree', 'lolbin', 'code_signing', 
                            'dns', 'memory', 'whitelist', 'dlp', 'vulnerability', 'amsi']:
            monitor_data = getattr(heartbeat.monitors, monitor_name, None)
            if monitor_data:
                monitor_doc[monitor_name] = monitor_data.model_dump()
        
        await db.agent_monitor_telemetry.insert_one(monitor_doc)
    
    # Get queued commands for this agent
    commands = agent_ws_manager.get_queued_commands(agent_id)
    
    return {
        "status": "ok",
        "commands": commands,
        "config": agent.get("config", {}),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/agents")
async def list_unified_agents(
    platform: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    full: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """List all unified agents"""
    
    query = {}
    if platform:
        query["platform"] = platform
    if status:
        query["status"] = status
    
    # Defensive limits: the UI should not try to render thousands of agents at once.
    limit = max(1, min(int(limit or 200), 500))
    offset = max(0, int(offset or 0))

    projection = {"_id": 0}
    if not full:
        projection = {
            "_id": 0,
            "agent_id": 1,
            "platform": 1,
            "hostname": 1,
            "ip_address": 1,
            "last_ip": 1,
            "version": 1,
            "status": 1,
            "last_heartbeat": 1,
            "cpu_usage": 1,
            "memory_usage": 1,
            "disk_usage": 1,
            "threat_count": 1,
            "network_connections": 1,
            "vpn": 1,
            "local_ui_url": 1,
        }

    cursor = db.unified_agents.find(query, projection).skip(offset).limit(limit)
    agents = await cursor.to_list(limit)
    
    # Mark offline agents
    now = datetime.now(timezone.utc)
    for agent in agents:
        last_hb = agent.get("last_heartbeat")
        if last_hb:
            try:
                last_hb_dt = datetime.fromisoformat(last_hb.replace('Z', '+00:00'))
                if now - last_hb_dt > timedelta(minutes=5):
                    agent["status"] = "offline"
            except:
                pass
    
    total = await db.unified_agents.count_documents(query)
    return {
        "agents": agents,
        "total": total,
        "returned": len(agents),
        "limit": limit,
        "offset": offset,
        "online": len([a for a in agents if a.get("status") == "online"]),
        "offline": len([a for a in agents if a.get("status") == "offline"]),
        "full": full,
    }


@router.get("/agents/{agent_id}")
async def get_unified_agent(
    agent_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get details of a specific agent"""
    
    agent = await db.unified_agents.find_one({"agent_id": agent_id}, {"_id": 0})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Get recent telemetry
    recent_telemetry = await db.agent_telemetry.find(
        {"agent_id": agent_id}
    ).sort("timestamp", -1).limit(10).to_list(10)
    
    # Get recent alerts
    recent_alerts = await db.unified_alerts.find(
        {"agent_id": agent_id}
    ).sort("timestamp", -1).limit(20).to_list(20)
    
    return {
        **agent,
        "recent_telemetry": [{k: v for k, v in t.items() if k != '_id'} for t in recent_telemetry],
        "recent_alerts": [{k: v for k, v in a.items() if k != '_id'} for a in recent_alerts],
        "ws_connected": agent_ws_manager.is_connected(agent_id)
    }


@router.delete("/agents/{agent_id}")
async def unregister_agent(
    agent_id: str,
    current_user: dict = Depends(check_permission("admin"))
):
    """Unregister an agent"""
    
    result = await db.unified_agents.delete_one({"agent_id": agent_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Disconnect WebSocket if connected
    agent_ws_manager.disconnect(agent_id)
    
    logger.info(f"Agent unregistered: {agent_id}")
    return {"status": "unregistered", "agent_id": agent_id}


class AgentRenameModel(BaseModel):
    """Model for agent rename/alias change"""
    new_name: str
    new_alias: Optional[str] = None


@router.patch("/agents/{agent_id}/rename")
async def rename_agent(
    agent_id: str,
    rename_data: AgentRenameModel,
    current_user: dict = Depends(check_permission("write"))
):
    """
    Rename an agent or change its display alias.
    
    This allows operators to assign friendly names to agents for easier
    identification in the dashboard, regardless of the original hostname.
    """
    agent = await db.unified_agents.find_one({"agent_id": agent_id})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Prepare update
    update_fields = {
        "display_name": rename_data.new_name,
        "renamed_at": datetime.now(timezone.utc).isoformat(),
        "renamed_by": current_user.get("username", "unknown")
    }
    
    if rename_data.new_alias:
        update_fields["alias"] = rename_data.new_alias
    
    # Store original name if not already stored
    if not agent.get("original_name"):
        update_fields["original_name"] = agent.get("agent_name", agent.get("hostname", "unknown"))
    
    await db.unified_agents.update_one(
        {"agent_id": agent_id},
        {"$set": update_fields}
    )
    
    logger.info(f"Agent {agent_id} renamed to '{rename_data.new_name}' by {current_user.get('username')}")
    
    return {
        "status": "renamed",
        "agent_id": agent_id,
        "new_name": rename_data.new_name,
        "new_alias": rename_data.new_alias,
        "original_name": update_fields.get("original_name", agent.get("original_name"))
    }


@router.post("/agents/{agent_id}/command")
async def send_agent_command(
    agent_id: str,
    command: AgentCommandModel,
    current_user: dict = Depends(check_permission("write"))
):
    """Send a command to an agent"""
    
    agent = await db.unified_agents.find_one({"agent_id": agent_id})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    resolved_command_type = command.command_type or command.command
    if not resolved_command_type:
        raise HTTPException(
            status_code=422,
            detail="Missing command type. Provide 'command_type' (preferred) or legacy 'command'."
        )

    resolved_parameters = command.parameters or command.params or {}

    return await _dispatch_agent_command(
        agent_id=agent_id,
        command_type=resolved_command_type,
        parameters=resolved_parameters,
        priority=command.priority,
        issued_by=current_user.get("email", "system"),
    )


async def _dispatch_agent_command(
    agent_id: str,
    command_type: str,
    parameters: Dict[str, Any],
    priority: str,
    issued_by: str,
) -> Dict[str, Any]:
    """Queue or immediately dispatch a command to a unified agent."""
    command_id = secrets.token_hex(8)
    command_data = {
        "command_id": command_id,
        "type": "command",
        "command_type": command_type,
        "parameters": parameters,
        "priority": priority,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "issued_by": issued_by,
    }

    sent = await agent_ws_manager.send_command(agent_id, command_data)
    await db.agent_commands.insert_one({
        **command_data,
        "agent_id": agent_id,
        "status": "sent" if sent else "queued",
        "state_version": 1,
        "state_transition_log": [
            {
                "from_status": None,
                "to_status": "sent" if sent else "queued",
                "actor": issued_by,
                "reason": "command dispatched",
                "timestamp": command_data["timestamp"],
                "metadata": {"delivery_mode": "websocket" if sent else "queue"},
            }
        ],
    })

    logger.info(f"Command {command_type} sent to {agent_id}: {'immediate' if sent else 'queued'}")
    return {
        "command_id": command_id,
        "status": "sent" if sent else "queued",
        "message": f"Command {'sent immediately' if sent else 'queued for delivery'}",
    }


async def _resolve_edm_targets(targets: EDMBulkTargetModel) -> List[Dict[str, Any]]:
    """Resolve target agents for bulk EDM operations."""
    query: Dict[str, Any] = {}
    limit = max(1, min(int(targets.limit or 500), 5000))

    if targets.online_only:
        query["status"] = "online"

    if targets.platforms:
        normalized = [p.lower().strip() for p in targets.platforms if p and p.strip()]
        if normalized:
            query["platform"] = {"$in": normalized}

    if targets.groups:
        normalized_groups = [g.strip() for g in targets.groups if g and g.strip()]
        if normalized_groups:
            query["$or"] = [
                {"group": {"$in": normalized_groups}},
                {"config.group": {"$in": normalized_groups}},
                {"config.groups": {"$in": normalized_groups}},
                {"tags": {"$in": normalized_groups}},
                {"config.tags": {"$in": normalized_groups}},
            ]

    if targets.agent_ids:
        ids = [a.strip() for a in targets.agent_ids if a and a.strip()]
        if ids:
            query["agent_id"] = {"$in": ids}

    agents = await db.unified_agents.find(query, {"_id": 0, "agent_id": 1, "platform": 1, "status": 1}).limit(limit).to_list(length=limit)
    return agents


def _cohort_percent(rollout_id: str, agent_id: str) -> int:
    """Deterministic 0-99 cohort placement per rollout and agent."""
    digest = hashlib.sha256(f"{rollout_id}:{agent_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def _select_rollout_agents(rollout_id: str, eligible_ids: List[str], cumulative_percent: int) -> List[str]:
    pct = max(0, min(int(cumulative_percent), 100))
    return [aid for aid in eligible_ids if _cohort_percent(rollout_id, aid) < pct]


async def _count_edm_hits(dataset_id: str, agent_ids: List[str], since_iso: str) -> int:
    if not agent_ids:
        return 0
    return await db[EDM_HITS_COLLECTION].count_documents({
        "dataset_id": dataset_id,
        "agent_id": {"$in": agent_ids},
        "ingested_at": {"$gte": since_iso},
    })


async def _ensure_edm_indexes() -> None:
    """Create EDM telemetry/rollout indexes lazily for production safety/perf."""
    global _edm_indexes_ready
    if _edm_indexes_ready:
        return
    try:
        await db[EDM_HITS_COLLECTION].create_index([("dataset_id", 1), ("ingested_at", -1)])
        await db[EDM_HITS_COLLECTION].create_index([("agent_id", 1), ("ingested_at", -1)])
        await db[EDM_HITS_COLLECTION].create_index([("fingerprint", 1), ("ingested_at", -1)])
        await db[EDM_HITS_COLLECTION].create_index([("ingested_at", -1)])

        await db[EDM_ROLLOUT_COLLECTION].create_index([("rollout_id", 1)], unique=True)
        await db[EDM_ROLLOUT_COLLECTION].create_index([("status", 1), ("updated_at", -1)])
        await db[EDM_ROLLOUT_COLLECTION].create_index([("dataset_id", 1), ("status", 1)])
        _edm_indexes_ready = True
    except Exception as e:
        logger.warning(f"Failed to initialize EDM indexes: {e}")


async def _compute_rollout_readiness(rollout: Dict[str, Any]) -> Dict[str, Any]:
    """Compute cohort/control anomaly metrics used for readiness/auto-rollback."""
    now = datetime.now(timezone.utc)
    dataset_id = rollout.get("dataset_id")
    policy = rollout.get("policy", {})
    eval_minutes = max(5, int(policy.get("evaluation_window_minutes", 15)))
    min_hits = max(1, int(policy.get("anomaly_min_hits", 20)))
    spike_multiplier = max(1.0, float(policy.get("anomaly_spike_multiplier", 3.0)))

    since_iso = (now - timedelta(minutes=eval_minutes)).isoformat()
    eligible_ids = rollout.get("eligible_agent_ids") or []
    cohort_ids = rollout.get("applied_agent_ids") or []
    cohort_set = set(cohort_ids)
    control_ids = [aid for aid in eligible_ids if aid not in cohort_set]

    cohort_hits = await _count_edm_hits(dataset_id, cohort_ids, since_iso)
    control_hits = await _count_edm_hits(dataset_id, control_ids, since_iso) if control_ids else 0
    cohort_rate = cohort_hits / max(len(cohort_ids), 1) / float(eval_minutes)
    control_rate = control_hits / max(len(control_ids), 1) / float(eval_minutes) if control_ids else 0.0
    threshold_rate = max(control_rate * spike_multiplier, 0.05)
    has_spike = cohort_hits >= min_hits and cohort_rate > threshold_rate

    return {
        "dataset_id": dataset_id,
        "window_minutes": eval_minutes,
        "since": since_iso,
        "cohort": {
            "agents": len(cohort_ids),
            "hits": cohort_hits,
            "rate_per_agent_min": cohort_rate,
        },
        "control": {
            "agents": len(control_ids),
            "hits": control_hits,
            "rate_per_agent_min": control_rate,
        },
        "threshold": {
            "multiplier": spike_multiplier,
            "min_hits": min_hits,
            "rate_per_agent_min": threshold_rate,
        },
        "has_spike": has_spike,
        "can_advance": not has_spike,
    }


def _rollout_conflict_error() -> HTTPException:
    return HTTPException(
        status_code=409,
        detail="Rollout state changed concurrently; refresh rollout state and retry",
    )


def _deployment_conflict_error() -> HTTPException:
    return HTTPException(
        status_code=409,
        detail="Deployment state changed concurrently; refresh deployment state and retry",
    )


async def _transition_unified_deployment_state(
    deployment_id: str,
    expected_statuses: List[str],
    next_status: str,
    extra_updates: Optional[Dict[str, Any]] = None,
    deployment_task_id: Optional[str] = None,
    transition_actor: str = "system",
    transition_reason: Optional[str] = None,
    transition_metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    query: Dict[str, Any] = {
        "deployment_id": deployment_id,
        "status": {"$in": expected_statuses},
    }
    if deployment_task_id is not None:
        query["deployment_task_id"] = deployment_task_id

    update_doc = {
        "status": next_status,
        "updated_at": now,
    }
    if extra_updates:
        update_doc.update(extra_updates)

    result = await db.unified_deployments.update_one(
        query,
        {
            "$set": update_doc,
            "$inc": {"state_version": 1},
            "$push": {
                "state_transition_log": {
                    "from_status": expected_statuses[0] if len(expected_statuses) == 1 else list(expected_statuses),
                    "to_status": next_status,
                    "actor": transition_actor,
                    "reason": transition_reason,
                    "metadata": transition_metadata or {},
                    "timestamp": now,
                }
            },
        },
    )
    return getattr(result, "matched_count", 0) > 0


async def _finalize_agent_command_result(
    command_id: str,
    status: str,
    result_payload: Dict[str, Any],
    transition_actor: str = "agent",
    transition_reason: str = "command result received",
) -> Dict[str, Any]:
    normalized_status = str(status or "completed").lower().strip()
    if normalized_status not in {"completed", "failed"}:
        normalized_status = "completed"

    now = datetime.now(timezone.utc).isoformat()
    update_result = await db.agent_commands.update_one(
        {
            "command_id": command_id,
            "status": {"$in": ["queued", "sent", "delivered", "in_progress", "running"]},
        },
        {
            "$set": {
                "status": normalized_status,
                "result": result_payload,
                "completed_at": now,
                "updated_at": now,
            },
            "$inc": {"state_version": 1},
            "$push": {
                "state_transition_log": {
                    "from_status": ["queued", "sent", "delivered", "in_progress", "running"],
                    "to_status": normalized_status,
                    "actor": transition_actor,
                    "reason": transition_reason,
                    "timestamp": now,
                }
            },
        },
    )

    if getattr(update_result, "matched_count", 0) > 0:
        return {"updated": True, "status": normalized_status}

    existing = await db.agent_commands.find_one(
        {"command_id": command_id},
        {"_id": 0, "status": 1},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Command not found")

    raise HTTPException(
        status_code=409,
        detail=f"Command is already terminal (status={existing.get('status')})",
    )


async def _claim_rollout_for_rollback(
    rollout_id: str,
    reason: str,
    requested_by: str,
    allowed_statuses: List[str],
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    claim = await db[EDM_ROLLOUT_COLLECTION].update_one(
        {
            "rollout_id": rollout_id,
            "status": {"$in": allowed_statuses},
        },
        {
            "$set": {
                "status": "rolling_back",
                "rollback_reason": reason,
                "rollback_requested_by": requested_by,
                "rollback_requested_at": now,
                "updated_at": now,
            },
            "$inc": {"state_version": 1},
            "$push": {
                "state_transition_log": {
                    "from_status": list(allowed_statuses),
                    "to_status": "rolling_back",
                    "actor": requested_by,
                    "reason": reason,
                    "timestamp": now,
                }
            },
        },
    )
    if getattr(claim, "matched_count", 0) == 0:
        raise _rollout_conflict_error()

    refreshed = await db[EDM_ROLLOUT_COLLECTION].find_one({"rollout_id": rollout_id}, {"_id": 0})
    if not refreshed:
        raise HTTPException(status_code=404, detail="Rollout not found")
    return refreshed


def _canonical_json(value: Any) -> str:
    """Stable canonical JSON serialization for checksums/signatures."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _compute_edm_checksum(dataset: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(dataset).encode("utf-8")).hexdigest()


def _normalize_edm_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    return " ".join(text.split())


def _canonicalize_edm_record(record: Any) -> str:
    """Canonicalization aligned with agent EDM behavior for quality estimation."""
    if isinstance(record, dict):
        parts: List[str] = []
        for key in sorted(record.keys()):
            val = _normalize_edm_text(record.get(key))
            if val:
                parts.append(f"{_normalize_edm_text(key)}={val}")
        return "|".join(parts)

    if isinstance(record, list):
        vals = [_normalize_edm_text(v) for v in record]
        vals = [v for v in vals if v]
        return "|".join(vals)

    return _normalize_edm_text(record)


def _validate_and_score_edm_dataset(dataset_payload: Any) -> Dict[str, Any]:
    """Validate EDM schema and score publish readiness quality gates."""
    report: Dict[str, Any] = {
        "valid": False,
        "quality_gate_passed": False,
        "schema_errors": [],
        "quality_errors": [],
        "quality_warnings": [],
        "metrics": {
            "datasets": 0,
            "total_records": 0,
            "canonicalizable_records": 0,
            "canonical_coverage": 0.0,
            "datasets_missing_id": 0,
            "datasets_with_empty_records": 0,
            "duplicate_dataset_ids": 0,
            "duplicate_record_ids": 0,
            "unknown_candidate_types": 0,
        },
    }

    schema_errors: List[str] = report["schema_errors"]
    quality_errors: List[str] = report["quality_errors"]
    quality_warnings: List[str] = report["quality_warnings"]
    metrics: Dict[str, Any] = report["metrics"]

    if not isinstance(dataset_payload, dict):
        schema_errors.append("dataset payload must be an object")
        return report

    datasets = dataset_payload.get("datasets")
    if not isinstance(datasets, list):
        schema_errors.append("dataset payload must contain 'datasets' as a list")
        return report

    metrics["datasets"] = len(datasets)
    if len(datasets) == 0:
        schema_errors.append("'datasets' must not be empty")
        return report

    seen_dataset_ids: set = set()
    seen_record_ids: set = set()
    unknown_candidate_types: set = set()

    for ds_index, ds in enumerate(datasets):
        if not isinstance(ds, dict):
            schema_errors.append(f"datasets[{ds_index}] must be an object")
            continue

        ds_id = str(ds.get("dataset_id") or ds.get("name") or "").strip()
        if not ds_id:
            metrics["datasets_missing_id"] += 1
            schema_errors.append(f"datasets[{ds_index}] missing dataset_id/name")
        else:
            if ds_id in seen_dataset_ids:
                metrics["duplicate_dataset_ids"] += 1
            seen_dataset_ids.add(ds_id)

        records = ds.get("records")
        if not isinstance(records, list):
            schema_errors.append(f"datasets[{ds_index}].records must be a list")
            continue
        if len(records) == 0:
            metrics["datasets_with_empty_records"] += 1
            quality_warnings.append(f"datasets[{ds_index}] has no records")

        precision = ds.get("precision")
        if precision is not None and not isinstance(precision, dict):
            schema_errors.append(f"datasets[{ds_index}].precision must be an object if provided")
            precision = None

        if isinstance(precision, dict):
            if "min_confidence" in precision:
                try:
                    min_conf = float(precision.get("min_confidence"))
                except Exception:
                    schema_errors.append(f"datasets[{ds_index}].precision.min_confidence must be numeric")
                    min_conf = None
                if min_conf is not None:
                    if min_conf < 0.0 or min_conf > 1.0:
                        schema_errors.append(f"datasets[{ds_index}].precision.min_confidence must be between 0 and 1")
                    elif min_conf < EDM_MIN_ALLOWED_MIN_CONFIDENCE:
                        quality_errors.append(
                            f"datasets[{ds_index}].precision.min_confidence ({min_conf}) below enforced floor ({EDM_MIN_ALLOWED_MIN_CONFIDENCE})"
                        )

            if "allowed_candidate_types" in precision:
                allowed = precision.get("allowed_candidate_types")
                if not isinstance(allowed, list):
                    schema_errors.append(f"datasets[{ds_index}].precision.allowed_candidate_types must be a list")
                else:
                    unknown = {str(v).strip() for v in allowed if str(v).strip() and str(v).strip() not in EDM_ALLOWED_CANDIDATE_TYPES}
                    if unknown:
                        unknown_candidate_types.update(unknown)

        for record_index, record in enumerate(records):
            metrics["total_records"] += 1
            canonical = _canonicalize_edm_record(record)
            if canonical:
                metrics["canonicalizable_records"] += 1

            if isinstance(record, dict):
                record_id = str(record.get("record_id") or "").strip()
                if record_id and ds_id:
                    key = f"{ds_id}:{record_id}"
                    if key in seen_record_ids:
                        metrics["duplicate_record_ids"] += 1
                    seen_record_ids.add(key)
            elif record is None:
                quality_warnings.append(f"datasets[{ds_index}].records[{record_index}] is null and contributes no fingerprint")

    total_records = int(metrics.get("total_records", 0))
    canonicalizable = int(metrics.get("canonicalizable_records", 0))
    coverage = (canonicalizable / total_records) if total_records else 0.0
    metrics["canonical_coverage"] = round(coverage, 6)
    metrics["unknown_candidate_types"] = len(unknown_candidate_types)

    if total_records == 0:
        quality_errors.append("dataset contains zero records")

    if total_records > EDM_MAX_RECORDS_PER_PUBLISH:
        quality_errors.append(
            f"record count {total_records} exceeds publish gate limit {EDM_MAX_RECORDS_PER_PUBLISH}"
        )

    if coverage < EDM_MIN_CANONICAL_COVERAGE:
        quality_errors.append(
            f"canonical coverage {coverage:.3f} below threshold {EDM_MIN_CANONICAL_COVERAGE:.3f}"
        )

    if metrics["duplicate_dataset_ids"] > 0:
        quality_errors.append("duplicate dataset_id values detected")

    if metrics["duplicate_record_ids"] > 0:
        quality_errors.append("duplicate record_id values detected within dataset scope")

    if unknown_candidate_types:
        quality_errors.append(
            f"unknown precision.allowed_candidate_types: {sorted(unknown_candidate_types)}"
        )

    report["valid"] = len(schema_errors) == 0
    report["quality_gate_passed"] = report["valid"] and len(quality_errors) == 0
    return report


def _enforce_edm_publish_gates(dataset_payload: Any, *, context: str) -> Dict[str, Any]:
    """Enforce schema and quality gates prior to version promotion/distribution."""
    report = _validate_and_score_edm_dataset(dataset_payload)
    if not report.get("valid") or not report.get("quality_gate_passed"):
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"EDM dataset failed {context} validation gates",
                "context": context,
                "validation": report,
            },
        )
    return report


def _sign_edm_metadata(dataset_id: str, version: int, checksum: str) -> str:
    message = f"{dataset_id}:{version}:{checksum}"
    return hmac.new(AGENT_SECRET.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def _build_edm_meta(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "dataset_id": doc.get("dataset_id"),
        "version": int(doc.get("version", 0)),
        "checksum": doc.get("checksum"),
        "signature": doc.get("signature"),
        "signed_at": doc.get("published_at"),
    }


async def _dispatch_edm_dataset_to_targets(
    dataset: Dict[str, Any],
    edm_meta: Dict[str, Any],
    targets: EDMBulkTargetModel,
    priority: str,
    issued_by: str,
) -> Dict[str, Any]:
    agents = await _resolve_edm_targets(targets)
    if not agents:
        return {
            "matched_agents": 0,
            "dispatched": 0,
            "sent": 0,
            "queued": 0,
            "results": [],
        }

    sent = 0
    queued = 0
    results: List[Dict[str, Any]] = []
    for agent in agents:
        dispatch = await _dispatch_agent_command(
            agent_id=agent["agent_id"],
            command_type="update_edm_dataset",
            parameters={"dataset": dataset, "edm_meta": edm_meta},
            priority=priority,
            issued_by=issued_by,
        )
        if dispatch.get("status") == "sent":
            sent += 1
        else:
            queued += 1
        results.append({
            "agent_id": agent["agent_id"],
            "platform": agent.get("platform"),
            "agent_status": agent.get("status"),
            "command_id": dispatch.get("command_id"),
            "delivery": dispatch.get("status"),
        })

    return {
        "matched_agents": len(agents),
        "dispatched": len(results),
        "sent": sent,
        "queued": queued,
        "results": results,
    }


@router.post("/agents/{agent_id}/edm/reload")
async def reload_agent_edm_dataset(
    agent_id: str,
    current_user: dict = Depends(check_permission("write")),
):
    """Trigger EDM dataset reload on an agent without restarting the process."""
    agent = await db.unified_agents.find_one({"agent_id": agent_id})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    cmd = await _dispatch_agent_command(
        agent_id=agent_id,
        command_type="reload_edm_dataset",
        parameters={},
        priority="high",
        issued_by=current_user.get("email", "system"),
    )
    return {
        "agent_id": agent_id,
        "action": "reload_edm_dataset",
        **cmd,
    }


@router.post("/agents/{agent_id}/edm/dataset")
async def update_agent_edm_dataset(
    agent_id: str,
    payload: EDMDatasetCommandModel,
    current_user: dict = Depends(check_permission("write")),
):
    """Push a full EDM dataset payload to an agent and hot-reload it."""
    agent = await db.unified_agents.find_one({"agent_id": agent_id})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    _enforce_edm_publish_gates(payload.dataset, context="single-agent edm update")

    adhoc_dataset_id = f"adhoc-{agent_id}"
    adhoc_version = int(datetime.now(timezone.utc).timestamp())
    checksum = _compute_edm_checksum(payload.dataset)
    signature = _sign_edm_metadata(adhoc_dataset_id, adhoc_version, checksum)
    edm_meta = {
        "dataset_id": adhoc_dataset_id,
        "version": adhoc_version,
        "checksum": checksum,
        "signature": signature,
        "signed_at": datetime.now(timezone.utc).isoformat(),
    }

    cmd = await _dispatch_agent_command(
        agent_id=agent_id,
        command_type="update_edm_dataset",
        parameters={"dataset": payload.dataset, "edm_meta": edm_meta},
        priority=payload.priority,
        issued_by=current_user.get("email", "system"),
    )
    return {
        "agent_id": agent_id,
        "action": "update_edm_dataset",
        "datasets_count": len(payload.dataset.get("datasets", [])),
        "edm_meta": edm_meta,
        **cmd,
    }


@router.post("/agents/edm/reload-all")
async def reload_edm_dataset_fleet(
    targets: EDMBulkTargetModel,
    current_user: dict = Depends(check_permission("write")),
):
    """Fanout EDM reload command to all matching agents."""
    agents = await _resolve_edm_targets(targets)
    if not agents:
        return {
            "action": "reload_edm_dataset",
            "matched_agents": 0,
            "dispatched": 0,
            "sent": 0,
            "queued": 0,
            "results": [],
        }

    results: List[Dict[str, Any]] = []
    sent = 0
    queued = 0
    for agent in agents:
        dispatch = await _dispatch_agent_command(
            agent_id=agent["agent_id"],
            command_type="reload_edm_dataset",
            parameters={},
            priority="high",
            issued_by=current_user.get("email", "system"),
        )
        if dispatch.get("status") == "sent":
            sent += 1
        else:
            queued += 1
        results.append({
            "agent_id": agent["agent_id"],
            "platform": agent.get("platform"),
            "agent_status": agent.get("status"),
            "command_id": dispatch.get("command_id"),
            "delivery": dispatch.get("status"),
        })

    return {
        "action": "reload_edm_dataset",
        "matched_agents": len(agents),
        "dispatched": len(results),
        "sent": sent,
        "queued": queued,
        "results": results,
    }


@router.post("/agents/edm/dataset-all")
async def update_edm_dataset_fleet(
    payload: EDMBulkDatasetCommandModel,
    current_user: dict = Depends(check_permission("write")),
):
    """Fanout EDM dataset update command to all matching agents."""
    _enforce_edm_publish_gates(payload.dataset, context="fleet edm update")

    agents = await _resolve_edm_targets(payload.targets)
    if not agents:
        return {
            "action": "update_edm_dataset",
            "matched_agents": 0,
            "dispatched": 0,
            "sent": 0,
            "queued": 0,
            "datasets_count": len(payload.dataset.get("datasets", [])),
            "results": [],
        }

    # Ad hoc fanout still signs payloads so agents can verify trust/integrity.
    adhoc_dataset_id = "adhoc-global"
    adhoc_version = int(datetime.now(timezone.utc).timestamp())
    checksum = _compute_edm_checksum(payload.dataset)
    signature = _sign_edm_metadata(adhoc_dataset_id, adhoc_version, checksum)
    edm_meta = {
        "dataset_id": adhoc_dataset_id,
        "version": adhoc_version,
        "checksum": checksum,
        "signature": signature,
        "signed_at": datetime.now(timezone.utc).isoformat(),
    }

    fanout = await _dispatch_edm_dataset_to_targets(
        dataset=payload.dataset,
        edm_meta=edm_meta,
        targets=payload.targets,
        priority=payload.priority,
        issued_by=current_user.get("email", "system"),
    )

    return {
        "action": "update_edm_dataset",
        "matched_agents": fanout.get("matched_agents", 0),
        "dispatched": fanout.get("dispatched", 0),
        "sent": fanout.get("sent", 0),
        "queued": fanout.get("queued", 0),
        "datasets_count": len(payload.dataset.get("datasets", [])),
        "edm_meta": edm_meta,
        "results": fanout.get("results", []),
    }


# ============================================================
# EDM SOURCE-OF-TRUTH DATASET REGISTRY
# ============================================================

@router.get("/edm/datasets")
async def list_edm_datasets(current_user: dict = Depends(check_permission("read"))):
    """List latest EDM dataset head per dataset_id."""
    _ = current_user
    docs = await db[EDM_DATASET_COLLECTION].find({}, {"_id": 0}).sort([("dataset_id", 1), ("version", -1)]).to_list(5000)
    latest: Dict[str, Dict[str, Any]] = {}
    for doc in docs:
        dsid = doc.get("dataset_id")
        if dsid and dsid not in latest:
            latest[dsid] = doc

    datasets = []
    for dsid, doc in latest.items():
        datasets.append({
            "dataset_id": dsid,
            "version": doc.get("version"),
            "checksum": doc.get("checksum"),
            "published_by": doc.get("published_by"),
            "published_at": doc.get("published_at"),
            "rollback_target": doc.get("rollback_target"),
            "note": doc.get("note"),
        })
    return {"datasets": datasets, "count": len(datasets)}


@router.get("/edm/datasets/{dataset_id}/versions")
async def list_edm_dataset_versions(dataset_id: str, current_user: dict = Depends(check_permission("read"))):
    """List all versions for a dataset_id."""
    _ = current_user
    versions = await db[EDM_DATASET_COLLECTION].find({"dataset_id": dataset_id}, {"_id": 0}).sort("version", -1).to_list(1000)
    return {"dataset_id": dataset_id, "versions": versions, "count": len(versions)}


@router.get("/edm/datasets/{dataset_id}/versions/{version}")
async def get_edm_dataset_version(dataset_id: str, version: int, current_user: dict = Depends(check_permission("read"))):
    """Get a specific dataset version payload + metadata."""
    _ = current_user
    doc = await db[EDM_DATASET_COLLECTION].find_one({"dataset_id": dataset_id, "version": version}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dataset version not found")
    return doc


@router.post("/edm/datasets/{dataset_id}/versions")
async def create_edm_dataset_version(
    dataset_id: str,
    payload: EDMDatasetVersionCreateModel,
    current_user: dict = Depends(check_permission("write")),
):
    """Create a new version in EDM source-of-truth registry."""
    quality_report = _enforce_edm_publish_gates(payload.dataset, context="dataset version creation")

    latest = await db[EDM_DATASET_COLLECTION].find_one({"dataset_id": dataset_id}, {"_id": 0, "version": 1}, sort=[("version", -1)])
    next_version = int(latest.get("version", 0)) + 1 if latest else 1
    checksum = _compute_edm_checksum(payload.dataset)
    signature = _sign_edm_metadata(dataset_id, next_version, checksum)
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "dataset_id": dataset_id,
        "version": next_version,
        "dataset": payload.dataset,
        "quality_report": quality_report,
        "checksum": checksum,
        "signature": signature,
        "published_by": current_user.get("email", "system"),
        "published_at": now,
        "rollback_target": None,
        "note": payload.note,
        "created_at": now,
    }
    await db[EDM_DATASET_COLLECTION].insert_one(doc)
    return {"status": "created", "contract_version": EDM_CONTROL_PLANE_CONTRACT_VERSION, **doc}


@router.post("/edm/datasets/{dataset_id}/versions/{version}/publish")
async def publish_edm_dataset_version(
    dataset_id: str,
    version: int,
    payload: EDMDatasetPublishModel,
    current_user: dict = Depends(check_permission("write")),
):
    """Publish a stored dataset version to matching agents."""
    doc = await db[EDM_DATASET_COLLECTION].find_one({"dataset_id": dataset_id, "version": version}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dataset version not found")

    quality_report = _enforce_edm_publish_gates(doc.get("dataset", {}), context="dataset publish")

    fanout = await _dispatch_edm_dataset_to_targets(
        dataset=doc.get("dataset", {}),
        edm_meta=_build_edm_meta(doc),
        targets=payload.targets,
        priority=payload.priority,
        issued_by=current_user.get("email", "system"),
    )

    await db[EDM_DATASET_COLLECTION].update_one(
        {"dataset_id": dataset_id, "version": version},
        {"$set": {"last_published_at": datetime.now(timezone.utc).isoformat(), "last_published_by": current_user.get("email", "system")}},
    )

    return {
        "action": "publish_edm_dataset_version",
        "contract_version": EDM_CONTROL_PLANE_CONTRACT_VERSION,
        "dataset_id": dataset_id,
        "version": version,
        "quality_report": quality_report,
        "edm_meta": _build_edm_meta(doc),
        **fanout,
    }


@router.post("/edm/datasets/{dataset_id}/rollback")
async def rollback_edm_dataset(
    dataset_id: str,
    payload: EDMDatasetRollbackModel,
    current_user: dict = Depends(check_permission("write")),
):
    """Rollback by cloning target version into new latest version, optionally publish immediately."""
    target = await db[EDM_DATASET_COLLECTION].find_one({"dataset_id": dataset_id, "version": payload.target_version}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Rollback target version not found")

    latest = await db[EDM_DATASET_COLLECTION].find_one({"dataset_id": dataset_id}, {"_id": 0, "version": 1}, sort=[("version", -1)])
    new_version = int((latest or {}).get("version", 0)) + 1
    dataset = target.get("dataset", {})
    checksum = _compute_edm_checksum(dataset)
    signature = _sign_edm_metadata(dataset_id, new_version, checksum)
    now = datetime.now(timezone.utc).isoformat()

    rollback_doc = {
        "dataset_id": dataset_id,
        "version": new_version,
        "dataset": dataset,
        "checksum": checksum,
        "signature": signature,
        "published_by": current_user.get("email", "system"),
        "published_at": now,
        "rollback_target": payload.target_version,
        "note": payload.note or f"Rollback to version {payload.target_version}",
        "created_at": now,
    }
    await db[EDM_DATASET_COLLECTION].insert_one(rollback_doc)

    response: Dict[str, Any] = {
        "status": "rolled_back",
        "contract_version": EDM_CONTROL_PLANE_CONTRACT_VERSION,
        "dataset_id": dataset_id,
        "new_version": new_version,
        "rollback_target": payload.target_version,
        "edm_meta": _build_edm_meta(rollback_doc),
    }

    if payload.publish:
        quality_report = _enforce_edm_publish_gates(dataset, context="rollback publish")
        fanout = await _dispatch_edm_dataset_to_targets(
            dataset=dataset,
            edm_meta=_build_edm_meta(rollback_doc),
            targets=payload.targets,
            priority=payload.priority,
            issued_by=current_user.get("email", "system"),
        )
        response["publish"] = {**fanout, "quality_report": quality_report}

    return response


@router.get("/edm/telemetry/summary")
async def get_edm_telemetry_summary(
    dataset_id: Optional[str] = None,
    since_minutes: int = 60,
    current_user: dict = Depends(check_permission("read")),
):
    """Centralized EDM hit analytics across agents."""
    _ = current_user
    await _ensure_edm_indexes()
    since_minutes = max(1, min(int(since_minutes), 24 * 60))
    since_iso = (datetime.now(timezone.utc) - timedelta(minutes=since_minutes)).isoformat()

    match: Dict[str, Any] = {"ingested_at": {"$gte": since_iso}}
    if dataset_id:
        match["dataset_id"] = dataset_id

    by_dataset = await db[EDM_HITS_COLLECTION].aggregate([
        {"$match": match},
        {"$group": {"_id": "$dataset_id", "hits": {"$sum": 1}, "agents": {"$addToSet": "$agent_id"}}},
        {"$project": {"_id": 0, "dataset_id": "$_id", "hits": 1, "agents": {"$size": "$agents"}}},
        {"$sort": {"hits": -1}},
    ]).to_list(200)

    by_platform = await db[EDM_HITS_COLLECTION].aggregate([
        {"$match": match},
        {"$group": {"_id": "$agent_platform", "hits": {"$sum": 1}}},
        {"$project": {"_id": 0, "platform": {"$ifNull": ["$_id", "unknown"]}, "hits": 1}},
        {"$sort": {"hits": -1}},
    ]).to_list(20)

    top_agents = await db[EDM_HITS_COLLECTION].aggregate([
        {"$match": match},
        {"$group": {"_id": "$agent_id", "hits": {"$sum": 1}, "host": {"$first": "$host"}}},
        {"$project": {"_id": 0, "agent_id": "$_id", "host": 1, "hits": 1}},
        {"$sort": {"hits": -1}},
        {"$limit": 20},
    ]).to_list(20)

    by_candidate_type = await db[EDM_HITS_COLLECTION].aggregate([
        {"$match": match},
        {"$group": {"_id": "$match_candidate_type", "hits": {"$sum": 1}}},
        {"$project": {"_id": 0, "candidate_type": {"$ifNull": ["$_id", "unknown"]}, "hits": 1}},
        {"$sort": {"hits": -1}},
    ]).to_list(20)

    confidence_bands = await db[EDM_HITS_COLLECTION].aggregate([
        {"$match": match},
        {"$project": {
            "band": {
                "$switch": {
                    "branches": [
                        {"case": {"$gte": ["$match_confidence", 0.98]}, "then": "0.98-1.00"},
                        {"case": {"$gte": ["$match_confidence", 0.95]}, "then": "0.95-0.97"},
                        {"case": {"$gte": ["$match_confidence", 0.90]}, "then": "0.90-0.94"},
                    ],
                    "default": "<0.90/unknown",
                }
            }
        }},
        {"$group": {"_id": "$band", "hits": {"$sum": 1}}},
        {"$project": {"_id": 0, "band": "$_id", "hits": 1}},
        {"$sort": {"hits": -1}},
    ]).to_list(10)

    total_hits = int(sum(int(i.get("hits", 0)) for i in by_dataset))
    return {
        "since_minutes": since_minutes,
        "dataset_filter": dataset_id,
        "total_hits": total_hits,
        "by_dataset": by_dataset,
        "by_platform": by_platform,
        "top_agents": top_agents,
        "by_candidate_type": by_candidate_type,
        "confidence_bands": confidence_bands,
    }


@router.get("/edm/rollouts")
async def list_edm_rollouts(
    status: Optional[str] = None,
    current_user: dict = Depends(check_permission("read")),
):
    """List EDM rollout runs with high-level state."""
    _ = current_user
    await _ensure_edm_indexes()
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    docs = await db[EDM_ROLLOUT_COLLECTION].find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"rollouts": docs, "count": len(docs)}


@router.get("/edm/rollouts/{rollout_id}")
async def get_edm_rollout(
    rollout_id: str,
    current_user: dict = Depends(check_permission("read")),
):
    """Get full rollout state and progress telemetry."""
    _ = current_user
    await _ensure_edm_indexes()
    doc = await db[EDM_ROLLOUT_COLLECTION].find_one({"rollout_id": rollout_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Rollout not found")
    return doc


@router.get("/edm/rollouts/{rollout_id}/readiness")
async def get_edm_rollout_readiness(
    rollout_id: str,
    current_user: dict = Depends(check_permission("read")),
):
    """Pre-advance readiness check using cohort/control anomaly rates."""
    _ = current_user
    await _ensure_edm_indexes()
    rollout = await db[EDM_ROLLOUT_COLLECTION].find_one({"rollout_id": rollout_id}, {"_id": 0})
    if not rollout:
        raise HTTPException(status_code=404, detail="Rollout not found")

    readiness = await _compute_rollout_readiness(rollout)
    stages = rollout.get("stages") or [5, 25, 100]
    stage_index = int(rollout.get("stage_index", 0))
    next_stage_index = stage_index + 1
    next_stage_percent = stages[next_stage_index] if next_stage_index < len(stages) else None
    readiness["rollout_id"] = rollout_id
    readiness["status"] = rollout.get("status")
    readiness["current_stage"] = {
        "index": stage_index,
        "percent": stages[stage_index] if stage_index < len(stages) else None,
    }
    readiness["next_stage"] = {
        "index": next_stage_index if next_stage_percent is not None else None,
        "percent": next_stage_percent,
    }
    readiness["can_advance"] = bool(
        rollout.get("status") == "active"
        and next_stage_percent is not None
        and not readiness.get("has_spike")
    )
    return readiness


@router.post("/edm/rollouts/start")
async def start_edm_rollout(
    payload: EDMRolloutStartModel,
    current_user: dict = Depends(check_permission("write")),
):
    """Start progressive canary rollout for an EDM dataset version."""
    await _ensure_edm_indexes()
    version_doc = await db[EDM_DATASET_COLLECTION].find_one(
        {"dataset_id": payload.dataset_id, "version": int(payload.target_version)},
        {"_id": 0},
    )
    if not version_doc:
        raise HTTPException(status_code=404, detail="Target dataset version not found")

    quality_report = _enforce_edm_publish_gates(version_doc.get("dataset", {}), context="rollout start")

    previous_doc = await db[EDM_DATASET_COLLECTION].find_one(
        {"dataset_id": payload.dataset_id, "version": {"$lt": int(payload.target_version)}},
        {"_id": 0, "version": 1},
        sort=[("version", -1)],
    )

    agents = await _resolve_edm_targets(payload.targets)
    if not agents:
        raise HTTPException(status_code=422, detail="No target agents matched rollout filters")

    rollout_id = f"edm-rollout-{secrets.token_hex(6)}"
    stages = [max(1, min(int(s), 100)) for s in (payload.policy.stages or [5, 25, 100])]
    stages = sorted(set(stages))
    if stages[-1] != 100:
        stages.append(100)

    eligible_ids = [a["agent_id"] for a in agents]
    stage_index = 0
    stage_pct = stages[stage_index]
    selected_ids = _select_rollout_agents(rollout_id, eligible_ids, stage_pct)
    if not selected_ids:
        selected_ids = eligible_ids[:1]

    fanout = await _dispatch_edm_dataset_to_targets(
        dataset=version_doc.get("dataset", {}),
        edm_meta=_build_edm_meta(version_doc),
        targets=EDMBulkTargetModel(agent_ids=selected_ids, online_only=False),
        priority=payload.priority,
        issued_by=current_user.get("email", "system"),
    )

    now = datetime.now(timezone.utc).isoformat()
    rollout_doc = {
        "contract_version": EDM_CONTROL_PLANE_CONTRACT_VERSION,
        "rollout_id": rollout_id,
        "dataset_id": payload.dataset_id,
        "target_version": int(payload.target_version),
        "previous_version": (previous_doc or {}).get("version"),
        "quality_report": quality_report,
        "status": "active",
        "targets": payload.targets.model_dump(),
        "policy": payload.policy.model_dump(),
        "stages": stages,
        "stage_index": stage_index,
        "eligible_agent_ids": eligible_ids,
        "applied_agent_ids": selected_ids,
        "created_at": now,
        "updated_at": now,
        "state_version": 1,
        "state_transition_log": [
            {
                "from_status": None,
                "to_status": "active",
                "actor": current_user.get("email", "system"),
                "reason": "rollout created",
                "timestamp": now,
                "metadata": {
                    "target_version": int(payload.target_version),
                    "initial_stage_index": stage_index,
                    "initial_stage_percent": stage_pct,
                },
            }
        ],
        "created_by": current_user.get("email", "system"),
        "stage_history": [{
            "stage_index": stage_index,
            "stage_percent": stage_pct,
            "applied_now": len(selected_ids),
            "applied_total": len(selected_ids),
            "fanout": fanout,
            "timestamp": now,
        }],
    }
    await db[EDM_ROLLOUT_COLLECTION].insert_one(rollout_doc)
    return rollout_doc


@router.post("/edm/rollouts/{rollout_id}/advance")
async def advance_edm_rollout(
    rollout_id: str,
    current_user: dict = Depends(check_permission("write")),
):
    """Advance rollout to next stage (5% -> 25% -> 100%)."""
    await _ensure_edm_indexes()
    rollout = await db[EDM_ROLLOUT_COLLECTION].find_one({"rollout_id": rollout_id}, {"_id": 0})
    if not rollout:
        raise HTTPException(status_code=404, detail="Rollout not found")
    if rollout.get("status") != "active":
        raise HTTPException(status_code=409, detail=f"Rollout is not active (status={rollout.get('status')})")

    readiness = await _compute_rollout_readiness(rollout)
    if readiness.get("has_spike"):
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Rollout advance blocked due to anomaly spike",
                "readiness": readiness,
            },
        )

    stages = rollout.get("stages") or [5, 25, 100]
    current_stage_index = int(rollout.get("stage_index", 0))
    stage_index = current_stage_index + 1
    if stage_index >= len(stages):
        close_result = await db[EDM_ROLLOUT_COLLECTION].update_one(
            {
                "rollout_id": rollout_id,
                "status": "active",
                "stage_index": current_stage_index,
            },
            {
                "$set": {"status": "completed", "updated_at": datetime.now(timezone.utc).isoformat()},
                "$inc": {"state_version": 1},
                "$push": {
                    "state_transition_log": {
                        "from_status": "active",
                        "to_status": "completed",
                        "actor": current_user.get("email", "system"),
                        "reason": "rollout completed all stages",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "metadata": {"stage_index": current_stage_index},
                    }
                },
            },
        )
        if getattr(close_result, "matched_count", 0) == 0:
            raise _rollout_conflict_error()
        return {"rollout_id": rollout_id, "status": "completed", "message": "All rollout stages already applied"}

    version_doc = await db[EDM_DATASET_COLLECTION].find_one(
        {"dataset_id": rollout.get("dataset_id"), "version": int(rollout.get("target_version"))},
        {"_id": 0},
    )
    if not version_doc:
        raise HTTPException(status_code=404, detail="Rollout target dataset version missing")

    eligible_ids = rollout.get("eligible_agent_ids") or []
    already_applied = set(rollout.get("applied_agent_ids") or [])
    stage_pct = int(stages[stage_index])
    target_set = set(_select_rollout_agents(rollout_id, eligible_ids, stage_pct))
    delta_ids = [aid for aid in target_set if aid not in already_applied]

    fanout = {"matched_agents": 0, "dispatched": 0, "sent": 0, "queued": 0, "results": []}
    if delta_ids:
        fanout = await _dispatch_edm_dataset_to_targets(
            dataset=version_doc.get("dataset", {}),
            edm_meta=_build_edm_meta(version_doc),
            targets=EDMBulkTargetModel(agent_ids=delta_ids, online_only=False),
            priority="high",
            issued_by=current_user.get("email", "system"),
        )

    updated_applied = list(already_applied.union(set(delta_ids)))
    now = datetime.now(timezone.utc).isoformat()
    done = stage_index >= len(stages) - 1
    update_result = await db[EDM_ROLLOUT_COLLECTION].update_one(
        {
            "rollout_id": rollout_id,
            "status": "active",
            "stage_index": current_stage_index,
        },
        {
            "$set": {
                "stage_index": stage_index,
                "applied_agent_ids": updated_applied,
                "updated_at": now,
                "status": "completed" if done else "active",
            },
            "$inc": {"state_version": 1},
            "$push": {
                "state_transition_log": {
                    "from_status": "active",
                    "to_status": "completed" if done else "active",
                    "actor": current_user.get("email", "system"),
                    "reason": "rollout stage advanced",
                    "timestamp": now,
                    "metadata": {
                        "from_stage_index": current_stage_index,
                        "to_stage_index": stage_index,
                        "stage_percent": stage_pct,
                        "applied_now": len(delta_ids),
                    },
                },
                "stage_history": {
                    "stage_index": stage_index,
                    "stage_percent": stage_pct,
                    "applied_now": len(delta_ids),
                    "applied_total": len(updated_applied),
                    "fanout": fanout,
                    "timestamp": now,
                }
            },
        },
    )
    if getattr(update_result, "matched_count", 0) == 0:
        raise _rollout_conflict_error()

    return {
        "rollout_id": rollout_id,
        "status": "completed" if done else "active",
        "stage_index": stage_index,
        "stage_percent": stage_pct,
        "applied_now": len(delta_ids),
        "applied_total": len(updated_applied),
        "fanout": fanout,
    }


@router.post("/edm/rollouts/{rollout_id}/rollback")
async def rollback_edm_rollout(
    rollout_id: str,
    payload: EDMRolloutRollbackModel,
    current_user: dict = Depends(check_permission("write")),
):
    """Manually rollback a rollout to previous or explicit dataset version."""
    await _ensure_edm_indexes()
    rollout = await db[EDM_ROLLOUT_COLLECTION].find_one({"rollout_id": rollout_id}, {"_id": 0})
    if not rollout:
        raise HTTPException(status_code=404, detail="Rollout not found")

    rollback_version = payload.rollback_version
    if rollback_version is None:
        rollback_version = rollout.get("previous_version")
    if rollback_version is None:
        raise HTTPException(status_code=422, detail="No rollback version available")

    refreshed = await _claim_rollout_for_rollback(
        rollout_id=rollout_id,
        reason=payload.reason or "Manual rollback requested",
        requested_by=current_user.get("email", "system"),
        allowed_statuses=["active", "completed"],
    )
    update_previous = await db[EDM_ROLLOUT_COLLECTION].update_one(
        {"rollout_id": rollout_id, "status": "rolling_back"},
        {
            "$set": {"previous_version": int(rollback_version), "updated_at": datetime.now(timezone.utc).isoformat()},
            "$inc": {"state_version": 1},
            "$push": {
                "state_transition_log": {
                    "from_status": "rolling_back",
                    "to_status": "rolling_back",
                    "actor": current_user.get("email", "system"),
                    "reason": "rollback version selected",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "metadata": {"rollback_version": int(rollback_version)},
                }
            },
        },
    )
    if getattr(update_previous, "matched_count", 0) == 0:
        raise _rollout_conflict_error()
    refreshed = await db[EDM_ROLLOUT_COLLECTION].find_one({"rollout_id": rollout_id}, {"_id": 0})
    rollback = await _execute_rollout_rollback(
        refreshed,
        payload.reason or "Manual rollback requested",
        current_user.get("email", "system"),
    )
    if not rollback.get("rolled_back"):
        raise HTTPException(status_code=422, detail=rollback.get("reason", "Rollback failed"))
    return {"rollout_id": rollout_id, **rollback}


@router.get("/agents/{agent_id}/commands")
async def get_agent_commands(
    agent_id: str,
    request: Request,
    auth: Dict = Depends(verify_agent_auth)
):
    """Get pending commands for an agent (polling endpoint for MCP)"""
    
    # Verify agent_id matches if authenticated with token
    if auth.get('agent_id') and auth['agent_id'] != agent_id:
        raise HTTPException(status_code=403, detail="Agent ID mismatch")
    
    # First check in-memory queue (WebSocket manager)
    queued = agent_ws_manager.get_queued_commands(agent_id)
    
    # Also check database for queued commands
    db_commands = await db.agent_commands.find({
        "agent_id": agent_id,
        "status": "queued"
    }).sort("timestamp", 1).limit(10).to_list(length=10)
    
    # Mark as delivered
    if db_commands:
        command_ids = [cmd["command_id"] for cmd in db_commands]
        await db.agent_commands.update_many(
            {
                "command_id": {"$in": command_ids},
                "status": "queued",
            },
            {
                "$set": {
                    "status": "delivered",
                    "delivered_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                "$inc": {"state_version": 1},
                "$push": {
                    "state_transition_log": {
                        "from_status": "queued",
                        "to_status": "delivered",
                        "actor": f"agent:{agent_id}",
                        "reason": "agent polled commands",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                },
            }
        )
    
    # Combine and return
    all_commands = queued + [_serialize_agent_command_for_delivery(c) for c in db_commands]
    
    return {"commands": all_commands, "count": len(all_commands)}


@router.post("/agents/{agent_id}/command-result")
async def report_command_result(
    agent_id: str,
    result: dict,
    request: Request,
    auth: Dict = Depends(verify_agent_auth)
):
    """Receive command execution result from agent"""
    
    # Verify agent_id matches
    if auth.get('agent_id') and auth['agent_id'] != agent_id:
        raise HTTPException(status_code=403, detail="Agent ID mismatch")
    
    command_id = result.get("command_id")
    if not command_id:
        raise HTTPException(status_code=400, detail="Missing command_id")
    
    finalize = await _finalize_agent_command_result(
        command_id=command_id,
        status=result.get("status", "completed"),
        result_payload=result.get("result", {}),
        transition_actor=f"agent:{agent_id}",
        transition_reason="agent reported command result",
    )
    
    # Store full result in command_results collection
    await db.command_results.insert_one({
        "command_id": command_id,
        "agent_id": agent_id,
        "command_type": result.get("command_type"),
        "status": result.get("status", "completed"),
        "result": result.get("result", {}),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    logger.info(f"Command result received: {command_id} from {agent_id} - {finalize.get('status')}")
    
    return {"status": "received", "command_id": command_id}


@router.get("/commands/{command_id}/status")
async def get_command_status(command_id: str, current_user: dict = Depends(check_permission("read"))):
    """Get the status of a specific command"""
    
    command = await db.agent_commands.find_one({"command_id": command_id})
    if not command:
        raise HTTPException(status_code=404, detail="Command not found")
    
    return {
        "command_id": command_id,
        "agent_id": command.get("agent_id"),
        "command_type": command.get("command_type"),
        "status": command.get("status"),
        "result": command.get("result"),
        "timestamp": command.get("timestamp"),
        "completed_at": command.get("completed_at")
    }


# ============================================================
# DEPLOYMENT ENDPOINTS
# ============================================================

@router.post("/deployments")
async def create_deployment(
    deployment: DeploymentRequestModel,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(check_permission("admin"))
):
    """Create a new agent deployment"""
    
    deployment_id = secrets.token_hex(8)
    
    deployment_doc = {
        "deployment_id": deployment_id,
        "target_platform": deployment.target_platform,
        "target_ip": deployment.target_ip,
        "agent_config": deployment.agent_config or {},
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "state_version": 1,
        "state_transition_log": [
            {
                "from_status": None,
                "to_status": "pending",
                "actor": current_user.get("email", "system"),
                "reason": "deployment created",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "target_platform": deployment.target_platform,
                    "target_ip": deployment.target_ip,
                },
            }
        ],
        "created_by": current_user.get("email", "system")
    }
    
    await db.unified_deployments.insert_one(deployment_doc)
    
    # Start deployment in background
    background_tasks.add_task(_process_deployment, deployment_id, deployment)
    
    logger.info(f"Deployment created: {deployment_id} for {deployment.target_platform} at {deployment.target_ip}")
    
    return {
        "deployment_id": deployment_id,
        "status": "pending",
        "message": "Deployment queued for processing"
    }


@router.get("/deployments")
async def list_deployments(
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """List all deployments"""
    
    query = {}
    if status:
        query["status"] = status
    
    deployments = await db.unified_deployments.find(query, {"_id": 0}).to_list(500)

    for deployment in deployments:
        await _sync_unified_deployment_status(deployment)
    
    return {
        "deployments": deployments,
        "total": len(deployments)
    }


@router.get("/deployments/{deployment_id}")
async def get_deployment(
    deployment_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get deployment details"""
    
    deployment = await db.unified_deployments.find_one(
        {"deployment_id": deployment_id},
        {"_id": 0}
    )
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    await _sync_unified_deployment_status(deployment)
    deployment = await db.unified_deployments.find_one(
        {"deployment_id": deployment_id},
        {"_id": 0}
    )
    
    return deployment


# ============================================================
# ALERTS ENDPOINTS
# ============================================================

@router.post("/alerts")
async def create_alert(alert: AlertModel):
    """Create an alert from an agent"""
    
    alert_id = secrets.token_hex(8)
    
    alert_doc = _build_unified_alert_doc(
        alert_id=alert_id,
        agent_id=alert.agent_id,
        severity=alert.severity,
        category=alert.category,
        message=alert.message,
        details=alert.details,
        mitre_technique=alert.mitre_technique,
        actor="system:api",
        reason="alert created via API",
    )
    
    await db.unified_alerts.insert_one(alert_doc)
    
    logger.warning(f"ALERT [{alert.severity.upper()}] from {alert.agent_id}: {alert.message}")
    
    return {"alert_id": alert_id, "status": "created"}


@router.get("/alerts")
async def list_alerts(
    severity: Optional[str] = None,
    acknowledged: Optional[bool] = None,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """List alerts"""
    
    query = {}
    if severity:
        query["severity"] = severity
    if acknowledged is not None:
        query["acknowledged"] = acknowledged
    
    alerts = await db.unified_alerts.find(query, {"_id": 0}).sort(
        "timestamp", -1
    ).limit(limit).to_list(limit)
    
    return {
        "alerts": alerts,
        "total": len(alerts)
    }


@router.put("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    current_user: dict = Depends(check_permission("write"))
):
    """Acknowledge an alert"""
    
    actor = current_user.get("email", "system")
    alert = await _ensure_unified_alert_state_fields(
        alert_id,
        actor=actor,
        reason="bootstrap unified alert durability fields",
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if bool(alert.get("acknowledged")):
        raise HTTPException(status_code=409, detail="Alert already acknowledged")

    current_version = int(alert.get("state_version") or 0)
    query: Dict[str, Any] = {
        "alert_id": alert_id,
        "acknowledged": False,
    }
    if current_version <= 0:
        query["$or"] = [{"state_version": {"$exists": False}}, {"state_version": 0}]
    else:
        query["state_version"] = current_version

    now = datetime.now(timezone.utc).isoformat()
    result = await db.unified_alerts.update_one(
        query,
        {
            "$set": {
                "acknowledged": True,
                "status": "acknowledged",
                "acknowledged_at": now,
                "acknowledged_by": actor,
                "updated_at": now,
            },
            "$inc": {"state_version": 1},
            "$push": {
                "state_transition_log": _alert_transition_entry(
                    from_status="unacknowledged",
                    to_status="acknowledged",
                    actor=actor,
                    reason="alert acknowledged",
                )
            },
        },
    )

    if getattr(result, "modified_count", 0) == 0:
        refreshed = await db.unified_alerts.find_one({"alert_id": alert_id}, {"_id": 0, "acknowledged": 1})
        if not refreshed:
            raise HTTPException(status_code=404, detail="Alert not found")
        if bool(refreshed.get("acknowledged")):
            raise HTTPException(status_code=409, detail="Alert already acknowledged")
        raise HTTPException(status_code=409, detail="Alert acknowledgment conflict; state changed concurrently")
    
    return {"status": "acknowledged"}


# ============================================================
# DASHBOARD / STATS ENDPOINTS
# ============================================================

@router.get("/dashboard")
async def get_unified_dashboard(current_user: dict = Depends(get_current_user)):
    """Get unified agent dashboard data"""
    
    # Count agents by status
    total_agents = await db.unified_agents.count_documents({})
    online_agents = await db.unified_agents.count_documents({"status": "online"})
    
    # Count by platform
    pipeline = [
        {"$group": {"_id": "$platform", "count": {"$sum": 1}}}
    ]
    platform_stats = await db.unified_agents.aggregate(pipeline).to_list(10)
    
    # Alert stats
    total_alerts = await db.unified_alerts.count_documents({})
    unack_alerts = await db.unified_alerts.count_documents({"acknowledged": False})
    
    # Deployment stats
    total_deployments = await db.unified_deployments.count_documents({})
    active_deployments = await db.unified_deployments.count_documents(
        {"status": {"$in": ["pending", "processing"]}}
    )
    
    # Recent agents
    recent_agents = await db.unified_agents.find(
        {}, {"_id": 0, "agent_id": 1, "hostname": 1, "platform": 1, "status": 1, "last_heartbeat": 1}
    ).sort("last_heartbeat", -1).limit(10).to_list(10)
    
    # Recent alerts
    recent_alerts = await db.unified_alerts.find(
        {}, {"_id": 0}
    ).sort("timestamp", -1).limit(10).to_list(10)
    
    return {
        "agents": {
            "total": total_agents,
            "online": online_agents,
            "offline": total_agents - online_agents,
            "by_platform": {s["_id"]: s["count"] for s in platform_stats},
            "recent": recent_agents
        },
        "alerts": {
            "total": total_alerts,
            "unacknowledged": unack_alerts,
            "recent": recent_alerts
        },
        "deployments": {
            "total": total_deployments,
            "active": active_deployments
        },
        "websocket_connections": len(agent_ws_manager.active_connections),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/stats")
async def get_unified_stats(current_user: dict = Depends(get_current_user)):
    """Get unified agent system statistics"""
    
    stats = {
        "total_agents": await db.unified_agents.count_documents({}),
        "online_agents": await db.unified_agents.count_documents({"status": "online"}),
        "total_alerts": await db.unified_alerts.count_documents({}),
        "total_commands": await db.agent_commands.count_documents({}),
        "total_deployments": await db.unified_deployments.count_documents({}),
        "websocket_connections": len(agent_ws_manager.active_connections),
        "supported_platforms": ["windows", "linux", "macos", "android", "ios"]
    }
    
    return stats


# ============================================================
# WEBSOCKET ENDPOINT
# ============================================================

@router.websocket("/ws/agent/{agent_id}")
async def websocket_agent_endpoint(websocket: WebSocket, agent_id: str):
    """WebSocket endpoint for real-time agent communication"""
    
    await agent_ws_manager.connect(agent_id, websocket)
    
    # Update agent status
    await db.unified_agents.update_one(
        {"agent_id": agent_id},
        {"$set": {"status": "online", "ws_connected": True}}
    )
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "heartbeat":
                # Update heartbeat
                await db.unified_agents.update_one(
                    {"agent_id": agent_id},
                    {"$set": {
                        "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                        "status": "online"
                    }}
                )
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            
            elif msg_type == "alert":
                # Store alert
                alert_data = data.get("data", {})
                alert_doc = _build_unified_alert_doc(
                    alert_id=secrets.token_hex(8),
                    agent_id=agent_id,
                    severity=alert_data.get("severity", "medium"),
                    category=alert_data.get("category", "unknown"),
                    message=alert_data.get("message", "Unknown alert"),
                    details=alert_data.get("details", {}),
                    mitre_technique=alert_data.get("mitre_technique"),
                    actor=f"agent:{agent_id}",
                    reason="alert received via websocket",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                await db.unified_alerts.insert_one(alert_doc)
                logger.warning(f"Alert from {agent_id}: {alert_data.get('message', 'Unknown')}")
            
            elif msg_type == "telemetry":
                # Store telemetry
                telemetry = data.get("data", {})
                await db.agent_telemetry.insert_one({
                    "agent_id": agent_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "telemetry": telemetry
                })
                # Run threat hunting
                await _hunt_telemetry(telemetry)
            
            elif msg_type == "command_result":
                # Store command result
                result = data.get("data", {})
                try:
                    await _finalize_agent_command_result(
                        command_id=result.get("command_id"),
                        status=result.get("status", "completed"),
                        result_payload=result,
                        transition_actor=f"agent:{agent_id}",
                        transition_reason="websocket command_result",
                    )
                except HTTPException:
                    # Commands can race with API completion; keep WS loop resilient.
                    pass
    
    except WebSocketDisconnect:
        agent_ws_manager.disconnect(agent_id)
        await db.unified_agents.update_one(
            {"agent_id": agent_id},
            {"$set": {"status": "offline", "ws_connected": False}}
        )


# ============================================================
# AGENT DOWNLOAD / INSTALL ENDPOINTS
# ============================================================

@router.get("/agent/download")
async def download_agent_package():
    """Download the unified agent package as a tarball"""
    import tarfile
    import io
    from fastapi.responses import StreamingResponse
    
    agent_dir = _agent_source_dir()
    
    # Create tarball in memory
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
        # The web dashboard imports ui/desktop/main.py to load the canonical agent core.
        for item in ['core', 'ui/web', 'ui/desktop', 'requirements.txt']:
            item_path = agent_dir / item
            if item_path.exists():
                tar.add(str(item_path), arcname=item)
    
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/gzip",
        headers={"Content-Disposition": "attachment; filename=seraph-agent.tar.gz"}
    )


@router.get("/agent/download/windows")
async def download_agent_package_windows():
    """Download the unified agent package as a ZIP archive for Windows installers."""
    import io
    import zipfile
    from fastapi.responses import StreamingResponse

    agent_dir = _agent_source_dir()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for item in ['core', 'ui/web', 'ui/desktop', 'requirements.txt']:
            item_path = agent_dir / item
            if not item_path.exists():
                continue

            if item_path.is_dir():
                for root, _, files in os.walk(str(item_path)):
                    for file_name in files:
                        full_path = Path(root) / file_name
                        arcname = str(full_path.relative_to(agent_dir))
                        zf.write(full_path, arcname=arcname)
            else:
                zf.write(item_path, arcname=item)

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=seraph-agent-windows.zip"}
    )


@router.get("/agent/download/android")
async def download_android_apk():
    """Download the built Android APK."""
    from fastapi.responses import FileResponse

    for apk_path in _artifact_paths("ui", "android", "seraph-agent-20260505.apk"):
        if apk_path.exists():
            return FileResponse(str(apk_path), media_type="application/vnd.android.package-archive", filename="seraph-agent-20260505.apk")
    for apk_path in _artifact_paths("ui", "android", "seraph-agent.apk"):
        if apk_path.exists():
            return FileResponse(str(apk_path), media_type="application/vnd.android.package-archive", filename="seraph-agent.apk")
    for apk_path in _artifact_paths("ui", "android", "app", "build", "outputs", "apk", "release", "app-release.apk"):
        if apk_path.exists():
            return FileResponse(str(apk_path), media_type="application/vnd.android.package-archive", filename="MetatronAgent.apk")
    for apk_path in _artifact_paths("ui", "android", "app", "build", "outputs", "apk", "debug", "app-debug.apk"):
        if apk_path.exists():
            return FileResponse(str(apk_path), media_type="application/vnd.android.package-archive", filename="MetatronAgent.apk")
    raise HTTPException(status_code=404, detail="Android APK not built. Run: cd unified_agent/ui/android && ./gradlew assembleDebug")


@router.get("/agent/install-script")
async def get_install_script(request: Request, server_url: Optional[str] = None, enrollment_key: Optional[str] = None, format: Optional[str] = None):
    """Get the agent installation script"""
    
    # Use explicit query param first; otherwise infer from request/proxy headers
    base_url = _infer_public_base_url(request, server_url)
    enrollment_arg = f' --enrollment-key "{enrollment_key}"' if enrollment_key else ""
    
    script = f'''#!/bin/bash
# Seraph AI Unified Agent Installer
# Automatically generated for: {base_url}

set -e

SERAPH_SERVER="{base_url}"
INSTALL_DIR="/opt/seraph-agent"
ENROLLMENT_KEY="{enrollment_key or ''}"

echo "================================================================"
echo "  SERAPH AI UNIFIED AGENT INSTALLER"
echo "  Target Server: $SERAPH_SERVER"
echo "================================================================"

# Check root
if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root (use sudo)"
    exit 1
fi

# Create installation directory
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# -----------------------------------------------------------------
# Detect distro family and install Python + build deps for psutil,
# cryptography, scapy, netifaces (these need a C compiler + headers).
# -----------------------------------------------------------------
LINUX_DEPS_APT=(python3 python3-pip python3-venv python3-dev build-essential libssl-dev libffi-dev curl openssl wireguard-tools nmap iproute2 net-tools libpcap-dev ca-certificates)
LINUX_DEPS_DNF=(python3 python3-pip python3-devel @"Development Tools" openssl-devel libffi-devel curl openssl wireguard-tools nmap iproute net-tools libpcap-devel ca-certificates)
LINUX_DEPS_PACMAN=(python python-pip base-devel openssl libffi curl wireguard-tools nmap iproute2 net-tools libpcap ca-certificates)
LINUX_DEPS_ZYPPER=(python3 python3-pip python3-devel gcc make openssl-devel libffi-devel curl openssl wireguard-tools nmap iproute2 net-tools libpcap-devel ca-certificates)
LINUX_DEPS_APK=(python3 py3-pip python3-dev build-base openssl-dev libffi-dev curl openssl wireguard-tools nmap iproute2 net-tools libpcap-dev ca-certificates)

echo "Installing Python and OS-level dependencies..."
if command -v apt-get >/dev/null 2>&1; then
    DEBIAN_FRONTEND=noninteractive apt-get update -y
    DEBIAN_FRONTEND=noninteractive apt-get install -y "${{LINUX_DEPS_APT[@]}}"
elif command -v dnf >/dev/null 2>&1; then
    dnf install -y "${{LINUX_DEPS_DNF[@]}}" || dnf install -y python3 python3-pip python3-devel gcc gcc-c++ make openssl-devel libffi-devel curl openssl nmap libpcap-devel
elif command -v yum >/dev/null 2>&1; then
    yum install -y python3 python3-pip python3-devel gcc gcc-c++ make openssl-devel libffi-devel curl openssl nmap libpcap-devel
elif command -v pacman >/dev/null 2>&1; then
    pacman -Sy --noconfirm "${{LINUX_DEPS_PACMAN[@]}}"
elif command -v zypper >/dev/null 2>&1; then
    zypper --non-interactive install "${{LINUX_DEPS_ZYPPER[@]}}"
elif command -v apk >/dev/null 2>&1; then
    apk add --no-cache "${{LINUX_DEPS_APK[@]}}"
else
    echo "[WARN] Unrecognized package manager. Continuing assuming Python 3 + build tools are present."
fi

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install required packages with build-from-source fallbacks
pip install --upgrade pip wheel setuptools
pip install psutil requests netifaces watchdog python-nmap aiohttp pyyaml flask flask-cors websockets cryptography || {{
    echo "[WARN] Falling back to --no-binary build for psutil/netifaces"
    pip install --no-binary :all: psutil netifaces || true
    pip install requests watchdog python-nmap aiohttp pyyaml flask flask-cors websockets cryptography
}}
# scapy is optional (raw sockets); skip silently if it fails to build.
pip install scapy || echo "[WARN] scapy install skipped"

# Download agent package
echo "Downloading agent from server..."
curl -fsSL -H "ngrok-skip-browser-warning: 1" "$SERAPH_SERVER/api/unified/agent/download" -o agent.tar.gz
tar -xzf agent.tar.gz
rm agent.tar.gz

# Best-effort install of the agent's bundled requirements.txt
if [[ -f requirements.txt ]]; then
    pip install -r requirements.txt || echo "[WARN] requirements.txt had partial failures; agent will still start"
fi

# Create a local self-signed agent identity certificate for the local dashboard.
mkdir -p "$INSTALL_DIR/certs"
if [[ ! -f "$INSTALL_DIR/certs/agent.crt" ]]; then
    openssl req -x509 -newkey rsa:4096 -sha256 -days 825 -nodes \
      -keyout "$INSTALL_DIR/certs/agent.key" \
      -out "$INSTALL_DIR/certs/agent.crt" \
      -subj "/CN=$(hostname)-seraph-agent/O=SeraphAI/OU=UnifiedAgent" >/dev/null 2>&1 || true
    chmod 600 "$INSTALL_DIR/certs/agent.key" 2>/dev/null || true
fi

# Create systemd service
cat > /etc/systemd/system/seraph-agent.service << EOF
[Unit]
Description=Seraph AI Unified Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
Environment="REMOTE_SERVER_URL=$SERAPH_SERVER"
Environment="BACKEND_URL=$SERAPH_SERVER"
Environment="SERAPH_ENROLLMENT_KEY={enrollment_key or ''}"
Environment="SERAPH_AGENT_CERT=$INSTALL_DIR/certs/agent.crt"
Environment="SERAPH_AGENT_KEY=$INSTALL_DIR/certs/agent.key"
ExecStart=$INSTALL_DIR/venv/bin/python ui/web/app.py --host 0.0.0.0 --port 5000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable seraph-agent
systemctl start seraph-agent

echo ""
echo "================================================================"
echo "  INSTALLATION COMPLETE"
echo "================================================================"
echo "Agent installed to: $INSTALL_DIR"
echo "Local dashboard: http://localhost:5000"
echo "Service status: systemctl status seraph-agent"
echo "Service logs: journalctl -u seraph-agent -f"
echo ""
'''
    
    usage = f"curl -sSL {base_url}/api/unified/agent/install-script | sudo bash"
    if (format or "").lower() == "json":
        return {"script": script, "usage": usage}

    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=script,
        media_type="text/x-shellscript",
        headers={"Content-Disposition": "attachment; filename=seraph-agent-install.sh", "X-Install-Usage": usage},
    )


@router.get("/agent/install-windows")
async def get_windows_install_script(request: Request, server_url: Optional[str] = None, enrollment_key: Optional[str] = None, format: Optional[str] = None):
    """Get the Windows agent installation script (PowerShell)"""
    
    base_url = _infer_public_base_url(request, server_url)
    enrollment_arg = f' --enrollment-key "{enrollment_key}"' if enrollment_key else ""
    
    script = f'''# Seraph AI Unified Agent - Windows Installer
# Run as Administrator

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$SERAPH_SERVER = "{base_url}"
$INSTALL_DIR = "C:\\ProgramData\\SeraphAgent"
$ZIP_PATH = "$INSTALL_DIR\\agent.zip"
$LOG_PATH = "$INSTALL_DIR\\install.log"

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  SERAPH AI UNIFIED AGENT INSTALLER (Windows)" -ForegroundColor Cyan
Write-Host "  Target Server: $SERAPH_SERVER" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

function Assert-Admin {{
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {{
        if ($PSCommandPath) {{
            Write-Host "Re-launching installer with Administrator privileges..." -ForegroundColor Yellow
            $argList = @(
                "-ExecutionPolicy", "Bypass",
                "-NoExit",
                "-File", "`"$PSCommandPath`""
            )
            Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList $argList
            exit 0
        }}
        throw "This installer must be run as Administrator."
    }}
}}

function Get-PythonExecutable {{
    if (Get-Command py -ErrorAction SilentlyContinue) {{ return "py -3" }}
    if (Get-Command python -ErrorAction SilentlyContinue) {{ return "python" }}
    return $null
}}

function Ensure-PythonInstalled {{
    $existing = Get-PythonExecutable
    if ($existing) {{ return $existing }}

    Write-Host "Python 3 not found. Attempting installation..." -ForegroundColor Yellow

    if (Get-Command winget -ErrorAction SilentlyContinue) {{
        try {{
            winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements --scope machine | Out-Null
        }} catch {{
            Write-Warning "winget Python install failed: $($_.Exception.Message)"
        }}
    }} elseif (Get-Command choco -ErrorAction SilentlyContinue) {{
        try {{ choco install -y python | Out-Null }} catch {{ Write-Warning "choco Python install failed: $($_.Exception.Message)" }}
    }} else {{
        # Fall back to direct Python.org installer download.
        try {{
            $pyInstaller = Join-Path $env:TEMP "python-3.12.6-amd64.exe"
            Invoke-WebRequest -UseBasicParsing -Uri "https://www.python.org/ftp/python/3.12.6/python-3.12.6-amd64.exe" -OutFile $pyInstaller
            Start-Process -FilePath $pyInstaller -ArgumentList "/quiet","InstallAllUsers=1","PrependPath=1","Include_pip=1","Include_launcher=1" -Wait
        }} catch {{
            Write-Warning "Direct Python installer download failed: $($_.Exception.Message)"
        }}
    }}

    # Refresh PATH for the current session so newly-installed py/python is visible.
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path","User")

    $resolved = Get-PythonExecutable
    if (-not $resolved) {{
        throw "Python 3 install did not complete. Please install Python 3 manually from https://www.python.org/downloads/ and re-run."
    }}
    return $resolved
}}

function Ensure-WireGuardInstalled {{
    $wgExe = "C:\\Program Files\\WireGuard\\wireguard.exe"
    if (Test-Path $wgExe) {{
        return $true
    }}

    Write-Host "WireGuard not found. Attempting installation via winget..." -ForegroundColor Yellow
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {{
        Write-Warning "winget not available; install WireGuard manually from https://www.wireguard.com/install/"
        return $false
    }}

    try {{
        winget install -e --id WireGuard.WireGuard --silent --accept-package-agreements --accept-source-agreements | Out-Null
    }} catch {{
        Write-Warning "Automatic WireGuard install failed: $($_.Exception.Message)"
        return $false
    }}

    Start-Sleep -Seconds 2
    if (Test-Path $wgExe) {{
        Write-Host "WireGuard installed successfully." -ForegroundColor Green
        return $true
    }}

    Write-Warning "WireGuard install completed but executable not found yet; VPN auto-start may require manual install verification."
    return $false
}}

$ngrokHeaders = @{{ "ngrok-skip-browser-warning" = "1" }}

try {{
    Assert-Admin

    New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null
    Start-Transcript -Path $LOG_PATH -Append | Out-Null

    # Create installation directory
    New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null
    Set-Location $INSTALL_DIR

    # Download agent (Windows ZIP variant)
    Write-Host "Downloading agent package..."
    Invoke-WebRequest -UseBasicParsing -Headers $ngrokHeaders -Uri "$SERAPH_SERVER/api/unified/agent/download/windows" -OutFile $ZIP_PATH

    # Extract
    Write-Host "Extracting package..."
    Expand-Archive -Path $ZIP_PATH -DestinationPath $INSTALL_DIR -Force
    Remove-Item $ZIP_PATH -Force

    $requiredFiles = @(
        [System.IO.Path]::Combine($INSTALL_DIR, "ui", "web", "app.py"),
        [System.IO.Path]::Combine($INSTALL_DIR, "ui", "desktop", "main.py"),
        [System.IO.Path]::Combine($INSTALL_DIR, "core", "agent.py")
    )
    foreach ($requiredFile in $requiredFiles) {{
        if (-not (Test-Path $requiredFile)) {{
            throw "Installer package is incomplete. Missing required file: $requiredFile"
        }}
    }}

    # Resolve Python executable, installing it via winget if absent.
    $pythonCmd = Ensure-PythonInstalled

    Write-Host "Installing Python dependencies..."
    cmd /c "$pythonCmd -m pip install --upgrade pip wheel setuptools"
    cmd /c "$pythonCmd -m pip install psutil requests netifaces watchdog pyyaml flask flask-cors aiohttp websockets cryptography pywin32"
    if (Test-Path (Join-Path $INSTALL_DIR "requirements.txt")) {{
        cmd /c "$pythonCmd -m pip install -r `"$INSTALL_DIR\\requirements.txt`""
    }}

    # Ensure WireGuard is available so the agent can auto-configure VPN on first registration.
    Ensure-WireGuardInstalled | Out-Null

    # ----------------------------------------------------------------
    # STEP: Register device with server NOW (before scheduled task).
    # This gives us agent_id + auth_token which are persisted so
    # the agent never needs an enrollment key again on restart.
    # ----------------------------------------------------------------
    $enrollmentKey = "{enrollment_key or ''}"
    $agentId = ("seraph-" + $env:COMPUTERNAME + "-" + [System.Guid]::NewGuid().ToString("N").Substring(0,8)).ToLower() -replace '[^a-z0-9-]','-'
    $primaryIp = try {{
        $s = [System.Net.Sockets.TcpClient]::new(); $s.Connect("8.8.8.8", 53); $s.Client.LocalEndPoint.Address.ToString()
    }} catch {{ "127.0.0.1" }}

    $regHeaders = @{{
        "ngrok-skip-browser-warning" = "1"
        "X-Enrollment-Key"           = $enrollmentKey
        "Content-Type"               = "application/json"
    }}
    $regBody = @{{
        agent_id     = $agentId
        node_id      = $agentId
        platform     = "windows"
        hostname     = $env:COMPUTERNAME
        ip_address   = $primaryIp
        version      = "1.0.0"
        capabilities = @("process_monitor","network_monitor","file_monitor","vpn")
        config       = @{{ auto_remediate = $false; is_admin = $true }}
    }} | ConvertTo-Json -Depth 4

    $authToken = ""
    Write-Host "Registering device with Seraph server..."
    try {{
        $regResp = Invoke-RestMethod -Uri "$SERAPH_SERVER/api/unified/agents/register" -Method POST -Headers $regHeaders -Body $regBody -ContentType "application/json"
        $authToken = $regResp.auth_token
        Write-Host "Device registered. Agent ID: $agentId" -ForegroundColor Green
    }} catch {{
        Write-Warning "Registration request failed: $($_.Exception.Message) -- agent will retry on first start."
    }}

    # Persist credentials so the agent reuses the same identity on every restart.
    $authJson = @{{ agent_id = $agentId; auth_token = $authToken }} | ConvertTo-Json
    $authJson | Set-Content -Path (Join-Path $INSTALL_DIR "agent_auth.json") -Encoding UTF8

    # ----------------------------------------------------------------
    # Create launcher: runs core/agent.py (register + heartbeat loop)
    # and the web dashboard (port 5000) in the same session.
    # ----------------------------------------------------------------
    $agentPy  = [System.IO.Path]::Combine($INSTALL_DIR, "core", "agent.py")
    $uiPy     = [System.IO.Path]::Combine($INSTALL_DIR, "ui", "web", "app.py")
    $launcher = Join-Path $INSTALL_DIR "start-seraph-agent.ps1"

    # NOTE: we write a plain literal here -- NO f-string interpolation inside the heredoc
    # for the variable names the launcher itself uses at runtime.
    $launcherContent = @"
`$ErrorActionPreference = "Continue"
`$env:REMOTE_SERVER_URL  = "$SERAPH_SERVER"
`$env:BACKEND_URL        = "$SERAPH_SERVER"
`$env:SERAPH_ENROLLMENT_KEY = "$enrollmentKey"
Set-Location "$INSTALL_DIR"

# Load persisted agent_id so the same identity is reused on every boot.
`$authFile = Join-Path "$INSTALL_DIR" "agent_auth.json"
`$savedId  = ""
if (Test-Path `$authFile) {{
    try {{
        `$savedData = Get-Content `$authFile -Raw | ConvertFrom-Json
        `$savedId   = `$savedData.agent_id
    }} catch {{ }}
}}
`$resolvedId = if (`$savedId) {{ `$savedId }} else {{ "seraph-`$env:COMPUTERNAME" }}

# Start web dashboard in a hidden background process.
`$uiProc = Start-Process -FilePath "powershell.exe" ``
    -ArgumentList "-ExecutionPolicy","Bypass","-NonInteractive","-Command",
                  "`& $pythonCmd ``"$uiPy``" --host 0.0.0.0 --port 5000" ``
    -WindowStyle Hidden -PassThru

# Run the core agent (registers with server + heartbeat/monitoring loop).
# This call blocks until the agent is stopped, keeping the scheduled task alive.
& $pythonCmd "$agentPy" --server "$SERAPH_SERVER" --enrollment-key "$enrollmentKey" --no-ui
"@
    $launcherContent | Set-Content -Path $launcher -Encoding UTF8

    # Create scheduled task to run at startup
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$launcher`"" -WorkingDirectory $INSTALL_DIR
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount
    Register-ScheduledTask -TaskName "SeraphAgent" -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null

    # Start agent immediately (don't wait for next reboot).
    Write-Host "Starting agent..."
    Start-ScheduledTask -TaskName "SeraphAgent"

    try {{ Stop-Transcript | Out-Null }} catch {{ }}
}} catch {{
    try {{ Stop-Transcript | Out-Null }} catch {{ }}
    Write-Host "INSTALL FAILED: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.InvocationInfo) {{
        Write-Host "FAILED AT: $($_.InvocationInfo.PositionMessage)" -ForegroundColor Yellow
    }}
    if ($_.Exception.StackTrace) {{
        Write-Host "STACK: $($_.Exception.StackTrace)" -ForegroundColor DarkYellow
    }}
    Write-Host "See log: $LOG_PATH" -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 1
}}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "  INSTALLATION COMPLETE" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Write-Host "Agent installed to : $INSTALL_DIR"
Write-Host "Agent ID           : $agentId"
Write-Host "Registered with    : $SERAPH_SERVER"
Write-Host "Local dashboard    : http://localhost:5000"
Write-Host "Credentials saved  : " + [System.IO.Path]::Combine($INSTALL_DIR, "agent_auth.json")
Write-Host ""
Write-Host "Check status  : Get-ScheduledTask -TaskName SeraphAgent | Format-List *"
Write-Host "Install log   : $LOG_PATH"
Read-Host "Press Enter to close"
'''
    
    usage = f"irm {base_url}/api/unified/agent/install-windows -Headers @{{'ngrok-skip-browser-warning'='1'}} | iex"
    if (format or "").lower() == "json":
        return {"script": script, "usage": usage}

    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=script,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=seraph-agent-install.ps1", "X-Install-Usage": usage},
    )


@router.get("/agent/install-macos")
async def get_macos_install_script(request: Request, server_url: Optional[str] = None, enrollment_key: Optional[str] = None, format: Optional[str] = None):
    """Get the macOS agent installation script"""
    
    base_url = _infer_public_base_url(request, server_url)
    
    script = f'''#!/bin/bash
# Seraph AI Unified Agent - macOS Installer

set -e

SERAPH_SERVER="{base_url}"
INSTALL_DIR="$HOME/Library/Application Support/SeraphAgent"
LAUNCH_AGENT_PATH="$HOME/Library/LaunchAgents/com.seraph.agent.plist"
ENROLLMENT_KEY="{enrollment_key or ''}"

echo "================================================================"
echo "  SERAPH AI UNIFIED AGENT INSTALLER (macOS)"
echo "  Target Server: $SERAPH_SERVER"
echo "================================================================"

# Create installation directory
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Resolve Homebrew prefix (Apple Silicon defaults to /opt/homebrew, Intel to /usr/local).
if [[ -x /opt/homebrew/bin/brew ]]; then
    BREW_BIN="/opt/homebrew/bin/brew"
elif [[ -x /usr/local/bin/brew ]]; then
    BREW_BIN="/usr/local/bin/brew"
else
    BREW_BIN="$(command -v brew || true)"
fi

# Ensure Xcode CLT (provides clang + headers needed for psutil/cryptography wheels).
if ! xcode-select -p >/dev/null 2>&1; then
    echo "Installing Xcode Command Line Tools (a dialog may appear; accept it and re-run if needed)..."
    xcode-select --install 2>/dev/null || true
fi

# Check for Python 3
if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 not found. Installing via Homebrew..."
    if [[ -z "$BREW_BIN" ]]; then
        echo "Homebrew not found. Installing Homebrew first..."
        NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        if [[ -x /opt/homebrew/bin/brew ]]; then
            BREW_BIN="/opt/homebrew/bin/brew"
        elif [[ -x /usr/local/bin/brew ]]; then
            BREW_BIN="/usr/local/bin/brew"
        fi
    fi
    "$BREW_BIN" install python@3.12 || "$BREW_BIN" install python3
fi

# Optional: install WireGuard tools so the agent can bring up its policy VPN.
if [[ -n "$BREW_BIN" ]] && ! command -v wg >/dev/null 2>&1; then
    "$BREW_BIN" install wireguard-tools || echo "[WARN] wireguard-tools install skipped"
fi

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies (cryptography wheel requires Xcode CLT which we ensured above).
pip install --upgrade pip wheel setuptools
pip install psutil requests netifaces watchdog pyyaml flask flask-cors aiohttp websockets cryptography
pip install scapy || echo "[WARN] scapy install skipped (raw sockets need root)"

# Download agent
echo "Downloading agent from server..."
curl -fsSL -H "ngrok-skip-browser-warning: 1" "$SERAPH_SERVER/api/unified/agent/download" -o agent.tar.gz
tar -xzf agent.tar.gz
rm agent.tar.gz

# Best-effort install of the agent's bundled requirements.txt
if [[ -f requirements.txt ]]; then
    pip install -r requirements.txt || echo "[WARN] requirements.txt had partial failures"
fi

# Create a local self-signed agent identity certificate for the local dashboard.
mkdir -p "$INSTALL_DIR/certs"
if [[ ! -f "$INSTALL_DIR/certs/agent.crt" ]]; then
    openssl req -x509 -newkey rsa:4096 -sha256 -days 825 -nodes \
      -keyout "$INSTALL_DIR/certs/agent.key" \
      -out "$INSTALL_DIR/certs/agent.crt" \
      -subj "/CN=$(hostname)-seraph-agent/O=SeraphAI/OU=UnifiedAgent" >/dev/null 2>&1 || true
    chmod 600 "$INSTALL_DIR/certs/agent.key" 2>/dev/null || true
fi

# Create LaunchAgent plist for auto-start
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$LAUNCH_AGENT_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.seraph.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>$INSTALL_DIR/venv/bin/python</string>
        <string>$INSTALL_DIR/ui/web/app.py</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>5000</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>REMOTE_SERVER_URL</key>
        <string>$SERAPH_SERVER</string>
        <key>BACKEND_URL</key>
        <string>$SERAPH_SERVER</string>
        <key>SERAPH_ENROLLMENT_KEY</key>
        <string>{enrollment_key or ''}</string>
        <key>SERAPH_AGENT_CERT</key>
        <string>$INSTALL_DIR/certs/agent.crt</string>
        <key>SERAPH_AGENT_KEY</key>
        <string>$INSTALL_DIR/certs/agent.key</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/agent.log</string>
    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/agent-error.log</string>
</dict>
</plist>
EOF

# Load the launch agent
launchctl load "$LAUNCH_AGENT_PATH"

echo ""
echo "================================================================"
echo "  INSTALLATION COMPLETE"
echo "================================================================"
echo "Agent installed to: $INSTALL_DIR"
echo "Local dashboard: http://localhost:5000"
echo "Logs: $INSTALL_DIR/agent.log"
echo "Stop: launchctl unload $LAUNCH_AGENT_PATH"
echo "Start: launchctl load $LAUNCH_AGENT_PATH"
'''
    
    usage = f"curl -sSL {base_url}/api/unified/agent/install-macos | bash"
    if (format or "").lower() == "json":
        return {"script": script, "usage": usage}

    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=script,
        media_type="text/x-shellscript",
        headers={"Content-Disposition": "attachment; filename=seraph-agent-install-macos.sh", "X-Install-Usage": usage},
    )


@router.get("/agent/install-android")
async def get_android_install_script(request: Request, server_url: Optional[str] = None, enrollment_key: Optional[str] = None, format: Optional[str] = None):
    """Get the Android agent installation script (Termux)"""
    
    base_url = _infer_public_base_url(request, server_url)
    enrollment_arg = f' --enrollment-key "{enrollment_key}"' if enrollment_key else ""
    
    script = f'''#!/data/data/com.termux/files/usr/bin/bash
# Seraph AI Unified Agent - Android Installer (Termux)
# Requires: Termux app from F-Droid (Play Store version has limitations)

set -e

SERAPH_SERVER="{base_url}"
INSTALL_DIR="$HOME/seraph-agent"
ENROLLMENT_KEY="{enrollment_key or ''}"

echo "================================================================"
echo "  SERAPH AI UNIFIED AGENT INSTALLER (Android/Termux)"
echo "  Target Server: $SERAPH_SERVER"
echo "================================================================"

# -----------------------------------------------------------------
# Storage permission so the agent can write logs/certs to a stable
# path. termux-setup-storage is a no-op if already granted.
# -----------------------------------------------------------------
if command -v termux-setup-storage >/dev/null 2>&1; then
    termux-setup-storage 2>/dev/null || true
fi

# Wake-lock so monitoring keeps running when the screen is off.
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock 2>/dev/null || true
fi

# Update packages
pkg update -y
pkg upgrade -y

# -----------------------------------------------------------------
# Install everything needed BEFORE pip wheel builds run.
# psutil + cryptography + netifaces + scapy all need: clang, make,
# libffi, openssl, rust (for cryptography), libxml2 (for some deps).
# python-psutil from the Termux repo is the safe fallback.
# -----------------------------------------------------------------
PKG_DEPS=(
    python python-pip
    clang make pkg-config
    libffi openssl libcrypt
    rust
    curl wget tar
    libjpeg-turbo
    nmap
    wireguard-tools
    termux-api
    python-cryptography
    python-psutil
)
for pkg in "${{PKG_DEPS[@]}}"; do
    pkg install -y "$pkg" || echo "[WARN] Optional Termux package '$pkg' could not be installed; continuing"
done

# Create installation directory
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Create virtual environment that can see Termux's pre-built python-psutil/cryptography wheels.
python -m venv --system-site-packages venv
source venv/bin/activate

# Build env so cryptography/cffi locate Termux's openssl/libffi headers.
export OPENSSL_DIR="$PREFIX"
export OPENSSL_LIB_DIR="$PREFIX/lib"
export OPENSSL_INCLUDE_DIR="$PREFIX/include"
export CARGO_BUILD_TARGET="$(uname -m)-linux-android"
export RUSTFLAGS="-C link-arg=-Wl,-rpath,$PREFIX/lib"
export LDFLAGS="-L$PREFIX/lib"
export CFLAGS="-I$PREFIX/include"

# Install Python packages
pip install --upgrade pip wheel setuptools

# psutil wheel build can fail on some Termux/Android combinations.
# Try pip first; if it fails, fall back to the Termux-provided python-psutil
# (already visible thanks to --system-site-packages).
if ! pip install psutil; then
    echo "[WARN] psutil pip wheel build failed; using Termux python-psutil fallback"
fi

# cryptography from pip can be slow because it builds Rust. Prefer the
# Termux package, only fall back to pip if importing fails.
python -c "import cryptography" 2>/dev/null || pip install cryptography || echo "[WARN] cryptography unavailable; some features will degrade"

pip install requests watchdog aiohttp pyyaml flask flask-cors websockets

# Download agent
echo "Downloading agent from server..."
curl -fsSL -H "ngrok-skip-browser-warning: 1" "$SERAPH_SERVER/api/unified/agent/download" -o agent.tar.gz
tar -xzf agent.tar.gz
rm agent.tar.gz

# Best-effort install of bundled requirements (skip lines we already covered).
if [ -f requirements.txt ]; then
    pip install -r requirements.txt || echo "[WARN] requirements.txt had partial failures; agent will still start"
fi

# Create a local self-signed agent identity certificate for the local dashboard.
mkdir -p "$INSTALL_DIR/certs"
if [ ! -f "$INSTALL_DIR/certs/agent.crt" ]; then
  openssl req -x509 -newkey rsa:2048 -sha256 -days 825 -nodes \
    -keyout "$INSTALL_DIR/certs/agent.key" \
    -out "$INSTALL_DIR/certs/agent.crt" \
    -subj "/CN=android-seraph-agent/O=SeraphAI/OU=UnifiedAgent" >/dev/null 2>&1 || true
  chmod 600 "$INSTALL_DIR/certs/agent.key" 2>/dev/null || true
fi

# Create startup script
BOOT_DIR="$HOME/.termux/boot"
BOOT_SCRIPT="$BOOT_DIR/start-seraph.sh"
mkdir -p "$BOOT_DIR"
cat > "$BOOT_SCRIPT" << EOF
#!/data/data/com.termux/files/usr/bin/bash
cd "$INSTALL_DIR"
source venv/bin/activate
export REMOTE_SERVER_URL="$SERAPH_SERVER"
export BACKEND_URL="$SERAPH_SERVER"
export SERAPH_ENROLLMENT_KEY="{enrollment_key or ''}"
nohup python ui/web/app.py --host 0.0.0.0 --port 5000 > agent.log 2>&1 &
EOF
chmod +x "$BOOT_SCRIPT"

# Create handy control script
cat > "$INSTALL_DIR/seraph-control.sh" << EOF
#!/data/data/com.termux/files/usr/bin/bash
case "\\$1" in
    start)
        cd "$INSTALL_DIR"
        source venv/bin/activate
        export REMOTE_SERVER_URL="$SERAPH_SERVER"
        export BACKEND_URL="$SERAPH_SERVER"
        export SERAPH_ENROLLMENT_KEY="{enrollment_key or ''}"
        nohup python ui/web/app.py --host 0.0.0.0 --port 5000 > agent.log 2>&1 &
        echo "Agent started"
        ;;
    stop)
        pkill -f "ui/web/app.py --host 0.0.0.0 --port 5000" || true
        echo "Agent stopped"
        ;;
    status)
        pgrep -f "ui/web/app.py --host 0.0.0.0 --port 5000" > /dev/null && echo "Running" || echo "Stopped"
        ;;
    logs)
        tail -f "$INSTALL_DIR/agent.log"
        ;;
    *)
        echo "Usage: seraph-control.sh {{start|stop|status|logs}}"
        ;;
esac
EOF
chmod +x "$INSTALL_DIR/seraph-control.sh"

# Start agent
source venv/bin/activate
export REMOTE_SERVER_URL="$SERAPH_SERVER"
export BACKEND_URL="$SERAPH_SERVER"
export SERAPH_ENROLLMENT_KEY="{enrollment_key or ''}"
nohup python ui/web/app.py --host 0.0.0.0 --port 5000 > agent.log 2>&1 &

echo ""
echo "================================================================"
echo "  INSTALLATION COMPLETE"
echo "================================================================"
echo "Agent installed to: $INSTALL_DIR"
echo "Local dashboard: http://127.0.0.1:5000"
echo "Control: $INSTALL_DIR/seraph-control.sh {{start|stop|status|logs}}"
echo ""
echo "NOTE: Enable Termux:Boot app for auto-start on device boot"
'''
    
    usage = f"curl -sSL {base_url}/api/unified/agent/install-android | bash"
    if (format or "").lower() == "json":
        return {"script": script, "usage": usage}

    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=script,
        media_type="text/x-shellscript",
        headers={"Content-Disposition": "attachment; filename=seraph-agent-install-android.sh", "X-Install-Usage": usage},
    )


@router.get("/agent/install-ios")
async def get_ios_install_instructions(request: Request, server_url: Optional[str] = None, enrollment_key: Optional[str] = None, format: Optional[str] = None):
    """Get iOS agent installation instructions (Pythonista or native app)"""

    base_url = _infer_public_base_url(request, server_url)
    enrollment_token = enrollment_key or os.environ.get("SERAPH_ENROLLMENT_KEY") or os.environ.get("ENROLLMENT_KEY") or AGENT_SECRET or ""

    pythonista_script = f'''# Seraph AI Agent for iOS (Pythonista 3)
# Pythonista 3 ships with: requests, json, uuid, platform, socket, time, threading,
# datetime, and `keychain` so this script needs ZERO additional installs.
#
# To run:
#   1. Open Pythonista 3 -> tap + -> Empty Script
#   2. Paste this entire file
#   3. Tap the play button
#
# The agent registers with the Seraph backend, sends a heartbeat every 60s,
# and polls for commands. Pythonista keeps the script alive while the app is
# in the foreground; for background heartbeat use the "Always Run" feature
# under "iOS Background Modes" in Pythonista's settings.

import json
import platform
import socket
import threading
import time
import uuid
from datetime import datetime

try:
    import requests  # bundled in Pythonista 3
except ImportError as exc:  # pragma: no cover
    raise SystemExit("This script must be run inside Pythonista 3 (requests is bundled).") from exc

# Pythonista has a `keychain` module for persistent secret storage.
try:
    import keychain  # type: ignore
except ImportError:  # pragma: no cover - non-Pythonista runtime
    keychain = None

SERAPH_SERVER = "{base_url}"
ENROLLMENT_KEY = "{enrollment_token}"
UPDATE_INTERVAL = 60

def _persist_agent_id(new_id: str) -> None:
    if keychain is None:
        return
    try:
        keychain.set_password("seraph_agent", "agent_id", new_id)
    except Exception:  # pragma: no cover
        pass

def _load_agent_id() -> str:
    if keychain is not None:
        try:
            existing = keychain.get_password("seraph_agent", "agent_id")
            if existing:
                return existing
        except Exception:  # pragma: no cover
            pass
    return f"ios-{{uuid.uuid4().hex[:8]}}"

AGENT_ID = _load_agent_id()
_persist_agent_id(AGENT_ID)
AUTH_TOKEN = ""

def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 53))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

class iOSAgent:
    def __init__(self) -> None:
        self.running = False
        self.agent_id = AGENT_ID

    def _headers(self):
        headers = {{"ngrok-skip-browser-warning": "1", "Content-Type": "application/json"}}
        if ENROLLMENT_KEY:
            headers["X-Enrollment-Key"] = ENROLLMENT_KEY
        if AUTH_TOKEN:
            headers["X-Agent-Token"] = AUTH_TOKEN
        return headers

    def get_system_info(self):
        return {{
            "hostname": socket.gethostname(),
            "platform": "ios",
            "version": platform.version(),
            "python": platform.python_version(),
        }}

    def register(self) -> bool:
        global AUTH_TOKEN
        try:
            response = requests.post(
                f"{{SERAPH_SERVER}}/api/unified/agents/register",
                json={{
                    "agent_id": self.agent_id,
                    "node_id": self.agent_id,
                    "platform": "ios",
                    "hostname": socket.gethostname(),
                    "ip_address": _local_ip(),
                    "version": "1.0.0",
                    "capabilities": ["monitor", "scan", "heartbeat", "command_poll"],
                    "config": {{"is_admin": False, "auto_remediate": False}},
                }},
                headers=self._headers(),
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            AUTH_TOKEN = data.get("auth_token", "") or AUTH_TOKEN
            print(f"Registered: agent_id={{self.agent_id}} status={{data.get('status')}}")
            return True
        except Exception as e:
            print(f"Registration failed: {{e}}")
            return False
    
    def heartbeat(self):
        try:
            requests.post(
                f"{{SERAPH_SERVER}}/api/unified/agents/{{self.agent_id}}/heartbeat",
                json={{
                    "status": "online",
                    "cpu_usage": 0,
                    "memory_usage": 0,
                    "timestamp": datetime.now().isoformat(),
                }},
                headers=self._headers(),
                timeout=10,
            )
            return True
        except Exception as e:
            print(f"Heartbeat failed: {{e}}")
            return False

    def poll_commands(self):
        try:
            response = requests.get(
                f"{{SERAPH_SERVER}}/api/unified/agents/{{self.agent_id}}/commands",
                headers=self._headers(),
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                for cmd in data.get("commands", []):
                    self.execute_command(cmd)
        except Exception as e:
            print(f"Command poll failed: {{e}}")

    def execute_command(self, cmd):
        cmd_type = cmd.get("command_type", "")
        print(f"Executing: {{cmd_type}}")

        result = {{"command_id": cmd.get("command_id"), "status": "completed", "result": {{}}}}

        if cmd_type == "get_status":
            result["result"] = self.get_system_info()

        try:
            requests.post(
                f"{{SERAPH_SERVER}}/api/unified/agents/{{self.agent_id}}/command-result",
                json=result,
                headers=self._headers(),
                timeout=10,
            )
        except Exception:
            pass
    
    def run(self):
        print(f"Starting iOS Agent: {{self.agent_id}}")
        self.running = True
        
        if not self.register():
            print("Failed to register. Retrying in 30s...")
            time.sleep(30)
            self.register()
        
        while self.running:
            self.heartbeat()
            self.poll_commands()
            time.sleep(UPDATE_INTERVAL)
    
    def stop(self):
        self.running = False
        print("Agent stopped")

# Run agent
agent = iOSAgent()

# For Pythonista, run in background
def start_background():
    thread = threading.Thread(target=agent.run, daemon=True)
    thread.start()
    print("Agent running in background")
    return thread

# Start agent
start_background()
'''

    usage = "Open in Pythonista 3 -> tap Run. The script needs ZERO additional installs."

    if (format or "").lower() in {"py", "script", "pythonista"}:
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            content=pythonista_script,
            media_type="text/x-python",
            headers={
                "Content-Disposition": "attachment; filename=seraph-agent-ios-pythonista.py",
                "X-Install-Usage": usage,
            },
        )

    return {
        "platform": "ios",
        "download_url": f"{base_url}/api/unified/agent/install-ios?format=py",
        "methods": [
            {
                "name": "Pythonista 3 App",
                "description": "Run agent as Python script in Pythonista 3 (no extra installs needed; requests + keychain are bundled)",
                "script": pythonista_script,
                "download_url": f"{base_url}/api/unified/agent/install-ios?format=py",
                "steps": [
                    "1. Install Pythonista 3 from the App Store",
                    "2. Tap the download link to save seraph-agent-ios-pythonista.py",
                    "3. Open it in Pythonista and tap the play button",
                    "4. Agent registers and begins heartbeating",
                ],
            },
            {
                "name": "Native SwiftUI App",
                "description": "Build and install the native iOS app",
                "steps": [
                    "1. Clone the repository",
                    "2. Open unified_agent/ui/ios/MetatronAgentApp.xcodeproj",
                    "3. Configure server URL in settings",
                    "4. Build and install on device (requires Apple Developer account)",
                ],
                "download_url": f"{base_url}/api/unified/agent/ios-source",
            },
        ],
    }


@router.get("/agent/installers")
async def get_all_installers(request: Request, server_url: Optional[str] = None):
    """Get installation info for all supported platforms"""
    
    forwarded_proto = request.headers.get("x-forwarded-proto")
    proto = forwarded_proto or request.url.scheme or "http"
    base_url = server_url or f"{proto}://{request.headers.get('host', 'localhost:8001')}"
    
    return {
        "server_url": base_url,
        "platforms": {
            "linux": {
                "name": "Linux",
                "icon": "🐧",
                "endpoint": f"{base_url}/api/unified/agent/install-script",
                "install_command": f"curl -sSL {base_url}/api/unified/agent/install-script | sudo bash",
                "requirements": ["Python 3.8+", "Root access", "systemd"]
            },
            "windows": {
                "name": "Windows",
                "icon": "🪟",
                "endpoint": f"{base_url}/api/unified/agent/install-windows",
                "install_command": f"Invoke-WebRequest -Headers @{{'ngrok-skip-browser-warning'='1'}} -Uri {base_url}/api/unified/agent/install-windows | Invoke-Expression",
                "requirements": ["Python 3.8+", "Administrator access", "PowerShell 5+"]
            },
            "macos": {
                "name": "macOS",
                "icon": "🍎",
                "endpoint": f"{base_url}/api/unified/agent/install-macos",
                "install_command": f"curl -sSL {base_url}/api/unified/agent/install-macos | bash",
                "requirements": ["Python 3.8+ (via Homebrew)", "User account"]
            },
            "android": {
                "name": "Android",
                "icon": "🤖",
                "endpoint": f"{base_url}/api/unified/agent/install-android",
                "install_command": f"curl -sSL {base_url}/api/unified/agent/install-android | bash",
                "requirements": ["Termux app from F-Droid", "Termux:Boot (optional, for auto-start)"]
            },
            "ios": {
                "name": "iOS",
                "icon": "📱",
                "endpoint": f"{base_url}/api/unified/agent/install-ios",
                "methods": ["Pythonista 3", "Native SwiftUI App"],
                "requirements": ["Pythonista 3 app OR Xcode + Apple Developer account"]
            }
        }
    }


# ============================================================
# HELPER FUNCTIONS
# ============================================================

async def _process_agent_alert(agent_id: str, alert_data: Dict):
    """Process an alert from an agent"""

    await db.unified_alerts.insert_one(
        _build_unified_alert_doc(
            alert_id=secrets.token_hex(8),
            agent_id=agent_id,
            severity=alert_data.get("severity", "medium"),
            category=alert_data.get("category", "unknown"),
            message=alert_data.get("message", "Unknown alert"),
            details=alert_data.get("details", {}),
            mitre_technique=alert_data.get("mitre_technique"),
            actor=f"agent:{agent_id}",
            reason="alert processed from heartbeat",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    )
    
    # Update agent alert count
    await db.unified_agents.update_one(
        {"agent_id": agent_id},
        {"$inc": {"alerts_count": 1}}
    )


async def _process_agent_edm_hit(agent_id: str, hit_data: Dict[str, Any], agent_doc: Optional[Dict[str, Any]] = None):
    """Persist EDM hit telemetry for centralized analytics."""
    if not hit_data.get("dataset_id") or not hit_data.get("fingerprint"):
        return

    now = datetime.now(timezone.utc).isoformat()
    path_masked = hit_data.get("file_path_masked")
    if not path_masked and hit_data.get("file_path"):
        raw_path = str(hit_data.get("file_path"))
        path_masked = f".../{os.path.basename(raw_path)}#{hashlib.sha256(raw_path.encode('utf-8')).hexdigest()[:12]}"

    await db[EDM_HITS_COLLECTION].insert_one({
        "agent_id": agent_id,
        "dataset_id": str(hit_data.get("dataset_id")),
        "record_id": hit_data.get("record_id"),
        "fingerprint": str(hit_data.get("fingerprint")),
        "host": hit_data.get("host") or (agent_doc or {}).get("hostname"),
        "process": hit_data.get("process") or "unknown",
        "file_path_masked": path_masked,
        "source": hit_data.get("source") or "unknown",
        "match_confidence": hit_data.get("match_confidence"),
        "match_candidate_type": hit_data.get("match_candidate_type"),
        "match_variant_type": hit_data.get("match_variant_type"),
        "agent_platform": (agent_doc or {}).get("platform"),
        "timestamp": hit_data.get("timestamp") or now,
        "ingested_at": now,
    })

    await db.unified_agents.update_one(
        {"agent_id": agent_id},
        {
            "$inc": {"edm_hits_count": 1},
            "$set": {"edm_last_hit_at": now},
        },
    )


async def _execute_rollout_rollback(rollout: Dict[str, Any], reason: str, triggered_by: str) -> Dict[str, Any]:
    dataset_id = rollout.get("dataset_id")
    rollback_version = rollout.get("previous_version")
    applied_ids = rollout.get("applied_agent_ids") or []

    if rollback_version is None:
        return {"rolled_back": False, "reason": "No previous_version available"}

    doc = await db[EDM_DATASET_COLLECTION].find_one(
        {"dataset_id": dataset_id, "version": int(rollback_version)},
        {"_id": 0},
    )
    if not doc:
        return {"rolled_back": False, "reason": "Rollback dataset version not found"}

    targets = EDMBulkTargetModel(agent_ids=applied_ids, online_only=False)
    fanout = await _dispatch_edm_dataset_to_targets(
        dataset=doc.get("dataset", {}),
        edm_meta=_build_edm_meta(doc),
        targets=targets,
        priority="critical",
        issued_by=triggered_by,
    )

    finalize = await db[EDM_ROLLOUT_COLLECTION].update_one(
        {
            "rollout_id": rollout.get("rollout_id"),
            "status": {"$in": ["active", "completed", "rolling_back"]},
        },
        {
            "$set": {
                "status": "rolled_back",
                "rolled_back_at": datetime.now(timezone.utc).isoformat(),
                "rollback_reason": reason,
                "rollback_triggered_by": triggered_by,
                "rollback_version": rollback_version,
                "rollback_fanout": fanout,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            "$inc": {"state_version": 1},
            "$push": {
                "state_transition_log": {
                    "from_status": ["active", "completed", "rolling_back"],
                    "to_status": "rolled_back",
                    "actor": triggered_by,
                    "reason": reason,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "metadata": {"rollback_version": rollback_version},
                }
            },
        },
    )
    if getattr(finalize, "matched_count", 0) == 0:
        existing = await db[EDM_ROLLOUT_COLLECTION].find_one(
            {"rollout_id": rollout.get("rollout_id")},
            {"_id": 0, "status": 1, "rollback_version": 1, "rollback_fanout": 1},
        )
        if existing and existing.get("status") == "rolled_back":
            return {
                "rolled_back": True,
                "rollback_version": existing.get("rollback_version", rollback_version),
                "fanout": existing.get("rollback_fanout", fanout),
            }
        return {"rolled_back": False, "reason": "Rollout state changed during rollback finalize"}
    return {"rolled_back": True, "rollback_version": rollback_version, "fanout": fanout}


async def _evaluate_active_edm_rollouts(agent_id: str):
    """Evaluate anomaly rate spikes for active EDM rollouts and auto-rollback when needed."""
    await _ensure_edm_indexes()
    active_rollouts = await db[EDM_ROLLOUT_COLLECTION].find(
        {
            "status": "active",
            "applied_agent_ids": {"$in": [agent_id]},
            "policy.auto_rollback": True,
        },
        {"_id": 0},
    ).to_list(100)

    for rollout in active_rollouts:
        readiness = await _compute_rollout_readiness(rollout)
        if not readiness.get("has_spike"):
            continue

        reason = (
            "Anomaly spike detected: "
            f"cohort_rate={readiness['cohort']['rate_per_agent_min']:.4f}/agent/min "
            f"control_rate={readiness['control']['rate_per_agent_min']:.4f}/agent/min "
            f"threshold={readiness['threshold']['rate_per_agent_min']:.4f}"
        )
        try:
            claimed = await _claim_rollout_for_rollback(
                rollout_id=rollout.get("rollout_id"),
                reason=reason,
                requested_by="system:auto-rollback",
                allowed_statuses=["active"],
            )
        except HTTPException:
            # Another worker likely claimed or transitioned this rollout.
            continue

        rollback = await _execute_rollout_rollback(claimed, reason, "system:auto-rollback")
        logger.warning(
            "EDM rollout auto-rollback executed for %s: %s (result=%s)",
            rollout.get("rollout_id"),
            reason,
            rollback,
        )


async def _hunt_telemetry(telemetry: Dict):
    """Run threat hunting on telemetry data"""
    try:
        from services.threat_hunting import threat_hunting_engine
        from dataclasses import asdict
        
        matches = threat_hunting_engine.hunt_all(telemetry)
        
        if matches:
            # Store matches
            for match in matches:
                await db.hunting_matches.insert_one(asdict(match))
            
            logger.info(f"Threat hunting found {len(matches)} matches")
    except Exception as e:
        logger.error(f"Threat hunting error: {e}")


async def _sync_unified_deployment_status(deployment: Dict[str, Any]):
    """Sync unified deployment status from underlying deployment task state."""
    task_id = deployment.get("deployment_task_id")
    if not task_id:
        return

    task_doc = await db.deployment_tasks.find_one({"task_id": task_id}, {"_id": 0})
    if not task_doc:
        return

    task_status = task_doc.get("status")
    simulated = bool(task_doc.get("simulated", False))
    error_message = task_doc.get("error_message")
    current_status = deployment.get("status")

    if task_status == "deployed" and current_status != "completed":
        await _transition_unified_deployment_state(
            deployment_id=deployment["deployment_id"],
            expected_statuses=["pending", "processing", "queued", "running"],
            next_status="completed",
            extra_updates={
                "simulated": simulated,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
            deployment_task_id=task_id,
            transition_reason="task reached deployed",
        )
    elif task_status == "failed" and current_status != "failed":
        await _transition_unified_deployment_state(
            deployment_id=deployment["deployment_id"],
            expected_statuses=["pending", "processing", "queued", "running"],
            next_status="failed",
            extra_updates={
                "error": error_message or "Deployment failed",
                "failed_at": datetime.now(timezone.utc).isoformat(),
            },
            deployment_task_id=task_id,
            transition_reason="task reached failed",
        )
    elif task_status in {"pending", "deploying"} and current_status not in {"running", "queued"}:
        await _transition_unified_deployment_state(
            deployment_id=deployment["deployment_id"],
            expected_statuses=["pending", "processing", "queued"],
            next_status="running",
            extra_updates={"last_checked_at": datetime.now(timezone.utc).isoformat()},
            deployment_task_id=task_id,
            transition_reason="task in progress",
        )


async def _process_deployment(deployment_id: str, deployment: DeploymentRequestModel):
    """Process a deployment in the background"""
    
    try:
        claimed = await _transition_unified_deployment_state(
            deployment_id=deployment_id,
            expected_statuses=["pending"],
            next_status="processing",
            extra_updates={"started_at": datetime.now(timezone.utc).isoformat()},
            transition_actor="system:deployment-worker",
            transition_reason="deployment worker claimed job",
        )
        if not claimed:
            logger.warning("Deployment %s was already claimed or transitioned by another worker", deployment_id)
            return

        from services.agent_deployment import get_deployment_service, start_deployment_service

        service = get_deployment_service()
        if service is None:
            import os
            api_url = os.environ.get('API_URL', 'http://localhost:8001')
            service = await start_deployment_service(db, api_url)

        task_id = await service.queue_deployment(
            device_ip=deployment.target_ip,
            device_hostname=None,
            os_type=deployment.target_platform,
            credentials=deployment.credentials
        )

        claimed_queue = await _transition_unified_deployment_state(
            deployment_id=deployment_id,
            expected_statuses=["processing"],
            next_status="queued",
            extra_updates={
                "deployment_task_id": task_id,
                "queued_at": datetime.now(timezone.utc).isoformat(),
            },
            transition_actor="system:deployment-worker",
            transition_reason="deployment task queued",
            transition_metadata={"deployment_task_id": task_id},
        )
        if not claimed_queue:
            logger.warning("Deployment %s queue transition lost due to concurrent update", deployment_id)
            return

        final_status = None
        simulated = False
        error_message = None

        for _ in range(120):
            task_doc = await db.deployment_tasks.find_one({"task_id": task_id}, {"_id": 0})
            if task_doc:
                task_status = task_doc.get("status")
                simulated = bool(task_doc.get("simulated", False))
                error_message = task_doc.get("error_message")
                if task_status in {"deployed", "failed"}:
                    final_status = task_status
                    break
            await asyncio.sleep(2)

        if final_status == "deployed":
            await _transition_unified_deployment_state(
                deployment_id=deployment_id,
                expected_statuses=["queued", "running", "processing"],
                next_status="completed",
                extra_updates={
                    "simulated": simulated,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                },
                deployment_task_id=task_id,
                transition_actor="system:deployment-worker",
                transition_reason="deployment task completed",
                transition_metadata={"deployment_task_id": task_id, "simulated": simulated},
            )
            logger.info(f"Deployment {deployment_id} completed (task={task_id}, simulated={simulated})")
        elif final_status == "failed":
            await _transition_unified_deployment_state(
                deployment_id=deployment_id,
                expected_statuses=["queued", "running", "processing"],
                next_status="failed",
                extra_updates={
                    "error": error_message or "Deployment failed",
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                },
                deployment_task_id=task_id,
                transition_actor="system:deployment-worker",
                transition_reason="deployment task failed",
                transition_metadata={"deployment_task_id": task_id},
            )
            logger.error(f"Deployment {deployment_id} failed (task={task_id}): {error_message}")
        else:
            await _transition_unified_deployment_state(
                deployment_id=deployment_id,
                expected_statuses=["queued", "processing"],
                next_status="running",
                extra_updates={
                    "deployment_task_id": task_id,
                    "last_checked_at": datetime.now(timezone.utc).isoformat(),
                },
                deployment_task_id=task_id,
                transition_actor="system:deployment-worker",
                transition_reason="deployment task still running",
                transition_metadata={"deployment_task_id": task_id},
            )
            logger.info(f"Deployment {deployment_id} still running (task={task_id})")
        
    except Exception as e:
        await _transition_unified_deployment_state(
            deployment_id=deployment_id,
            expected_statuses=["pending", "processing", "queued", "running"],
            next_status="failed",
            extra_updates={
                "error": str(e),
                "failed_at": datetime.now(timezone.utc).isoformat(),
            },
            transition_actor="system:deployment-worker",
            transition_reason="deployment worker exception",
            transition_metadata={"exception": str(e)},
        )
        logger.error(f"Deployment {deployment_id} failed: {e}")


# ============================================================================
# MONITOR TELEMETRY ENDPOINTS
# ============================================================================

@router.get("/agents/{agent_id}/monitors")
async def get_agent_monitors(
    agent_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all monitor summaries for an agent."""
    agent = await db.unified_agents.find_one({"agent_id": agent_id})
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    monitors_summary = agent.get("monitors_summary", {})
    
    # Get latest detailed telemetry for each monitor
    latest_telemetry = await db.agent_monitor_telemetry.find_one(
        {"agent_id": agent_id},
        sort=[("timestamp", -1)]
    )
    
    return {
        "agent_id": agent_id,
        "monitors_summary": monitors_summary,
        "latest_telemetry": latest_telemetry.get("monitors") if latest_telemetry else None,
        "last_updated": agent.get("last_heartbeat")
    }


@router.get("/agents/{agent_id}/monitors/{monitor_name}")
async def get_agent_monitor_history(
    agent_id: str,
    monitor_name: str,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """Get historical telemetry for a specific monitor."""
    valid_monitors = [
        "registry", "process_tree", "lolbin", "code_signing", "dns",
        "memory", "app_whitelist", "dlp", "vulnerability", "amsi"
    ]
    
    if monitor_name not in valid_monitors:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid monitor name. Valid monitors: {valid_monitors}"
        )
    
    # Fetch historical telemetry for this monitor
    cursor = db.agent_monitor_telemetry.find(
        {"agent_id": agent_id, f"monitors.{monitor_name}": {"$exists": True}},
        {f"monitors.{monitor_name}": 1, "timestamp": 1, "_id": 0}
    ).sort("timestamp", -1).limit(limit)
    
    history = []
    async for doc in cursor:
        if doc.get("monitors", {}).get(monitor_name):
            history.append({
                "timestamp": doc.get("timestamp"),
                "data": doc["monitors"][monitor_name]
            })
    
    return {
        "agent_id": agent_id,
        "monitor": monitor_name,
        "history": history,
        "count": len(history)
    }


@router.get("/stats/monitors")
async def get_monitors_aggregate_stats(
    current_user: dict = Depends(get_current_user)
):
    """Get aggregate monitor statistics across all agents."""
    # Aggregate monitor stats across all agents
    pipeline = [
        {"$match": {"monitors_summary": {"$exists": True}}},
        {"$group": {
            "_id": None,
            "total_agents": {"$sum": 1},
            "registry_alerts": {"$sum": {"$ifNull": ["$monitors_summary.registry.alerts", 0]}},
            "registry_persistence": {"$sum": {"$ifNull": ["$monitors_summary.registry.persistence_locations", 0]}},
            "process_tree_anomalies": {"$sum": {"$ifNull": ["$monitors_summary.process_tree.anomalies", 0]}},
            "lolbin_detections": {"$sum": {"$ifNull": ["$monitors_summary.lolbin.detections", 0]}},
            "unsigned_binaries": {"$sum": {"$ifNull": ["$monitors_summary.code_signing.unsigned", 0]}},
            "dns_alerts": {"$sum": {"$ifNull": ["$monitors_summary.dns.alerts", 0]}},
            "dga_detections": {"$sum": {"$ifNull": ["$monitors_summary.dns.dga_detected", 0]}},
            "memory_injections": {"$sum": {"$ifNull": ["$monitors_summary.memory.injections", 0]}},
            "rwx_regions": {"$sum": {"$ifNull": ["$monitors_summary.memory.rwx_regions", 0]}},
            "whitelist_violations": {"$sum": {"$ifNull": ["$monitors_summary.app_whitelist.violations", 0]}},
            "dlp_alerts": {"$sum": {"$ifNull": ["$monitors_summary.dlp.total_alerts", 0]}},
            "vulnerabilities_critical": {"$sum": {"$ifNull": ["$monitors_summary.vulnerability.critical", 0]}},
            "vulnerabilities_high": {"$sum": {"$ifNull": ["$monitors_summary.vulnerability.high", 0]}},
            "amsi_threats": {"$sum": {"$ifNull": ["$monitors_summary.amsi.threats_detected", 0]}},
            # New monitors - Ransomware
            "canary_alerts": {"$sum": {"$ifNull": ["$monitors_summary.ransomware.canary_alerts", 0]}},
            "shadow_copy_attempts": {"$sum": {"$ifNull": ["$monitors_summary.ransomware.shadow_copy_threats", 0]}},
            "entropy_alerts": {"$sum": {"$ifNull": ["$monitors_summary.ransomware.entropy_alerts", 0]}},
            # New monitors - Rootkit
            "hidden_processes": {"$sum": {"$ifNull": ["$monitors_summary.rootkit.hidden_processes", 0]}},
            "kernel_module_threats": {"$sum": {"$ifNull": ["$monitors_summary.rootkit.kernel_module_threats", 0]}},
            "dkom_detections": {"$sum": {"$ifNull": ["$monitors_summary.rootkit.dkom_detections", 0]}},
            # New monitors - Kernel Security
            "syscall_anomalies": {"$sum": {"$ifNull": ["$monitors_summary.kernel_security.syscall_anomalies", 0]}},
            "ptrace_detections": {"$sum": {"$ifNull": ["$monitors_summary.kernel_security.ptrace_detections", 0]}},
            "audit_log_alerts": {"$sum": {"$ifNull": ["$monitors_summary.kernel_security.audit_alerts", 0]}},
            # New monitors - Self Protection
            "tamper_events": {"$sum": {"$ifNull": ["$monitors_summary.self_protection.tamper_events", 0]}},
            "debug_attempts": {"$sum": {"$ifNull": ["$monitors_summary.self_protection.debug_attempts", 0]}},
            "injection_attempts": {"$sum": {"$ifNull": ["$monitors_summary.self_protection.injection_attempts", 0]}},
            # New monitors - Identity Protection  
            "credential_tools": {"$sum": {"$ifNull": ["$monitors_summary.identity.credential_tools_detected", 0]}},
            "lsass_access": {"$sum": {"$ifNull": ["$monitors_summary.identity.lsass_access_events", 0]}},
            "kerberos_anomalies": {"$sum": {"$ifNull": ["$monitors_summary.identity.kerberos_anomalies", 0]}},
            # ============================================
            # NEW MONITORS - Unified Agent v2.0
            # ============================================
            # Trusted AI Detection
            "trusted_ai_violations": {"$sum": {"$ifNull": ["$monitors_summary.trusted_ai.violations", 0]}},
            "untrusted_models": {"$sum": {"$ifNull": ["$monitors_summary.trusted_ai.untrusted_models", 0]}},
            "ai_processes": {"$sum": {"$ifNull": ["$monitors_summary.trusted_ai.total_processes", 0]}},
            # Bootkit Detection
            "bootkit_threats": {"$sum": {"$ifNull": ["$monitors_summary.bootkit.threats_detected", 0]}},
            "mbr_anomalies": {"$sum": {"$ifNull": ["$monitors_summary.bootkit.mbr_threats", 0]}},
            "uefi_violations": {"$sum": {"$ifNull": ["$monitors_summary.bootkit.uefi_violations", 0]}},
            # Certificate Authority Monitor
            "rogue_ca_certs": {"$sum": {"$ifNull": ["$monitors_summary.certificate_authority.rogue_certs", 0]}},
            "untrusted_roots": {"$sum": {"$ifNull": ["$monitors_summary.certificate_authority.untrusted_roots", 0]}},
            # BIOS/UEFI Security
            "bios_threats": {"$sum": {"$ifNull": ["$monitors_summary.bios_uefi.threats_detected", 0]}},
            "secure_boot_disabled": {"$sum": {"$ifNull": ["$monitors_summary.bios_uefi.secure_boot_disabled", 0]}},
            # Scheduled Task Monitor
            "suspicious_tasks": {"$sum": {"$ifNull": ["$monitors_summary.scheduled_task.suspicious_count", 0]}},
            "hidden_tasks": {"$sum": {"$ifNull": ["$monitors_summary.scheduled_task.hidden_tasks", 0]}},
            # Service Integrity Monitor
            "suspicious_services": {"$sum": {"$ifNull": ["$monitors_summary.service_integrity.suspicious_count", 0]}},
            "service_dll_hijacks": {"$sum": {"$ifNull": ["$monitors_summary.service_integrity.dll_hijacks", 0]}},
            # WMI Persistence Monitor
            "wmi_consumers": {"$sum": {"$ifNull": ["$monitors_summary.wmi_persistence.suspicious_consumers", 0]}},
            "wmi_subscriptions": {"$sum": {"$ifNull": ["$monitors_summary.wmi_persistence.malicious_subscriptions", 0]}},
            # USB Device Monitor
            "usb_violations": {"$sum": {"$ifNull": ["$monitors_summary.usb_device.violations", 0]}},
            "unauthorized_usb": {"$sum": {"$ifNull": ["$monitors_summary.usb_device.unauthorized_devices", 0]}},
            # Power State Monitor
            "power_anomalies": {"$sum": {"$ifNull": ["$monitors_summary.power_state.anomalies", 0]}},
            "wake_on_lan_events": {"$sum": {"$ifNull": ["$monitors_summary.power_state.wol_events", 0]}},
            # AutoThrottle Monitor
            "throttled_processes": {"$sum": {"$ifNull": ["$monitors_summary.auto_throttle.throttled_count", 0]}},
            "cryptominers": {"$sum": {"$ifNull": ["$monitors_summary.auto_throttle.cryptominers_detected", 0]}},
            # Firewall Monitor
            "firewall_disabled": {"$sum": {"$ifNull": ["$monitors_summary.firewall.disabled_count", 0]}},
            "firewall_rules": {"$sum": {"$ifNull": ["$monitors_summary.firewall.suspicious_rules", 0]}},
            # WebView2 Monitor
            "webview2_suspicious": {"$sum": {"$ifNull": ["$monitors_summary.webview2.suspicious_instances", 0]}},
            "webview2_debug": {"$sum": {"$ifNull": ["$monitors_summary.webview2.remote_debug_active", 0]}},
            # CLI Telemetry
            "cli_commands": {"$sum": {"$ifNull": ["$monitors_summary.cli_telemetry.commands_captured", 0]}},
            "cli_lolbins": {"$sum": {"$ifNull": ["$monitors_summary.cli_telemetry.lolbin_executions", 0]}},
            # Hidden File Scanner
            "hidden_files": {"$sum": {"$ifNull": ["$monitors_summary.hidden_file.hidden_count", 0]}},
            "ads_found": {"$sum": {"$ifNull": ["$monitors_summary.hidden_file.ads_streams", 0]}},
            # Alias/Rename Monitor
            "renamed_exes": {"$sum": {"$ifNull": ["$monitors_summary.alias_rename.renamed_executables", 0]}},
            "path_hijacks": {"$sum": {"$ifNull": ["$monitors_summary.alias_rename.path_hijack_risks", 0]}},
            # Privilege Escalation
            "dangerous_privs": {"$sum": {"$ifNull": ["$monitors_summary.privilege_escalation.dangerous_privileges", 0]}},
            "system_processes": {"$sum": {"$ifNull": ["$monitors_summary.privilege_escalation.system_processes", 0]}},
            "system_tasks": {"$sum": {"$ifNull": ["$monitors_summary.privilege_escalation.non_ms_system_tasks", 0]}}
        }}
    ]
    
    result = await db.unified_agents.aggregate(pipeline).to_list(1)
    
    if not result:
        return {
            "total_agents": 0,
            "monitors": {}
        }
    
    stats = result[0]
    del stats["_id"]
    
    # Organize into categories
    return {
        "total_agents_with_monitors": stats.pop("total_agents", 0),
        "threat_summary": {
            "registry_persistence": stats.get("registry_persistence", 0),
            "process_anomalies": stats.get("process_tree_anomalies", 0),
            "lolbin_abuse": stats.get("lolbin_detections", 0),
            "memory_injections": stats.get("memory_injections", 0),
            "dga_domains": stats.get("dga_detections", 0),
            "amsi_threats": stats.get("amsi_threats", 0),
            # Ransomware
            "canary_alerts": stats.get("canary_alerts", 0),
            "shadow_copy_attempts": stats.get("shadow_copy_attempts", 0),
            "entropy_alerts": stats.get("entropy_alerts", 0),
            # Rootkit
            "hidden_processes": stats.get("hidden_processes", 0),
            "kernel_module_threats": stats.get("kernel_module_threats", 0),
            "dkom_detections": stats.get("dkom_detections", 0),
            # Kernel Security
            "syscall_anomalies": stats.get("syscall_anomalies", 0),
            "ptrace_detections": stats.get("ptrace_detections", 0),
            "audit_log_alerts": stats.get("audit_log_alerts", 0),
            # Self Protection
            "tamper_events": stats.get("tamper_events", 0),
            "debug_attempts": stats.get("debug_attempts", 0),
            "injection_attempts": stats.get("injection_attempts", 0),
            # Identity Protection
            "credential_tools": stats.get("credential_tools", 0),
            "lsass_access": stats.get("lsass_access", 0),
            "kerberos_anomalies": stats.get("kerberos_anomalies", 0),
            # ============================================
            # NEW MONITORS - Unified Agent v2.0
            # ============================================
            # Trusted AI Detection
            "trusted_ai_violations": stats.get("trusted_ai_violations", 0),
            "untrusted_models": stats.get("untrusted_models", 0),
            "ai_processes": stats.get("ai_processes", 0),
            # Bootkit Detection
            "bootkit_threats": stats.get("bootkit_threats", 0),
            "mbr_anomalies": stats.get("mbr_anomalies", 0),
            "uefi_violations": stats.get("uefi_violations", 0),
            # Certificate Authority Monitor
            "rogue_ca_certs": stats.get("rogue_ca_certs", 0),
            "untrusted_roots": stats.get("untrusted_roots", 0),
            # BIOS/UEFI Security
            "bios_threats": stats.get("bios_threats", 0),
            "secure_boot_disabled": stats.get("secure_boot_disabled", 0),
            # Scheduled Task Monitor
            "suspicious_tasks": stats.get("suspicious_tasks", 0),
            "hidden_tasks": stats.get("hidden_tasks", 0),
            # Service Integrity Monitor
            "suspicious_services": stats.get("suspicious_services", 0),
            "service_dll_hijacks": stats.get("service_dll_hijacks", 0),
            # WMI Persistence Monitor
            "wmi_consumers": stats.get("wmi_consumers", 0),
            "wmi_subscriptions": stats.get("wmi_subscriptions", 0),
            # USB Device Monitor
            "usb_violations": stats.get("usb_violations", 0),
            "unauthorized_usb": stats.get("unauthorized_usb", 0),
            # Power State Monitor
            "power_anomalies": stats.get("power_anomalies", 0),
            "wake_on_lan_events": stats.get("wake_on_lan_events", 0),
            # AutoThrottle Monitor
            "throttled_processes": stats.get("throttled_processes", 0),
            "cryptominers": stats.get("cryptominers", 0),
            # Firewall Monitor
            "firewall_disabled": stats.get("firewall_disabled", 0),
            "firewall_rules": stats.get("firewall_rules", 0),
            # WebView2 Monitor
            "webview2_suspicious": stats.get("webview2_suspicious", 0),
            "webview2_debug": stats.get("webview2_debug", 0),
            # CLI Telemetry
            "cli_commands": stats.get("cli_commands", 0),
            "cli_lolbins": stats.get("cli_lolbins", 0),
            # Hidden File Scanner
            "hidden_files": stats.get("hidden_files", 0),
            "ads_found": stats.get("ads_found", 0),
            # Alias/Rename Monitor
            "renamed_exes": stats.get("renamed_exes", 0),
            "path_hijacks": stats.get("path_hijacks", 0),
            # Privilege Escalation
            "dangerous_privs": stats.get("dangerous_privs", 0),
            "system_processes": stats.get("system_processes", 0),
            "system_tasks": stats.get("system_tasks", 0)
        },
        "compliance_summary": {
            "unsigned_binaries": stats.get("unsigned_binaries", 0),
            "whitelist_violations": stats.get("whitelist_violations", 0),
            "dlp_alerts": stats.get("dlp_alerts", 0),
            "critical_vulnerabilities": stats.get("vulnerabilities_critical", 0),
            "high_vulnerabilities": stats.get("vulnerabilities_high", 0)
        },
        "raw_stats": stats
    }


@router.get("/monitors/alerts")
async def get_recent_monitor_alerts(
    limit: int = 50,
    monitor_type: Optional[str] = None,
    severity: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get recent alerts from all monitors across all agents."""
    # Build match conditions
    match_conditions = {}
    
    if monitor_type:
        valid_monitors = [
            "registry", "process_tree", "lolbin", "code_signing", "dns",
            "memory", "app_whitelist", "dlp", "vulnerability", "amsi",
            "ransomware", "rootkit", "kernel_security", "self_protection", "identity"
        ]
        if monitor_type not in valid_monitors:
            raise HTTPException(status_code=400, detail=f"Invalid monitor type")
        match_conditions[f"monitors.{monitor_type}"] = {"$exists": True}
    
    # Fetch recent telemetry with alerts
    cursor = db.agent_monitor_telemetry.find(
        match_conditions,
        {"agent_id": 1, "timestamp": 1, "monitors": 1, "_id": 0}
    ).sort("timestamp", -1).limit(limit)
    
    alerts = []
    async for doc in cursor:
        monitors = doc.get("monitors", {})
        for mon_name, mon_data in monitors.items():
            if isinstance(mon_data, dict):
                # Check for alerts/detections in this monitor
                alert_count = (
                    mon_data.get("alerts", 0) or
                    mon_data.get("detections", 0) or
                    mon_data.get("threats_detected", 0) or
                    mon_data.get("total_alerts", 0) or
                    mon_data.get("anomalies_detected", 0) or
                    mon_data.get("injections_detected", 0)
                )
                if alert_count and alert_count > 0:
                    alerts.append({
                        "agent_id": doc.get("agent_id"),
                        "monitor": mon_name,
                        "timestamp": doc.get("timestamp"),
                        "alert_count": alert_count,
                        "details": mon_data
                    })
    
    return {
        "alerts": alerts,
        "count": len(alerts),
        "filter": {
            "monitor_type": monitor_type,
            "severity": severity
        }
    }
