"""
Audit Logging Service
=====================
Comprehensive audit logging for security operations, user actions,
and system events. Supports multiple storage backends and retention policies.
"""
import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
import hashlib
from runtime_paths import ensure_data_dir

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

AUDIT_LOG_DIR = ensure_data_dir("audit_logs")

class AuditConfig:
    def __init__(self):
        self.retention_days = int(os.environ.get("AUDIT_RETENTION_DAYS", "90"))
        self.log_to_file = os.environ.get("AUDIT_LOG_TO_FILE", "true").lower() == "true"
        self.log_to_db = os.environ.get("AUDIT_LOG_TO_DB", "true").lower() == "true"
        self.log_to_elasticsearch = os.environ.get("AUDIT_LOG_TO_ES", "false").lower() == "true"

config = AuditConfig()

# =============================================================================
# ENUMS AND DATA MODELS
# =============================================================================

class AuditCategory(Enum):
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    USER_ACTION = "user_action"
    SYSTEM_EVENT = "system_event"
    SECURITY_EVENT = "security_event"
    THREAT_RESPONSE = "threat_response"
    CONFIGURATION = "configuration"
    DATA_ACCESS = "data_access"
    AGENT_EVENT = "agent_event"

class AuditSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class AuditEntry:
    """Represents a single audit log entry"""
    id: str
    timestamp: str
    category: str
    action: str
    severity: str
    actor: Optional[str]  # User email or system component
    actor_ip: Optional[str]
    target_type: Optional[str]  # threat, alert, user, setting, etc.
    target_id: Optional[str]
    description: str
    details: Dict[str, Any] = field(default_factory=dict)
    result: str = "success"  # success, failure, partial
    session_id: Optional[str] = None

# =============================================================================
# AUDIT LOGGER
# =============================================================================

