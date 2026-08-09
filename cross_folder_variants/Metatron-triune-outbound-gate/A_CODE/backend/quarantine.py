"""
Auto-Quarantine Service with Full Pipeline Integration

PIPELINE STAGES:
1. quarantined - File isolated from system
2. scanning - Automated analysis in progress (YARA, ClamAV, custom rules)
3. sandboxed - Dynamic analysis in sandbox environment
4. analyzed - Full analysis complete, verdict available
5. stored - Archived for retention period

INTEGRATIONS:
- SOAR Engine: Pipeline items synced with playbook execution
- Sandbox Analysis: Dynamic detonation and behavior capture
- Threat Intelligence: IOC extraction and sharing
- Forensics: Chain of custody and evidence preservation
"""
import os
import shutil
import hashlib
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from runtime_paths import ensure_data_dir

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

_quarantine_env = os.environ.get("QUARANTINE_DIR")
if _quarantine_env:
    _env_path = Path(_quarantine_env)
    try:
        _env_path.mkdir(parents=True, exist_ok=True)
        _probe = _env_path / ".quarantine-write-probe"
        with open(_probe, "w", encoding="utf-8") as handle:
            handle.write("ok")
        try:
            _probe.unlink()
        except OSError:
            pass
        QUARANTINE_BASE_PATH = _env_path
    except OSError:
        logger.warning(
            "Configured QUARANTINE_DIR is not writable (%s). Falling back to managed runtime path.",
            _quarantine_env,
        )
        QUARANTINE_BASE_PATH = ensure_data_dir("quarantine")
else:
    QUARANTINE_BASE_PATH = ensure_data_dir("quarantine")

QUARANTINE_BASE_DIR = str(QUARANTINE_BASE_PATH)
QUARANTINE_INDEX_FILE = str(QUARANTINE_BASE_PATH / "quarantine_index.json")
MAX_QUARANTINE_SIZE_MB = int(os.environ.get("MAX_QUARANTINE_SIZE_MB", "1000"))  # 1GB default

# =============================================================================
# DATA MODELS
# =============================================================================

class PipelineStage(Enum):
    """Quarantine pipeline stages"""
    QUARANTINED = "quarantined"   # Initial isolation
    SCANNING = "scanning"          # Automated analysis
    SANDBOXED = "sandboxed"        # Dynamic analysis
    ANALYZED = "analyzed"          # Analysis complete
    STORED = "stored"              # Long-term storage
    RESTORED = "restored"          # Restored to original location
    DELETED = "deleted"            # Permanently deleted

class ThreatVerdict(Enum):
    """Final threat verdict"""
    PENDING = "pending"
    BENIGN = "benign"
    SUSPICIOUS = "suspicious"
    MALICIOUS = "malicious"
    UNKNOWN = "unknown"

@dataclass
class ScanResult:
    """Results from automated scanning"""
    scanner: str
    scan_time: str
    detection: bool
    threat_name: Optional[str]
    threat_category: Optional[str]
    confidence: float
    signatures_matched: List[str] = field(default_factory=list)
    raw_output: Optional[str] = None

@dataclass
class SandboxResult:
    """Results from sandbox detonation"""
    sandbox_id: str
    sandbox_type: str  # "light", "full", "extended"
    execution_time_s: int
    verdict: ThreatVerdict
    behaviors: List[str] = field(default_factory=list)
    network_iocs: List[str] = field(default_factory=list)
    file_iocs: List[str] = field(default_factory=list)
    registry_iocs: List[str] = field(default_factory=list)
    process_tree: List[Dict] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)
    memory_dumps: List[str] = field(default_factory=list)
    raw_report: Optional[str] = None

@dataclass
class ThreatIntelHit:
    """Threat intelligence match"""
    source: str
    ioc_type: str
    ioc_value: str
    threat_actor: Optional[str]
    campaign: Optional[str]
    confidence: float
    last_seen: Optional[str]
    references: List[str] = field(default_factory=list)

@dataclass
class QuarantineEntry:
    """Represents a quarantined file with full pipeline tracking"""
    id: str
    original_path: str
    quarantine_path: str
    file_hash: str
    file_hash_md5: Optional[str]
    file_hash_sha1: Optional[str]
    file_size: int
    file_type: Optional[str]
    mime_type: Optional[str]
    threat_name: str
    threat_type: str
    detection_source: str
    agent_id: Optional[str]
    agent_name: Optional[str]
    quarantined_at: str
    status: str  # Maps to PipelineStage value

    # Governance durability
    state_version: int = 1
    state_transition_log: List[Dict[str, Any]] = field(default_factory=list)
    
    # Pipeline tracking
    pipeline_stage: str = "quarantined"
    stage_history: List[Dict] = field(default_factory=list)
    
    # Analysis results
    scan_results: List[Dict] = field(default_factory=list)
    sandbox_result: Optional[Dict] = None
    threat_intel_hits: List[Dict] = field(default_factory=list)
    final_verdict: str = "pending"
    
    # Forensics
    forensics_id: Optional[str] = None
    chain_of_custody: List[Dict] = field(default_factory=list)
    evidence_preserved: bool = False
    
    # Playbook integration
    playbook_id: Optional[str] = None
    execution_id: Optional[str] = None
    soar_synced: bool = False
    
    # Retention
    retention_days: int = 90
    auto_delete_at: Optional[str] = None
    
    metadata: Dict[str, Any] = field(default_factory=dict)

