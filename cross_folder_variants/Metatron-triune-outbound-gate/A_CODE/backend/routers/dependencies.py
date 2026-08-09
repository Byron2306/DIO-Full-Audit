"""Shared dependencies for all routers"""
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
import uuid
import os
import logging
import ipaddress

logger = logging.getLogger(__name__)


def _is_production_security_mode() -> bool:
    environment = os.environ.get("ENVIRONMENT", "").strip().lower()
    strict_flag = os.environ.get("SERAPH_STRICT_SECURITY", "false").strip().lower()
    return environment in {"prod", "production"} or strict_flag in {"1", "true", "yes", "on"}


def _resolve_jwt_secret() -> str:
    configured_secret = os.environ.get("JWT_SECRET")
    weak_defaults = {
        "anti-ai-defense-secret",
        "secret",
        "changeme",
        "password",
        "default",
        "your-super-secret-jwt-key-change-in-production",
    }

    if not configured_secret:
        if _is_production_security_mode():
            raise RuntimeError(
                "JWT_SECRET is required in production/strict mode. "
                "Refusing to start without a strong secret."
            )
        generated_secret = f"ephemeral-{uuid.uuid4().hex}{uuid.uuid4().hex}"
        logger.warning(
            "JWT_SECRET is not set. Using an ephemeral in-memory secret for this process. "
            "Set a strong JWT_SECRET (>=32 chars) for persistent authentication."
        )
        return generated_secret

    if configured_secret in weak_defaults or len(configured_secret) < 32:
        message = (
            "Weak JWT_SECRET detected. Use a strong random secret with length >= 32 "
            "for secure token signing."
        )
        if _is_production_security_mode():
            raise RuntimeError(f"{message} Refusing to start in production/strict mode.")
        logger.warning(message)

    return configured_secret


# JWT Configuration
JWT_SECRET = _resolve_jwt_secret()
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)

# MongoDB connection - will be set by main app
db = None


def set_database(database):
    """Set the database instance for all routers"""
    global db
    db = database


def get_db():
    """Get the database instance"""
    global db
    return db


# ============ AUTH HELPERS ============

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_token(user_id: str, email: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _is_local_request(request: Request) -> bool:
    # Prefer X-Forwarded-For when behind reverse proxy.
    xff = request.headers.get("x-forwarded-for", "")
    client_ip = (xff.split(",")[0].strip() if xff else (request.client.host if request.client else "")).lower()
    trusted = {
        "127.0.0.1",
        "::1",
        "localhost",
        "172.17.0.1",  # common Docker host bridge address
        "host.docker.internal",
    }
    if client_ip in trusted:
        return True

    try:
        ip_obj = ipaddress.ip_address(client_ip)
        return ip_obj.is_loopback or ip_obj.is_private
    except Exception:
        return False


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        # Remote admin-only gate (for server-exposed ports): remote clients must be admin.
        remote_admin_only = os.environ.get("REMOTE_ADMIN_ONLY", "true").strip().lower() in {"1", "true", "yes", "on"}
        if remote_admin_only and not _is_local_request(request):
            allowed_admin_emails = {
                e.strip().lower()
                for e in os.environ.get("REMOTE_ADMIN_EMAILS", "").split(",")
                if e.strip()
            }
            if allowed_admin_emails:
                if user.get("email", "").lower() not in allowed_admin_emails:
                    raise HTTPException(status_code=403, detail="Remote access denied for this account")
            elif user.get("role", "viewer") != "admin":
                raise HTTPException(status_code=403, detail="Remote access requires admin role")

        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_optional_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
):
    """Return the current user when an Authorization header is present, else None.

    This is used for endpoints that support either user auth (JWT) or machine-to-machine
    auth (internal token headers).
    """
    if credentials is None:
        return None
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload.get("user_id")}, {"_id": 0}) if db is not None else None
        if not user:
            return None

        remote_admin_only = os.environ.get("REMOTE_ADMIN_ONLY", "true").strip().lower() in {"1", "true", "yes", "on"}
        if remote_admin_only and not _is_local_request(request):
            allowed_admin_emails = {
                e.strip().lower()
                for e in os.environ.get("REMOTE_ADMIN_EMAILS", "").split(",")
                if e.strip()
            }
            if allowed_admin_emails:
                if user.get("email", "").lower() not in allowed_admin_emails:
                    return None
            elif user.get("role", "viewer") != "admin":
                return None

        return user
    except Exception:
        return None


# ============ ROLE-BASED ACCESS CONTROL ============

ROLES = {
    "admin": ["read", "write", "delete", "manage_users", "manage_honeypots", "export_reports"],
    "analyst": ["read", "write", "export_reports"],
    "viewer": ["read"],
}


def _open_rbac_enabled() -> bool:
    if _is_production_security_mode():
        return False
    return os.environ.get("SERAPH_OPEN_RBAC", "true").strip().lower() in {"1", "true", "yes", "on"}


def has_permission(user: Optional[dict], permission: str) -> bool:
    if not user:
        return False
    if _open_rbac_enabled():
        return True
    user_role = user.get("role", "viewer")
    return permission in ROLES.get(user_role, [])