class AuditLogger:
    """
    Centralized audit logging service.
    Logs all security-relevant events for compliance and forensics.
    """
    
    # In-memory buffer for recent entries (for quick access)
    _buffer: List[AuditEntry] = []
    _buffer_max_size = 1000
    
    # Database reference (set by server.py)
    _db = None
    
    @classmethod
    def set_database(cls, db):
        """Set the MongoDB database reference"""
        cls._db = db
    
    @classmethod
    def _generate_id(cls) -> str:
        """Generate unique audit entry ID"""
        return hashlib.md5(
            f"{datetime.now().isoformat()}{id(cls)}".encode()
        ).hexdigest()[:16]
    
    @classmethod
    async def log(
        cls,
        category: AuditCategory,
        action: str,
        description: str,
        actor: Optional[str] = None,
        actor_ip: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        result: str = "success",
        session_id: Optional[str] = None
    ) -> AuditEntry:
        """
        Log an audit entry.
        
        Args:
            category: Category of the event
            action: Specific action performed
            description: Human-readable description
            actor: User or system component that performed the action
            actor_ip: IP address of the actor
            target_type: Type of object affected
            target_id: ID of the object affected
            details: Additional structured data
            severity: Severity level
            result: Result of the action
            session_id: Session identifier for correlation
        
        Returns:
            The created AuditEntry
        """
        entry = AuditEntry(
            id=cls._generate_id(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            category=category.value,
            action=action,
            severity=severity.value,
            actor=actor,
            actor_ip=actor_ip,
            target_type=target_type,
            target_id=target_id,
            description=description,
            details=details or {},
            result=result,
            session_id=session_id
        )
        
        # Add to buffer
        cls._buffer.append(entry)
        if len(cls._buffer) > cls._buffer_max_size:
            cls._buffer = cls._buffer[-cls._buffer_max_size:]
        
        # Log to file
        if config.log_to_file:
            cls._log_to_file(entry)
        
        # Log to database
        if config.log_to_db and cls._db is not None:
            try:
                await cls._db.audit_logs.insert_one(asdict(entry))
            except Exception as e:
                logger.error(f"Failed to log audit entry to DB: {e}")
        
        # Log to standard logger
        log_level = logging.INFO if severity == AuditSeverity.INFO else \
                    logging.WARNING if severity == AuditSeverity.WARNING else \
                    logging.CRITICAL
        logger.log(log_level, f"AUDIT: [{category.value}] {action} - {description}")
        
        return entry
    
    @classmethod
    def _log_to_file(cls, entry: AuditEntry):
        """Write audit entry to daily log file"""
        try:
            date_str = datetime.now().strftime("%Y-%m-%d")
            log_file = AUDIT_LOG_DIR / f"audit_{date_str}.jsonl"
            
            with open(log_file, "a") as f:
                f.write(json.dumps(asdict(entry)) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log to file: {e}")
    
    @classmethod
    async def get_recent(cls, limit: int = 100) -> List[AuditEntry]:
        """Get recent audit entries from buffer"""
        return list(reversed(cls._buffer[-limit:]))
    
    @classmethod
    async def search(
        cls,
        category: Optional[str] = None,
        actor: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        severity: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Search audit logs with filters"""
        def _buffer_fallback() -> List[Dict[str, Any]]:
            rows = [asdict(entry) for entry in reversed(cls._buffer)]
            if category:
                rows = [r for r in rows if r.get("category") == category]
            if actor:
                term = actor.lower()
                rows = [r for r in rows if term in str(r.get("actor") or "").lower()]
            if target_type:
                rows = [r for r in rows if r.get("target_type") == target_type]
            if target_id:
                rows = [r for r in rows if r.get("target_id") == target_id]
            if severity:
                rows = [r for r in rows if r.get("severity") == severity]
            if start_time:
                rows = [r for r in rows if str(r.get("timestamp") or "") >= start_time]
            if end_time:
                rows = [r for r in rows if str(r.get("timestamp") or "") <= end_time]
            return rows[:limit]

        if cls._db is None:
            return _buffer_fallback()
        
        query = {}
        if category:
            query["category"] = category
        if actor:
            query["actor"] = {"$regex": actor, "$options": "i"}
        if target_type:
            query["target_type"] = target_type
        if target_id:
            query["target_id"] = target_id
        if severity:
            query["severity"] = severity
        if start_time:
            query["timestamp"] = {"$gte": start_time}
        if end_time:
            query.setdefault("timestamp", {})["$lte"] = end_time
        
        try:
            cursor = cls._db.audit_logs.find(
                query, {"_id": 0}
            ).sort("timestamp", -1).limit(limit)
            rows = await cursor.to_list(length=limit)
            if rows:
                return rows
            return _buffer_fallback()
        except Exception as e:
            logger.error(f"Audit search failed: {e}")
            return _buffer_fallback()
    
    @classmethod
    async def get_stats(cls) -> Dict[str, Any]:
        """Get audit log statistics"""
        if cls._db is None:
            return {"total": len(cls._buffer), "by_category": {}, "by_severity": {}}
        
        try:
            # Get counts by category
            pipeline = [
                {"$group": {"_id": "$category", "count": {"$sum": 1}}}
            ]
            by_category = {}
            async for doc in cls._db.audit_logs.aggregate(pipeline):
                by_category[doc["_id"]] = doc["count"]
            
            # Get counts by severity
            pipeline = [
                {"$group": {"_id": "$severity", "count": {"$sum": 1}}}
            ]
            by_severity = {}
            async for doc in cls._db.audit_logs.aggregate(pipeline):
                by_severity[doc["_id"]] = doc["count"]
            
            # Get total
            total = await cls._db.audit_logs.count_documents({})
            
            return {
                "total": total,
                "by_category": by_category,
                "by_severity": by_severity,
                "buffer_size": len(cls._buffer)
            }
        except Exception as e:
            logger.error(f"Failed to get audit stats: {e}")
            return {"total": len(cls._buffer), "by_category": {}, "by_severity": {}}
    
    @classmethod
    async def cleanup_old_entries(cls, days: Optional[int] = None) -> int:
        """Remove audit entries older than retention period"""
        retention = days or config.retention_days
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention)
        cutoff_str = cutoff.isoformat()
        
        deleted = 0
        
        # Clean database
        if cls._db is not None:
            try:
                result = await cls._db.audit_logs.delete_many({
                    "timestamp": {"$lt": cutoff_str}
                })
                deleted = result.deleted_count
            except Exception as e:
                logger.error(f"Failed to cleanup audit DB: {e}")
        
        # Clean old log files
        try:
            for log_file in AUDIT_LOG_DIR.glob("audit_*.jsonl"):
                try:
                    date_str = log_file.stem.replace("audit_", "")
                    file_date = datetime.strptime(date_str, "%Y-%m-%d")
                    if file_date < cutoff.replace(tzinfo=None):
                        log_file.unlink()
                        logger.info(f"Deleted old audit log: {log_file}")
                except ValueError:
                    pass
        except Exception as e:
            logger.error(f"Failed to cleanup audit files: {e}")
        
        return deleted

# Global instance
audit = AuditLogger()

# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def log_auth_event(
    action: str,
    actor: str,
    actor_ip: Optional[str] = None,
    success: bool = True,
    details: Optional[Dict] = None
):
    """Log authentication events"""
    await audit.log(
        category=AuditCategory.AUTHENTICATION,
        action=action,
        description=f"Authentication: {action} by {actor}",
        actor=actor,
        actor_ip=actor_ip,
        severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
        result="success" if success else "failure",
        details=details
    )

async def log_user_action(
    action: str,
    actor: str,
    target_type: str,
    target_id: str,
    description: str,
    actor_ip: Optional[str] = None,
    details: Optional[Dict] = None
):
    """Log user actions"""
    await audit.log(
        category=AuditCategory.USER_ACTION,
        action=action,
        description=description,
        actor=actor,
        actor_ip=actor_ip,
        target_type=target_type,
        target_id=target_id,
        details=details
    )

async def log_threat_response(
    action: str,
    description: str,
    target_type: str,
    target_id: str,
    severity: AuditSeverity = AuditSeverity.WARNING,
    details: Optional[Dict] = None
):
    """Log automated threat responses"""
    await audit.log(
        category=AuditCategory.THREAT_RESPONSE,
        action=action,
        description=description,
        actor="SYSTEM:threat_response",
        target_type=target_type,
        target_id=target_id,
        severity=severity,
        details=details
    )

async def log_security_event(
    action: str,
    description: str,
    severity: AuditSeverity = AuditSeverity.WARNING,
    source: Optional[str] = None,
    details: Optional[Dict] = None
):
    """Log security events"""
    await audit.log(
        category=AuditCategory.SECURITY_EVENT,
        action=action,
        description=description,
        actor=source or "SYSTEM",
        severity=severity,
        details=details
    )

async def log_config_change(
    setting: str,
    actor: str,
    old_value: Any,
    new_value: Any,
    actor_ip: Optional[str] = None
):
    """Log configuration changes"""
    await audit.log(
        category=AuditCategory.CONFIGURATION,
        action="config_change",
        description=f"Configuration changed: {setting}",
        actor=actor,
        actor_ip=actor_ip,
        target_type="setting",
        target_id=setting,
        details={"old_value": str(old_value)[:100], "new_value": str(new_value)[:100]}
    )

async def log_agent_event(
    agent_id: str,
    agent_name: str,
    event_type: str,
    description: str,
    details: Optional[Dict] = None
):
    """Log agent events"""
    await audit.log(
        category=AuditCategory.AGENT_EVENT,
        action=event_type,
        description=description,
        actor=f"AGENT:{agent_name}",
        target_type="agent",
        target_id=agent_id,
        details=details
    )