# =============================================================================
# QUARANTINE INDEX MANAGEMENT
# =============================================================================

def _load_index() -> Dict[str, QuarantineEntry]:
    """Load quarantine index from disk"""
    if os.path.exists(QUARANTINE_INDEX_FILE):
        try:
            with open(QUARANTINE_INDEX_FILE, 'r') as f:
                data = json.load(f)
                return {k: QuarantineEntry(**v) for k, v in data.items()}
        except Exception as e:
            logger.error(f"Failed to load quarantine index: {e}")
    return {}

def _save_index(index: Dict[str, QuarantineEntry]):
    """Save quarantine index to disk"""
    try:
        os.makedirs(QUARANTINE_BASE_DIR, exist_ok=True)
        with open(QUARANTINE_INDEX_FILE, 'w') as f:
            json.dump({k: asdict(v) for k, v in index.items()}, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save quarantine index: {e}")


def _append_state_transition(
    entry: QuarantineEntry,
    from_status: Optional[str],
    to_status: str,
    *,
    actor: str = "system",
    reason: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    timestamp: Optional[str] = None,
    increment_version: bool = True,
) -> str:
    """Append a state transition entry and optionally increment the state version."""
    now = timestamp or datetime.now(timezone.utc).isoformat()

    if entry.state_transition_log is None:
        entry.state_transition_log = []

    entry.state_transition_log.append(
        {
            "from_status": from_status,
            "to_status": to_status,
            "timestamp": now,
            "actor": actor,
            "reason": reason,
            "metadata": metadata or {},
        }
    )

    if increment_version:
        current_version = int(getattr(entry, "state_version", 0) or 0)
        entry.state_version = max(current_version + 1, 1)

    return now

def _get_quarantine_stats() -> Dict[str, Any]:
    """Get quarantine directory statistics"""
    total_size = 0
    file_count = 0
    
    if os.path.exists(QUARANTINE_BASE_DIR):
        for root, dirs, files in os.walk(QUARANTINE_BASE_DIR):
            for f in files:
                if f != "quarantine_index.json":
                    filepath = os.path.join(root, f)
                    try:
                        total_size += os.path.getsize(filepath)
                        file_count += 1
                    except OSError:
                        pass
    
    return {
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "file_count": file_count,
        "max_size_mb": MAX_QUARANTINE_SIZE_MB,
        "usage_percent": round((total_size / (MAX_QUARANTINE_SIZE_MB * 1024 * 1024)) * 100, 2) if MAX_QUARANTINE_SIZE_MB > 0 else 0
    }

# =============================================================================
# QUARANTINE OPERATIONS
# =============================================================================

def quarantine_file(
    filepath: str,
    threat_name: str,
    threat_type: str = "unknown",
    detection_source: str = "manual",
    agent_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    playbook_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    auto_scan: bool = True,
    auto_sandbox: bool = False,
    preserve_evidence: bool = False
) -> Optional[QuarantineEntry]:
    """
    Quarantine an infected file with full pipeline integration
    
    Args:
        filepath: Path to the infected file
        threat_name: Name of the detected threat
        threat_type: Type of threat (malware, virus, ransomware, etc.)
        detection_source: What detected the threat (yara, clamav, manual, etc.)
        agent_id: ID of the reporting agent
        agent_name: Name of the reporting agent
        metadata: Additional metadata about the detection
        playbook_id: Associated SOAR playbook ID
        execution_id: Associated SOAR execution ID
        auto_scan: Whether to start scanning pipeline automatically
        auto_sandbox: Whether to send to sandbox for dynamic analysis
        preserve_evidence: Whether to preserve for forensic chain of custody
    
    Returns:
        QuarantineEntry if successful, None otherwise
    """
    if not os.path.exists(filepath):
        logger.warning(f"Cannot quarantine - file not found: {filepath}")
        return None
    
    # Check quarantine size limits
    stats = _get_quarantine_stats()
    if stats["usage_percent"] >= 100:
        logger.error("Quarantine directory at capacity. Cannot quarantine new files.")
        return None
    
    try:
        # Calculate multiple hashes for threat intel matching
        sha256_hash = hashlib.sha256()
        md5_hash = hashlib.md5()
        sha1_hash = hashlib.sha1()
        file_size = os.path.getsize(filepath)
        
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256_hash.update(chunk)
                md5_hash.update(chunk)
                sha1_hash.update(chunk)
        
        file_hash = sha256_hash.hexdigest()
        file_hash_md5 = md5_hash.hexdigest()
        file_hash_sha1 = sha1_hash.hexdigest()
        
        # Detect file type
        file_type = _detect_file_type(filepath)
        mime_type = _detect_mime_type(filepath)
        
        # Generate unique ID
        entry_id = hashlib.md5(f"{filepath}{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        
        # Create quarantine subdirectory by date
        date_dir = datetime.now().strftime("%Y-%m-%d")
        quarantine_dir = os.path.join(QUARANTINE_BASE_DIR, date_dir)
        os.makedirs(quarantine_dir, exist_ok=True)
        
        # Generate quarantine filename
        original_name = os.path.basename(filepath)
        quarantine_filename = f"{entry_id}_{original_name}.quarantined"
        quarantine_path = os.path.join(quarantine_dir, quarantine_filename)
        
        # Move file to quarantine
        shutil.move(filepath, quarantine_path)
        
        # Set restrictive permissions
        os.chmod(quarantine_path, 0o400)
        
        # Calculate retention dates
        retention_days = 90
        auto_delete_at = (datetime.now(timezone.utc) + timedelta(days=retention_days)).isoformat()
        
        # Create initial stage history entry
        now = datetime.now(timezone.utc).isoformat()
        stage_history = [{
            "stage": "quarantined",
            "timestamp": now,
            "reason": f"Detected by {detection_source}: {threat_name}"
        }]
        
        # Initialize chain of custody if preserving evidence
        chain_of_custody = []
        forensics_id = None
        if preserve_evidence:
            forensics_id = f"FOR-{entry_id}"
            chain_of_custody.append({
                "action": "quarantined",
                "timestamp": now,
                "actor": "system",
                "notes": f"Original path: {filepath}, Hash: {file_hash}"
            })
        
        # Create entry
        transition_log = [{
            "from_status": None,
            "to_status": "quarantined",
            "timestamp": now,
            "actor": "system",
            "reason": f"Detected by {detection_source}: {threat_name}",
            "metadata": {
                "detection_source": detection_source,
                "threat_type": threat_type,
            },
        }]

        entry = QuarantineEntry(
            id=entry_id,
            original_path=filepath,
            quarantine_path=quarantine_path,
            file_hash=file_hash,
            file_hash_md5=file_hash_md5,
            file_hash_sha1=file_hash_sha1,
            file_size=file_size,
            file_type=file_type,
            mime_type=mime_type,
            threat_name=threat_name,
            threat_type=threat_type,
            detection_source=detection_source,
            agent_id=agent_id,
            agent_name=agent_name,
            quarantined_at=now,
            status="quarantined",
            state_version=1,
            state_transition_log=transition_log,
            pipeline_stage="quarantined",
            stage_history=stage_history,
            scan_results=[],
            sandbox_result=None,
            threat_intel_hits=[],
            final_verdict="pending",
            forensics_id=forensics_id,
            chain_of_custody=chain_of_custody,
            evidence_preserved=preserve_evidence,
            playbook_id=playbook_id,
            execution_id=execution_id,
            soar_synced=False,
            retention_days=retention_days,
            auto_delete_at=auto_delete_at,
            metadata=metadata or {}
        )
        
        # Update index
        index = _load_index()
        index[entry_id] = entry
        _save_index(index)
        
        logger.info(f"File quarantined: {filepath} -> {quarantine_path} (threat: {threat_name})")
        
        # Queue for automatic scanning if enabled
        if auto_scan:
            asyncio.create_task(_queue_for_scanning(entry_id))
        
        # Queue for sandbox if enabled
        if auto_sandbox:
            asyncio.create_task(_queue_for_sandbox(entry_id))
        
        return entry
        
    except Exception as e:
        logger.error(f"Failed to quarantine file {filepath}: {e}")
        return None

def restore_file(entry_id: str, restore_path: Optional[str] = None) -> bool:
    """
    Restore a quarantined file
    
    Args:
        entry_id: ID of the quarantine entry
        restore_path: Optional path to restore to (defaults to original path)
    
    Returns:
        bool: True if successful
    """
    index = _load_index()
    
    if entry_id not in index:
        logger.warning(f"Quarantine entry not found: {entry_id}")
        return False
    
    entry = index[entry_id]
    
    if entry.status != "quarantined":
        logger.warning(f"Entry {entry_id} is not in quarantined state: {entry.status}")
        return False
    
    if not os.path.exists(entry.quarantine_path):
        logger.error(f"Quarantined file not found: {entry.quarantine_path}")
        return False
    
    try:
        target_path = restore_path or entry.original_path
        
        # Ensure target directory exists
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        # Restore file
        shutil.move(entry.quarantine_path, target_path)
        
        # Update entry
        previous_status = entry.status
        entry.status = "restored"
        restored_at = datetime.now(timezone.utc).isoformat()
        entry.metadata["restored_at"] = restored_at
        entry.metadata["restored_to"] = target_path
        _append_state_transition(
            entry,
            previous_status,
            "restored",
            actor="system",
            reason="File restored from quarantine",
            metadata={"target_path": target_path},
            timestamp=restored_at,
        )
        index[entry_id] = entry
        _save_index(index)
        
        logger.info(f"File restored: {entry_id} -> {target_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to restore file {entry_id}: {e}")
        return False

def delete_quarantined(entry_id: str) -> bool:
    """
    Permanently delete a quarantined file
    
    Args:
        entry_id: ID of the quarantine entry
    
    Returns:
        bool: True if successful
    """
    index = _load_index()
    
    if entry_id not in index:
        logger.warning(f"Quarantine entry not found: {entry_id}")
        return False
    
    entry = index[entry_id]
    
    try:
        if os.path.exists(entry.quarantine_path):
            os.remove(entry.quarantine_path)
        
        # Update entry
        previous_status = entry.status
        entry.status = "deleted"
        deleted_at = datetime.now(timezone.utc).isoformat()
        entry.metadata["deleted_at"] = deleted_at
        _append_state_transition(
            entry,
            previous_status,
            "deleted",
            actor="system",
            reason="Quarantined file deleted",
            metadata={"quarantine_path": entry.quarantine_path},
            timestamp=deleted_at,
        )
        index[entry_id] = entry
        _save_index(index)
        
        logger.info(f"Quarantined file deleted: {entry_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to delete quarantined file {entry_id}: {e}")
        return False

def list_quarantined(
    status: Optional[str] = None,
    threat_type: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = 100
) -> List[QuarantineEntry]:
    """
    List quarantined files with optional filtering
    
    Args:
        status: Filter by status (quarantined, restored, deleted)
        threat_type: Filter by threat type
        agent_id: Filter by agent ID
        limit: Maximum number of results
    
    Returns:
        List of QuarantineEntry objects
    """
    index = _load_index()
    results = []
    
    for entry in index.values():
        if status and entry.status != status:
            continue
        if threat_type and entry.threat_type != threat_type:
            continue
        if agent_id and entry.agent_id != agent_id:
            continue
        
        results.append(entry)
        if len(results) >= limit:
            break
    
    # Sort by quarantine date descending
    results.sort(key=lambda x: x.quarantined_at, reverse=True)
    return results

def get_quarantine_entry(entry_id: str) -> Optional[QuarantineEntry]:
    """Get a specific quarantine entry"""
    index = _load_index()
    return index.get(entry_id)

def get_quarantine_summary() -> Dict[str, Any]:
    """Get summary statistics for the quarantine system"""
    index = _load_index()
    stats = _get_quarantine_stats()
    
    by_status = {"quarantined": 0, "restored": 0, "deleted": 0}
    by_type = {}
    by_source = {}
    
    for entry in index.values():
        by_status[entry.status] = by_status.get(entry.status, 0) + 1
        by_type[entry.threat_type] = by_type.get(entry.threat_type, 0) + 1
        by_source[entry.detection_source] = by_source.get(entry.detection_source, 0) + 1
    
    return {
        "total_entries": len(index),
        "storage": stats,
        "by_status": by_status,
        "by_threat_type": by_type,
        "by_detection_source": by_source
    }

# =============================================================================
# CLEANUP FUNCTIONS
# =============================================================================

def cleanup_old_entries(days: int = 30) -> int:
    """
    Delete quarantine entries older than specified days
    
    Args:
        days: Number of days to keep entries
    
    Returns:
        Number of entries cleaned up
    """
    from datetime import timedelta
    
    index = _load_index()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cleaned = 0
    
    for entry_id, entry in list(index.items()):
        try:
            entry_date = datetime.fromisoformat(entry.quarantined_at.replace('Z', '+00:00'))
            if entry_date < cutoff and entry.status == "quarantined":
                if delete_quarantined(entry_id):
                    cleaned += 1
        except (ValueError, KeyError):
            pass
    
    logger.info(f"Cleaned up {cleaned} old quarantine entries")
    return cleaned

# =============================================================================
# AUTO-QUARANTINE HANDLER (for agent integration)
# =============================================================================

async def handle_malware_detection(
    filepath: str,
    threat_name: str,
    threat_type: str,
    detection_source: str,
    agent_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    auto_quarantine: bool = True,
    notify: bool = True
) -> Dict[str, Any]:
    """
    Handle a malware detection event with optional auto-quarantine
    
    Args:
        filepath: Path to the infected file
        threat_name: Name of the detected threat
        threat_type: Type of threat
        detection_source: Detection source (yara, clamav, etc.)
        agent_id: ID of the reporting agent
        agent_name: Name of the reporting agent
        auto_quarantine: Whether to automatically quarantine
        notify: Whether to send notifications
    
    Returns:
        Dict with action results
    """
    result = {
        "filepath": filepath,
        "threat_name": threat_name,
        "threat_type": threat_type,
        "detection_source": detection_source,
        "quarantined": False,
        "quarantine_entry": None,
        "notifications_sent": {}
    }
    
    # Auto-quarantine if enabled
    if auto_quarantine:
        entry = quarantine_file(
            filepath=filepath,
            threat_name=threat_name,
            threat_type=threat_type,
            detection_source=detection_source,
            agent_id=agent_id,
            agent_name=agent_name
        )
        if entry:
            result["quarantined"] = True
            result["quarantine_entry"] = asdict(entry)
    
    # Send notifications if enabled
    if notify:
        try:
            from notifications import notify_malware_detected, notify_quarantine_action
            
            result["notifications_sent"]["malware"] = await notify_malware_detected(
                filepath=filepath,
                malware_type=f"{threat_type}: {threat_name}",
                action_taken="Auto-quarantined" if result["quarantined"] else "Detected (no action)",
                agent_name=agent_name
            )
            
            if result["quarantined"]:
                result["notifications_sent"]["quarantine"] = await notify_quarantine_action(
                    filepath=filepath,
                    threat_name=threat_name,
                    quarantine_path=result["quarantine_entry"]["quarantine_path"],
                    agent_name=agent_name
                )
        except Exception as e:
            logger.error(f"Failed to send notifications: {e}")
    
    return result


# =============================================================================
# FILE TYPE DETECTION HELPERS
# =============================================================================

def _detect_file_type(filepath: str) -> Optional[str]:
    """Detect file type based on magic bytes"""
    magic_signatures = {
        b'\x4d\x5a': 'PE',  # Windows executable
        b'\x7f\x45\x4c\x46': 'ELF',  # Linux executable
        b'\x50\x4b\x03\x04': 'ZIP',  # ZIP archive (also Office docs)
        b'\x25\x50\x44\x46': 'PDF',  # PDF document
        b'\xd0\xcf\x11\xe0': 'OLE',  # OLE compound (older Office)
        b'\x52\x61\x72\x21': 'RAR',  # RAR archive
        b'\x1f\x8b\x08': 'GZIP',  # GZIP compressed
        b'\x42\x5a\x68': 'BZIP2',  # BZIP2 compressed
        b'\xfd\x37\x7a\x58\x5a': 'XZ',  # XZ compressed
        b'#!': 'SCRIPT',  # Shebang script
    }
    
    try:
        with open(filepath, 'rb') as f:
            header = f.read(8)
            for sig, ftype in magic_signatures.items():
                if header.startswith(sig):
                    return ftype
    except Exception:
        pass
    
    return None

def _detect_mime_type(filepath: str) -> Optional[str]:
    """Detect MIME type"""
    import mimetypes
    mime_type, _ = mimetypes.guess_type(filepath)
    return mime_type


# =============================================================================
# PIPELINE MANAGEMENT - SCANNING
# =============================================================================

async def _queue_for_scanning(entry_id: str):
    """Queue entry for automated scanning"""
    await asyncio.sleep(0.1)  # Small delay to ensure entry is saved
    
    entry = get_quarantine_entry(entry_id)
    if not entry:
        return
    
    # Update stage
    advance_pipeline_stage(entry_id, "scanning", reason="Queued for automated scanning")
    logger.info(f"Quarantine pipeline: {entry_id} queued for scanning")

async def _queue_for_sandbox(entry_id: str):
    """Queue entry for sandbox detonation"""
    await asyncio.sleep(0.1)
    
    entry = get_quarantine_entry(entry_id)
    if not entry:
        return
    
    # Will be processed when scanning is complete
    entry.metadata["sandbox_requested"] = True
    _update_entry(entry_id, entry)
    logger.info(f"Quarantine pipeline: {entry_id} sandbox analysis requested")

def advance_pipeline_stage(
    entry_id: str,
    new_stage: str,
    reason: str = "",
    results: Optional[Dict] = None
) -> Optional[QuarantineEntry]:
    """
    Advance a quarantine entry to the next pipeline stage
    
    Args:
        entry_id: ID of the quarantine entry
        new_stage: New pipeline stage
        reason: Reason for advancement
        results: Analysis results to attach
    
    Returns:
        Updated QuarantineEntry or None
    """
    index = _load_index()
    
    if entry_id not in index:
        logger.warning(f"Entry not found for pipeline advancement: {entry_id}")
        return None
    
    entry = index[entry_id]
    old_stage = entry.pipeline_stage
    now = datetime.now(timezone.utc).isoformat()
    
    # Update stage
    entry.pipeline_stage = new_stage
    entry.status = new_stage

    _append_state_transition(
        entry,
        old_stage,
        new_stage,
        actor="system",
        reason=reason or "Pipeline stage advanced",
        metadata={"results_attached": bool(results)},
        timestamp=now,
    )
    
    # Add to history
    entry.stage_history.append({
        "stage": new_stage,
        "from_stage": old_stage,
        "timestamp": now,
        "reason": reason
    })
    
    # Add to chain of custody if evidence preserved
    if entry.evidence_preserved:
        entry.chain_of_custody.append({
            "action": f"stage_change: {old_stage} -> {new_stage}",
            "timestamp": now,
            "actor": "system",
            "notes": reason
        })
    
    # Attach results
    if results:
        if new_stage == "scanning" or old_stage == "scanning":
            entry.scan_results.append(results)
        elif new_stage == "sandboxed" or old_stage == "sandboxed":
            entry.sandbox_result = results
    
    index[entry_id] = entry
    _save_index(index)
    
    logger.info(f"Quarantine pipeline: {entry_id} advanced from {old_stage} to {new_stage}")
    return entry

# -----------------------------------------------------------------------------
# Metadata ingest (for remote agents / demos)
# -----------------------------------------------------------------------------

def ingest_quarantine_metadata(
    *,
    original_path: str,
    threat_name: str,
    threat_type: str = "unknown",
    detection_source: str = "remote_agent",
    agent_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    file_hash_sha256: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> QuarantineEntry:
    """Create a quarantine entry when the backend cannot access the original file.

    Local agents often quarantine on-device and only report metadata to the
    server. The port-3000 Quarantine page expects entries to exist; without this
    helper, the UI looks empty even when the agent performed actions.
    """
    index = _load_index()
    now = datetime.now(timezone.utc).isoformat()

    entry_id = hashlib.md5(f"{original_path}{now}{threat_name}".encode("utf-8", errors="ignore")).hexdigest()[:12]
    safe_name = os.path.basename(original_path or "artifact") or "artifact"
    date_dir = datetime.now().strftime("%Y-%m-%d")
    quarantine_dir = os.path.join(QUARANTINE_BASE_DIR, "ingested", date_dir)
    os.makedirs(quarantine_dir, exist_ok=True)
    meta_filename = f"{entry_id}_{safe_name}.metadata.json"
    meta_path = os.path.join(quarantine_dir, meta_filename)

    sha256_value = (file_hash_sha256 or "").strip()
    if not sha256_value:
        sha256_value = hashlib.sha256(f"{original_path}{now}".encode("utf-8", errors="ignore")).hexdigest()

    entry = QuarantineEntry(
        id=entry_id,
        original_path=original_path,
        quarantine_path=meta_path,
        file_hash=sha256_value,
        file_hash_md5=None,
        file_hash_sha1=None,
        file_size=0,
        file_type=None,
        mime_type=None,
        threat_name=threat_name,
        threat_type=threat_type,
        detection_source=detection_source,
        agent_id=agent_id,
        agent_name=agent_name,
        quarantined_at=now,
        status=PipelineStage.QUARANTINED.value,
        pipeline_stage=PipelineStage.QUARANTINED.value,
        metadata=metadata or {},
    )
    _append_state_transition(
        entry,
        from_status=None,
        to_status=PipelineStage.QUARANTINED.value,
        actor=f"agent:{agent_id}" if agent_id else "system:ingest",
        reason="quarantine metadata ingested",
    )
    index[entry_id] = entry
    _save_index(index)

    try:
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(asdict(entry), fh, indent=2)
    except Exception:
        # Index durability is the primary path; meta file is best-effort.
        pass

    return entry

def add_scan_result(
    entry_id: str,
    scanner: str,
    detection: bool,
    threat_name: Optional[str] = None,
    threat_category: Optional[str] = None,
    confidence: float = 0.0,
    signatures: Optional[List[str]] = None,
    raw_output: Optional[str] = None
) -> Optional[QuarantineEntry]:
    """Add scan results to a quarantine entry"""
    index = _load_index()
    
    if entry_id not in index:
        return None
    
    entry = index[entry_id]
    
    scan_result = {
        "scanner": scanner,
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "detection": detection,
        "threat_name": threat_name,
        "threat_category": threat_category,
        "confidence": confidence,
        "signatures_matched": signatures or [],
        "raw_output": raw_output
    }
    
    entry.scan_results.append(scan_result)
    
    # Update verdict based on detections
    if detection and confidence > 0.7:
        entry.final_verdict = "malicious"
    elif detection:
        entry.final_verdict = "suspicious"
    
    index[entry_id] = entry
    _save_index(index)
    
    logger.info(f"Added scan result from {scanner} to {entry_id}: detection={detection}")
    return entry

def add_sandbox_result(
    entry_id: str,
    sandbox_id: str,
    sandbox_type: str,
    execution_time_s: int,
    verdict: str,  # ThreatVerdict value
    behaviors: Optional[List[str]] = None,
    network_iocs: Optional[List[str]] = None,
    file_iocs: Optional[List[str]] = None,
    process_tree: Optional[List[Dict]] = None
) -> Optional[QuarantineEntry]:
    """Add sandbox analysis results to a quarantine entry"""
    index = _load_index()
    
    if entry_id not in index:
        return None
    
    entry = index[entry_id]
    
    sandbox_result = {
        "sandbox_id": sandbox_id,
        "sandbox_type": sandbox_type,
        "execution_time_s": execution_time_s,
        "verdict": verdict,
        "behaviors": behaviors or [],
        "network_iocs": network_iocs or [],
        "file_iocs": file_iocs or [],
        "registry_iocs": [],
        "process_tree": process_tree or [],
        "screenshots": [],
        "memory_dumps": [],
        "completed_at": datetime.now(timezone.utc).isoformat()
    }
    
    entry.sandbox_result = sandbox_result
    
    # Update final verdict based on sandbox
    if verdict == "malicious":
        entry.final_verdict = "malicious"
    elif verdict == "suspicious" and entry.final_verdict != "malicious":
        entry.final_verdict = "suspicious"
    
    # Advance pipeline to analyzed if sandbox complete
    old_stage = entry.pipeline_stage
    entry.pipeline_stage = "analyzed"
    old_status = entry.status
    entry.status = "analyzed"
    analyzed_at = datetime.now(timezone.utc).isoformat()
    entry.stage_history.append({
        "stage": "analyzed",
        "from_stage": old_stage,
        "timestamp": analyzed_at,
        "reason": f"Sandbox analysis complete: {verdict}"
    })

    _append_state_transition(
        entry,
        old_status,
        "analyzed",
        actor="system",
        reason=f"Sandbox analysis complete: {verdict}",
        metadata={"sandbox_id": sandbox_id, "sandbox_type": sandbox_type},
        timestamp=analyzed_at,
    )
    
    index[entry_id] = entry
    _save_index(index)
    
    logger.info(f"Added sandbox result to {entry_id}: verdict={verdict}")
    return entry

def add_threat_intel_hit(
    entry_id: str,
    source: str,
    ioc_type: str,
    ioc_value: str,
    threat_actor: Optional[str] = None,
    campaign: Optional[str] = None,
    confidence: float = 0.0
) -> Optional[QuarantineEntry]:
    """Add threat intelligence hit to a quarantine entry"""
    index = _load_index()
    
    if entry_id not in index:
        return None
    
    entry = index[entry_id]
    
    intel_hit = {
        "source": source,
        "ioc_type": ioc_type,
        "ioc_value": ioc_value,
        "threat_actor": threat_actor,
        "campaign": campaign,
        "confidence": confidence,
        "last_seen": datetime.now(timezone.utc).isoformat(),
        "references": []
    }
    
    entry.threat_intel_hits.append(intel_hit)
    
    # High confidence TI hits elevate to malicious
    if confidence >= 0.9:
        entry.final_verdict = "malicious"
    
    index[entry_id] = entry
    _save_index(index)
    
    logger.info(f"Added TI hit to {entry_id}: {source} - {ioc_type}={ioc_value}")
    return entry


# =============================================================================
# SOAR INTEGRATION
# =============================================================================

def sync_with_soar(entry_id: str, soar_engine) -> bool:
    """
    Synchronize quarantine entry with SOAR engine pipeline
    
    Args:
        entry_id: Quarantine entry ID
        soar_engine: SOAREngine instance
    
    Returns:
        bool: True if sync successful
    """
    entry = get_quarantine_entry(entry_id)
    if not entry:
        return False
    
    try:
        # Create SOAR pipeline item
        from soar_engine import QuarantinePipelineItem
        
        pipeline_item = QuarantinePipelineItem(
            item_id=entry.id,
            item_type="file",
            source_host=entry.agent_id or "unknown",
            source_path=entry.original_path,
            quarantine_path=entry.quarantine_path,
            hash_sha256=entry.file_hash,
            hash_md5=entry.file_hash_md5,
            size_bytes=entry.file_size,
            quarantined_at=entry.quarantined_at,
            playbook_id=entry.playbook_id or "manual",
            execution_id=entry.execution_id or "unknown",
            stage=entry.pipeline_stage,
            scan_results={r["scanner"]: r for r in entry.scan_results} if entry.scan_results else {},
            sandbox_results=entry.sandbox_result or {},
            threat_intel_hits=entry.threat_intel_hits,
            forensics_complete=entry.evidence_preserved
        )
        
        soar_engine.quarantine_pipeline[entry.id] = pipeline_item
        
        # Mark as synced
        index = _load_index()
        if entry_id in index:
            index[entry_id].soar_synced = True
            _save_index(index)
        
        logger.info(f"Quarantine entry {entry_id} synced with SOAR engine")
        return True
        
    except Exception as e:
        logger.error(f"Failed to sync {entry_id} with SOAR: {e}")
        return False

def get_pipeline_status(entry_id: str) -> Optional[Dict[str, Any]]:
    """Get full pipeline status for a quarantine entry"""
    entry = get_quarantine_entry(entry_id)
    if not entry:
        return None
    
    return {
        "entry_id": entry.id,
        "current_stage": entry.pipeline_stage,
        "stage_history": entry.stage_history,
        "final_verdict": entry.final_verdict,
        "scan_count": len(entry.scan_results),
        "sandbox_analyzed": entry.sandbox_result is not None,
        "threat_intel_hits": len(entry.threat_intel_hits),
        "evidence_preserved": entry.evidence_preserved,
        "forensics_id": entry.forensics_id,
        "soar_synced": entry.soar_synced,
        "playbook_id": entry.playbook_id,
        "execution_id": entry.execution_id
    }

def _update_entry(entry_id: str, entry: QuarantineEntry):
    """Update a quarantine entry in the index"""
    index = _load_index()
    index[entry_id] = entry
    _save_index(index)


# =============================================================================
# FORENSICS & EVIDENCE PRESERVATION
# =============================================================================

def preserve_for_forensics(
    entry_id: str,
    analyst_id: Optional[str] = None,
    case_id: Optional[str] = None,
    notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Mark a quarantine entry for forensic preservation
    
    Args:
        entry_id: Quarantine entry ID
        analyst_id: ID of the analyst requesting preservation
        case_id: Associated case ID
        notes: Additional notes
    
    Returns:
        Dict with forensics metadata
    """
    index = _load_index()
    
    if entry_id not in index:
        return None
    
    entry = index[entry_id]
    now = datetime.now(timezone.utc).isoformat()
    
    # Generate forensics ID if not exists
    if not entry.forensics_id:
        entry.forensics_id = f"FOR-{entry.id}"
    
    entry.evidence_preserved = True
    
    # Add to chain of custody
    entry.chain_of_custody.append({
        "action": "marked_for_preservation",
        "timestamp": now,
        "actor": analyst_id or "system",
        "case_id": case_id,
        "notes": notes or "Marked for forensic preservation"
    })
    
    # Disable auto-deletion
    entry.auto_delete_at = None
    entry.retention_days = 365 * 7  # 7 years
    
    # Add to metadata
    entry.metadata["forensics"] = {
        "preserved_at": now,
        "analyst_id": analyst_id,
        "case_id": case_id,
        "notes": notes
    }
    
    index[entry_id] = entry
    _save_index(index)
    
    logger.info(f"Entry {entry_id} marked for forensic preservation (forensics_id={entry.forensics_id})")
    
    return {
        "entry_id": entry_id,
        "forensics_id": entry.forensics_id,
        "preserved_at": now,
        "case_id": case_id,
        "chain_of_custody_length": len(entry.chain_of_custody)
    }

def add_custody_event(
    entry_id: str,
    action: str,
    actor: str,
    notes: Optional[str] = None
) -> bool:
    """Add an event to the chain of custody"""
    index = _load_index()
    
    if entry_id not in index:
        return False
    
    entry = index[entry_id]
    
    if not entry.evidence_preserved:
        logger.warning(f"Entry {entry_id} is not marked for forensic preservation")
        return False
    
    entry.chain_of_custody.append({
        "action": action,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "notes": notes
    })
    
    index[entry_id] = entry
    _save_index(index)
    
    logger.info(f"Added custody event to {entry_id}: {action} by {actor}")
    return True

def get_chain_of_custody(entry_id: str) -> Optional[List[Dict]]:
    """Get the full chain of custody for a quarantine entry"""
    entry = get_quarantine_entry(entry_id)
    if not entry:
        return None
    
    return entry.chain_of_custody


# =============================================================================
# BATCH OPERATIONS
# =============================================================================

async def batch_scan_pending(max_items: int = 50) -> List[str]:
    """
    Process all quarantine entries pending scanning
    
    Returns:
        List of entry IDs processed
    """
    index = _load_index()
    processed = []
    
    for entry_id, entry in index.items():
        if entry.pipeline_stage == "quarantined" and len(processed) < max_items:
            advance_pipeline_stage(entry_id, "scanning", reason="Batch scan initiated")
            processed.append(entry_id)
    
    return processed

def get_entries_by_stage(stage: str, limit: int = 100) -> List[QuarantineEntry]:
    """Get all quarantine entries at a specific pipeline stage"""
    index = _load_index()
    results = []
    
    for entry in index.values():
        if entry.pipeline_stage == stage:
            results.append(entry)
            if len(results) >= limit:
                break
    
    return sorted(results, key=lambda x: x.quarantined_at, reverse=True)

def get_entries_pending_analysis() -> Dict[str, List[str]]:
    """Get summary of entries pending at each stage"""
    index = _load_index()
    pending = {
        "quarantined": [],
        "scanning": [],
        "sandboxed": []
    }
    
    for entry_id, entry in index.items():
        if entry.pipeline_stage in pending:
            pending[entry.pipeline_stage].append(entry_id)
    
    return pending