def optional_machine_token(
    *,
    env_keys: List[str],
    header_names: List[str],
    subject: str = "machine",
):
    """Optional internal auth via shared secret header.

    - If none of the headers are present -> returns None (let user auth handle it).
    - If a header is present but no env secret is configured -> 503 (so callers can retry with JWT).
    - If a header is present but does not match -> 401.
    - If matches -> returns a small auth dict.
    """

    header_names_lc = [h.lower() for h in (header_names or []) if h]
    env_keys_clean = [k for k in (env_keys or []) if k]

    async def _dep(request: Request) -> Optional[Dict[str, Any]]:
        provided = None
        for name in header_names_lc:
            if name in request.headers:
                provided = request.headers.get(name)
                break
        if not provided:
            return None

        configured = None
        configured_key = None
        for k in env_keys_clean:
            val = os.environ.get(k, "").strip()
            if val:
                configured = val
                configured_key = k
                break

        if not configured:
            raise HTTPException(status_code=503, detail="machine_token_not_configured")

        if provided.strip() != configured:
            raise HTTPException(status_code=401, detail="invalid_machine_token")

        return {"subject": subject, "env_key": configured_key, "auth": "machine_token"}

    return _dep


def require_machine_token(
    *,
    env_keys: List[str],
    header_names: List[str],
    subject: str = "machine",
):
    """Strict internal auth via shared secret header.

    Unlike optional_machine_token, this requires one of the configured headers
    to be present and valid.
    """

    optional_dep = optional_machine_token(
        env_keys=env_keys,
        header_names=header_names,
        subject=subject,
    )

    async def _dep(request: Request) -> Dict[str, Any]:
        auth = await optional_dep(request)
        if auth is None:
            raise HTTPException(status_code=401, detail="missing_machine_token")
        return auth

    return _dep

def check_permission(required_permission: str):
    async def permission_checker(current_user: dict = Depends(get_current_user)):
        if _open_rbac_enabled():
            return current_user
        user_role = current_user.get("role", "viewer")
        permissions = ROLES.get(user_role, [])
        if required_permission not in permissions:
            raise HTTPException(status_code=403, detail=f"Permission denied. Required: {required_permission}")
        return current_user
    return permission_checker

# ============ SHARED MODELS ============

class UserCreate(BaseModel):
    email: str
    password: str
    name: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    name: str
    role: str = "analyst"
    created_at: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class ThreatCreate(BaseModel):
    name: str
    type: str
    severity: str
    source_ip: Optional[str] = None
    target_system: Optional[str] = None
    description: Optional[str] = None
    indicators: Optional[List[str]] = []

class ThreatResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    type: str
    severity: str
    status: str
    source_ip: Optional[str] = None
    target_system: Optional[str] = None
    description: Optional[str] = None
    indicators: List[str] = []
    ai_analysis: Optional[str] = None
    created_at: str
    updated_at: str

class AlertCreate(BaseModel):
    title: str
    type: str
    severity: str
    threat_id: Optional[str] = None
    message: str

class AlertResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    title: str
    type: str
    severity: str
    threat_id: Optional[str] = None
    message: str
    status: str
    created_at: str

class AIAnalysisRequest(BaseModel):
    content: str
    analysis_type: str

class AIAnalysisResponse(BaseModel):
    analysis_id: str
    analysis_type: str
    result: str
    threat_indicators: List[str]
    risk_score: float
    recommendations: List[str]
    timestamp: str

class DashboardStats(BaseModel):
    total_threats: int
    active_threats: int
    contained_threats: int
    resolved_threats: int
    critical_alerts: int
    threats_by_type: dict
    threats_by_severity: dict
    recent_threats: List[ThreatResponse]
    recent_alerts: List[AlertResponse]
    ai_scans_today: int
    system_health: float

class NetworkNode(BaseModel):
    id: str
    label: str
    type: str
    ip: Optional[str] = None
    status: str = "normal"
    threat_count: int = 0

class NetworkLink(BaseModel):
    source: str
    target: str
    type: str = "connection"
    strength: float = 1.0

class NetworkTopology(BaseModel):
    nodes: List[NetworkNode]
    links: List[NetworkLink]

class HuntingHypothesis(BaseModel):
    id: str
    title: str
    description: str
    category: str
    confidence: float
    indicators: List[str]
    recommended_actions: List[str]
    related_threats: List[str]
    status: str = "pending"
    created_at: str

class HuntingRequest(BaseModel):
    focus_area: Optional[str] = None
    time_range_hours: int = 24

class HoneypotCreate(BaseModel):
    name: str
    type: str
    ip: str
    port: int
    description: Optional[str] = None

class HoneypotResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    type: str
    ip: str
    port: int
    description: Optional[str] = None
    status: str
    interactions: int
    last_interaction: Optional[str] = None
    created_at: str

class HoneypotInteraction(BaseModel):
    id: str
    honeypot_id: str
    source_ip: str
    source_port: int
    timestamp: str
    action: str
    data: Dict[str, Any]
    threat_level: str

class AgentEvent(BaseModel):
    agent_id: str
    agent_name: str
    event_type: str
    timestamp: str
    data: Dict[str, Any]

class AgentInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    ip: Optional[str] = None
    os: Optional[str] = None
    status: str = "online"
    last_heartbeat: Optional[str] = None
    system_info: Dict[str, Any] = {}
    created_at: Optional[str] = None

class RoleUpdate(BaseModel):
    role: str
