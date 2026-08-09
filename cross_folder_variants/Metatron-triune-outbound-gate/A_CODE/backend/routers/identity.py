"""
Identity Protection API Router (frontend compatibility)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Depends, HTTPException
from pydantic import BaseModel

from identity_protection import get_identity_protection_engine

from .dependencies import get_db, get_current_user, check_permission

# Optional identity and authentication services
try:
    from backend.services.attested_identity_bridge import AttestedIdentityBridge
except ImportError:
    AttestedIdentityBridge = None

try:
    from backend.services.node_identity_service import NodeIdentityService
except ImportError:
    NodeIdentityService = None

try:
    from backend.services.voice_registry import get_voice_registry
except ImportError:
    get_voice_registry = None

try:
    from backend.services.peer_registry import get_peer_registry
except ImportError:
    get_peer_registry = None
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

IDENTITY_INCIDENT_COLLECTION = "identity_incidents"
IDENTITY_SCAN_COLLECTION = "identity_scan_runs"
IDENTITY_INCIDENT_TERMINAL_STATUSES = {"resolved", "suppressed", "false_positive"}

def _incident_transition_entry(from_status: Optional[str], to_status: str, actor: str, reason: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "from_status": from_status,
        "to_status": to_status,
        "actor": actor,
        "reason": reason,
    }
    if metadata:
        entry["metadata"] = metadata
    return entry

def _incident_doc_from_threat(threat: Dict[str, Any]) -> Dict[str, Any]:
    status = str(threat.get("status") or "active")
    now = datetime.now(timezone.utc).isoformat()
    doc = dict(threat)
    doc.update({
        "state_version": int(doc.get("state_version") or 1),
        "state_transition_log": doc.get("state_transition_log") or [
            _incident_transition_entry(
                from_status=None,
                to_status=status,
                actor="system:identity",
                reason="incident discovered by identity engine",
            )
        ],
        "updated_at": now,
    })
    return doc

async def _persist_identity_incidents(threats: List[Dict[str, Any]]) -> None:
    db = get_db()
    if db is None:
        return
    for threat in threats:
        doc = _incident_doc_from_threat(threat)
        await db[IDENTITY_INCIDENT_COLLECTION].update_one(
            {"id": doc.get("id")},
            {"$set": doc, "$setOnInsert": {"created_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )

async def _get_incident_record(incident_id: str) -> Dict[str, Any]:
    db = get_db()
    if db is None:
        return {}
    return await db[IDENTITY_INCIDENT_COLLECTION].find_one({"id": incident_id}, {"_id": 0}) or {}

async def _ensure_incident_state_fields(incident_id: str, *, actor: str, reason: str) -> Dict[str, Any]:
    db = get_db()
    if db is None:
        return {}
    incident = await db[IDENTITY_INCIDENT_COLLECTION].find_one({"id": incident_id}, {"_id": 0})
    if not incident:
        return {}
    if incident.get("state_version") is not None and incident.get("state_transition_log") is not None:
        return incident
    current_status = str(incident.get("status") or "active")
    bootstrap = {
        "state_version": int(incident.get("state_version") or 1),
        "state_transition_log": incident.get("state_transition_log") or [
            _incident_transition_entry(
                from_status=None,
                to_status=current_status,
                actor=actor,
                reason=reason,
            )
        ],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db[IDENTITY_INCIDENT_COLLECTION].update_one({"id": incident_id}, {"$set": bootstrap})
    return await db[IDENTITY_INCIDENT_COLLECTION].find_one({"id": incident_id}, {"_id": 0}) or {}

async def _transition_incident_status(
    incident_id: str,
    *,
    expected_statuses: List[str],
    next_status: str,
    actor: str,
    reason: str,
    expected_state_version: Optional[int] = None,
    transition_metadata: Optional[Dict[str, Any]] = None,
    extra_updates: Optional[Dict[str, Any]] = None,
) -> bool:
    db = get_db()
    if db is None:
        return False
    incident = await db[IDENTITY_INCIDENT_COLLECTION].find_one({"id": incident_id}, {"_id": 0})
    if not incident:
        return False
    from_status = str(incident.get("status") or "").lower().strip()
    if from_status not in expected_statuses:
        return False
    resolved_version = expected_state_version
    if resolved_version is None:
        resolved_version = int(incident.get("state_version") or 0)
    query: Dict[str, Any] = {
        "id": incident_id,
        "status": {"$in": expected_statuses},
    }
    if resolved_version <= 0:
        query["$or"] = [{"state_version": {"$exists": False}}, {"state_version": 0}]
    else:
        query["state_version"] = resolved_version
    set_doc = {
        "status": next_status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra_updates:
        set_doc.update(extra_updates)
    result = await db[IDENTITY_INCIDENT_COLLECTION].update_one(
        query,
        {
            "$set": set_doc,
            "$inc": {"state_version": 1},
            "$push": {
                "state_transition_log": _incident_transition_entry(
                    from_status=from_status,
                    to_status=next_status,
                    actor=actor,
                    reason=reason,
                    metadata=transition_metadata,
                )
            },
        },
    )
    return bool(getattr(result, "modified_count", 0))

router = APIRouter(prefix="/api/v1/identity", tags=["Identity Protection"])


class IdentityScanRequest(BaseModel):
    include_kerberos: bool = True
    include_ldap: bool = True
    include_ntlm: bool = True


def _to_iso(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return datetime.now(timezone.utc).isoformat()


def _normalize_threat(threat: Dict[str, Any]) -> Dict[str, Any]:
    mitre = threat.get("mitre_techniques") or []
    return {
        "id": threat.get("event_id"),
        "type": threat.get("attack_type", "unknown"),
        "severity": threat.get("severity", "medium"),
        "source_user": threat.get("evidence", {}).get("source_user") or threat.get("source_ip", "unknown"),
        "target": threat.get("target_principal", "unknown"),
        "timestamp": _to_iso(threat.get("timestamp")),
        "mitre": mitre[0] if mitre else "",
        "status": "active",
        "details": threat.get("description", ""),
        "raw": threat,
    }

def _list_local_accounts(limit: int = 5000) -> List[Dict[str, Any]]:
    """Best-effort local account inventory for environments without AD telemetry."""
    accounts: List[Dict[str, Any]] = []
    try:
        # Linux-like: /etc/passwd
        if os.path.exists("/etc/passwd"):
            with open("/etc/passwd", "r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    parts = line.strip().split(":")
                    if len(parts) < 7:
                        continue
                    username = parts[0]
                    try:
                        uid = int(parts[2])
                    except Exception:
                        uid = -1
                    shell = parts[6]
                    accounts.append({"username": username, "uid": uid, "shell": shell})
                    if len(accounts) >= limit:
                        break
    except Exception:
        return accounts
    return accounts


def _local_privileged_count(accounts: List[Dict[str, Any]]) -> int:
    count = 0
    for a in accounts:
        uid = a.get("uid")
        if uid == 0:
            count += 1
    return count


@router.get("/stats")
async def get_identity_stats() -> Dict[str, Any]:
    engine = get_identity_protection_engine()
    summary = engine.get_threat_summary()
    det_health = engine.get_detector_health()

    kerberos_stats = det_health.get("detectors", {}).get("kerberos", {}).get("stats", {})
    credential_stats = det_health.get("detectors", {}).get("credential", {}).get("stats", {})

    total_users = kerberos_stats.get("unique_users_tracked", 0)
    privileged_accounts = credential_stats.get("privileged_accounts_monitored", 0)
    active_threats_count = summary.get("active_threats", 0)
    blocked_attacks_count = summary.get("metrics", {}).get("auto_responses_triggered", 0)
    kerberos_anomalies_count = summary.get("attack_type_distribution", {}).get("kerberoasting", 0)
    credential_dumps_count = summary.get("attack_type_distribution", {}).get("credential_dumping", 0)

    db = get_db()
    last_scan = None
    if db is not None:
        last_scan = await db[IDENTITY_SCAN_COLLECTION].find_one({}, {"_id": 0}, sort=[("timestamp", -1)])
        if last_scan:
            total_users = total_users or int(last_scan.get("total_users") or 0)
            privileged_accounts = privileged_accounts or int(last_scan.get("privileged_accounts") or 0)

        # Supplement in-memory engine stats with real MongoDB counts
        non_terminal = {"$nin": list(IDENTITY_INCIDENT_TERMINAL_STATUSES)}
        db_active = await db[IDENTITY_INCIDENT_COLLECTION].count_documents({"status": non_terminal})
        db_kerberos = await db[IDENTITY_INCIDENT_COLLECTION].count_documents(
            {"$or": [{"attack_type": "kerberoasting"}, {"type": "kerberoasting"}, {"type": "as_rep_roasting"}, {"attack_type": "as_rep_roasting"}]}
        )
        db_cred = await db[IDENTITY_INCIDENT_COLLECTION].count_documents(
            {"$or": [
                {"attack_type": {"$in": ["credential_dumping", "pass_the_hash", "dcsync", "golden_ticket", "credential_dump"]}},
                {"type": {"$in": ["credential_dump", "pass_the_hash", "dcsync", "golden_ticket"]}},
            ]}
        )
        db_blocked = await db["response_history"].count_documents({})
        db_total_users = await db["users"].count_documents({})
        db_privileged = await db["users"].count_documents({"is_privileged": True})

        active_threats_count = active_threats_count or db_active
        kerberos_anomalies_count = kerberos_anomalies_count or db_kerberos
        credential_dumps_count = credential_dumps_count or db_cred
        blocked_attacks_count = blocked_attacks_count or db_blocked
        total_users = total_users or db_total_users
        privileged_accounts = privileged_accounts or db_privileged

    # If no AD/kerberos telemetry exists, fall back to local account inventory so the
    # UI doesn't look broken in single-host/container installs.
    local_accounts = []
    if not total_users:
        local_accounts = _list_local_accounts()
        total_users = len(local_accounts)
        privileged_accounts = privileged_accounts or _local_privileged_count(local_accounts)

    return {
        "total_users": int(total_users or 0),
        "privileged_accounts": int(privileged_accounts or 0),
        "active_threats": active_threats_count,
        "blocked_attacks": blocked_attacks_count,
        "kerberos_anomalies": kerberos_anomalies_count,
        "credential_dumps": credential_dumps_count,
        "summary": summary,
        "last_scan": last_scan,
        "local_inventory": {
            "used": bool(local_accounts),
            "account_count": len(local_accounts) if local_accounts else 0,
            "privileged_count": _local_privileged_count(local_accounts) if local_accounts else 0,
            "sample_accounts": [a.get("username") for a in local_accounts[:20]] if local_accounts else [],
        },
    }


@router.get("/threats")
async def get_identity_threats(limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    db = get_db()
    if db is not None:
        docs = await db[IDENTITY_INCIDENT_COLLECTION].find({}, {"_id": 0}).to_list(5000)
        docs.sort(key=lambda d: (d.get("severity", "medium"), d.get("timestamp", "")), reverse=True)
        total = len(docs)
        docs = docs[:limit]
        return {
            "threats": docs,
            "count": total,
        }

    # Fallback to in-memory engine
    engine = get_identity_protection_engine()
    active = engine.get_active_threats()
    history = [_normalize_threat(t) for t in active]
    if len(history) < limit:
        more = [_normalize_threat(t) for t in [t.__dict__ if hasattr(t, "__dict__") else t for t in engine.threat_history[-limit:]]]
        seen = {h["id"] for h in history}
        for item in reversed(more):
            if item["id"] not in seen:
                history.append(item)
                seen.add(item["id"])
            if len(history) >= limit:
                break
    return {
        "threats": history[:limit],
        "count": len(history[:limit]),
    }
@router.get("/incident/{incident_id}")
async def get_identity_incident(incident_id: str) -> Dict[str, Any]:
    durable = await _get_incident_record(incident_id)
    if durable:
        return durable
    engine = get_identity_protection_engine()
    for t in engine.get_active_threats():
        norm = _normalize_threat(t)
        if norm["id"] == incident_id:
            return norm
    for t in engine.threat_history:
        norm = _normalize_threat(t.__dict__ if hasattr(t, "__dict__") else t)
        if norm["id"] == incident_id:
            return norm
    return {}
class IncidentStatusUpdate(BaseModel):
    status: str
    reason: Optional[str] = None
    updated_by: str

@router.post("/incident/{incident_id}/status")
async def update_identity_incident_status(incident_id: str, update: IncidentStatusUpdate) -> Dict[str, Any]:
    if update.status == "suppressed" and not update.reason:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Reason required for suppression")

    db = get_db()
    if db is not None:
        incident = await _ensure_incident_state_fields(
            incident_id,
            actor=update.updated_by,
            reason="bootstrap identity incident durability fields",
        )
        if not incident:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Incident not found")
        current_status = str(incident.get("status") or "active")
        target_status = update.status
        if current_status == target_status:
            from fastapi import HTTPException
            raise HTTPException(status_code=409, detail=f"Incident already in status={target_status}")
        allowed_targets = {
            "active": {"in_progress", "resolved", "suppressed", "false_positive"},
            "in_progress": {"resolved", "suppressed", "false_positive"},
        }
        if current_status in IDENTITY_INCIDENT_TERMINAL_STATUSES:
            from fastapi import HTTPException
            raise HTTPException(status_code=409, detail=f"Incident already terminal (status={current_status})")
        if target_status not in allowed_targets.get(current_status, set()):
            from fastapi import HTTPException
            raise HTTPException(
                status_code=409,
                detail=f"Invalid incident transition {current_status} -> {target_status}",
            )
        reason = update.reason or f"status updated to {target_status}"
        extra_updates: Dict[str, Any] = {}
        evidence = dict(incident.get("evidence") or {})
        if target_status == "suppressed":
            evidence["suppression_reason"] = reason
            evidence["suppressed_by"] = update.updated_by
            evidence["suppressed_at"] = datetime.now(timezone.utc).isoformat()
        elif target_status == "resolved":
            evidence["resolution_note"] = reason
            evidence["resolved_at"] = datetime.now(timezone.utc).isoformat()
        if evidence:
            extra_updates["evidence"] = evidence
        transitioned = await _transition_incident_status(
            incident_id,
            expected_statuses=[current_status],
            next_status=target_status,
            actor=update.updated_by,
            reason=reason,
            expected_state_version=int(incident.get("state_version") or 0),
            transition_metadata={"updated_by": update.updated_by},
            extra_updates=extra_updates,
        )
        if not transitioned:
            refreshed = await _get_incident_record(incident_id)
            if not refreshed:
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Incident not found")
            if str(refreshed.get("status") or "") == target_status:
                from fastapi import HTTPException
                raise HTTPException(status_code=409, detail=f"Incident already in status={target_status}")
            from fastapi import HTTPException
            raise HTTPException(status_code=409, detail="Incident update conflict; state changed concurrently")
        return {
            "incident_id": incident_id,
            "status": target_status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    # Fallback in-memory path
    engine = get_identity_protection_engine()
    found = None
    for t in engine.get_active_threats():
        norm = _normalize_threat(t)
        if norm["id"] == incident_id:
            found = norm
            break
    if not found:
        for t in engine.threat_history:
            norm = _normalize_threat(t.__dict__ if hasattr(t, "__dict__") else t)
            if norm["id"] == incident_id:
                found = norm
                break
    if not found:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Incident not found")
    found["status"] = update.status
    return {
        "incident_id": incident_id,
        "status": update.status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/alerts")
async def get_identity_alerts(limit: int = Query(100, ge=1, le=500)) -> Dict[str, Any]:
    threats_resp = await get_identity_threats(limit=limit)
    alerts: List[Dict[str, Any]] = []

    for t in threats_resp["threats"]:
        alerts.append({
            "id": t["id"],
            "severity": t["severity"],
            "message": (t.get("details") or t.get("description") or f"Identity threat: {t.get('type', 'unknown')}"),
            "user": t.get("source_user", "unknown"),
            "endpoint": t.get("target", "unknown"),
            "timestamp": t.get("timestamp"),
            "type": t.get("type"),
        })

    return {
        "alerts": alerts,
        "count": len(alerts),
    }


@router.post("/scan")
async def run_identity_scan(request: Optional[IdentityScanRequest] = None) -> Dict[str, Any]:
    # The identity engine is event-driven; additionally perform a lightweight local
    # baseline so operators see tangible scan output even without AD telemetry.
    req = request or IdentityScanRequest()
    engine = get_identity_protection_engine()
    summary = engine.get_threat_summary()

    scan_id = f"identity-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    ts = datetime.now(timezone.utc).isoformat()
    local_accounts = _list_local_accounts()
    scan_doc = {
        "scan_id": scan_id,
        "timestamp": ts,
        "include_kerberos": bool(req.include_kerberos),
        "include_ldap": bool(req.include_ldap),
        "include_ntlm": bool(req.include_ntlm),
        "total_users": len(local_accounts),
        "privileged_accounts": _local_privileged_count(local_accounts),
        "sample_users": [a.get("username") for a in local_accounts[:50]],
        "engine_active_threats": summary.get("active_threats", 0),
        "engine_metrics": summary.get("metrics", {}),
    }
    db = get_db()
    if db is not None:
        try:
            await db[IDENTITY_SCAN_COLLECTION].insert_one(dict(scan_doc))
        except Exception:
            pass

    return {
        "status": "completed",
        "scan_id": scan_id,
        "timestamp": ts,
        "active_threats": summary.get("active_threats", 0),
        "threats_last_hour": summary.get("threats_last_hour", 0),
        "local_users_enumerated": len(local_accounts),
        "local_privileged_accounts": scan_doc["privileged_accounts"],
    }


@router.get("/attested/identity")
async def get_attested_identity(
    current_user: dict = Depends(get_current_user),
):
    """Get cryptographically attested identity."""
    if not AttestedIdentityBridge:
        raise HTTPException(status_code=501, detail="Attested identity service not available")
    
    try:
        bridge = AttestedIdentityBridge()
        identity = await bridge.get_attested_identity()
        return {"success": True, "identity": identity}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get attested identity: {str(e)}")


@router.post("/node/register")
async def register_node_identity(
    node_id: str,
    public_key: str,
    current_user: dict = Depends(check_permission("write")),
):
    """Register a node in the peer registry."""
    if not NodeIdentityService:
        raise HTTPException(status_code=501, detail="Node identity service not available")
    
    try:
        service = NodeIdentityService()
        result = await service.register_node(node_id, public_key)
        return {"success": True, "registered": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Node registration failed: {str(e)}")


@router.get("/peers/list")
async def list_peer_identities(
    current_user: dict = Depends(get_current_user),
):
    """List known peer identities."""
    if not get_peer_registry:
        raise HTTPException(status_code=501, detail="Peer registry not available")
    
    try:
        registry = get_peer_registry()
        peers = await registry.list_peers()
        return {
            "success": True,
            "peers": peers,
            "count": len(peers),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list peers: {str(e)}")


@router.post("/voice/enroll")
async def enroll_voice_identity(
    voice_sample: bytes,
    principal_id: str,
    current_user: dict = Depends(check_permission("write")),
):
    """Enroll voice in voice registry for biometric identity."""
    if not get_voice_registry:
        raise HTTPException(status_code=501, detail="Voice registry not available")
    
    try:
        registry = get_voice_registry()
        enrollment = await registry.enroll(principal_id, voice_sample)
        return {
            "success": True,
            "principal_id": principal_id,
            "enrollment_id": enrollment.get("id"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice enrollment failed: {str(e)}")
